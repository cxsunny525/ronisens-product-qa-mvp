from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - app can still run without overrides.
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "data" / "tms_lite_full.db"
EXPORT_DIR = ROOT / "data" / "exports"
MANUAL_OVERRIDES_PATH = ROOT / "manual_overrides.yaml"
NO_EXACT_ZH = "当前数据库未记录明确匹配结果。"
NO_EXACT_EN = "No exact match found in the current database."
NO_SUPPORTED_ANSWER_ZH = "目前系统尚未有这个答案。当前 MVP 只会在能够明确理解问题，并且当前 TMS Lite 数据库或已配置规则中有直接依据时回答；为避免误导，本问题暂不做推测。"
NO_SUPPORTED_ANSWER_EN = "The system does not have this answer yet. This MVP only answers when the question is clearly understood and directly supported by the current TMS Lite database or configured rules; to avoid misleading guidance, it will not infer an answer."


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
        "keywords": ["metal", "\u91d1\u5c5e", "scratch", "\u5212\u75d5", "\u522e\u75d5", "\u6697\u573a", "dark-field", "dark field", "low angle", "\u4f4e\u89d2\u5ea6"],
        "logic": "Metal scratch inspection often starts with low-angle or dark-field illumination because shallow grazing light can make surface defects stand out. Coaxial light may help on flat reflective surfaces.",
        "query": "low angle dark field metal scratch DLQ DLA coaxial",
    },
    "transparent_edge": {
        "keywords": ["transparent", "\u900f\u660e", "bottle", "\u74f6", "edge", "\u8fb9\u7f18", "backlight", "\u80cc\u5149"],
        "logic": "Transparent bottle edge inspection usually starts with backlight for silhouette/edge contrast. Coaxial or dome illumination can be explored if the inspection target is print or surface reflection.",
        "query": "backlight transparent edge BHL BHH BHS BIDS",
    },
    "pcb": {
        "keywords": ["pcb", "\u7535\u8def\u677f", "solder", "\u710a\u70b9", "component", "\u5143\u4ef6"],
        "logic": "PCB inspection may use ring/bar lighting for general features, coaxial lighting for reflective pads, and dome/diffuse lighting to reduce glare. UV can be useful for fluorescence targets.",
        "query": "ring coaxial dome bar RGBW UV PCB",
    },
    "backlight": {
        "keywords": ["backlight", "\u80cc\u5149", "silhouette", "\u8f6e\u5ed3", "\u5c3a\u5bf8", "\u5916\u5f62"],
        "logic": "Backlight is suitable for silhouette, edge, hole, and dimension checks where the part blocks light and creates high contrast.",
        "query": "backlight BHL BHH BHS BIDS",
    },
}


APPLICATION_LOGIC_ZH = {
    "metal_scratch": "\u91d1\u5c5e\u5212\u75d5\u68c0\u6d4b\u901a\u5e38\u5148\u8003\u8651\u4f4e\u89d2\u5ea6\u6216\u6697\u573a\u7167\u660e\uff0c\u56e0\u4e3a\u63a0\u5c04\u5149\u66f4\u5bb9\u6613\u628a\u8868\u9762\u5212\u75d5\u51f8\u663e\u51fa\u6765\uff1b\u5e73\u6574\u53cd\u5149\u8868\u9762\u4e5f\u53ef\u4ee5\u8bc4\u4f30\u540c\u8f74\u5149\u3002",
    "transparent_edge": "\u900f\u660e\u74f6\u6216\u900f\u660e\u4ef6\u8fb9\u7f18\u68c0\u6d4b\u901a\u5e38\u5148\u8003\u8651\u80cc\u5149\uff0c\u7528\u8f6e\u5ed3\u53cd\u5dee\u628a\u8fb9\u7f18\u62c9\u51fa\u6765\uff1b\u5982\u679c\u76ee\u6807\u662f\u5370\u5237\u6216\u8868\u9762\u53cd\u5c04\uff0c\u518d\u8bc4\u4f30\u540c\u8f74\u5149\u6216\u7a79\u9876\u6f2b\u5c04\u5149\u3002",
    "pcb": "PCB \u68c0\u6d4b\u53ef\u4ee5\u5148\u6309\u76ee\u6807\u62c6\u5206\uff1a\u4e00\u822c\u5b9a\u4f4d\u53ef\u770b\u73af\u5f62\u5149\u6216\u6761\u5f62\u5149\uff0c\u710a\u76d8\u7b49\u53cd\u5149\u533a\u57df\u53ef\u770b\u540c\u8f74\u5149\uff0c\u5f3a\u53cd\u5149\u6216\u9634\u5f71\u95ee\u9898\u53ef\u770b\u7a79\u9876/\u6f2b\u5c04\u5149\uff0c\u8367\u5149\u76ee\u6807\u518d\u8003\u8651 UV\u3002",
    "backlight": "\u80cc\u5149\u9002\u5408\u8f6e\u5ed3\u3001\u8fb9\u7f18\u3001\u5b54\u4f4d\u548c\u5c3a\u5bf8\u68c0\u6d4b\uff0c\u6838\u5fc3\u903b\u8f91\u662f\u8ba9\u88ab\u6d4b\u7269\u906e\u6321\u5149\u5f62\u6210\u9ad8\u5bf9\u6bd4\u526a\u5f71\u3002",
}


LIGHT_TYPE_TERMS = {
    "ring": ["ring", "\u73af\u5f62", "lbr", "dlr", "hpd"],
    "bar": ["bar", "\u6761\u5f62", "lsw", "lla", "hlbs", "hlbq"],
    "backlight": ["backlight", "\u80cc\u5149", "bhl", "bhh", "bhs", "bids", "hbl"],
    "coaxial": ["coaxial", "co-axial", "\u540c\u8f74", "cas", "mcax"],
    "dome": ["dome", "\u7a79\u9876", "diffused", "\u6f2b\u5c04", "fdd", "hbf"],
    "low_angle": ["low angle", "\u4f4e\u89d2\u5ea6", "dark field", "\u6697\u573a", "dlq", "dla"],
    "line": ["line", "\u7ebf\u626b", "\u7ebf\u5149", "line scan"],
    "spot": ["spot", "\u70b9\u5149", "hbf", "fib"],
    "uv": ["uv", "\u7d2b\u5916", "uv365", "uv395"],
    "ir": ["ir", "\u7ea2\u5916", "infrared", "ir850", "ir940"],
    "rgb": ["rgb"],
    "rgbw": ["rgbw"],
}

