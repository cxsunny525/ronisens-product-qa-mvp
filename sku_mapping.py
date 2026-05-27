from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "ioo_product_test.db"
MAPPING_PATH = ROOT / "ioo_sku_mapping.csv"
PUBLIC_PRODUCTS_PATH = ROOT / "public_products.csv"
REPORT_PATH = ROOT / "SKU_MAPPING_REPORT.md"

INTERNAL_SUPPLIER_BRAND = "TMS LITE"
PUBLIC_BRAND = "IOO"

CATEGORY_CODES = {
    "ring": "RL",
    "ring_light": "RL",
    "backlight": "BL",
    "bar": "BAR",
    "bar_light": "BAR",
    "coaxial": "CL",
    "coaxial_light": "CL",
    "line": "LS",
    "line_scan_light": "LS",
    "spot": "SP",
    "spot_light": "SP",
    "darkfield": "DF",
    "dark_field": "DF",
    "dome": "DM",
    "dome_light": "DM",
    "diffuse": "DM",
}

LIGHT_TYPE_PATTERNS = [
    ("backlight", ["backlight", "back light", "bhl", "bhh", "bhlq", "bhlc", "blhx", "bl2"]),
    ("ring_light", ["ring", "hlbr", "hlbrx", "rl", "annular"]),
    ("bar_light", ["bar light", "bar", "hlbq", "hlbs", "hlb2", "hlb3", "hlb"]),
    ("coaxial_light", ["coaxial", "idcc", "lswc", "dlrc", "idq"]),
    ("line_scan_light", ["line scan", "line light", "linear", "ls"]),
    ("spot_light", ["spot", "point light"]),
    ("dark_field", ["dark field", "darkfield", "low angle", "dl-f", "dlc"]),
    ("dome_light", ["dome", "diffuse dome", "dome light"]),
]

TAG_RULES = {
    "scratch_detection": ["scratch", "dark field", "darkfield", "low angle", "metal", "surface defect"],
    "reflective_surface": ["reflective", "metal", "glare", "coaxial", "polarized"],
    "transparent_edge": ["transparent", "edge", "bottle", "glass", "backlight", "silhouette"],
    "pcb_inspection": ["pcb", "circuit", "coaxial", "dome", "ring"],
    "line_scan": ["line scan", "web inspection", "continuous"],
    "measurement": ["measurement", "gauging", "dimension", "edge", "hole"],
    "ocr_barcode": ["ocr", "barcode", "code", "print"],
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _clean_public_text(value: Any) -> str:
    text = str(value or "")
    for forbidden in ["TMS Lite", "TMS-Lite", "TMS_LITE", "TMS LITE", "tms-lite", "Advanced Illumination"]:
        text = re.sub(re.escape(forbidden), "IOO", text, flags=re.I)
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def infer_light_type(row: dict[str, Any]) -> str:
    explicit = (row.get("light_type") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if explicit and explicit != "not_available":
        if explicit in CATEGORY_CODES:
            return explicit if explicit.endswith("_light") or explicit in {"backlight", "dark_field"} else f"{explicit}_light"
        return explicit
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ["model", "title", "family_name", "series_code", "product_type", "search_text", "category_path"]
    ).lower()
    for light_type, needles in LIGHT_TYPE_PATTERNS:
        if any(needle in haystack for needle in needles):
            return light_type
    return "illumination"


def category_code(light_type: str) -> str:
    key = (light_type or "").lower()
    if key in CATEGORY_CODES:
        return CATEGORY_CODES[key]
    for fragment, code in CATEGORY_CODES.items():
        if fragment in key:
            return code
    return "LT"


def compact_dimensions(raw: Any) -> str:
    if not raw:
        return "not available"
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return _clean_public_text(raw) or "not available"
    else:
        parsed = raw
    if isinstance(parsed, dict):
        parts = []
        for key in ["length_mm", "width_mm", "height_mm", "outer_diameter_mm", "inner_diameter_mm", "diameter_mm"]:
            value = parsed.get(key)
            if value not in (None, "", "not available"):
                label = key.replace("_mm", "").replace("_", " ")
                parts.append(f"{label}: {value} mm")
        return "; ".join(parts) if parts else "not available"
    return _clean_public_text(parsed) or "not available"


def recommendation_tags(row: dict[str, Any], light_type: str) -> list[str]:
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ["model", "title", "family_name", "product_type", "search_text", "category_path", "short_description", "applications"]
    ).lower()
    tags = {light_type}
    for tag, needles in TAG_RULES.items():
        if any(needle in haystack for needle in needles):
            tags.add(tag)
    if light_type == "backlight":
        tags.update(["transparent_edge", "measurement"])
    if light_type == "dark_field":
        tags.update(["scratch_detection", "reflective_surface"])
    if light_type == "coaxial_light":
        tags.update(["reflective_surface", "pcb_inspection"])
    if light_type == "bar_light":
        tags.update(["scratch_detection", "line_scan"])
    return sorted(tags)


