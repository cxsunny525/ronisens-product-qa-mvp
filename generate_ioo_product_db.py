from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_DB = ROOT / "data" / "tms_lite_full.db"
OUTPUT_DB = ROOT / "data" / "ioo_products.db"
PUBLIC_PRODUCTS_CSV = ROOT / "public_products.csv"
SKU_MAPPING_CSV = ROOT / "ioo_sku_mapping.csv"
INTERNAL_MAPPING_CSV = ROOT / "internal_sku_mapping.csv"
DATA_SOURCE_AUDIT = ROOT / "DATA_SOURCE_AUDIT.md"
DATABASE_REPORT = ROOT / "IOO_PRODUCT_DATABASE_REPORT.md"
MIGRATION_REPORT = ROOT / "IOO_REBRAND_DATABASE_MIGRATION_REPORT.md"

PUBLIC_BRAND = "IOO"
PRIVATE_SUPPLIER = "private_oem_supplier"


FORBIDDEN_PUBLIC_RE = re.compile(
    r"tms[\s_-]*lite|tms-lite|tms_lite|tms lite|advanced illumination|advancedillumination|supplier",
    re.I,
)


LIGHT_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("backlight", ["backlight", "back light", "bhh", "bhl", "bhlq", "bhlc", "blhx", "bl2", "back-lit"]),
    ("coaxial_light", ["coaxial", "co-axial", "idcc", "lswc", "dlrc", "idq", "idd"]),
    ("ring_light", ["ring", "annular", "hlbr", "hlbrx", "rl", "casc", "cas2", "cas3"]),
    ("bar_light", ["bar light", "bar", "linear", "hlbq", "hlbs", "hlb2", "hlb3", "hlb", "lsw", "lsq", "lla"]),
    ("line_scan_light", ["line scan", "line light", "linescan"]),
    ("spot_light", ["spot", "point light"]),
    ("dark_field", ["dark field", "darkfield", "low angle", "dl-f", "dlc"]),
    ("dome_light", ["dome", "diffuse dome", "diffuse light", "hpd", "dome light"]),
]

