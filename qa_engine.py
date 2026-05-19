from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "data" / "tms_lite_full.db"
EXPORT_DIR = ROOT / "data" / "exports"


CANONICAL_DISPLAY = {
    "brand": "Brand",
    "product_family": "Product family",
    "series": "Series",
    "model": "Model",
    "product_category": "Product category",
    "light_type": "Light type",
    "color": "Color",
    "wavelength_nm": "Wavelength",
    "voltage_v": "Voltage",
    "power_w": "Power",
    "current_a": "Current",
    "outer_diameter_mm": "Outer diameter",
    "inner_diameter_mm": "Inner diameter",
    "length_mm": "Length",
    "width_mm": "Width",
    "height_mm": "Height",
    "working_distance_mm": "Working distance",
    "emitting_area_mm": "Emitting area",
    "illumination_area_mm": "Illumination area",
    "connector": "Connector",
    "cable_length_mm": "Cable length",
    "mounting": "Mounting",
    "ip_rating": "IP rating",
    "controller_compatibility": "Controller compatibility",
    "strobe_mode": "Strobe mode",
    "datasheet_url": "Datasheet URL",
    "product_url": "Product URL",
}


APPLICATION_INTENTS = {
    "metal_scratch": {
        "keywords": ["metal", "金属", "scratch", "划痕", "刮痕", "暗场", "dark-field", "dark field", "low angle", "低角度"],
        "logic": "Metal scratch inspection often starts with low-angle or dark-field illumination because shallow grazing light can make surface defects stand out. Coaxial light may help on flat reflective surfaces.",
        "query": "low angle dark field metal scratch DLQ DLA coaxial",
    },
    "transparent_edge": {
        "keywords": ["transparent", "透明", "bottle", "瓶", "edge", "边缘", "backlight", "背光"],
        "logic": "Transparent bottle edge inspection usually starts with backlight for silhouette/edge contrast. Coaxial or dome illumination can be explored if the inspection target is print or surface reflection.",
        "query": "backlight transparent edge BHL BHH BHS BIDS",
    },
    "pcb": {
        "keywords": ["pcb", "电路板", "solder", "焊点", "component", "元件"],
        "logic": "PCB inspection may use ring/bar lighting for general features, coaxial lighting for reflective pads, and dome/diffuse lighting to reduce glare. UV can be useful for fluorescence targets.",
        "query": "ring coaxial dome bar RGBW UV PCB",
    },
    "backlight": {
        "keywords": ["backlight", "背光", "silhouette", "轮廓", "尺寸", "外形"],
        "logic": "Backlight is suitable for silhouette, edge, hole, and dimension checks where the part blocks light and creates high contrast.",
        "query": "backlight BHL BHH BHS BIDS",
    },
}


LIGHT_TYPE_TERMS = {
    "ring": ["ring", "环形", "lbr", "dlr", "hpd"],
    "bar": ["bar", "条形", "lsw", "lla", "hlbs", "hlbq"],
    "backlight": ["backlight", "背光", "bhl", "bhh", "bhs", "bids", "hbl"],
    "coaxial": ["coaxial", "co-axial", "同轴", "cas", "mcax"],
    "dome": ["dome", "穹顶", "diffused", "漫射", "fdd", "hbf"],
    "low_angle": ["low angle", "低角度", "dark field", "暗场", "dlq", "dla"],
    "line": ["line", "线扫", "线光", "line scan"],
    "spot": ["spot", "点光", "hbf", "fib"],
    "uv": ["uv", "紫外", "uv365", "uv395"],
    "ir": ["ir", "红外", "infrared", "ir850", "ir940"],
    "rgb": ["rgb"],
    "rgbw": ["rgbw"],
}


@dataclass
class Dataset:
    source_type: str
    db_path: Path | None
    products: list[dict[str, Any]]
    specs: list[dict[str, Any]]
    assets: list[dict[str, Any]]
    crawl_pages: list[dict[str, Any]]
    counts: dict[str, int]
    schema: dict[str, list[str]]


_DATASET: Dataset | None = None


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _text(value: Any) -> str:
    return _clean(value).lower()


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params)]


