from __future__ import annotations

import csv
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import sku_mapping


ROOT = Path(__file__).resolve().parent
IOO_DB_PATH = ROOT / "data" / "ioo_products.db"


DISPLAY_FIELDS = [
    "public_model",
    "light_type",
    "product_category",
    "product_family",
    "color",
    "wavelength_nm",
    "voltage_v",
    "power_w",
    "current_a",
    "dimensions",
    "fit_type",
    "why_it_may_fit",
]


def connect() -> sqlite3.Connection:
    sku_mapping.ensure_catalog()
    conn = sqlite3.connect(IOO_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def all_products() -> list[dict[str, Any]]:
    return db_rows(
        """
        SELECT *
        FROM products
        WHERE lower(coalesce(product_category, '')) != 'demo_kit'
        ORDER BY public_model
        """
    )


@lru_cache(maxsize=1)
def spec_haystack_by_model() -> dict[str, str]:
    rows = db_rows(
        """
        SELECT public_model, canonical_field, raw_field, raw_value, normalized_value, unit
        FROM product_specs
        """
    )
    grouped: dict[str, list[str]] = {}
    for row in rows:
        model = str(row.get("public_model") or "").upper()
        if not model:
            continue
        grouped.setdefault(model, []).append(
            " ".join(
                str(row.get(field) or "")
                for field in ["canonical_field", "raw_field", "raw_value", "normalized_value", "unit"]
            )
        )
    return {model: " ".join(parts).lower() for model, parts in grouped.items()}


@lru_cache(maxsize=1)
def color_haystack_by_model() -> dict[str, str]:
    rows = db_rows(
        """
        SELECT public_model, canonical_field, raw_field, raw_value, normalized_value, unit
        FROM product_specs
        """
    )
    grouped: dict[str, list[str]] = {}
    color_words = re.compile(r"\b(red|green|blue|white|uv|ultraviolet|ir|infrared|rgb|rgbw)\b", re.I)
    for row in rows:
        model = str(row.get("public_model") or "").upper()
        field_text = " ".join(str(row.get(field) or "") for field in ["canonical_field", "raw_field"]).lower()
        value_text = " ".join(str(row.get(field) or "") for field in ["raw_value", "normalized_value", "unit"]).lower()
        field_is_color_related = any(token in field_text for token in ["color", "colour", "wavelength", "wave length", "led"])
        if field_is_color_related or color_words.search(value_text):
            grouped.setdefault(model, []).append(field_text + " " + value_text)
    return {model: " ".join(parts).lower() for model, parts in grouped.items()}


def get_product(public_model: str) -> dict[str, Any] | None:
    if not public_model:
        return None
    rows = db_rows("SELECT * FROM products WHERE public_model = ? LIMIT 1", (public_model.upper(),))
    return rows[0] if rows else None


def model_mentions(text: str) -> list[str]:
    raw = text or ""
    candidates = re.findall(r"\bIOO-[A-Z0-9][A-Z0-9_.-]*\b", raw.upper())
    candidates.extend(re.findall(r"\b[A-Z]{2,}[A-Z0-9]*-[A-Z0-9][A-Z0-9_.-]*\b", raw.upper()))
    seen = []
    for candidate in candidates:
        candidate = candidate.strip(".,;:()[]{}")
        if candidate not in seen:
            seen.append(candidate)
    return seen


def resolve_model(model: str) -> dict[str, Any] | None:
    if not model:
        return None
    model = model.strip().upper()
    if model.startswith("IOO-"):
        product = get_product(model)
        if product:
            return product
    public = sku_mapping.public_model_for_internal_model(model)
    return get_product(public) if public else None


def infer_filters(query: str) -> dict[str, str]:
    text = (query or "").lower()
    compact = text.replace(" ", "")
    filters: dict[str, str] = {}

    nm_match = re.search(r"\b(365|375|385|395|400|405|410|420|450|470|525|625|850|940)\s*nm\b", text)
    if nm_match:
        filters["wavelength_nm"] = nm_match.group(1)

    if any(token in text for token in ["purple", "violet", "purple light", "violet light", "紫光", "紫色光", "紫色"]):
        filters["color"] = "violet_uv"
    elif any(token in text for token in ["uv", "ultraviolet", "紫外", "紫外光"]):
        filters["color"] = "uv"
    elif any(token in text for token in ["red light", "red", "红光", "红色"]):
        filters["color"] = "red"
    elif any(token in text for token in ["green light", "green", "绿光", "绿色"]):
        filters["color"] = "green"
    elif any(token in text for token in ["blue light", "blue", "蓝光", "蓝色"]):
        filters["color"] = "blue"
    elif any(token in text for token in ["white light", "white", "白光", "白色"]):
        filters["color"] = "white"
    elif any(token in text for token in ["ir", "infrared", "红外", "红外光"]):
        filters["color"] = "ir"

    if any(token in compact for token in ["24v", "dc24v", "24伏"]):
        filters["voltage_v"] = "24v"

    light_type_rules = [
        ("ring_light", ["ring light", "ring", "环形", "环光"]),
        ("backlight", ["backlight", "back light", "背光"]),
        ("coaxial_light", ["coaxial", "同轴"]),
        ("bar_light", ["bar light", "bar", "条形", "条光"]),
        ("line_scan_light", ["line scan", "linescan", "线扫"]),
        ("dark_field", ["dark field", "darkfield", "暗场", "低角度"]),
        ("dome_light", ["dome", "diffuse", "穹顶", "漫射"]),
    ]
    for light_type, needles in light_type_rules:
        if any(needle in text for needle in needles):
            filters["light_type"] = light_type
            break
    return filters


def product_haystack(product: dict[str, Any]) -> str:
    model = str(product.get("public_model") or "").upper()
    public_text = " ".join(
        str(product.get(field) or "")
        for field in [
            "public_model",
            "light_type",
            "product_category",
            "product_family",
            "series",
            "color",
            "wavelength_nm",
            "voltage_v",
            "power_w",
            "dimensions",
            "public_description",
            "recommendation_tags",
            "key_specs",
        ]
    )
    return (public_text + " " + spec_haystack_by_model().get(model, "")).lower()


def matches_filters(product: dict[str, Any], filters: dict[str, str]) -> bool:
    full_hay = product_haystack(product)
    color_hay = str(product.get("color") or "").lower()
    wavelength_hay = str(product.get("wavelength_nm") or "").lower()
    spec_hay = color_haystack_by_model().get(str(product.get("public_model") or "").upper(), "")
    model_hay = str(product.get("public_model") or "").lower()
    color_signal = " ".join([color_hay, wavelength_hay, spec_hay, model_hay if "uv" in model_hay else ""]).lower()
    ir_signal = " ".join([color_signal, model_hay if "ir" in model_hay else ""]).lower()
    voltage_hay = str(product.get("voltage_v") or "").lower().replace(" ", "")
    for field, value in filters.items():
        value = str(value).lower()
        if field == "color":
            if value == "red" and not (re.search(r"\bred\b", color_signal) or "rgb" in color_signal or "625" in color_signal):
                return False
            if value == "green" and not (re.search(r"\bgreen\b", color_signal) or "rgb" in color_signal or "525" in color_signal):
                return False
            if value == "blue" and not (re.search(r"\bblue\b", color_signal) or "rgb" in color_signal or "470" in color_signal):
                return False
            if value == "white" and not (re.search(r"\bwhite\b", color_signal) or "rgbw" in color_signal):
                return False
            if value == "uv" and not any(token in color_signal for token in ["uv", "ultraviolet", "365", "375", "385", "395"]):
                return False
            if value == "violet_uv" and not any(
                token in color_signal
                for token in ["violet", "purple", "uv", "ultraviolet", "365", "375", "385", "395", "400", "405", "410", "420"]
            ):
                return False
            if value == "ir" and not any(token in ir_signal for token in ["ir", "infrared", "850", "940"]):
                return False
            if value not in {"red", "green", "blue", "white", "uv", "violet_uv", "ir"} and value not in color_hay:
                return False
        elif field == "wavelength_nm":
            if value not in color_signal:
                return False
        elif field == "voltage_v":
            if value.replace(" ", "") not in voltage_hay:
                return False
        else:
            if value != str(product.get(field) or "").lower():
                return False
    return True


def search_products(query: str, filters: dict[str, str] | None = None, limit: int | None = None) -> dict[str, Any]:
    filters = filters or infer_filters(query)
    products = all_products()
    if filters:
        matched = [product for product in products if matches_filters(product, filters)]
    else:
        terms = [token for token in sku_mapping.tokenize(query) if token not in {"ioo", "products", "product"}]
        matched = []
        for product in products:
            hay = product_haystack(product)
            if not terms or all(term.lower() in hay for term in terms[:3]):
                matched.append(product)
    total = len(matched)
    shown = matched if limit is None else matched[:limit]
    return {"products": shown, "total": total, "filters": filters, "showing": len(shown)}


def list_products_by_attribute(attribute: str, value: str, limit: int = 20) -> dict[str, Any]:
    return search_products("", {attribute: value}, limit=limit)


def recommend_products(question: str, limit: int = 5) -> list[dict[str, Any]]:
    scored = []
    for product in all_products():
        score, reasons = sku_mapping.score_product(question, product)
        if score > 0:
            item = dict(product)
            item["score"] = round(score, 2)
            item["fit_type"] = "Exact fit" if score >= 22 else "Close fit" if score >= 10 else "Workaround fit"
            item["why_it_may_fit"] = "; ".join(reasons) if reasons else "closest available IOO lighting configuration"
            scored.append(item)
    scored.sort(key=lambda row: (-float(row["score"]), str(row.get("public_model", ""))))
    if not scored:
        for product in all_products()[:limit]:
            item = dict(product)
            item["score"] = 0.1
            item["fit_type"] = "Workaround fit"
            item["why_it_may_fit"] = "closest searchable IOO product; more inspection details are needed"
            scored.append(item)
    return sku_mapping.validate_public_products(scored[:limit])


def compare_products(models: list[str]) -> dict[str, Any]:
    products = []
    missing = []
    for model in models:
        product = resolve_model(model)
        if product:
            product["fit_type"] = "Exact fit"
            product["why_it_may_fit"] = "model explicitly requested"
            products.append(product)
        else:
            missing.append(model)
    return {"products": products, "missing": missing, "total": len(products)}


def extract_product_specs(public_model: str) -> list[dict[str, Any]]:
    return db_rows(
        """
        SELECT public_model, canonical_field, raw_field, raw_value, normalized_value, unit, confidence, source_type
        FROM product_specs
        WHERE public_model = ?
        ORDER BY canonical_field, raw_field
        LIMIT 200
        """,
        (public_model.upper(),),
    )


def product_table_rows(products: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    for product in products[:limit]:
        rows.append({field: product.get(field, "not available") for field in DISPLAY_FIELDS})
    return rows


def write_query_results_csv(path: Path, products: list[dict[str, Any]]) -> None:
    rows = product_table_rows(products, limit=len(products))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISPLAY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
