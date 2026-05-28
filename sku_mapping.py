from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
IOO_DB_PATH = ROOT / "data" / "ioo_products.db"
PUBLIC_PRODUCTS_PATH = ROOT / "public_products.csv"
MAPPING_PATH = ROOT / "ioo_sku_mapping.csv"

PUBLIC_BRAND = "IOO"


def to_ioo_model(internal_model: str) -> str:
    from generate_ioo_product_db import to_ioo_model as _to_ioo_model

    return _to_ioo_model(internal_model)


def generate_files() -> dict[str, Any]:
    from generate_ioo_product_db import build_database

    return build_database()


def ensure_catalog() -> None:
    if not IOO_DB_PATH.exists() or not PUBLIC_PRODUCTS_PATH.exists() or not MAPPING_PATH.exists():
        generate_files()


def _db_rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    ensure_catalog()
    with sqlite3.connect(IOO_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def load_public_products() -> list[dict[str, Any]]:
    ensure_catalog()
    if IOO_DB_PATH.exists():
        return _db_rows("SELECT * FROM products ORDER BY public_model")
    with PUBLIC_PRODUCTS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_mapping() -> list[dict[str, Any]]:
    ensure_catalog()
    with MAPPING_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def public_model_exists(public_model: str) -> bool:
    if not public_model:
        return False
    rows = _db_rows("SELECT 1 FROM products WHERE public_model = ? LIMIT 1", (public_model.upper(),))
    return bool(rows)


def public_model_for_internal_model(model: str) -> str | None:
    if not model:
        return None
    query = str(model).strip().upper()
    if query.startswith("IOO-") and public_model_exists(query):
        return query
    rows = _db_rows(
        """
        SELECT public_model
        FROM internal_mapping
        WHERE UPPER(internal_model) = ?
        ORDER BY original_product_id
        LIMIT 1
        """,
        (query,),
    )
    if rows:
        return str(rows[0]["public_model"])
    candidate = to_ioo_model(query)
    return candidate if public_model_exists(candidate) else None


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_+./-]{1,}|[\u4e00-\u9fff]{1,}", (text or "").lower())


def infer_query_tags(question: str) -> list[str]:
    text = (question or "").lower()
    tags = set(tokenize(text))
    mappings = {
        "scratch_detection": ["scratch", "scratches", "划痕", "刮痕", "擦伤"],
        "reflective_surface": ["reflective", "reflection", "glare", "metal", "金属", "反光", "镜面"],
        "transparent_edge": ["transparent", "bottle", "glass", "edge", "透明", "玻璃", "瓶", "边缘"],
        "pcb_inspection": ["pcb", "circuit", "board", "电路板", "线路板"],
        "line_scan": ["line scan", "linescan", "web inspection", "线扫"],
        "measurement": ["measurement", "dimension", "measure", "尺寸", "测量"],
        "backlight": ["backlight", "back light", "silhouette", "背光"],
        "dark_field": ["dark-field", "darkfield", "dark field", "low angle", "暗场", "低角度"],
        "coaxial_light": ["coaxial", "co-axial", "同轴"],
        "bar_light": ["bar light", "bar", "linear", "条形", "条光"],
        "ring_light": ["ring light", "ring", "环形", "环光"],
        "dome_light": ["dome", "diffuse", "穹顶", "漫射"],
        "red_light": ["red light", "red", "红光", "红色"],
        "green_light": ["green light", "green", "绿光", "绿色"],
        "blue_light": ["blue light", "blue", "蓝光", "蓝色"],
        "white_light": ["white light", "white", "白光", "白色"],
        "uv_light": ["uv", "ultraviolet", "紫外"],
        "ir_light": ["ir", "infrared", "红外"],
        "24v": ["24v", "24 v", "dc24v", "24伏"],
    }
    for tag, needles in mappings.items():
        if any(needle in text for needle in needles):
            tags.add(tag)
    return sorted(tags)


def score_product(question: str, product: dict[str, Any]) -> tuple[float, list[str]]:
    tags = infer_query_tags(question)
    haystack = " ".join(
        str(product.get(field) or "")
        for field in [
            "public_model",
            "product_family",
            "series",
            "product_category",
            "light_type",
            "color",
            "wavelength_nm",
            "voltage_v",
            "power_w",
            "dimensions",
            "public_description",
            "recommendation_tags",
            "key_specs",
        ]
    ).lower()
    score = 0.0
    reasons: list[str] = []
    for tag in tags:
        if tag and tag.lower() in haystack:
            score += 4 if "_" in tag else 1
            if "_" in tag:
                reasons.append(f"matches {tag.replace('_', ' ')}")
    light_type = str(product.get("light_type") or "")
    color = str(product.get("color") or "").lower()
    voltage = str(product.get("voltage_v") or "").lower()
    if "red_light" in tags and ("red" in color or "rgb" in color or "625" in haystack):
        score += 12
        reasons.append("red light evidence")
    if "24v" in tags and "24v" in voltage.replace(" ", ""):
        score += 12
        reasons.append("24V evidence")
    if "ring_light" in tags and light_type == "ring_light":
        score += 12
        reasons.append("ring light geometry")
    if "backlight" in tags and light_type == "backlight":
        score += 12
        reasons.append("backlight geometry")
    if "coaxial_light" in tags and light_type == "coaxial_light":
        score += 12
        reasons.append("coaxial geometry")
    if "scratch_detection" in tags and light_type in {"dark_field", "bar_light", "ring_light"}:
        score += 9
        reasons.append("surface defect lighting approach")
    if "transparent_edge" in tags and light_type in {"backlight", "bar_light"}:
        score += 10
        reasons.append("edge/silhouette lighting approach")
    if "reflective_surface" in tags and light_type in {"coaxial_light", "dark_field", "dome_light"}:
        score += 7
        reasons.append("reflective surface lighting approach")
    if "pcb_inspection" in tags and light_type in {"coaxial_light", "dome_light", "ring_light"}:
        score += 7
        reasons.append("flat electronics inspection approach")
    if "line_scan" in tags and light_type in {"line_scan_light", "bar_light"}:
        score += 9
        reasons.append("line scan lighting approach")
    if not reasons and product.get("light_type") not in {"", "machine_vision_light"}:
        score += 0.25
        reasons.append("general IOO lighting candidate")
    return score, list(dict.fromkeys(reasons))


def search_public_products(question: str, limit: int | None = 5) -> list[dict[str, Any]]:
    products = load_public_products()
    scored = []
    for product in products:
        score, reasons = score_product(question, product)
        if score > 0:
            item = dict(product)
            item["score"] = round(score, 2)
            item["fit_type"] = "Exact fit" if score >= 22 else "Close fit" if score >= 10 else "Workaround fit"
            item["why_it_may_fit"] = "; ".join(reasons) if reasons else "closest available IOO lighting configuration"
            scored.append(item)
    scored.sort(key=lambda row: (-float(row["score"]), str(row.get("public_model", ""))))
    if not scored:
        fallback = products[: limit or 20]
        for product in fallback:
            item = dict(product)
            item["score"] = 0.1
            item["fit_type"] = "Workaround fit"
            item["why_it_may_fit"] = "closest searchable IOO product; more inspection details are needed"
            scored.append(item)
    return scored if limit is None else scored[:limit]


def validate_public_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = []
    for product in products:
        model = str(product.get("public_model") or "").upper()
        if model.startswith("IOO-") and public_model_exists(model):
            valid.append(product)
    return valid


if __name__ == "__main__":
    print(json.dumps(generate_files(), indent=2, ensure_ascii=False))