def public_description(row: dict[str, Any], light_type: str, tags: list[str]) -> str:
    readable_type = light_type.replace("_", " ")
    if "scratch_detection" in tags:
        return f"IOO {readable_type} candidate for surface defect and scratch inspection experiments."
    if "transparent_edge" in tags:
        return f"IOO {readable_type} candidate for silhouette, edge, and transparent-object inspection trials."
    if "pcb_inspection" in tags:
        return f"IOO {readable_type} candidate for electronics and flat-part inspection trials."
    return f"IOO {readable_type} candidate for machine vision lighting evaluation."


def load_internal_products() -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with connect() as conn:
        return _rows(
            conn,
            """
            SELECT
                p.*,
                b.name AS internal_supplier,
                pf.family_name,
                pf.series_code,
                pf.category_path,
                pf.short_description,
                pf.applications
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            LEFT JOIN product_families pf ON pf.id = p.family_id
            WHERE b.name = ?
              AND COALESCE(p.product_type, '') NOT IN ('controller', 'lens_or_optics', 'station_or_mounting', 'demo_kit')
            ORDER BY p.id
            """,
            (INTERNAL_SUPPLIER_BRAND,),
        )


def build_public_catalog() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    products = load_internal_products()
    counters: dict[str, int] = defaultdict(int)
    public_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for row in products:
        light_type = infer_light_type(row)
        code = category_code(light_type)
        counters[code] += 1
        public_model = f"IOO-{code}-{counters[code]:04d}"
        tags = recommendation_tags(row, light_type)
        dimensions = compact_dimensions(row.get("dimensions_mm_json"))
        voltage = row.get("voltage_v") or "not available"
        power = row.get("power_w") or "not available"
        current = row.get("current_ma") or "not available"
        color = row.get("color_options") or "not available"
        wavelength = row.get("wavelength_nm") or "not available"
        key_specs = "; ".join(
            item
            for item in [
                f"Voltage: {voltage}" if voltage != "not available" else "",
                f"Power: {power}" if power != "not available" else "",
                f"Current: {current}" if current != "not available" else "",
                f"Dimensions: {dimensions}" if dimensions != "not available" else "",
            ]
            if item
        ) or "not available"
        public_rows.append(
            {
                "public_brand": PUBLIC_BRAND,
                "public_model": public_model,
                "product_category": _clean_public_text(row.get("product_type") or "machine_vision_lighting"),
                "light_type": light_type,
                "color": _clean_public_text(color) or "not available",
                "wavelength_nm": _clean_public_text(wavelength) or "not available",
                "voltage_v": _clean_public_text(voltage) or "not available",
                "power_w": _clean_public_text(power) or "not available",
                "current_a": _clean_public_text(current) or "not available",
                "dimensions": dimensions,
                "key_specs": key_specs,
                "public_description": public_description(row, light_type, tags),
                "recommendation_tags": "|".join(tags),
                "internal_model": row.get("model"),
                "internal_supplier": "private_supplier",
                "internal_product_id": row.get("id"),
            }
        )
        mapping_rows.append(
            {
                "public_model": public_model,
                "public_brand": PUBLIC_BRAND,
                "light_type": light_type,
                "internal_model": row.get("model"),
                "internal_supplier": "private_supplier",
                "internal_product_id": row.get("id"),
            }
        )
    return public_rows, mapping_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_files() -> dict[str, Any]:
    public_rows, mapping_rows = build_public_catalog()
    write_csv(PUBLIC_PRODUCTS_PATH, public_rows)
    write_csv(MAPPING_PATH, mapping_rows)
    counts = Counter(row["light_type"] for row in public_rows)
    report = [
        "# SKU Mapping Report",
        "",
        "The public IOO catalog maps internal supplier records to IOO-only public SKUs.",
        "Supplier names and source URLs are retained only as private/internal fields and should not be shown in the public UI.",
        "",
        f"- Public brand: {PUBLIC_BRAND}",
        f"- Public products generated: {len(public_rows)}",
        f"- Mapping rows generated: {len(mapping_rows)}",
        "",
        "## Public SKU Pattern",
        "",
        "- `IOO-RL-####`: ring light candidates",
        "- `IOO-BL-####`: backlight candidates",
        "- `IOO-CL-####`: coaxial / in-line candidates",
        "- `IOO-BAR-####`: bar light candidates",
        "- `IOO-LS-####`: line scan candidates",
        "- `IOO-SP-####`: spot light candidates",
        "- `IOO-DF-####`: dark-field / low-angle candidates",
        "- `IOO-DM-####`: dome / diffuse candidates",
        "- `IOO-LT-####`: uncategorized lighting candidates",
        "",
        "## Light Type Distribution",
        "",
    ]
    for light_type, count in counts.most_common():
        report.append(f"- {light_type}: {count}")
    report.extend(
        [
            "",
            "## Public UI Rule",
            "",
            "The public UI should display `public_model` and `public_brand` only. Internal model, supplier, and private source URL fields are for internal review and debugging only.",
        ]
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    return {
        "public_products": len(public_rows),
        "mapping_rows": len(mapping_rows),
        "public_products_path": str(PUBLIC_PRODUCTS_PATH),
        "mapping_path": str(MAPPING_PATH),
        "report_path": str(REPORT_PATH),
        "light_type_counts": dict(counts),
    }


def _ensure_files() -> None:
    if not PUBLIC_PRODUCTS_PATH.exists() or not MAPPING_PATH.exists():
        generate_files()


def load_public_products() -> list[dict[str, str]]:
    _ensure_files()
    with PUBLIC_PRODUCTS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_+-]{1,}|[\u4e00-\u9fff]{2,}", (text or "").lower())