def _first_datasheet(assets: list[dict[str, Any]]) -> str | None:
    for asset in assets:
        if asset.get("asset_type") == "datasheet" and asset.get("url"):
            return asset["url"]
    for asset in assets:
        if asset.get("asset_type") in {"pdf", "catalogue"} and asset.get("url"):
            return asset["url"]
    return None


def _infer_light_type(product: dict[str, Any]) -> str | None:
    haystack = " ".join(
        _text(product.get(key))
        for key in ["model", "product_family", "series", "title", "product_category", "search_text"]
    )
    for light_type, terms in LIGHT_TYPE_TERMS.items():
        if any(term in haystack for term in terms):
            return light_type
    return None


def _sqlite_dataset(db_path: Path) -> Dataset:
    conn = sqlite3.connect(db_path)
    try:
        table_names = [row["name"] for row in _rows(conn, "SELECT name FROM sqlite_master WHERE type='table'")]
        schema = {table: [row["name"] for row in _rows(conn, f"PRAGMA table_info({table})")] for table in table_names}
        counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in table_names}

        raw_products = _rows(
            conn,
            """
            SELECT
                p.id,
                b.name AS brand,
                pf.family_name AS product_family,
                pf.series_code AS series,
                pf.category_path AS category,
                p.model,
                p.model_normalized,
                p.product_type AS product_category,
                p.title,
                p.color_options AS color,
                p.wavelength_nm,
                p.voltage_v,
                p.power_w,
                p.current_ma,
                p.weight_g,
                p.dimensions_mm_json,
                p.specs_json,
                p.search_text,
                p.source_url AS product_url,
                p.source_url
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            LEFT JOIN product_families pf ON pf.id = p.family_id
            ORDER BY p.model
            """,
        )
        specs = _rows(
            conn,
            """
            SELECT
                ps.id,
                p.model,
                p.model_normalized,
                ps.spec_group,
                ps.spec_name,
                ps.raw_value,
                ps.normalized_value,
                ps.unit,
                ps.source_url
            FROM product_specs ps
            JOIN products p ON p.id = ps.product_id
            ORDER BY p.model, ps.spec_name
            """,
        )
        assets = _rows(
            conn,
            """
            SELECT
                pa.id,
                p.model,
                p.model_normalized,
                pf.family_name AS product_family,
                pa.asset_type,
                pa.title,
                pa.url,
                pa.final_url,
                pa.local_path,
                pa.source_url
            FROM product_assets pa
            LEFT JOIN products p ON p.id = pa.product_id
            LEFT JOIN product_families pf ON pf.id = pa.family_id
            ORDER BY COALESCE(p.model, ''), pa.asset_type, pa.title
            """,
        )
        crawl_pages = _rows(conn, "SELECT * FROM crawl_pages ORDER BY id")
    finally:
        conn.close()

    assets_by_model: dict[str, list[dict[str, Any]]] = {}
    assets_by_family: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        if asset.get("model_normalized"):
            assets_by_model.setdefault(asset["model_normalized"], []).append(asset)
        if asset.get("product_family"):
            assets_by_family.setdefault(asset["product_family"], []).append(asset)

    products: list[dict[str, Any]] = []
    for product in raw_products:
        related_assets = assets_by_model.get(product.get("model_normalized"), [])
        if not related_assets and product.get("product_family"):
            related_assets = assets_by_family.get(product["product_family"], [])
        product["datasheet_url"] = _first_datasheet(related_assets)
        product["current_a"] = product.get("current_ma")
        product["light_type"] = _infer_light_type(product)
        product["asset_count"] = len(related_assets)
        products.append(product)

    return Dataset(
        source_type="SQLite",
        db_path=db_path,
        products=products,
        specs=specs,
        assets=assets,
        crawl_pages=crawl_pages,
        counts=counts,
        schema=schema,
    )


