from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "ioo_product_test.db"
REPORT_PATH = ROOT / "advanced_illumination_data_quality_report.md"
ISSUES_PATH = ROOT / "advanced_illumination_data_issues.csv"
BRAND_NAME = "Advanced Illumination"


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params)]


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def empty(value: Any) -> bool:
    return clean(value).lower() in {"", "none", "not available", "null"}


def product_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT
            p.id,
            b.name AS brand,
            pf.family_name AS product_family,
            p.model,
            p.product_type,
            p.title,
            p.color_options,
            p.wavelength_nm,
            p.voltage_v,
            p.power_w,
            p.source_url,
            p.description,
            p.light_type
        FROM products p
        JOIN brands b ON b.id = p.brand_id
        LEFT JOIN product_families pf ON pf.id = p.family_id
        WHERE b.name = ?
        ORDER BY p.model
        """,
        (BRAND_NAME,),
    )


def asset_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT p.model, pf.family_name AS product_family, pa.asset_type, pa.url, pa.source_url
        FROM product_assets pa
        JOIN products p ON p.id = pa.product_id
        LEFT JOIN product_families pf ON pf.id = p.family_id
        JOIN brands b ON b.id = p.brand_id
        WHERE b.name = ?
        ORDER BY p.model, pa.asset_type
        """,
        (BRAND_NAME,),
    )