CHINESE_QUERY_EXPANSIONS = [
    (["\u6761\u5f62", "\u6761\u72b6", "\u6761\u706f", "\u6761\u5149", "\u7ebf\u6027\u5149", "\u7ebf\u5f62\u5149"], "bar light HLBS HLBQ LSW LLA"),
    (["\u73af\u5f62", "\u73af\u72b6", "\u73af\u706f", "\u5706\u5f62"], "ring light LBR DLR HPD"),
    (["\u80cc\u5149", "\u80cc\u5149\u6e90"], "backlight BHL BHH BHS BIDS HBL"),
    (["\u540c\u8f74"], "coaxial CAS MCAX"),
    (["\u7a79\u9876", "\u6f2b\u5c04", "\u65e0\u5f71"], "dome diffuse FDD HBF"),
    (["\u4f4e\u89d2\u5ea6", "\u6697\u573a"], "low angle dark field DLQ DLA"),
    (["\u7ebf\u626b", "\u7ebf\u5149\u6e90"], "line scan line light"),
    (["\u70b9\u5149", "\u70b9\u5149\u6e90"], "spot light"),
    (["\u7ea2\u5149", "\u7ea2\u8272"], "red"),
    (["\u84dd\u5149", "\u84dd\u8272"], "blue"),
    (["\u7eff\u5149", "\u7eff\u8272"], "green"),
    (["\u767d\u5149", "\u767d\u8272"], "white"),
    (["\u7d2b\u5916", "UV"], "UV ultraviolet"),
    (["\u7ea2\u5916", "IR"], "IR infrared"),
    (["\u6570\u636e\u8868", "\u89c4\u683c\u4e66", "\u8d44\u6599", "\u76ee\u5f55", "PDF"], "datasheet catalog pdf"),
    (["\u7535\u538b"], "voltage"),
    (["\u529f\u7387"], "power watt"),
    (["\u7535\u6d41"], "current"),
    (["\u5c3a\u5bf8", "\u5916\u5f84", "\u5185\u5f84", "\u957f\u5ea6", "\u5bbd\u5ea6", "\u9ad8\u5ea6"], "dimension diameter length width height mm"),
]

DATASHEET_TERMS = ["datasheet", "\u6570\u636e\u8868", "\u89c4\u683c\u4e66", "\u8d44\u6599", "\u76ee\u5f55", "pdf", "catalog", "catalogue"]
QUERY_TERMS = [
    "which",
    "find",
    "what tms",
    "\u6709\u54ea\u4e9b",
    "\u54ea\u4e9b",
    "\u6709\u54ea",
    "\u6709\u6ca1\u6709",
    "\u67e5\u8be2",
    "\u5bfb\u627e",
    "\u627e",
    "\u5217\u51fa",
    "\u4ea7\u54c1",
    "\u5149\u6e90",
    "\u578b\u53f7",
    "\u53c2\u6570",
    "24v",
    "red",
    "\u7ea2",
    "coaxial",
    "ring",
    "bar",
    "backlight",
    "datasheet",
]
APPLICATION_CUE_TERMS = [
    "inspection",
    "detect",
    "selection",
    "suitable",
    "useful",
    "consider",
    "recommend",
    "\u68c0\u6d4b",
    "\u9009\u578b",
    "\u9002\u5408",
    "\u5e94\u8be5",
    "\u63a8\u8350",
    "\u5e94\u7528",
    "\u770b\u4ec0\u4e48\u5149\u6e90",
]
UNSUPPORTED_BUSINESS_FIELDS = [
    "price",
    "pricing",
    "cost",
    "lead time",
    "stock",
    "inventory",
    "availability",
    "warranty",
    "\u4ef7\u683c",
    "\u591a\u5c11\u94b1",
    "\u62a5\u4ef7",
    "\u5e93\u5b58",
    "\u73b0\u8d27",
    "\u4ea4\u671f",
    "\u8d27\u671f",
    "\u4fdd\u4fee",
    "discontinued",
    "obsolete",
    "lifecycle",
    "eol",
    "\u505c\u4ea7",
    "\u751f\u547d\u5468\u671f",
]


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
_MANUAL_OVERRIDES: dict[str, Any] | None = None


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _text(value: Any) -> str:
    return _clean(value).lower()


def _has_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def _wants_datasheet(question: str) -> bool:
    return _contains_any(question, DATASHEET_TERMS)


def _expanded_query(query: str) -> str:
    expanded = [query]
    for triggers, addition in CHINESE_QUERY_EXPANSIONS:
        if any(trigger.lower() in query.lower() for trigger in triggers):
            expanded.append(addition)
    return " ".join(dict.fromkeys(expanded))


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


PUBLIC_TO_CANONICAL_FIELD = {
    "brand": "brand",
    "family": "product_family",
    "series": "series",
    "category": "product_category",
    "light_type": "light_type",
    "color": "color",
    "voltage": "voltage_v",
    "power": "power_w",
    "current": "current_a",
    "dimensions": "dimensions_mm_json",
    "product_url": "product_url",
    "datasheet_url": "datasheet_url",
    "search_text": "search_text",
}


def load_manual_overrides(force: bool = False) -> dict[str, Any]:
    """Read human-reviewed corrections without modifying the source database."""
    global _MANUAL_OVERRIDES
    if _MANUAL_OVERRIDES is not None and not force:
        return _MANUAL_OVERRIDES
    if yaml is None or not MANUAL_OVERRIDES_PATH.exists():
        _MANUAL_OVERRIDES = {"products": {}}
        return _MANUAL_OVERRIDES
    try:
        with MANUAL_OVERRIDES_PATH.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except Exception:
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    loaded.setdefault("products", {})
    _MANUAL_OVERRIDES = loaded
    return _MANUAL_OVERRIDES


def _model_overrides(model: str | None) -> dict[str, Any]:
    products = load_manual_overrides().get("products", {})
    if not isinstance(products, dict):
        return {}
    target = _norm(model)
    for key, value in products.items():
        if _norm(key) == target and isinstance(value, dict):
            return value
    return {}


def _override_entry(model: str | None, canonical_field: str) -> dict[str, Any] | None:
    entry = _model_overrides(model).get(canonical_field)
    return entry if isinstance(entry, dict) and "value" in entry else None


