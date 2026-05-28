from __future__ import annotations

import csv
import re
import sqlite3
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
    return db_rows("SELECT * FROM products ORDER BY public_model")


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
    filters: dict[str, str] = {}
    if any(token in text for token in ["red light", "red", "红光", "红色"]):
        filters["color"] = "red"
    if any(token in text for token in ["green light", "green", "绿光", "绿色"]):
        filters["color"] = "green"
    if any(token in text for token in ["blue light", "blue", "蓝光", "蓝色"]):
        filters["color"] = "blue"
    if any(token in text for token in ["white light", "white", "白光", "白色"]):
        filters["color"] = "white"
    if any(token in text for token in ["uv", "紫外"]):
        filters["color"] = "uv"
    if any(token in text for token in ["ir", "infrared", "红外"]):
        filters["color"] = "ir"
    if any(token in text.replace(" ", "") for token in ["24v", "dc24v", "24伏"]):
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


def matches_filters(product: dict[str, Any], filters: dict[str, str]) -> bool:
    for field, value in filters.items():
        hay = str(product.get(field) or "").lower()
        if field == "color":
            if value == "red" and not any(token in hay for token in ["red", "rgb", "625"]):
                return False
            if value == "green" and not any(token in hay for token in ["green", "rgb", "525"]):
                return False
            if value == "blue" and not any(token in hay for token in ["blue", "rgb", "470"]):
                return False
            if value == "white" and not any(token in hay for token in ["white", "rgbw"]):
                return False
            if value == "uv" and "uv" not in hay and "365" not in hay:
                return False
            if value == "ir" and "ir" not in hay and "850" not in hay:
                return False
        elif field == "voltage_v":
            if value.replace(" ", "") not in hay.replace(" ", "").lower():
                return False
        else:
            if value.lower() != hay:
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
            hay = " ".join(str(product.get(field) or "") for field in DISPLAY_FIELDS + ["public_description", "recommendation_tags"]).lower()
            if not terms or all(term.lower() in hay for term in terms[:3]):
                matched.append(product)
    total = len(matched)
    shown = matched if limit is None else matched[:limit]
    return {"products": shown, "total": total, "filters": filters, "showing": len(shown)}


def list_products_by_attribute(attribute: str, value: str, limit: int = 20) -> dict[str, Any]:
    return search_products("", {attribute: value}, limit=limit)


def recommend_products(question: str, limit: int = 5) -> list[dict[str, Any]]:
    candidates = sku_mapping.search_public_products(question, limit=limit)
    return sku_mapping.validate_public_products(candidates)


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