def _csv_dataset() -> Dataset:
    products_csv = _read_csv(EXPORT_DIR / "products_flat.csv")
    specs_csv = _read_csv(EXPORT_DIR / "product_specs.csv")
    assets_csv = _read_csv(EXPORT_DIR / "product_assets.csv")

    assets_by_model: dict[str, list[dict[str, Any]]] = {}
    for asset in assets_csv:
        model = _norm(asset.get("model"))
        if model:
            assets_by_model.setdefault(model, []).append(asset)

    products = []
    for i, row in enumerate(products_csv, start=1):
        model = row.get("model") or ""
        product = {
            "id": i,
            "brand": row.get("brand"),
            "product_family": row.get("family_name"),
            "series": None,
            "category": None,
            "model": model,
            "model_normalized": _norm(model),
            "product_category": row.get("product_type"),
            "title": row.get("family_name"),
            "color": row.get("color_options"),
            "wavelength_nm": row.get("wavelength_nm"),
            "voltage_v": row.get("voltage_v"),
            "power_w": row.get("power_w"),
            "current_ma": row.get("current_ma"),
            "current_a": row.get("current_ma"),
            "weight_g": row.get("weight_g"),
            "dimensions_mm_json": row.get("dimensions_mm_json"),
            "specs_json": row.get("specs_json"),
            "search_text": " ".join(str(v or "") for v in row.values()),
            "product_url": row.get("source_url"),
            "source_url": row.get("source_url"),
        }
        related_assets = assets_by_model.get(product["model_normalized"], [])
        product["datasheet_url"] = _first_datasheet(related_assets)
        product["light_type"] = _infer_light_type(product)
        product["asset_count"] = len(related_assets)
        products.append(product)

    counts = {
        "brands": len({p.get("brand") for p in products if p.get("brand")}),
        "product_families": len({p.get("product_family") for p in products if p.get("product_family")}),
        "products": len(products),
        "product_specs": len(specs_csv),
        "product_assets": len(assets_csv),
        "crawl_pages": 0,
    }
    return Dataset(
        source_type="CSV fallback",
        db_path=None,
        products=products,
        specs=specs_csv,
        assets=assets_csv,
        crawl_pages=[],
        counts=counts,
        schema={},
    )


def load_database(force: bool = False, db_path: str | Path | None = None) -> Dataset:
    """Load SQLite product data, falling back to exported CSV files if needed."""
    global _DATASET
    if _DATASET is not None and not force:
        return _DATASET
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    try:
        if path.exists():
            _DATASET = _sqlite_dataset(path)
        else:
            _DATASET = _csv_dataset()
    except Exception:
        _DATASET = _csv_dataset()
    return _DATASET


def get_database_stats() -> dict[str, Any]:
    ds = load_database()
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "source_type": ds.source_type,
        "db_path": str(ds.db_path) if ds.db_path else None,
        "counts": ds.counts,
        "schema": ds.schema,
        "mode": "OpenAI available" if has_openai_key else "Local fallback",
    }


def _product_public_row(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "brand": product.get("brand") or "not available",
        "model": product.get("model") or "not available",
        "family": product.get("product_family") or "not available",
        "series": product.get("series") or "not available",
        "category": product.get("product_category") or "not available",
        "light_type": product.get("light_type") or "not available",
        "color": product.get("color") or product.get("wavelength_nm") or "not available",
        "voltage": product.get("voltage_v") or "not available",
        "power": product.get("power_w") or "not available",
        "current": product.get("current_ma") or "not available",
        "weight": product.get("weight_g") or "not available",
        "dimensions": product.get("dimensions_mm_json") or "not available",
        "product_url": product.get("product_url") or product.get("source_url") or "not available",
        "datasheet_url": product.get("datasheet_url") or "not available",
    }


def _tokens(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9.+/-]+|[\u4e00-\u9fff]+", query.lower())
    out: list[str] = []
    for word in words:
        if len(word) >= 2:
            out.append(word)
            out.append(word.replace("-", ""))
    return list(dict.fromkeys(out))


def _haystack(product: dict[str, Any]) -> str:
    return _text(
        " ".join(
            str(product.get(key) or "")
            for key in [
                "brand",
                "product_family",
                "series",
                "category",
                "model",
                "product_category",
                "title",
                "color",
                "wavelength_nm",
                "voltage_v",
                "power_w",
                "current_ma",
                "dimensions_mm_json",
                "specs_json",
                "search_text",
                "light_type",
            ]
        )
    )