def _field_value_with_source(product: dict[str, Any], public_field: str, raw_value: Any) -> tuple[Any, str, bool, str]:
    canonical_field = PUBLIC_TO_CANONICAL_FIELD.get(public_field, public_field)
    override = _override_entry(product.get("model"), canonical_field)
    if override is not None:
        verified = bool(override.get("verified"))
        source = "manual_verified" if verified else "manual_override"
        return override.get("value"), source, verified, str(override.get("note") or "")
    if raw_value in (None, ""):
        return "not available", "not_available", False, ""
    return raw_value, "scraped", False, ""


def _product_public_row(product: dict[str, Any]) -> dict[str, Any]:
    row = {
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
        "search_text": product.get("search_text") or "not available",
    }
    for public_field in PUBLIC_TO_CANONICAL_FIELD:
        raw_value = row.get(public_field)
        value, source, verified, note = _field_value_with_source(product, public_field, raw_value)
        row[public_field] = value if value not in (None, "") else "not available"
        row[f"{public_field}_source"] = source
        row[f"{public_field}_verified"] = verified
        if note:
            row[f"{public_field}_note"] = note
    row["data_source_summary"] = (
        "manual verified fields present"
        if any(row.get(f"{field}_source") == "manual_verified" for field in PUBLIC_TO_CANONICAL_FIELD)
        else "scraped"
    )
    return row


def _tokens(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9.+/-]+|[\u4e00-\u9fff]+", _expanded_query(query).lower())
    out: list[str] = []
    for word in words:
        if len(word) >= 2:
            out.append(word)
            out.append(word.replace("-", ""))
    return list(dict.fromkeys(out))


def _requested_light_types(query: str) -> list[str]:
    q = _text(_expanded_query(query))
    requested = []
    for light_type, terms in LIGHT_TYPE_TERMS.items():
        if any(term in q for term in terms):
            requested.append(light_type)
    return list(dict.fromkeys(requested))


def _select_application_intent(question: str) -> str | None:
    q = _text(_expanded_query(question))
    has_application_cue = _contains_any(q, APPLICATION_CUE_TERMS)
    for intent, payload in APPLICATION_INTENTS.items():
        if any(keyword in q for keyword in payload["keywords"]) and has_application_cue:
            return intent
    return None


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
    expanded_query = _expanded_query(query)
    q = _text(expanded_query)
    compact_q = _norm(query)
    hay = _haystack(product)
    model = _norm(product.get("model"))
    family = _text(product.get("product_family"))
    score = 0.0
    reasons: list[str] = []

    if model and len(model) >= 4 and model in compact_q:
        score += 100
        reasons.append("exact model match")

    for token in _tokens(expanded_query):
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
    if ("red" in q or "\u7ea2" in q) and "red" in hay:
        score += 8
        reasons.append("red light evidence")
    if ("coaxial" in q or "\u540c\u8f74" in q) and ("coaxial" in hay or "cas" in hay or "mcax" in hay):
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
        elif "(mm)" in lname or "\xf8" in name:
            dimensions[name] = value
        elif "datasheet" in lname:
            normalized["datasheet_label"] = value
    if dimensions:
        normalized["dimensions_mm"] = dimensions
    return normalized


def _extract_models_from_question(question: str) -> list[str]:
    ds = load_database()
    compact = str(question or "").upper()
    found = []
    for product in sorted(ds.products, key=lambda p: len(str(p.get("model") or "")), reverse=True):
        model = str(product.get("model") or "")
        normalized_model = _norm(model)
        if not model or len(normalized_model) < 4:
            continue
        for match in re.finditer(re.escape(normalized_model), compact):
            before = compact[match.start() - 1] if match.start() > 0 else ""
            after = compact[match.end()] if match.end() < len(compact) else ""
            if before and re.match(r"[A-Z0-9-]", before):
                continue
            if after and re.match(r"[A-Z0-9-]", after):
                continue
            found.append(model)
            break
    if found:
        unique = list(dict.fromkeys(found))
        return [
            model
            for model in unique
            if not any(model != other and _norm(model) in _norm(other) for other in unique)
        ]
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
    mode: str = "strict",
    evidence: list[dict[str, Any]] | None = None,
    match_reason: list[dict[str, Any]] | None = None,
    query_interpretation: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "matched_products": matched_products or [],
        "spec_table": spec_table or [],
        "sources": sources or [],
        "missing_or_uncertain": missing_or_uncertain or [],
        "confidence": confidence,
        "mode": mode,
        "evidence": evidence or [],
        "match_reason": match_reason or [],
        "query_interpretation": query_interpretation or {},
        "warnings": warnings or [],
    }