CANONICAL_SPEC_FIELDS = {
    "voltage": "voltage_v",
    "voltage (v)": "voltage_v",
    "voltage (v) / watt (w)": "voltage_v",
    "watt": "power_w",
    "power": "power_w",
    "current": "current_a",
    "color": "color",
    "wavelength": "wavelength_nm",
    "datasheet": "datasheet_url",
    "drawing (2d)": "drawing_2d",
    "step (3d)": "step_3d",
    "weight (g)": "weight_g",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_source() -> sqlite3.Connection:
    conn = sqlite3.connect(SOURCE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def sanitize_public_text(value: Any) -> str:
    text = str(value or "")
    text = FORBIDDEN_PUBLIC_RE.sub("IOO", text)
    text = re.sub(r"https?://(?:www\.)?tms-lite\.com/\S*", "IOO internal product database", text, flags=re.I)
    text = re.sub(r"https?://futureip-tms\.com/\S*", "IOO internal product database", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_ioo_model(internal_model: str) -> str:
    """Deterministically convert one internal OEM model into one IOO public model."""
    raw = str(internal_model or "").strip()
    if not raw:
        raw = "UNSPECIFIED"
    model = raw
    model = re.sub(r"(?i)tms[\s_-]*lite[\s_-]*", "IOO-", model)
    model = re.sub(r"(?i)\btms\b", "IOO", model)
    if not re.match(r"(?i)^ioo(?:[-_\s]|$)", model):
        model = "IOO-" + model
    model = re.sub(r"[\s_]+", "-", model)
    model = re.sub(r"[^A-Za-z0-9.+-]+", "-", model)
    model = re.sub(r"-{2,}", "-", model)
    model = model.strip("-").upper()
    if not model.startswith("IOO"):
        model = "IOO-" + model
    model = FORBIDDEN_PUBLIC_RE.sub("IOO", model)
    model = re.sub(r"-{2,}", "-", model).strip("-")
    return model


def public_model_map(products: list[dict[str, Any]]) -> tuple[dict[int, str], list[dict[str, Any]]]:
    seen: dict[str, int] = defaultdict(int)
    mapping: dict[int, str] = {}
    duplicate_events: list[dict[str, Any]] = []
    for product in sorted(products, key=lambda row: int(row["id"])):
        base = to_ioo_model(str(product.get("model") or f"PRODUCT-{product['id']}"))
        seen[base] += 1
        public_model = base if seen[base] == 1 else f"{base}-{seen[base]}"
        mapping[int(product["id"])] = public_model
        if seen[base] > 1:
            duplicate_events.append(
                {
                    "original_product_id": product["id"],
                    "internal_model": product.get("model"),
                    "base_public_model": base,
                    "public_model": public_model,
                    "duplicate_index": seen[base],
                }
            )
    return mapping, duplicate_events


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def load_source_data() -> dict[str, Any]:
    with connect_source() as conn:
        products = rows(
            conn,
            """
            SELECT
                p.*,
                pf.family_name,
                pf.series_code,
                pf.product_type AS family_product_type,
                pf.category_path,
                pf.short_description,
                pf.applications
            FROM products p
            LEFT JOIN product_families pf ON pf.id = p.family_id
            ORDER BY p.id
            """,
        )
        specs = rows(conn, "SELECT * FROM product_specs ORDER BY product_id, id")
        assets = rows(conn, "SELECT * FROM product_assets ORDER BY COALESCE(product_id, 0), id")
        families = rows(conn, "SELECT * FROM product_families ORDER BY id")
        counts = {
            "brands": conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0],
            "products": len(products),
            "product_specs": len(specs),
            "product_assets": len(assets),
            "product_families": len(families),
            "crawl_pages": conn.execute("SELECT COUNT(*) FROM crawl_pages").fetchone()[0],
        }
    return {"products": products, "specs": specs, "assets": assets, "families": families, "counts": counts}


def parse_json_object(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def infer_light_type(product: dict[str, Any]) -> str:
    haystack = " ".join(
        str(product.get(key) or "")
        for key in [
            "model",
            "title",
            "product_type",
            "family_name",
            "series_code",
            "category_path",
            "short_description",
            "applications",
            "search_text",
        ]
    ).lower()
    for light_type, needles in LIGHT_TYPE_PATTERNS:
        if any(needle in haystack for needle in needles):
            return light_type
    return "machine_vision_light"


def infer_color(product: dict[str, Any]) -> str:
    explicit = str(product.get("color_options") or "").strip()
    if explicit:
        return sanitize_public_text(explicit)
    specs = parse_json_object(product.get("specs_json"))
    text = " ".join([str(product.get("model") or ""), str(product.get("title") or ""), json.dumps(specs, ensure_ascii=False)]).lower()
    colors: list[str] = []
    color_rules = [
        ("red", ["red", "-r-", "-rgb", "rgb", "rgbw"]),
        ("green", ["green", "-g-", "rgb", "rgbw"]),
        ("blue", ["blue", "-b-", "rgb", "rgbw"]),
        ("white", ["white", "-w", "rgbw", "fwna"]),
        ("ir850", ["ir850", "850"]),
        ("uv365", ["uv365", "365"]),
    ]
    for color, needles in color_rules:
        if any(needle in text for needle in needles):
            colors.append(color)
    return " / ".join(dict.fromkeys(colors)) if colors else "not available"


def infer_wavelength(product: dict[str, Any], color: str) -> str:
    explicit = str(product.get("wavelength_nm") or "").strip()
    if explicit:
        return sanitize_public_text(explicit)
    values = []
    if "red" in color:
        values.append("625")
    if "green" in color:
        values.append("525")
    if "blue" in color:
        values.append("470")
    if "white" in color:
        values.append("white")
    if "ir850" in color:
        values.append("850")
    if "uv365" in color:
        values.append("365")
    return " / ".join(values) if values else "not available"


def compact_dimensions(product: dict[str, Any]) -> str:
    dims = parse_json_object(product.get("dimensions_mm_json"))
    if not dims:
        dims = {
            key: value
            for key, value in parse_json_object(product.get("specs_json")).items()
            if "(mm)" in str(key).lower() or "diameter" in str(key).lower()
        }
    if not dims:
        return "not available"
    parts = []
    for key, value in dims.items():
        value_text = sanitize_public_text(value)
        if value_text and value_text.lower() not in {"pdf", "dxf", "3d view"}:
            parts.append(f"{sanitize_public_text(key)}: {value_text}")
    return "; ".join(parts[:8]) if parts else "not available"


def recommendation_tags(product: dict[str, Any], light_type: str, color: str) -> list[str]:
    haystack = " ".join(
        str(product.get(key) or "")
        for key in ["model", "title", "product_type", "family_name", "series_code", "category_path", "search_text"]
    ).lower()
    tags = {light_type, "machine_vision_lighting"}
    if light_type in {"bar_light", "dark_field", "ring_light"}:
        tags.add("scratch_detection")
    if light_type in {"backlight", "bar_light"}:
        tags.update(["transparent_edge", "measurement"])
    if light_type in {"coaxial_light", "dome_light", "ring_light"}:
        tags.update(["reflective_surface", "pcb_inspection"])
    if light_type in {"line_scan_light", "bar_light"} or "line scan" in haystack:
        tags.add("line_scan")
    if "red" in color:
        tags.add("red_light")
    if "24v" in str(product.get("voltage_v") or "").lower() or "24v" in haystack:
        tags.add("24v")
    return sorted(tags)


def key_specs(product: dict[str, Any], dimensions: str) -> str:
    parts = []
    for label, key in [
        ("Voltage", "voltage_v"),
        ("Power", "power_w"),
        ("Current", "current_ma"),
        ("Weight", "weight_g"),
    ]:
        value = sanitize_public_text(product.get(key))
        if value:
            parts.append(f"{label}: {value}")
    if dimensions != "not available":
        parts.append(f"Dimensions: {dimensions}")
    return "; ".join(parts) if parts else "not available"


def public_description(light_type: str, tags: list[str]) -> str:
    readable = light_type.replace("_", " ")
    if "transparent_edge" in tags:
        return f"IOO {readable} configuration for edge, silhouette, and transmitted-light inspection trials."
    if "scratch_detection" in tags:
        return f"IOO {readable} configuration for surface contrast and defect visibility experiments."
    if "pcb_inspection" in tags:
        return f"IOO {readable} configuration for flat-part, electronics, and controlled reflection inspection."
    return f"IOO {readable} configuration for machine vision lighting evaluation."


def canonical_field(raw_field: str) -> str:
    lower = (raw_field or "").lower().strip()
    for key, value in CANONICAL_SPEC_FIELDS.items():
        if key in lower:
            return value
    if "(mm)" in lower:
        return "dimension_mm"
    return "unmapped"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS product_specs;
        DROP TABLE IF EXISTS product_assets;
        DROP TABLE IF EXISTS internal_mapping;

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            public_brand TEXT NOT NULL,
            public_model TEXT NOT NULL UNIQUE,
            product_family TEXT,
            series TEXT,
            product_category TEXT,
            light_type TEXT,
            color TEXT,
            wavelength_nm TEXT,
            voltage_v TEXT,
            current_a TEXT,
            power_w TEXT,
            dimensions TEXT,
            description TEXT,
            public_description TEXT,
            recommendation_tags TEXT,
            key_specs TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE product_specs (
            product_id INTEGER,
            public_model TEXT,
            canonical_field TEXT,
            raw_field TEXT,
            raw_value TEXT,
            normalized_value TEXT,
            unit TEXT,
            confidence TEXT,
            source_type TEXT
        );

        CREATE TABLE product_assets (
            product_id INTEGER,
            public_model TEXT,
            asset_type TEXT,
            public_asset_label TEXT,
            asset_url_or_path TEXT,
            source_type TEXT
        );

        CREATE TABLE internal_mapping (
            public_model TEXT PRIMARY KEY,
            internal_model TEXT,
            internal_supplier TEXT,
            original_product_id INTEGER,
            original_source_table TEXT,
            original_source_url TEXT,
            mapping_rule TEXT,
            mapping_confidence TEXT
        );

        CREATE INDEX idx_products_model ON products(public_model);
        CREATE INDEX idx_products_light_type ON products(light_type);
        CREATE INDEX idx_products_color ON products(color);
        CREATE INDEX idx_products_voltage ON products(voltage_v);
        CREATE INDEX idx_specs_model ON product_specs(public_model);
        """
    )


def build_database() -> dict[str, Any]:
    data = load_source_data()
    products = data["products"]
    specs = data["specs"]
    assets = data["assets"]
    public_map, duplicate_events = public_model_map(products)
    spec_by_product: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for spec in specs:
        if spec.get("product_id") is not None:
            spec_by_product[int(spec["product_id"])].append(spec)
    asset_by_product: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets:
        product_id = asset.get("product_id")
        if product_id is not None:
            asset_by_product[int(product_id)].append(asset)

    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT_DB) as conn:
        create_schema(conn)
        public_rows: list[dict[str, Any]] = []
        mapping_rows: list[dict[str, Any]] = []
        for product in products:
            original_id = int(product["id"])
            public_model = public_map[original_id]
            light_type = infer_light_type(product)
            color = infer_color(product)
            wavelength = infer_wavelength(product, color)
            dimensions = compact_dimensions(product)
            tags = recommendation_tags(product, light_type, color)
            category = sanitize_public_text(product.get("product_type") or product.get("family_product_type") or "machine_vision_lighting")
            family = sanitize_public_text(product.get("family_name") or product.get("title") or "")
            series = sanitize_public_text(product.get("series_code") or "")
            row = {
                "id": original_id,
                "public_brand": PUBLIC_BRAND,
                "public_model": public_model,
                "product_family": family,
                "series": series,
                "product_category": category,
                "light_type": light_type,
                "color": color,
                "wavelength_nm": wavelength,
                "voltage_v": sanitize_public_text(product.get("voltage_v")) or "not available",
                "current_a": sanitize_public_text(product.get("current_ma")) or "not available",
                "power_w": sanitize_public_text(product.get("power_w")) or "not available",
                "dimensions": dimensions,
                "description": sanitize_public_text(product.get("title") or family or public_model),
                "public_description": public_description(light_type, tags),
                "recommendation_tags": "|".join(tags),
                "key_specs": key_specs(product, dimensions),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            conn.execute(
                """
                INSERT INTO products VALUES (
                    :id, :public_brand, :public_model, :product_family, :series,
                    :product_category, :light_type, :color, :wavelength_nm, :voltage_v,
                    :current_a, :power_w, :dimensions, :description, :public_description,
                    :recommendation_tags, :key_specs, :created_at, :updated_at
                )
                """,
                row,
            )
            public_rows.append({key: row[key] for key in row if key not in {"id", "created_at", "updated_at"}})
            internal_model = str(product.get("model") or "")
            mapping_rule = "replace_tms_with_ioo" if re.search(r"tms", internal_model, re.I) else "prefix_ioo"
            mapping_row = {
                "public_model": public_model,
                "public_brand": PUBLIC_BRAND,
                "internal_model": internal_model,
                "internal_supplier": PRIVATE_SUPPLIER,
                "original_product_id": original_id,
                "original_source_table": "data/tms_lite_full.db.products",
                "original_source_url": str(product.get("source_url") or ""),
                "mapping_rule": mapping_rule,
                "mapping_confidence": "high",
            }
            conn.execute(
                """
                INSERT INTO internal_mapping VALUES (
                    :public_model, :internal_model, :internal_supplier,
                    :original_product_id, :original_source_table, :original_source_url,
                    :mapping_rule, :mapping_confidence
                )
                """,
                mapping_row,
            )
            mapping_rows.append(mapping_row)
            for spec in spec_by_product.get(original_id, []):
                raw_field = sanitize_public_text(spec.get("spec_name") or spec.get("raw_field") or "")
                raw_value = sanitize_public_text(spec.get("raw_value"))
                normalized = sanitize_public_text(spec.get("normalized_value") or raw_value)
                conn.execute(
                    """
                    INSERT INTO product_specs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        original_id,
                        public_model,
                        canonical_field(raw_field),
                        raw_field,
                        raw_value,
                        normalized,
                        sanitize_public_text(spec.get("unit")),
                        "scraped_internal",
                        "private_internal",
                    ),
                )
            for asset in asset_by_product.get(original_id, []):
                asset_type = sanitize_public_text(asset.get("asset_type") or "asset")
                label = sanitize_public_text(asset.get("title") or asset_type)
                conn.execute(
                    "INSERT INTO product_assets VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        original_id,
                        public_model,
                        asset_type,
                        label or asset_type,
                        f"IOO internal asset reference {asset.get('id')}",
                        "private_internal",
                    ),
                )

    write_csv(PUBLIC_PRODUCTS_CSV, public_rows)
    write_csv(SKU_MAPPING_CSV, mapping_rows)
    write_csv(INTERNAL_MAPPING_CSV, mapping_rows)
    write_reports(data, public_rows, mapping_rows, duplicate_events)
    return {
        "source_products": len(products),
        "public_products": len(public_rows),
        "specs": len(specs),
        "assets": len(assets),
        "duplicates_handled": len(duplicate_events),
        "output_db": str(OUTPUT_DB),
    }