def _score_product(product: dict[str, Any], query: str) -> tuple[float, list[str]]:
    q = _text(query)
    compact_q = _norm(query)
    hay = _haystack(product)
    model = _norm(product.get("model"))
    family = _text(product.get("product_family"))
    score = 0.0
    reasons: list[str] = []

    if model and len(model) >= 4 and model in compact_q:
        score += 100
        reasons.append("exact model match")

    for token in _tokens(query):
        if token in _text(product.get("model")) or token.replace("-", "") in model.lower():
            score += 12
            reasons.append(f"model contains {token}")
        elif token in family:
            score += 6
            reasons.append(f"family contains {token}")
        elif token in hay:
            score += 2

    for light_type, terms in LIGHT_TYPE_TERMS.items():
        if any(term in q for term in terms):
            if product.get("light_type") == light_type or any(term in hay for term in terms):
                score += 12
                reasons.append(f"light type evidence: {light_type}")

    for value, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(v|w|ma|g|mm|nm)\b", q):
        target = f"{value}{unit}"
        if target in hay.replace(" ", ""):
            score += 10
            reasons.append(f"parameter evidence: {target}")

    if "datasheet" in q and product.get("datasheet_url"):
        score += 12
        reasons.append("has datasheet")
    if "24v" in q.replace(" ", "") and "24v" in _text(product.get("voltage_v")).replace(" ", ""):
        score += 12
        reasons.append("24V match")
    if ("red" in q or "红" in q) and "red" in hay:
        score += 8
        reasons.append("red light evidence")
    if ("coaxial" in q or "同轴" in q) and ("coaxial" in hay or "cas" in hay or "mcax" in hay):
        score += 10
        reasons.append("coaxial evidence")

    return score, list(dict.fromkeys(reasons))[:6]


def search_products(query: str, limit: int = 20) -> list[dict[str, Any]]:
    ds = load_database()
    hits = []
    for product in ds.products:
        score, reasons = _score_product(product, query)
        if score > 0:
            row = _product_public_row(product)
            row["score"] = round(score, 2)
            row["match_reasons"] = "; ".join(reasons)
            hits.append(row)
    hits.sort(key=lambda row: (-float(row["score"]), row["model"]))
    return hits[:limit]


def get_product_by_model(model: str) -> dict[str, Any] | None:
    ds = load_database()
    target = _norm(model)
    for product in ds.products:
        if _norm(product.get("model")) == target:
            return _product_public_row(product)
    return None


def _raw_product_by_model(model: str) -> dict[str, Any] | None:
    ds = load_database()
    target = _norm(model)
    for product in ds.products:
        if _norm(product.get("model")) == target:
            return product
    return None


def get_product_specs(model: str) -> list[dict[str, Any]]:
    ds = load_database()
    target = _norm(model)
    specs = []
    for spec in ds.specs:
        spec_model = spec.get("model_normalized") or _norm(spec.get("model"))
        if spec_model == target:
            specs.append(
                {
                    "model": spec.get("model"),
                    "spec_name": spec.get("spec_name"),
                    "raw_value": spec.get("raw_value"),
                    "normalized_value": spec.get("normalized_value"),
                    "unit": spec.get("unit"),
                    "source_url": spec.get("source_url"),
                }
            )
    return specs


def compare_products(models: list[str]) -> list[dict[str, Any]]:
    comparison = []
    for model in models:
        product = get_product_by_model(model)
        if product is None:
            comparison.append(
                {
                    "model": model,
                    "status": "not available in the current database",
                    "voltage": "not available",
                    "power": "not available",
                    "current": "not available",
                    "dimensions": "not available",
                    "datasheet_url": "not available",
                    "product_url": "not available",
                }
            )
        else:
            row = {
                "model": product["model"],
                "status": "found",
                "family": product["family"],
                "category": product["category"],
                "voltage": product["voltage"],
                "power": product["power"],
                "current": product["current"],
                "weight": product["weight"],
                "dimensions": product["dimensions"],
                "datasheet_url": product["datasheet_url"],
                "product_url": product["product_url"],
            }
            comparison.append(row)
    return comparison