def _apply_openai_polish(question: str, local_result: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or os.getenv("RONISENS_ENABLE_OPENAI_POLISH", "").lower() not in {"1", "true", "yes"}:
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


def _sources_from_hits(hits: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    sources = []
    seen = set()
    for hit in hits:
        for key, source_type in [("product_url", "product_url"), ("datasheet_url", "datasheet")]:
            url = hit.get(key)
            if url and url != "not available" and url not in seen:
                seen.add(url)
                sources.append({"type": source_type, "title": hit.get("model"), "url": url})
            if len(sources) >= limit:
                return sources
    return sources


def _legacy_answer_question(question: str) -> dict[str, Any]:
    original_q = _text(question)
    q = _text(_expanded_query(question))
    is_zh = _has_chinese(question)
    if not original_q:
        return _response("\u8bf7\u8f93\u5165\u4e00\u4e2a\u95ee\u9898\u3002" if is_zh else "Please enter a question.", confidence="low")

    if any(brand in q for brand in ["basler", "ccs", "opt ", "keyence", "smart vision lights", "cognex", "\u57fa\u6069\u58eb"]) and "tms" not in q:
        return _response(
            "\u5f53\u524d\u6570\u636e\u5e93\u53ea\u8986\u76d6 TMS Lite\uff1b\u6240\u95ee\u54c1\u724c\u6682\u672a\u6536\u5f55\u3002" if is_zh else "The current database only covers TMS Lite. Products from the requested brand are not available in the current database.",
            [],
            [],
            [],
            ["\u5f53\u524d MVP \u53ea\u52a0\u8f7d\u4e86 TMS Lite \u8bb0\u5f55\u3002" if is_zh else "Only TMS Lite records are loaded in this MVP."],
            "high",
        )

    models = _extract_models_from_question(question)

    if any(term in q for term in UNSUPPORTED_BUSINESS_FIELDS):
        products = [get_product_by_model(model) for model in models]
        products = [product for product in products if product]
        sources = []
        for product in products:
            sources.extend(get_product_sources(product["model"])[:3])
        return _response(
            "\u5f53\u524d\u6570\u636e\u5e93\u6ca1\u6709\u4ef7\u683c\u3001\u5e93\u5b58\u3001\u4ea4\u671f\u3001\u4fdd\u4fee\u6216\u5546\u52a1\u53ef\u5f97\u6027\u8bb0\u5f55\uff1b\u6211\u4e0d\u4f1a\u63a8\u6d4b\u8fd9\u4e9b\u4fe1\u606f\u3002" if is_zh else "Pricing, stock, lead time, warranty, and commercial availability are not available in the current database.",
            products,
            [],
            sources,
            ["\u6570\u636e\u5e93\u76ee\u524d\u53ea\u5305\u542b\u6293\u53d6\u5230\u7684\u4ea7\u54c1\u3001\u53c2\u6570\u548c\u6765\u6e90\u8bb0\u5f55\u3002" if is_zh else "The database currently contains scraped product/spec/source records only, not commercial terms."],
            "high" if products else "medium",
        )

    if "compare" in q or "\u6bd4\u8f83" in q or "\u5bf9\u6bd4" in q:
        if not models or "sample" in q or "\u793a\u4f8b" in q:
            sample_hits = search_products("24V backlight ring coaxial", limit=3)
            models = [hit["model"] for hit in sample_hits]
        table = compare_products(models)
        sources = []
        for model in models:
            sources.extend(get_product_sources(model)[:3])
        found_count = sum(1 for row in table if row.get("status") == "found")
        answer = (
            f"\u5df2\u5bf9\u6bd4 {len(models)} \u4e2a\u578b\u53f7\uff0c\u5176\u4e2d {found_count} \u4e2a\u5728\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709\u8bb0\u5f55\uff1b\u672a\u6536\u5f55\u578b\u53f7\u4f1a\u660e\u786e\u6807\u4e3a not available\u3002"
            if is_zh
            else f"Compared {len(models)} model(s). {found_count} were found in the current database; missing models are explicitly marked."
        )
        return _apply_openai_polish(question, _response(answer, table, table, sources, confidence="high" if found_count else "low"))

    quality_question = (
        any(term in q for term in ["missing", "\u7f3a\u5931", "\u7f3a\u5c11", "\u5b57\u6bb5", "no voltage", "\u6ca1\u6709\u7535\u538b", "\u672a\u8bb0\u5f55"])
        or ((not models) and "\u6ca1\u6709" in question and (_wants_datasheet(question) or "\u7535\u538b" in question))
    )
    if quality_question:
        if _wants_datasheet(question):
            products = [p for p in load_database().products if not p.get("datasheet_url")]
            rows = [_product_public_row(p) for p in products[:50]]
            answer = (
                f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 {len(products)} \u6761\u4ea7\u54c1\u8bb0\u5f55\u6ca1\u6709 datasheet_url\u3002"
                if is_zh
                else f"{len(products)} product records currently have no datasheet URL recorded."
            )
            return _response(
                answer,
                rows,
                [{"model": row["model"], "missing_field": "datasheet_url"} for row in rows[:50]],
                [],
                ["\u6ca1\u6709 datasheet_url \u53ef\u80fd\u8868\u793a\u722c\u866b\u6ca1\u6709\u89e3\u6790\u5230\u5916\u90e8\u94fe\u63a5\uff0c\u4e0d\u4e00\u5b9a\u4ee3\u8868\u5382\u5bb6\u6ca1\u6709\u89c4\u683c\u4e66\u3002" if is_zh else "Absence of a datasheet URL may mean the crawler did not resolve an external link, not necessarily that no datasheet exists."],
                "high",
            )
        if "voltage" in q or "\u7535\u538b" in q:
            missing = find_missing_fields("voltage_v")
            examples = missing["examples"].get("voltage_v", [])
            rows = []
            for model in examples:
                product = get_product_by_model(model)
                if product:
                    rows.append(product)
            answer = (
                f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 {missing['summary'][0]['missing_count']} \u6761\u4ea7\u54c1\u8bb0\u5f55\u6ca1\u6709\u7535\u538b\u53c2\u6570\u3002"
                if is_zh
                else f"{missing['summary'][0]['missing_count']} product records currently have no voltage parameter recorded."
            )
            return _response(answer, rows[:50], missing["summary"], [], [], "high")
        missing = find_missing_fields()
        answer = (
            "\u5df2\u6839\u636e\u5f53\u524d\u6570\u636e\u5e93\u751f\u6210\u7f3a\u5931\u5b57\u6bb5\u7edf\u8ba1\uff0c\u7f3a\u5931\u6700\u591a\u7684\u5b57\u6bb5\u5e94\u4f18\u5148\u6e05\u6d17\u3002"
            if is_zh
            else "Missing-field summary generated from the current database. Fields with the largest missing counts should be fixed first."
        )
        return _response(answer, [], missing["summary"], [], [], "high")

    if models:
        model = models[0]
        product = get_product_by_model(model)
        if product is None:
            return _response(
                f"{model} \u5f53\u524d\u6570\u636e\u5e93\u672a\u8bb0\u5f55\uff1b\u6211\u4e0d\u4f1a\u63a8\u6d4b\u6216\u7f16\u9020\u8fd9\u4e2a\u578b\u53f7\u3002" if is_zh else f"{model} is not available in the current database. I will not infer or invent this model.",
                [],
                [],
                [],
                [f"\u672a\u627e\u5230\u578b\u53f7: {model}" if is_zh else f"Model not found: {model}"],
                "high",
            )
        specs = get_product_specs(product["model"])
        sources = get_product_sources(product["model"])
        if _wants_datasheet(question):
            answer = (
                f"{product['model']} \u5728\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 datasheet URL: {product['datasheet_url']}"
                if is_zh and product.get("datasheet_url") != "not available"
                else f"{product['model']} \u5f53\u524d\u6570\u636e\u5e93\u6709\u8bb0\u5f55\uff0c\u4f46\u6ca1\u6709 datasheet URL\u3002"
                if is_zh
                else f"{product['model']} has a datasheet URL recorded: {product['datasheet_url']}"
                if product.get("datasheet_url") != "not available"
                else f"{product['model']} is in the database, but no datasheet URL is recorded."
            )
        else:
            answer = (
                f"{product['model']} \u5f53\u524d\u6570\u636e\u5e93\u6709\u8bb0\u5f55\u3002\u5173\u952e\u5b57\u6bb5\uff1a\u7535\u538b {product['voltage']}\uff0c\u529f\u7387 {product['power']}\uff0c\u7535\u6d41 {product['current']}\uff0c\u5c3a\u5bf8 {product['dimensions']}\u3002"
                if is_zh
                else f"{product['model']} is in the current database. Key known fields: voltage {product['voltage']}, power {product['power']}, current {product['current']}, dimensions {product['dimensions']}."
            )
        return _apply_openai_polish(question, _response(answer, [product], specs[:30], sources, [], "high"))

    selected_intent = _select_application_intent(question)
    if selected_intent:
        payload = APPLICATION_INTENTS[selected_intent]
        hits = search_products(payload["query"], limit=10)
        answer = (
            f"\u521d\u6b65\u9009\u578b\u903b\u8f91\uff1a{APPLICATION_LOGIC_ZH.get(selected_intent, payload['logic'])} \u4e0b\u65b9\u5019\u9009\u4ea7\u54c1\u53ea\u6765\u81ea\u5f53\u524d TMS Lite \u6570\u636e\u5e93\u3002"
            if is_zh
            else f"Initial lighting-selection logic: {payload['logic']} The products below are candidates retrieved from the current TMS Lite database only."
        )
        missing = [
            "\u9009\u578b\u5efa\u8bae\u53ea\u662f\u521d\u6b65\u5efa\u8bae\uff0c\u9700\u8981\u7ed3\u5408\u6837\u54c1\u3001\u51e0\u4f55\u7ed3\u6784\u3001\u5de5\u4f5c\u8ddd\u79bb\u3001\u76f8\u673a/\u955c\u5934\u548c\u5b9e\u9645\u56fe\u50cf\u9a8c\u8bc1\u3002"
            if is_zh
            else "Selection recommendations are preliminary and should be validated with samples, geometry, working distance, camera/lens setup, and actual part images.",
        ]
        if not hits:
            missing.append("current database evidence is limited")
        return _apply_openai_polish(question, _response(answer, hits, [], _sources_from_hits(hits), missing, "medium" if hits else "low"))

    requested_types = _requested_light_types(question)
    if _contains_any(q, QUERY_TERMS) or requested_types or _wants_datasheet(question):
        hits = search_products(question, limit=40)
        if requested_types:
            strict_hits = [hit for hit in hits if hit.get("light_type") in requested_types]
            if strict_hits:
                hits = strict_hits
        if _wants_datasheet(question):
            hits = [hit for hit in hits if hit.get("datasheet_url") != "not available"]
        hits = hits[:20]
        type_note = f"\uff08\u5339\u914d\u5149\u6e90\u7c7b\u578b\uff1a{', '.join(requested_types)}\uff09" if is_zh and requested_types else ""
        answer = (
            f"\u5f53\u524d\u6570\u636e\u5e93\u627e\u5230 {len(hits)} \u6761\u5339\u914d\u4ea7\u54c1\u8bb0\u5f55{type_note}\u3002\u7ed3\u679c\u57fa\u4e8e\u6570\u636e\u5e93\u5b57\u6bb5\u3001\u7cfb\u5217\u540d\u3001\u578b\u53f7\u548c\u6765\u6e90\u6587\u672c\u6392\u5e8f\uff1b\u8bf7\u7ee7\u7eed\u6838\u5bf9\u8868\u683c\u4e2d\u7684 light_type\u3001family \u548c\u6765\u6e90\u94fe\u63a5\u3002"
            if is_zh and hits
            else "\u5f53\u524d\u6570\u636e\u5e93\u672a\u627e\u5230\u5339\u914d\u4ea7\u54c1\u8bb0\u5f55\u3002"
            if is_zh
            else f"Found {len(hits)} matching product records in the current database."
            if hits
            else "No matching products are available in the current database."
        )
        return _response(answer, hits, [], _sources_from_hits(hits), [], "medium" if hits else "low")

    hits = search_products(question, limit=10)
    answer = (
        f"\u5f53\u524d\u6570\u636e\u5e93\u627e\u5230 {len(hits)} \u6761\u53ef\u80fd\u76f8\u5173\u7684\u4ea7\u54c1\u8bb0\u5f55\uff0c\u7ed3\u679c\u53ea\u57fa\u4e8e\u5f53\u524d\u6570\u636e\u5e93\u3002"
        if is_zh and hits
        else "\u5f53\u524d\u6570\u636e\u5e93\u672a\u627e\u5230\u76f8\u5173\u8bb0\u5f55\u3002\u53ef\u4ee5\u8865\u5145\u4ea7\u54c1\u7c7b\u578b\u3001\u7535\u538b\u3001\u989c\u8272\u6216\u5e94\u7528\u573a\u666f\u518d\u8bd5\u3002"
        if is_zh
        else f"Found {len(hits)} potentially relevant product records. Results are based only on the current database."
        if hits
        else "I could not find relevant records in the current database."
    )
    missing = [] if hits else ["\u53ef\u4ee5\u8865\u5145\u4ea7\u54c1\u7c7b\u578b\u3001\u7535\u538b\u3001\u989c\u8272\u6216\u5e94\u7528\u573a\u666f\u3002" if is_zh else "Use more product terms, voltage, color, or application details for better results."]
    return _response(answer, hits, [], _sources_from_hits(hits), missing, "medium" if hits else "low")


def _is_zh_question(question: str) -> bool:
    return _has_chinese(question)


def _confidence_floor_for_no_result(question: str) -> str:
    return "high" if _extract_models_from_question(question) else "medium"


def _supported_application_intent(question: str) -> str | None:
    q = _text(_expanded_query(question))
    if not _contains_any(q, APPLICATION_CUE_TERMS):
        return None
    has_scratch = _contains_any(q, ["scratch", "划痕", "刮痕", "擦伤"])
    has_metal = _contains_any(q, ["metal", "金属", "铝", "钢", "不锈钢", "铜", "铁"])
    if has_scratch and has_metal:
        return "metal_scratch"
    if _contains_any(q, ["transparent", "透明", "bottle", "瓶"]) and _contains_any(q, ["edge", "边缘", "轮廓", "backlight", "背光"]):
        return "transparent_edge"
    if _contains_any(q, ["pcb", "电路板", "solder", "焊点", "component", "元件"]):
        return "pcb"
    if _contains_any(q, ["backlight", "背光", "silhouette", "轮廓", "尺寸", "外形"]):
        return "backlight"
    return None


def _looks_like_application_question(question: str) -> bool:
    q = _text(question)
    return _contains_any(q, APPLICATION_CUE_TERMS)


def _unsupported_application_question(question: str) -> bool:
    if not _looks_like_application_question(question):
        return False
    if _supported_application_intent(question):
        return False
    return True


def _query_interpretation(question: str, mode: str) -> dict[str, Any]:
    return {
        "language": "zh" if _is_zh_question(question) else "en",
        "mode": mode,
        "detected_models": _extract_models_from_question(question),
        "requested_light_types": _requested_light_types(question),
        "requested_datasheet": _wants_datasheet(question),
        "application_intent": _supported_application_intent(question),
        "application_question": _looks_like_application_question(question),
        "exact_required": mode == "strict",
    }


def _no_exact_response(question: str, mode: str = "strict", reason: str | None = None) -> dict[str, Any]:
    is_zh = _is_zh_question(question)
    warning = reason or ("当前数据库没有明确证据支持该问题。" if is_zh else "The current database has no explicit evidence for this question.")
    answer = NO_EXACT_ZH if is_zh else NO_EXACT_EN
    if warning:
        answer = f"{answer} {warning}"
    return _response(
        answer,
        [],
        [],
        [],
        [warning],
        _confidence_floor_for_no_result(question),
        mode,
        [],
        [],
        _query_interpretation(question, mode),
        [warning],
    )


def _no_supported_answer(question: str, mode: str = "strict") -> dict[str, Any]:
    is_zh = _is_zh_question(question)
    warning = (
        "该应用场景尚未进入已验证选型规则，也没有足够数据库证据。"
        if is_zh
        else "This application scenario is not covered by verified selection rules and lacks sufficient database evidence."
    )
    return _response(
        NO_SUPPORTED_ANSWER_ZH if is_zh else NO_SUPPORTED_ANSWER_EN,
        [],
        [],
        [],
        [warning],
        "low",
        mode,
        [],
        [],
        _query_interpretation(question, mode),
        [warning],
    )


def _public_field_source_table(public_field: str, row: dict[str, Any]) -> str:
    source = str(row.get(f"{public_field}_source") or "")
    if source.startswith("manual"):
        return "manual_overrides"
    if public_field == "datasheet_url":
        return "product_assets"
    return "products"


def _evidence_item(
    product_model: str,
    field_name: str,
    raw_value: Any,
    normalized_value: Any,
    source_table: str,
    source_url: str | None,
    confidence: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "product_model": product_model,
        "field_name": field_name,
        "raw_value": raw_value if raw_value not in (None, "") else "not available",
        "normalized_value": normalized_value if normalized_value not in (None, "") else "not available",
        "source_table": source_table,
        "source_url": source_url or "not available",
        "confidence": confidence,
        "reason": reason,
    }


def _evidence_for_public_row(row: dict[str, Any], fields: list[str], reason: str) -> list[dict[str, Any]]:
    model = row.get("model") or "not available"
    source_url = row.get("product_url")
    evidence = []
    for public_field in fields:
        value = row.get(public_field)
        if value in (None, "", "not available"):
            continue
        evidence.append(
            _evidence_item(
                model,
                PUBLIC_TO_CANONICAL_FIELD.get(public_field, public_field),
                value,
                value,
                _public_field_source_table(public_field, row),
                row.get("datasheet_url") if public_field == "datasheet_url" else source_url,
                "high" if row.get(f"{public_field}_source") != "not_available" else "low",
                reason,
            )
        )
    if not evidence and row.get("product_url") not in (None, "", "not available"):
        evidence.append(
            _evidence_item(model, "product_url", row.get("product_url"), row.get("product_url"), "products", row.get("product_url"), "high", reason)
        )
    return evidence


def _evidence_for_specs(specs: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    evidence = []
    for spec in specs:
        evidence.append(
            _evidence_item(
                spec.get("model") or "not available",
                spec.get("spec_name") or "spec",
                spec.get("raw_value"),
                spec.get("normalized_value") or spec.get("raw_value"),
                "product_specs",
                spec.get("source_url"),
                "high",
                reason,
            )
        )
    return evidence


def _match_reason(
    row: dict[str, Any],
    reason: str,
    fields: list[str],
    exact: bool = True,
    partial: bool = False,
    inferred: bool = False,
    similarity_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "product_model": row.get("model") or "not available",
        "reason": reason,
        "matched_fields": fields,
        "exact_match": exact,
        "partial_match": partial,
        "inferred_match": inferred,
        "similarity_reason": similarity_reason or "",
    }


def _detect_exact_filters(question: str) -> dict[str, Any]:
    q = _text(_expanded_query(question))
    compact = q.replace(" ", "")
    filters: dict[str, Any] = {}
    voltages = [f"{value}V" for value in re.findall(r"(\d+(?:\.\d+)?)\s*v\b", q)]
    if "24v" in compact and "24V" not in voltages:
        voltages.append("24V")
    if voltages:
        filters["voltage"] = list(dict.fromkeys(voltages))
    if _wants_datasheet(question) and not any(term in q for term in ["missing", "缺失", "缺少", "没有"]):
        filters["has_datasheet"] = True
    requested_types = _requested_light_types(question)
    if requested_types:
        filters["light_type"] = requested_types
    colors = []
    color_terms = {
        "red": ["red", "红光", "红色"],
        "blue": ["blue", "蓝光", "蓝色"],
        "green": ["green", "绿光", "绿色"],
        "white": ["white", "白光", "白色"],
        "uv": ["uv", "紫外"],
        "ir": ["ir", "红外"],
    }
    for color, terms in color_terms.items():
        if any(term in q for term in terms):
            colors.append(color)
    if colors:
        filters["color"] = colors
    return filters


def _row_matches_exact_filters(row: dict[str, Any], filters: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    fields = []
    reasons = []
    if filters.get("voltage"):
        value = _text(row.get("voltage")).replace(" ", "")
        if not any(_text(voltage).replace(" ", "") in value for voltage in filters["voltage"]):
            return False, fields, reasons
        fields.append("voltage")
        reasons.append(f"voltage exactly matches {', '.join(filters['voltage'])}")
    if filters.get("has_datasheet"):
        if row.get("datasheet_url") in (None, "", "not available"):
            return False, fields, reasons
        fields.append("datasheet_url")
        reasons.append("datasheet URL is recorded")
    if filters.get("light_type"):
        value = _text(row.get("light_type"))
        if value not in filters["light_type"]:
            return False, fields, reasons
        fields.append("light_type")
        reasons.append(f"light_type matches {value}")
    if filters.get("color"):
        # Strict mode must not treat generic page/search text as a verified
        # color field. If color was not parsed into the canonical row, the
        # answer should be "not recorded" instead of returning a misleading
        # product row with color = not available.
        color_value = _text(row.get("color"))
        if color_value in {"", "not available", "none"}:
            return False, fields, reasons
        if not any(color in color_value for color in filters["color"]):
            return False, fields, reasons
        fields.append("color")
        reasons.append(f"color evidence matches {', '.join(filters['color'])}")
    return bool(fields), fields, reasons


def _strict_filter_products(question: str, limit: int = 20) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    filters = _detect_exact_filters(question)
    if not filters:
        return [], [], [], []
    rows_with_fields: list[tuple[dict[str, Any], list[str], list[str]]] = []
    evidence: list[dict[str, Any]] = []
    match_reasons: list[dict[str, Any]] = []
    for product in load_database().products:
        row = _product_public_row(product)
        matches, fields, reasons = _row_matches_exact_filters(row, filters)
        if not matches:
            continue
        row["match_reasons"] = "; ".join(reasons)
        rows_with_fields.append((row, fields, reasons))
    rows_with_fields.sort(key=lambda item: str(item[0].get("model") or ""))
    selected = rows_with_fields[:limit]
    rows = [item[0] for item in selected]
    for row, fields, reasons in selected:
        evidence.extend(_evidence_for_public_row(row, fields, "strict filter match"))
        match_reasons.append(_match_reason(row, "; ".join(reasons), fields, exact=True))
    return rows, evidence, match_reasons, list(filters.keys())


def _enrich_result(
    result: dict[str, Any],
    question: str,
    mode: str,
    evidence: list[dict[str, Any]] | None = None,
    match_reason: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    result["mode"] = mode
    result.setdefault("evidence", [])
    result.setdefault("match_reason", [])
    result.setdefault("query_interpretation", _query_interpretation(question, mode))
    result.setdefault("warnings", [])
    if evidence:
        result["evidence"].extend(evidence)
    if match_reason:
        result["match_reason"].extend(match_reason)
    if warnings:
        result["warnings"].extend(warnings)
        result["missing_or_uncertain"] = list(dict.fromkeys((result.get("missing_or_uncertain") or []) + warnings))
    return result


def _strict_answer_question(question: str) -> dict[str, Any]:
    q = _text(_expanded_query(question))
    is_zh = _is_zh_question(question)
    if not _text(question):
        return _response("请输入一个问题。" if is_zh else "Please enter a question.", confidence="low", mode="strict", query_interpretation=_query_interpretation(question, "strict"))

    if any(brand in q for brand in ["basler", "ccs", "opt ", "keyence", "smart vision lights", "cognex", "基恩士"]) and "tms" not in q:
        return _no_exact_response(question, "strict", "当前数据库只覆盖 TMS Lite。" if is_zh else "The current database only covers TMS Lite.")

    if any(term in q for term in UNSUPPORTED_BUSINESS_FIELDS):
        return _no_exact_response(question, "strict", "数据库没有价格、库存、交期或保修信息。" if is_zh else "The database has no pricing, stock, lead-time, or warranty records.")

    if _unsupported_application_question(question):
        return _no_supported_answer(question, "strict")

    models = _extract_models_from_question(question)

    if "compare" in q or "比较" in q or "对比" in q:
        if not models:
            return _no_exact_response(question, "strict", "对比问题需要明确型号。" if is_zh else "Comparison requires explicit model names.")
        table = compare_products(models)
        found_rows = [row for row in table if row.get("status") == "found"]
        sources = []
        evidence = []
        match_reasons = []
        for row in found_rows:
            sources.extend(get_product_sources(row["model"])[:3])
            evidence.extend(_evidence_for_public_row(row, ["voltage", "power", "current", "dimensions", "product_url", "datasheet_url"], "comparison field"))
            match_reasons.append(_match_reason(row, "model found exactly for comparison", ["model"], exact=True))
        missing_models = [row["model"] for row in table if row.get("status") != "found"]
        warnings = [f"Not found in current database: {', '.join(missing_models)}"] if missing_models else []
        answer = (
            f"已对比 {len(models)} 个明确型号，其中 {len(found_rows)} 个在当前数据库中有记录。未收录型号不会用替代产品回答。"
            if is_zh
            else f"Compared {len(models)} explicit model(s). {len(found_rows)} were found in the current database; missing models were not replaced by alternative products."
        )
        confidence = "high" if found_rows else "low"
        return _response(answer, found_rows, table, sources, warnings, confidence, "strict", evidence, match_reasons, _query_interpretation(question, "strict"), warnings)

    quality_question = (
        any(term in q for term in ["missing", "缺失", "缺少", "字段", "no voltage", "没有电压", "未记录"])
        or ((not models) and "没有" in question and (_wants_datasheet(question) or "电压" in question))
    )
    if quality_question:
        legacy = _legacy_answer_question(question)
        if legacy.get("matched_products") and not legacy.get("sources"):
            legacy["sources"] = _sources_from_hits(legacy["matched_products"], limit=20)
        return _enrich_result(legacy, question, "strict", warnings=[])

    if models:
        exact_products = [get_product_by_model(model) for model in models]
        exact_products = [product for product in exact_products if product]
        if not exact_products:
            return _no_exact_response(question, "strict", f"Model not found: {', '.join(models)}")
        model = exact_products[0]["model"]
        specs = get_product_specs(model)
        sources = get_product_sources(model)
        fields = ["brand", "family", "series", "category", "light_type", "color", "voltage", "power", "current", "dimensions", "product_url", "datasheet_url"]
        evidence = _evidence_for_public_row(exact_products[0], fields, "exact model lookup")
        evidence.extend(_evidence_for_specs(specs[:30], "raw spec for exact model lookup"))
        match_reasons = [_match_reason(exact_products[0], "model exactly matches requested model", ["model"], exact=True)]
        if _wants_datasheet(question):
            if exact_products[0].get("datasheet_url") != "not available":
                answer = f"{model} 有已记录的 datasheet URL。" if is_zh else f"{model} has a datasheet URL recorded."
            else:
                answer = f"{model} 当前数据库有产品记录，但没有 datasheet URL。" if is_zh else f"{model} is recorded, but no datasheet URL is available in the current database."
        else:
            answer = (
                f"{model} 当前数据库有明确记录。关键字段：电压 {exact_products[0]['voltage']}，功率 {exact_products[0]['power']}，电流 {exact_products[0]['current']}，尺寸 {exact_products[0]['dimensions']}。"
                if is_zh
                else f"{model} is explicitly recorded in the current database. Known fields: voltage {exact_products[0]['voltage']}, power {exact_products[0]['power']}, current {exact_products[0]['current']}, dimensions {exact_products[0]['dimensions']}."
            )
        return _response(answer, exact_products, specs[:30], sources, [], "high", "strict", evidence, match_reasons, _query_interpretation(question, "strict"), [])

    selected_intent = _supported_application_intent(question)
    if selected_intent:
        payload = APPLICATION_INTENTS[selected_intent]
        hits = search_products(payload["query"], limit=10)
        if not hits:
            return _no_supported_answer(question, "strict")
        sources = _sources_from_hits(hits)
        evidence = []
        match_reasons = []
        for hit in hits:
            fields = ["model", "family", "light_type", "product_url"]
            if hit.get("datasheet_url") != "not available":
                fields.append("datasheet_url")
            evidence.extend(_evidence_for_public_row(hit, fields, "configured application rule candidate"))
            match_reasons.append(
                _match_reason(
                    hit,
                    f"configured application intent '{selected_intent}' retrieved this database candidate",
                    fields,
                    exact=True,
                    partial=False,
                    inferred=True,
                )
            )
        answer = (
            f"初步选型逻辑：{APPLICATION_LOGIC_ZH.get(selected_intent, payload['logic'])} 下方候选产品只来自当前 TMS Lite 数据库；这不是最终选型结论。"
            if is_zh
            else f"Initial selection logic: {payload['logic']} The candidates below come only from the current TMS Lite database and are not a final selection conclusion."
        )
        warnings = [
            "选型建议需要样品、几何结构、工作距离、相机/镜头和实际成像验证。"
            if is_zh
            else "Selection guidance requires sample, geometry, working distance, camera/lens, and image validation."
        ]
        return _response(answer, hits, [], sources, warnings, "medium", "strict", evidence, match_reasons, _query_interpretation(question, "strict"), warnings)

    hits, evidence, match_reasons, filter_keys = _strict_filter_products(question, limit=20)
    if hits:
        sources = _sources_from_hits(hits)
        answer = (
            f"当前数据库找到 {len(hits)} 条明确匹配产品记录。匹配条件：{', '.join(filter_keys)}。"
            if is_zh
            else f"Found {len(hits)} exact database match(es). Matched filter(s): {', '.join(filter_keys)}."
        )
        return _response(answer, hits, [], sources, [], "high", "strict", evidence, match_reasons, _query_interpretation(question, "strict"), [])

    return _no_exact_response(question, "strict")


def _exploratory_answer_question(question: str) -> dict[str, Any]:
    is_zh = _is_zh_question(question)
    strict_result = _strict_answer_question(question)
    if strict_result.get("matched_products") or strict_result.get("spec_table"):
        strict_result["mode"] = "exploratory"
        strict_result["query_interpretation"] = _query_interpretation(question, "exploratory")
        if strict_result.get("confidence") == "high":
            strict_result["confidence"] = "medium"
        note = (
            "Exploratory mode is active; confidence is capped at medium even when exact database records are found."
        )
        strict_result["warnings"] = list(dict.fromkeys((strict_result.get("warnings") or []) + [note]))
        strict_result["missing_or_uncertain"] = list(dict.fromkeys((strict_result.get("missing_or_uncertain") or []) + [note]))
        return strict_result

    hits = search_products(question, limit=20)
    if not hits:
        model_queries = []
        for model in _extract_models_from_question(question):
            parts = str(model).split("-")
            if len(parts) > 1:
                model_queries.append("-".join(parts[:-1]))
            model_queries.append(parts[0])
        for query in model_queries:
            hits = search_products(query, limit=20)
            if hits:
                break
    if not hits:
        return _response(
            "当前数据库未记录，也没有找到可用的相似匹配。" if is_zh else "No exact or similar matches were found in the current database.",
            [],
            [],
            [],
            ["Exploratory search found no candidates."],
            "low",
            "exploratory",
            [],
            [],
            _query_interpretation(question, "exploratory"),
            ["Exploratory search found no candidates."],
        )
    evidence = []
    match_reasons = []
    for hit in hits:
        reason = hit.get("match_reasons") or "keyword overlap"
        evidence.extend(_evidence_for_public_row(hit, ["model", "family", "light_type", "product_url", "datasheet_url"], "exploratory similar match"))
        match_reasons.append(
            _match_reason(
                hit,
                "These are similar matches, not exact matches.",
                ["model", "family", "light_type", "search_text"],
                exact=False,
                partial=True,
                inferred=True,
                similarity_reason=reason,
            )
        )
    warning = "These are similar matches, not exact matches."
    answer = (
        f"这些是相似匹配，不是精确匹配。当前数据库找到 {len(hits)} 条可能相关记录；请优先核对 similarity reason、来源链接和字段证据。"
        if is_zh
        else f"These are similar matches, not exact matches. Found {len(hits)} potentially relevant records; review similarity reasons, sources, and evidence before using them."
    )
    return _response(answer, hits, [], _sources_from_hits(hits), [warning], "medium", "exploratory", evidence, match_reasons, _query_interpretation(question, "exploratory"), [warning])


def answer_question(question: str, mode: str = "strict") -> dict[str, Any]:
    normalized_mode = _text(mode)
    if normalized_mode not in {"strict", "exploratory"}:
        normalized_mode = "strict"
    if normalized_mode == "exploratory":
        return _exploratory_answer_question(question)
    return _strict_answer_question(question)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ask the Ronisens Product QA engine.")
    parser.add_argument("question", nargs="+")
    parser.add_argument("--mode", choices=["strict", "exploratory"], default="strict")
    args = parser.parse_args()
    print(json.dumps(answer_question(" ".join(args.question), mode=args.mode), ensure_ascii=False, indent=2))
