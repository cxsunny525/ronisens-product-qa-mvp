from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from normalize_advanced_illumination import append_unmapped_fields, normalize_specs


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SOURCE_DB = DATA_DIR / "tms_lite_full.db"
TARGET_DB = DATA_DIR / "ioo_product_test.db"
RAW_JSONL = ROOT / "advanced_illumination_raw_products.jsonl"
BRAND_NAME = "Advanced Illumination"
BRAND_SHORT_NAME = "AI"
BRAND_COUNTRY = "USA"
BRAND_SITE = "https://advancedillumination.com/"


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def norm_model(value: Any) -> str:
    return "".join(clean(value).upper().split())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params)]


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return column in {row["name"] for row in rows(conn, f"PRAGMA table_info({table})")}


def add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not has_column(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def prepare_database(target_db: Path = TARGET_DB) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not target_db.exists():
        if not SOURCE_DB.exists():
            raise FileNotFoundError(f"Source database not found: {SOURCE_DB}")
        shutil.copy2(SOURCE_DB, target_db)

    with sqlite3.connect(target_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        add_column(conn, "brands", "brand_short_name", "TEXT")
        add_column(conn, "brands", "brand_country", "TEXT")
        add_column(conn, "brands", "official_site", "TEXT")

        add_column(conn, "products", "description", "TEXT")
        add_column(conn, "products", "light_type", "TEXT")

        add_column(conn, "product_specs", "raw_field", "TEXT")
        add_column(conn, "product_specs", "canonical_field", "TEXT")
        add_column(conn, "product_specs", "confidence", "TEXT")

        add_column(conn, "product_assets", "asset_url", "TEXT")
        add_column(conn, "product_assets", "filename", "TEXT")

        add_column(conn, "crawl_pages", "brand", "TEXT")
        add_column(conn, "crawl_pages", "source_url", "TEXT")
        add_column(conn, "crawl_pages", "page_type", "TEXT")
        add_column(conn, "crawl_pages", "raw_html", "TEXT")
        add_column(conn, "crawl_pages", "extracted_text", "TEXT")
        add_column(conn, "crawl_pages", "extraction_status", "TEXT")
        conn.commit()


def get_or_create_brand(conn: sqlite3.Connection) -> int:
    existing = conn.execute("SELECT id FROM brands WHERE lower(name)=lower(?)", (BRAND_NAME,)).fetchone()
    if existing:
        brand_id = int(existing[0])
        conn.execute(
            """
            UPDATE brands
            SET website = COALESCE(NULLIF(website, ''), ?),
                country = COALESCE(NULLIF(country, ''), ?),
                brand_short_name = ?,
                brand_country = ?,
                official_site = ?
            WHERE id = ?
            """,
            (BRAND_SITE, BRAND_COUNTRY, BRAND_SHORT_NAME, BRAND_COUNTRY, BRAND_SITE, brand_id),
        )
        return brand_id
    cur = conn.execute(
        """
        INSERT INTO brands (name, website, country, created_at, brand_short_name, brand_country, official_site)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (BRAND_NAME, BRAND_SITE, BRAND_COUNTRY, datetime.utcnow().isoformat(timespec="seconds") + "Z", BRAND_SHORT_NAME, BRAND_COUNTRY, BRAND_SITE),
    )
    return int(cur.lastrowid)


def get_or_create_family(conn: sqlite3.Connection, brand_id: int, record: dict[str, Any]) -> int:
    family_name = clean(record.get("product_family") or record.get("title") or record.get("model"))
    existing = conn.execute(
        "SELECT id FROM product_families WHERE brand_id=? AND family_name=?",
        (brand_id, family_name),
    ).fetchone()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if existing:
        family_id = int(existing[0])
        conn.execute(
            """
            UPDATE product_families
            SET product_type = COALESCE(NULLIF(product_type, ''), ?),
                category_path = COALESCE(NULLIF(category_path, ''), ?),
                short_description = COALESCE(NULLIF(short_description, ''), ?),
                source_url = COALESCE(NULLIF(source_url, ''), ?),
                updated_at = ?
            WHERE id = ?
            """,
            ("lighting", record.get("light_type"), record.get("description"), record.get("source_url") or record.get("product_url"), now, family_id),
        )
        return family_id
    cur = conn.execute(
        """
        INSERT INTO product_families
            (brand_id, family_name, series_code, product_type, category_path, short_description, applications, source_url, raw_text, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brand_id,
            family_name,
            clean(record.get("model")),
            "lighting",
            clean(record.get("light_type")),
            clean(record.get("description")),
            "",
            record.get("source_url") or record.get("product_url"),
            json.dumps(record, ensure_ascii=False),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def first_numeric_spec(raw_specs: dict[str, Any], canonical: str) -> str | None:
    for normalized in normalize_specs(raw_specs):
        if normalized.canonical_field == canonical and normalized.normalized_value:
            return normalized.normalized_value
    return None


def upsert_product(conn: sqlite3.Connection, brand_id: int, family_id: int, record: dict[str, Any]) -> int:
    model = clean(record.get("model"))
    if not model:
        raise ValueError("Advanced Illumination record missing model")
    existing = conn.execute("SELECT id FROM products WHERE brand_id=? AND model_normalized=?", (brand_id, norm_model(model))).fetchone()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    raw_specs = record.get("raw_specs") or {}
    wavelength = first_numeric_spec(raw_specs, "wavelength_nm")
    search_text = " ".join(
        clean(part)
        for part in [
            BRAND_NAME,
            record.get("product_family"),
            record.get("model"),
            record.get("title"),
            record.get("light_type"),
            record.get("description"),
            json.dumps(raw_specs, ensure_ascii=False),
        ]
        if clean(part)
    )
    payload = (
        brand_id,
        family_id,
        model,
        norm_model(model),
        "",
        "lighting",
        clean(record.get("title")),
        wavelength,
        wavelength,
        None,
        None,
        None,
        None,
        None,
        json.dumps(raw_specs, ensure_ascii=False),
        search_text,
        record.get("product_url") or record.get("source_url"),
        now,
        now,
        clean(record.get("description")),
        clean(record.get("light_type")),
    )
    if existing:
        product_id = int(existing[0])
        conn.execute(
            """
            UPDATE products
            SET brand_id=?, family_id=?, model=?, model_normalized=?, variant_code=?,
                product_type=?, title=?, color_options=?, wavelength_nm=?, voltage_v=?,
                power_w=?, current_ma=?, weight_g=?, dimensions_mm_json=?, specs_json=?,
                search_text=?, source_url=?, updated_at=?, description=?, light_type=?
            WHERE id=?
            """,
            payload[:17] + (payload[18], payload[19], payload[20], product_id),
        )
        return product_id
    cur = conn.execute(
        """
        INSERT INTO products
            (brand_id, family_id, model, model_normalized, variant_code, product_type, title,
             color_options, wavelength_nm, voltage_v, power_w, current_ma, weight_g,
             dimensions_mm_json, specs_json, search_text, source_url, created_at, updated_at,
             description, light_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    return int(cur.lastrowid)


def replace_specs(conn: sqlite3.Connection, product_id: int, record: dict[str, Any]) -> set[str]:
    conn.execute("DELETE FROM product_specs WHERE product_id=?", (product_id,))
    unmapped = set()
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for index, spec in enumerate(normalize_specs(record.get("raw_specs") or {})):
        if not spec.mapped:
            unmapped.add(spec.raw_field)
        conn.execute(
            """
            INSERT INTO product_specs
                (product_id, spec_group, spec_name, raw_value, normalized_value, unit, source_url,
                 source_table_index, source_row_index, created_at, raw_field, canonical_field, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                "Advanced Illumination Quick Specs",
                spec.raw_field,
                spec.raw_value,
                spec.normalized_value,
                spec.unit,
                record.get("source_url") or record.get("product_url"),
                0,
                index,
                now,
                spec.raw_field,
                spec.canonical_field,
                spec.confidence,
            ),
        )
    return unmapped


def replace_assets(conn: sqlite3.Connection, brand_id: int, family_id: int, product_id: int, record: dict[str, Any]) -> None:
    conn.execute("DELETE FROM product_assets WHERE product_id=?", (product_id,))
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    for asset in record.get("asset_links") or []:
        url = clean(asset.get("url"))
        if not url:
            continue
        filename = url.rstrip("/").split("/")[-1] or clean(asset.get("title")) or "asset"
        conn.execute(
            """
            INSERT INTO product_assets
                (brand_id, family_id, product_id, asset_type, title, url, final_url, local_path,
                 content_type, file_sha256, source_url, downloaded_at, created_at, asset_url, filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brand_id,
                family_id,
                product_id,
                clean(asset.get("asset_type")) or "asset",
                clean(asset.get("title")) or filename,
                url,
                url,
                "",
                "application/pdf" if ".pdf" in url.lower() else "",
                None,
                record.get("source_url") or record.get("product_url"),
                "",
                now,
                url,
                filename,
            ),
        )


def upsert_crawl_page(conn: sqlite3.Connection, brand_id: int, record: dict[str, Any]) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sources = record.get("crawl_sources") or [record.get("source_url") or record.get("product_url")]
    for source in dict.fromkeys(url for url in sources if url):
        existing = conn.execute("SELECT id FROM crawl_pages WHERE url=? AND brand=?", (source, BRAND_NAME)).fetchone()
        extracted_text = " ".join(
            clean(part)
            for part in [record.get("title"), record.get("description"), json.dumps(record.get("raw_specs") or {}, ensure_ascii=False)]
            if clean(part)
        )
        if existing:
            conn.execute(
                """
                UPDATE crawl_pages
                SET brand_id=?, final_url=?, status_code=?, content_type=?, is_product_candidate=?,
                    crawled_at=?, brand=?, source_url=?, page_type=?, extracted_text=?, extraction_status=?
                WHERE id=?
                """,
                (brand_id, source, 200, "text/html", 1, now, BRAND_NAME, source, "advanced_illumination_pilot", extracted_text, "pilot_import", int(existing[0])),
            )
        else:
            conn.execute(
                """
                INSERT INTO crawl_pages
                    (brand_id, url, final_url, status_code, content_type, raw_path, page_sha256,
                     is_product_candidate, crawled_at, error, brand, source_url, page_type,
                     raw_html, extracted_text, extraction_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    brand_id,
                    source,
                    source,
                    200,
                    "text/html",
                    "",
                    None,
                    1,
                    now,
                    "",
                    BRAND_NAME,
                    source,
                    "advanced_illumination_pilot",
                    "",
                    extracted_text,
                    "pilot_import",
                ),
            )


def import_records(raw_jsonl: Path = RAW_JSONL, db_path: Path = TARGET_DB) -> dict[str, int]:
    if not raw_jsonl.exists():
        raise FileNotFoundError(f"Raw JSONL not found: {raw_jsonl}. Run scrape_advanced_illumination.py first.")
    prepare_database(db_path)
    records = read_jsonl(raw_jsonl)
    unmapped_fields: set[str] = set()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        brand_id = get_or_create_brand(conn)
        imported_products = 0
        imported_assets = 0
        imported_specs = 0
        families = set()
        for record in records:
            if clean(record.get("brand")) and clean(record.get("brand")) != BRAND_NAME:
                continue
            if clean(record.get("product_category")).lower() != "lighting":
                continue
            family_id = get_or_create_family(conn, brand_id, record)
            families.add(clean(record.get("product_family")))
            product_id = upsert_product(conn, brand_id, family_id, record)
            unmapped_fields.update(replace_specs(conn, product_id, record))
            replace_assets(conn, brand_id, family_id, product_id, record)
            upsert_crawl_page(conn, brand_id, record)
            imported_products += 1
            imported_assets += len(record.get("asset_links") or [])
            imported_specs += len(record.get("raw_specs") or {})
        conn.commit()
    append_unmapped_fields(unmapped_fields)
    return {
        "families": len(families),
        "products": imported_products,
        "specs": imported_specs,
        "assets": imported_assets,
        "unmapped_fields": len(unmapped_fields),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Advanced Illumination pilot records into the unified IOO.pro database.")
    parser.add_argument("--input", default=str(RAW_JSONL), help="Input JSONL path from scraper.")
    parser.add_argument("--db", default=str(TARGET_DB), help="Target SQLite database.")
    args = parser.parse_args()
    summary = import_records(Path(args.input), Path(args.db))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Unified database: {Path(args.db)}")


if __name__ == "__main__":
    main()