def filter_products(filters: dict[str, Any]) -> list[dict[str, Any]]:
    ds = load_database()
    results = []
    for product in ds.products:
        keep = True
        hay = _haystack(product)
        for key, value in filters.items():
            if value in (None, "", False):
                continue
            value_text = _text(value)
            if key in {"has_datasheet", "datasheet"}:
                if bool(value) and not product.get("datasheet_url"):
                    keep = False
                    break
            elif key == "missing_field":
                if product.get(value_text) not in (None, ""):
                    keep = False
                    break
            elif key in product:
                if value_text not in _text(product.get(key)):
                    keep = False
                    break
            elif value_text not in hay:
                keep = False
                break
        if keep:
            results.append(_product_public_row(product))
    return results


def find_missing_fields(field_name: str | None = None) -> dict[str, Any]:
    ds = load_database()
    fields = [
        "brand",
        "product_family",
        "series",
        "model",
        "product_category",
        "light_type",
        "color",
        "wavelength_nm",
        "voltage_v",
        "power_w",
        "current_a",
        "dimensions_mm_json",
        "datasheet_url",
        "product_url",
    ]
    if field_name:
        fields = [field_name]
    summary = []
    examples: dict[str, list[str]] = {}
    for field in fields:
        missing = []
        for product in ds.products:
            value = product.get(field)
            if value is None or _clean(value) == "" or _clean(value).lower() in {"not available", "none"}:
                missing.append(product.get("model") or "")
        summary.append({"field": field, "missing_count": len(missing), "total": len(ds.products)})
        examples[field] = missing[:50]
    summary.sort(key=lambda row: row["missing_count"], reverse=True)
    return {"summary": summary, "examples": examples}


def get_product_sources(model: str) -> list[dict[str, Any]]:
    ds = load_database()
    product = _raw_product_by_model(model)
    if product is None:
        return []
    target = _norm(product.get("model"))
    sources = []
    if product.get("product_url") or product.get("source_url"):
        sources.append({"type": "product_url", "title": product.get("model"), "url": product.get("product_url") or product.get("source_url")})
    if product.get("datasheet_url"):
        sources.append({"type": "datasheet", "title": product.get("model"), "url": product.get("datasheet_url")})
    for asset in ds.assets:
        spec_model = asset.get("model_normalized") or _norm(asset.get("model"))
        if spec_model == target and asset.get("url"):
            sources.append({"type": asset.get("asset_type") or "asset", "title": asset.get("title") or asset.get("asset_type"), "url": asset.get("url")})
    unique = []
    seen = set()
    for source in sources:
        url = source.get("url")
        if url and url not in seen:
            seen.add(url)
            unique.append(source)
    return unique[:20]


def normalize_specs(raw_specs: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_specs, dict):
        iterable = [{"spec_name": k, "raw_value": v} for k, v in raw_specs.items()]
    else:
        iterable = raw_specs
    normalized: dict[str, Any] = {}
    dimensions: dict[str, Any] = {}
    for spec in iterable:
        name = _clean(spec.get("spec_name"))
        value = _clean(spec.get("raw_value"))
        lname = name.lower()
        if not value:
            continue
        if "voltage" in lname:
            volts = re.findall(r"\d+(?:\.\d+)?\s*V", value, flags=re.I)
            watts = re.findall(r"\d+(?:\.\d+)?\s*W", value, flags=re.I)
            if volts:
                normalized["voltage_v"] = " / ".join(dict.fromkeys(volts))
            if watts:
                normalized["power_w"] = " / ".join(dict.fromkeys(watts))
        elif "current" in lname:
            normalized["current_a"] = value
        elif "weight" in lname:
            normalized["weight_g"] = value
        elif "colour" in lname or "color" in lname or lname in {"ir", "uv", "rgbw"}:
            normalized["color"] = value
        elif "(mm)" in lname or "ø" in name:
            dimensions[name] = value
        elif "datasheet" in lname:
            normalized["datasheet_label"] = value
    if dimensions:
        normalized["dimensions_mm"] = dimensions
    return normalized