def spec_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT
            p.model,
            pf.family_name AS product_family,
            ps.spec_name,
            ps.raw_field,
            ps.raw_value,
            ps.canonical_field,
            ps.normalized_value,
            ps.unit,
            ps.source_url,
            ps.confidence
        FROM product_specs ps
        JOIN products p ON p.id = ps.product_id
        LEFT JOIN product_families pf ON pf.id = p.family_id
        JOIN brands b ON b.id = p.brand_id
        WHERE b.name = ?
        ORDER BY p.model, ps.spec_name
        """,
        (BRAND_NAME,),
    )


def add_issue(
    issues: list[dict[str, Any]],
    issue_type: str,
    severity: str,
    product: dict[str, Any] | None = None,
    field_name: str = "",
    raw_value: Any = "",
    source_url: str = "",
    suggested_fix: str = "",
    status: str = "open",
) -> None:
    issues.append(
        {
            "issue_type": issue_type,
            "severity": severity,
            "model": product.get("model", "") if product else "",
            "product_family": product.get("product_family", "") if product else "",
            "field_name": field_name,
            "raw_value": clean(raw_value),
            "source_url": source_url or (product.get("source_url", "") if product else ""),
            "suggested_fix": suggested_fix,
            "status": status,
        }
    )


def generate(db_path: Path = DB_PATH) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    with sqlite3.connect(db_path) as conn:
        products = product_rows(conn)
        specs = spec_rows(conn)
        assets = asset_rows(conn)
        family_count = len({p.get("product_family") for p in products if p.get("product_family")})
        product_count = len(products)
        spec_count = len(specs)
        asset_count = len(assets)
        datasheet_products = {
            asset["model"]
            for asset in assets
            if clean(asset.get("url")) and clean(asset.get("asset_type")).lower() in {"datasheet", "pdf", "catalogue"}
        }
        product_url_count = sum(1 for p in products if not empty(p.get("source_url")))
        duplicate_counts = Counter(clean(p.get("model")).upper() for p in products if clean(p.get("model")))
        issues: list[dict[str, Any]] = []

        for product in products:
            if product.get("model") not in datasheet_products:
                add_issue(issues, "missing_datasheet", "medium", product, "datasheet_url", "", product.get("source_url"), "Verify whether a datasheet exists on the official product page.")
            if empty(product.get("source_url")):
                add_issue(issues, "missing_product_url", "high", product, "product_url", "", "", "Add the official Advanced Illumination product URL.")
            if empty(product.get("voltage_v")):
                add_issue(issues, "missing_voltage", "medium", product, "voltage_v", "", product.get("source_url"), "Parse voltage from verified datasheet if available.")
            if empty(product.get("power_w")):
                add_issue(issues, "missing_power", "medium", product, "power_w", "", product.get("source_url"), "Parse power from verified datasheet if available.")
            if empty(product.get("color_options")) and empty(product.get("wavelength_nm")):
                add_issue(issues, "missing_color", "medium", product, "color", "", product.get("source_url"), "Normalize wavelengths/color options from quick specs.")
            if empty(product.get("light_type")):
                add_issue(issues, "missing_category", "high", product, "light_type", "", product.get("source_url"), "Assign product light type from official category.")
            product_specs = [spec for spec in specs if spec.get("model") == product.get("model")]
            if not product_specs:
                add_issue(issues, "empty_specs", "high", product, "specs", "", product.get("source_url"), "Review scraper/importer for missing quick specs.")

        for model, count in duplicate_counts.items():
            if count > 1:
                product = next((p for p in products if clean(p.get("model")).upper() == model), None)
                add_issue(issues, "duplicate_model", "high", product, "model", model, product.get("source_url") if product else "", "Check brand + model uniqueness.")

        for spec in specs:
            fake_product = {"model": spec.get("model"), "product_family": spec.get("product_family"), "source_url": spec.get("source_url")}
            if empty(spec.get("canonical_field")):
                add_issue(issues, "unmapped_field", "low", fake_product, spec.get("raw_field") or spec.get("spec_name"), spec.get("raw_value"), spec.get("source_url"), "Map only after the field meaning is verified.")
            value = clean(spec.get("raw_value"))
            canonical = clean(spec.get("canonical_field"))
            if canonical.endswith("_mm") and "mm" not in value.lower():
                add_issue(issues, "unparsed_unit", "low", fake_product, spec.get("raw_field") or spec.get("spec_name"), value, spec.get("source_url"), "Review unit parser.")
            if canonical == "wavelength_nm" and not re_like_wavelength(value):
                add_issue(issues, "suspicious_value", "medium", fake_product, spec.get("raw_field") or spec.get("spec_name"), value, spec.get("source_url"), "Check wavelength/color parsing.")

        for asset in assets:
            fake_product = {"model": asset.get("model"), "product_family": asset.get("product_family"), "source_url": asset.get("source_url")}
            url = clean(asset.get("url"))
            if not url.startswith("http"):
                add_issue(issues, "broken_asset_url", "medium", fake_product, "asset_url", url, asset.get("source_url"), "Replace with a full public URL.")

    with ISSUES_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["issue_type", "severity", "model", "product_family", "field_name", "raw_value", "source_url", "suggested_fix", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

    issue_counts = Counter(issue["issue_type"] for issue in issues)
    severity_counts = Counter(issue["severity"] for issue in issues)
    unmapped_count = issue_counts.get("unmapped_field", 0)
    unique_unmapped = sorted({clean(issue.get("field_name")) for issue in issues if issue.get("issue_type") == "unmapped_field"})
    report = [
        "# Advanced Illumination Data Quality Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "This report covers the Advanced Illumination pilot import only. TMS Lite data was not re-crawled or modified.",
        "",
        "Source URLs used for the pilot:",
        "",
        "- https://advancedillumination.com/",
        "- https://advancedillumination.com/advill-visual-product-catalog/",
        "- https://www.advancedillumination.com/products/",
        "- https://www.advancedillumination.com/wp-content/uploads/2025/03/DL110-Series.pdf",
        "- https://www.advancedillumination.com/wp-content/uploads/2025/03/DL225-Series.pdf",
        "",
        "## Summary",
        "",
        f"- Imported product families: {family_count}",
        f"- Imported products: {product_count}",
        f"- Imported specs: {spec_count}",
        f"- Imported assets: {asset_count}",
        f"- Datasheet coverage: {len(datasheet_products)} / {product_count}",
        f"- Product URL coverage: {product_url_count} / {product_count}",
        f"- Missing voltage count: {issue_counts.get('missing_voltage', 0)}",
        f"- Missing power count: {issue_counts.get('missing_power', 0)}",
        f"- Missing color count: {issue_counts.get('missing_color', 0)}",
        f"- Missing category count: {issue_counts.get('missing_category', 0)}",
        f"- Unmapped field occurrences: {unmapped_count}",
        f"- Unique unmapped field names: {len(unique_unmapped)}" + (f" ({', '.join(unique_unmapped)})" if unique_unmapped else ""),
        f"- Duplicate model count: {issue_counts.get('duplicate_model', 0)}",
        f"- Suspicious value count: {issue_counts.get('suspicious_value', 0)}",
        "",
        "## Issue Counts",
        "",
    ]
    for issue_type, count in issue_counts.most_common():
        report.append(f"- {issue_type}: {count}")
    report.extend(["", "## Severity Counts", ""])
    for severity, count in severity_counts.most_common():
        report.append(f"- {severity}: {count}")
    report.extend(
        [
            "",
            "## MVP Suitability",
            "",
            "The pilot data is suitable for validating multi-brand search, brand filtering, source links, and no-hallucination behavior. It is not yet complete enough for final commercial selection without human verification of datasheets and electrical parameters.",
        ]
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    return {
        "families": family_count,
        "products": product_count,
        "specs": spec_count,
        "assets": asset_count,
        "issues": len(issues),
        "unmapped_fields": unmapped_count,
        "datasheets": len(datasheet_products),
    }


def re_like_wavelength(value: str) -> bool:
    value_l = value.lower()
    return bool(any(token in value_l for token in ["nm", "white", "whi", "rgb"]) or re_search_digit(value_l))


def re_search_digit(value: str) -> bool:
    import re

    return bool(re.search(r"\b\d{3,4}\b", value))


def main() -> None:
    summary = generate()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {ISSUES_PATH}")


if __name__ == "__main__":
    main()