def infer_query_tags(question: str) -> list[str]:
    text = (question or "").lower()
    tags = set(tokenize(text))
    mappings = {
        "scratch_detection": ["scratch", "scratches", "划痕", "刮痕"],
        "reflective_surface": ["reflective", "metal", "glare", "反光", "金属"],
        "transparent_edge": ["transparent", "bottle", "glass", "edge", "透明", "瓶", "玻璃", "边缘"],
        "pcb_inspection": ["pcb", "circuit", "电路板", "缺陷"],
        "line_scan": ["line scan", "linescan", "线扫"],
        "measurement": ["measurement", "dimension", "measure", "测量", "尺寸"],
        "backlight": ["backlight", "silhouette", "背光"],
        "dark_field": ["dark-field", "darkfield", "dark field", "暗场", "低角度"],
        "coaxial_light": ["coaxial", "同轴"],
        "bar_light": ["bar light", "bar", "条形"],
        "ring_light": ["ring light", "ring", "环形"],
    }
    for tag, needles in mappings.items():
        if any(needle in text for needle in needles):
            tags.add(tag)
    return sorted(tags)


def score_product(question: str, product: dict[str, str]) -> tuple[float, list[str]]:
    tags = infer_query_tags(question)
    haystack = " ".join(
        str(product.get(field) or "")
        for field in [
            "public_model",
            "product_category",
            "light_type",
            "public_description",
            "recommendation_tags",
            "key_specs",
        ]
    ).lower()
    score = 0.0
    reasons: list[str] = []
    for tag in tags:
        if tag and tag.lower() in haystack:
            score += 5 if "_" in tag else 1
            if "_" in tag:
                reasons.append(f"matches {tag.replace('_', ' ')}")
    if "scratch_detection" in tags and product.get("light_type") in {"dark_field", "bar_light", "ring_light"}:
        score += 8
        reasons.append("surface defect lighting approach")
    if "transparent_edge" in tags and product.get("light_type") in {"backlight", "bar_light"}:
        score += 10
        reasons.append("edge/silhouette lighting approach")
    if "reflective_surface" in tags and product.get("light_type") in {"coaxial_light", "dark_field", "dome_light"}:
        score += 7
        reasons.append("reflective surface lighting approach")
    if "pcb_inspection" in tags and product.get("light_type") in {"coaxial_light", "dome_light", "ring_light"}:
        score += 7
        reasons.append("flat electronics inspection approach")
    if "line_scan" in tags and product.get("light_type") in {"line_scan_light", "bar_light"}:
        score += 9
        reasons.append("line scan lighting approach")
    if not reasons and product.get("light_type") != "illumination":
        score += 0.5
        reasons.append("general IOO lighting candidate")
    return score, list(dict.fromkeys(reasons))


def search_public_products(question: str, limit: int = 5) -> list[dict[str, Any]]:
    products = load_public_products()
    scored = []
    for product in products:
        score, reasons = score_product(question, product)
        if score > 0:
            item = dict(product)
            item["score"] = round(score, 2)
            item["fit_type"] = "Exact fit" if score >= 20 else "Close fit" if score >= 9 else "Workaround fit"
            item["why_it_may_fit"] = "; ".join(reasons) if reasons else "closest available IOO lighting configuration"
            scored.append(item)
    scored.sort(key=lambda row: (-float(row["score"]), row.get("public_model", "")))
    if not scored:
        for product in products[:limit]:
            item = dict(product)
            item["score"] = 0.1
            item["fit_type"] = "Workaround fit"
            item["why_it_may_fit"] = "closest available IOO lighting configuration"
            scored.append(item)
    return scored[:limit]


if __name__ == "__main__":
    print(json.dumps(generate_files(), indent=2, ensure_ascii=False))