def _extract_models_from_question(question: str) -> list[str]:
    ds = load_database()
    compact = _norm(question)
    found = []
    for product in sorted(ds.products, key=lambda p: len(str(p.get("model") or "")), reverse=True):
        model = str(product.get("model") or "")
        if model and len(_norm(model)) >= 4 and _norm(model) in compact:
            found.append(model)
    if found:
        return list(dict.fromkeys(found))
    stop = {
        "WHAT", "WHICH", "WHERE", "WHEN", "HAVE", "HAS", "WITH", "COMPARE",
        "PRODUCTS", "PRODUCT", "MODEL", "MODELS", "TMS", "LITE", "FIND",
        "THREE", "SAMPLE", "PARAMETERS", "DATASHEET", "VOLTAGE", "POWER",
    }
    candidates = [
        token
        for token in re.findall(r"\b[A-Z0-9][A-Z0-9-]{2,}\b", question.upper())
        if token not in stop
        and not re.fullmatch(r"\d+(?:V|W|MA|MM|NM|G)", token)
        and ("-" in token or any(ch.isdigit() for ch in token))
    ]
    return list(dict.fromkeys(candidates))


def _response(
    answer: str,
    matched_products: list[dict[str, Any]] | None = None,
    spec_table: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    missing_or_uncertain: list[str] | None = None,
    confidence: str = "medium",
    mode: str = "local",
) -> dict[str, Any]:
    return {
        "answer": answer,
        "matched_products": matched_products or [],
        "spec_table": spec_table or [],
        "sources": sources or [],
        "missing_or_uncertain": missing_or_uncertain or [],
        "confidence": confidence,
        "mode": mode,
    }