def write_csv(path: Path, rows_to_write: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows_to_write:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_to_write[0].keys()))
        writer.writeheader()
        writer.writerows(rows_to_write)


def write_reports(
    data: dict[str, Any],
    public_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    duplicate_events: list[dict[str, Any]],
) -> None:
    products = data["products"]
    counts = data["counts"]
    model_counter = Counter(str(row.get("model") or "") for row in products)
    duplicate_models = {model: count for model, count in model_counter.items() if model and count > 1}
    empty_models = [row for row in products if not str(row.get("model") or "").strip()]
    type_counts = Counter(row["light_type"] for row in public_rows)
    color_counts = Counter(row["color"] for row in public_rows)
    audit_lines = [
        "# Data Source Audit",
        "",
        f"- Source selected: `{SOURCE_DB}`",
        "- Reason: this is the most complete single-source TMS Lite dataset in the current repo.",
        f"- Original product count: {counts['products']}",
        f"- Original product_specs count: {counts['product_specs']}",
        f"- Original product_assets count: {counts['product_assets']}",
        f"- Original product_families count: {counts['product_families']}",
        f"- Original crawl_pages count: {counts['crawl_pages']}",
        f"- Duplicate internal model groups: {len(duplicate_models)}",
        f"- Products with empty model: {len(empty_models)}",
        f"- Final products used for conversion: {len(products)}",
        "",
        "## Duplicate Model Handling",
        "",
        "Duplicate converted public models receive a stable numeric suffix based on source product id order.",
    ]
    for model, count in list(duplicate_models.items())[:25]:
        audit_lines.append(f"- `{model}`: {count}")
    DATA_SOURCE_AUDIT.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    db_lines = [
        "# IOO Product Database Report",
        "",
        f"- Generated database: `{OUTPUT_DB}`",
        f"- Public product CSV: `{PUBLIC_PRODUCTS_CSV}`",
        f"- SKU mapping CSV: `{SKU_MAPPING_CSV}`",
        f"- IOO public products generated: {len(public_rows)}",
        f"- Mapping rows generated: {len(mapping_rows)}",
        f"- Duplicate public model suffixes added: {len(duplicate_events)}",
        "",
        "## Light Type Distribution",
        "",
    ]
    for light_type, count in type_counts.most_common():
        db_lines.append(f"- {light_type}: {count}")
    db_lines.extend(["", "## Color Distribution", ""])
    for color, count in color_counts.most_common(20):
        db_lines.append(f"- {color}: {count}")
    DATABASE_REPORT.write_text("\n".join(db_lines) + "\n", encoding="utf-8")

    migration_lines = [
        "# IOO Rebrand Database Migration Report",
        "",
        f"1. Original TMS product count: {len(products)}",
        f"2. Generated IOO product count: {len(public_rows)}",
        f"3. One-to-one mapping completed: {'yes' if len(products) == len(public_rows) == len(mapping_rows) else 'no'}",
        "4. Public model conversion rule: replace TMS/TMS-LITE tokens with IOO; otherwise prefix the original model with `IOO-`; duplicates get stable `-2`, `-3` suffixes.",
        f"5. Duplicate model handling count: {len(duplicate_events)}",
        f"6. public_products.csv path: `{PUBLIC_PRODUCTS_CSV}`",
        f"7. data/ioo_products.db path: `{OUTPUT_DB}`",
        f"8. ioo_sku_mapping.csv path: `{SKU_MAPPING_CSV}`",
        "9. Public TMS leakage risk: mitigated by public-text sanitization and public UI source hiding.",
        "10. Query-class handling: list/filter questions are backed by product_search.py and can return counts plus first 20 rows.",
        "11. Recommendation handling: closest-fit recommendations are selected from data/ioo_products.db before any AI response is composed.",
        "12. OpenAI restriction: answer_engine.py only passes retrieved IOO candidates and validates/filters model names.",
        "13. Test status: see IOO_PRODUCT_MAPPING_TEST_REPORT.md and TEST_REPORT.md after test run.",
        "14. Current unresolved issue: source quality still depends on original scraped parameter completeness; missing values remain `not available`.",
    ]
    MIGRATION_REPORT.write_text("\n".join(migration_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(build_database(), indent=2, ensure_ascii=False))