def _apply_openai_polish(question: str, local_result: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return local_result
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        context = {
            "local_answer": local_result["answer"],
            "matched_products": local_result["matched_products"][:8],
            "spec_table": local_result["spec_table"][:12],
            "sources": local_result["sources"][:12],
            "missing_or_uncertain": local_result["missing_or_uncertain"],
        }
        prompt = (
            "Rewrite the local answer for a machine-vision product QA MVP. "
            "Do not invent product models, specs, URLs, or claims. "
            "If evidence is missing, say it is not available in the current database.\n\n"
            f"Question: {question}\n"
            f"Evidence JSON: {json.dumps(context, ensure_ascii=False)}"
        )
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        text = completion.choices[0].message.content
        if text:
            local_result["answer"] = text
            local_result["mode"] = "openai"
        return local_result
    except Exception as exc:
        local_result["missing_or_uncertain"].append(f"OpenAI polishing failed; local fallback used: {exc}")
        local_result["mode"] = "local"
        return local_result


def answer_question(question: str) -> dict[str, Any]:
    q = _text(question)
    if not q:
        return _response("Please enter a question.", confidence="low")

    if any(brand in q for brand in ["basler", "ccs", "opt ", "smart vision lights", "cognex"]) and "tms" not in q:
        return _response(
            "The current database only covers TMS Lite. Products from the requested brand are not available in the current database.",
            [],
            [],
            [],
            ["Only TMS Lite records are loaded in this MVP."],
            "high",
        )

    models = _extract_models_from_question(question)

    unsupported_business_fields = ["price", "pricing", "cost", "lead time", "stock", "inventory", "availability", "warranty"]
    if any(term in q for term in unsupported_business_fields):
        products = [get_product_by_model(model) for model in models]
        products = [product for product in products if product]
        sources = []
        for product in products:
            sources.extend(get_product_sources(product["model"])[:3])
        return _response(
            "Pricing, stock, lead time, warranty, and commercial availability are not available in the current database.",
            products,
            [],
            sources,
            ["The database currently contains scraped product/spec/source records only, not commercial terms."],
            "high" if products else "medium",
        )

    if "compare" in q or "比较" in q or "对比" in q:
        if not models or "sample" in q:
            sample_hits = search_products("24V backlight ring coaxial", limit=3)
            models = [hit["model"] for hit in sample_hits]
        table = compare_products(models)
        sources = []
        for model in models:
            sources.extend(get_product_sources(model)[:3])
        found_count = sum(1 for row in table if row.get("status") == "found")
        answer = f"Compared {len(models)} model(s). {found_count} were found in the current database; missing models are explicitly marked."
        return _apply_openai_polish(question, _response(answer, table, table, sources, confidence="high" if found_count else "low"))

    if any(term in q for term in ["missing", "缺失", "没有 datasheet", "missing datasheet", "字段", "no voltage", "没有电压"]):
        if "datasheet" in q:
            products = [p for p in load_database().products if not p.get("datasheet_url")]
            rows = [_product_public_row(p) for p in products[:50]]
            answer = f"{len(products)} product records currently have no datasheet URL recorded."
            return _response(
                answer,
                rows,
                [{"model": row["model"], "missing_field": "datasheet_url"} for row in rows[:50]],
                [],
                ["Absence of a datasheet URL may mean the crawler did not resolve an external link, not necessarily that no datasheet exists."],
                "high",
            )
        if "voltage" in q or "电压" in q:
            missing = find_missing_fields("voltage_v")
            examples = missing["examples"].get("voltage_v", [])
            rows = []
            for model in examples:
                product = get_product_by_model(model)
                if product:
                    rows.append(product)
            answer = f"{missing['summary'][0]['missing_count']} product records currently have no voltage parameter recorded."
            return _response(answer, rows[:50], missing["summary"], [], [], "high")
        missing = find_missing_fields()
        answer = "Missing-field summary generated from the current database. Fields with the largest missing counts should be fixed first."
        return _response(answer, [], missing["summary"], [], [], "high")

    if models:
        model = models[0]
        product = get_product_by_model(model)
        if product is None:
            return _response(
                f"{model} is not available in the current database. I will not infer or invent this model.",
                [],
                [],
                [],
                [f"Model not found: {model}"],
                "high",
            )
        specs = get_product_specs(product["model"])
        sources = get_product_sources(product["model"])
        if "datasheet" in q:
            answer = (
                f"{product['model']} has a datasheet URL recorded: {product['datasheet_url']}"
                if product.get("datasheet_url") != "not available"
                else f"{product['model']} is in the database, but no datasheet URL is recorded."
            )
        else:
            answer = f"{product['model']} is in the current database. Key known fields: voltage {product['voltage']}, power {product['power']}, current {product['current']}, dimensions {product['dimensions']}."
        return _apply_openai_polish(question, _response(answer, [product], specs[:30], sources, [], "high"))

    if any(term in q for term in ["which", "find", "有哪些", "哪些", "what tms", "24v", "red", "红", "coaxial", "ring", "datasheet"]):
        hits = search_products(question, limit=20)
        if "datasheet" in q:
            hits = [hit for hit in hits if hit.get("datasheet_url") != "not available"]
        answer = (
            f"Found {len(hits)} matching product records in the current database."
            if hits
            else "No matching products are available in the current database."
        )
        sources = [{"type": "product_url", "title": hit["model"], "url": hit["product_url"]} for hit in hits[:10] if hit.get("product_url") != "not available"]
        return _response(answer, hits, [], sources, [], "medium" if hits else "low")

    selected_intent = None
    for intent, payload in APPLICATION_INTENTS.items():
        if any(keyword in q for keyword in payload["keywords"]):
            selected_intent = intent
            break
    if selected_intent:
        payload = APPLICATION_INTENTS[selected_intent]
        hits = search_products(payload["query"], limit=10)
        answer = (
            f"Initial lighting-selection logic: {payload['logic']} "
            f"The products below are candidates retrieved from the current TMS Lite database only."
        )
        missing = [
            "Selection recommendations are preliminary and should be validated with samples, geometry, working distance, camera/lens setup, and actual part images.",
        ]
        if not hits:
            missing.append("current database evidence is limited")
        sources = [{"type": "product_url", "title": hit["model"], "url": hit["product_url"]} for hit in hits[:10] if hit.get("product_url") != "not available"]
        return _apply_openai_polish(question, _response(answer, hits, [], sources, missing, "medium" if hits else "low"))

    hits = search_products(question, limit=10)
    answer = (
        f"Found {len(hits)} potentially relevant product records. Results are based only on the current database."
        if hits
        else "I could not find relevant records in the current database."
    )
    sources = [{"type": "product_url", "title": hit["model"], "url": hit["product_url"]} for hit in hits if hit.get("product_url") != "not available"]
    return _response(answer, hits, [], sources[:10], ["Use more product terms, voltage, color, or application details for better results."] if not hits else [], "medium" if hits else "low")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ask the Ronisens Product QA engine.")
    parser.add_argument("question", nargs="+")
    args = parser.parse_args()
    print(json.dumps(answer_question(" ".join(args.question)), ensure_ascii=False, indent=2))
