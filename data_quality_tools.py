from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import qa_engine


ROOT = Path(__file__).resolve().parent
ISSUES_CSV = ROOT / "data_issues.csv"
SUMMARY_MD = ROOT / "data_issues_summary.md"
EXPECTED_ISSUE_TYPES = [
    "missing_datasheet",
    "missing_product_url",
    "missing_voltage",
    "missing_power",
    "missing_color",
    "missing_category",
    "duplicate_model",
    "unmapped_field",
    "unparsed_unit",
    "broken_asset_url",
    "suspicious_value",
    "empty_specs",
]


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _missing(value: Any) -> bool:
    text = _clean(value).lower()
    return text in {"", "none", "not available", "null"}


def _issue(
    issue_type: str,
    severity: str,
    model: str,
    product_family: str,
    field_name: str,
    raw_value: Any,
    source_url: str,
    suggested_fix: str,
    status: str = "open",
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "model": model,
        "product_family": product_family,
        "field_name": field_name,
        "raw_value": raw_value,
        "source_url": source_url,
        "suggested_fix": suggested_fix,
        "status": status,
    }


def _unmapped_fields() -> list[str]:
    path = ROOT / "unmapped_fields.md"
    if not path.exists():
        return []
    fields = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\|\s*`(.+?)`\s*\|", line)
        if match:
            fields.append(match.group(1))
    return fields


def generate_data_issues() -> list[dict[str, Any]]:
    ds = qa_engine.load_database()
    issues: list[dict[str, Any]] = []
    model_counts = Counter(_clean(product.get("model")) for product in ds.products if product.get("model"))
    specs_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in ds.specs:
        specs_by_model[qa_engine._norm(spec.get("model"))].append(spec)  # type: ignore[attr-defined]

    for product in ds.products:
        row = qa_engine._product_public_row(product)  # type: ignore[attr-defined]
        model = _clean(row.get("model"))
        family = _clean(row.get("family"))
        source_url = _clean(row.get("product_url"))
        if _missing(row.get("datasheet_url")):
            issues.append(_issue("missing_datasheet", "medium", model, family, "datasheet_url", row.get("datasheet_url"), source_url, "Verify whether a datasheet/catalog URL exists for this product or family."))
        if _missing(row.get("product_url")):
            issues.append(_issue("missing_product_url", "high", model, family, "product_url", row.get("product_url"), source_url, "Backfill source_url from crawl_pages or product family page."))
        if _missing(row.get("voltage")):
            issues.append(_issue("missing_voltage", "high", model, family, "voltage_v", row.get("voltage"), source_url, "Parse voltage from product_specs or datasheet table."))
        if _missing(row.get("power")):
            issues.append(_issue("missing_power", "medium", model, family, "power_w", row.get("power"), source_url, "Parse wattage from product_specs or datasheet table."))
        if _missing(row.get("color")):
            issues.append(_issue("missing_color", "low", model, family, "color", row.get("color"), source_url, "Map color from Colour/Color/RGBW/IR/UV specs where available."))
        if _missing(row.get("category")) or _missing(row.get("light_type")):
            issues.append(_issue("missing_category", "medium", model, family, "product_category/light_type", f"{row.get('category')} / {row.get('light_type')}", source_url, "Add or verify product category/light type mapping."))
        if model_counts[model] > 1:
            issues.append(_issue("duplicate_model", "high", model, family, "model", model, source_url, "Inspect duplicate rows and merge or disambiguate if they are not variants."))
        if not specs_by_model.get(qa_engine._norm(model)):  # type: ignore[attr-defined]
            issues.append(_issue("empty_specs", "medium", model, family, "product_specs", "", source_url, "Check if this product inherited only family-level assets or if specs failed to parse."))

    unmapped = set(_unmapped_fields())
    for spec in ds.specs:
        name = _clean(spec.get("spec_name"))
        raw_value = _clean(spec.get("raw_value"))
        if name in unmapped:
            issues.append(_issue("unmapped_field", "low", _clean(spec.get("model")), "", name, raw_value, _clean(spec.get("source_url")), "Map this raw spec name to canonical_fields.yaml or keep it explicitly unmapped."))
        if re.search(r"\d", raw_value) and not re.search(r"(V|W|A|mA|mm|nm|g|kg|%)", raw_value, flags=re.I) and any(term in name.lower() for term in ["voltage", "watt", "current", "(mm)", "weight"]):
            issues.append(_issue("unparsed_unit", "medium", _clean(spec.get("model")), "", name, raw_value, _clean(spec.get("source_url")), "Normalize numeric value and unit."))
        if any(term in raw_value.lower() for term in ["please contact", "contact our sales", "n/a"]):
            issues.append(_issue("suspicious_value", "medium", _clean(spec.get("model")), "", name, raw_value, _clean(spec.get("source_url")), "Review whether this is a real parameter value or a vendor note."))

    for asset in ds.assets:
        url = _clean(asset.get("url") or asset.get("final_url"))
        if url and not re.match(r"^https?://", url):
            issues.append(_issue("broken_asset_url", "high", _clean(asset.get("model")), _clean(asset.get("product_family")), "asset_url", url, _clean(asset.get("source_url")), "Repair or remove malformed asset URL."))

    return issues


def write_outputs() -> tuple[Path, Path, dict[str, Any]]:
    issues = generate_data_issues()
    with ISSUES_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["issue_type", "severity", "model", "product_family", "field_name", "raw_value", "source_url", "suggested_fix", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

    by_type = Counter(issue["issue_type"] for issue in issues)
    by_severity = Counter(issue["severity"] for issue in issues)
    lines = [
        "# Data Issues Summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Total issues: {len(issues)}",
        "",
        "## By Severity",
        "",
    ]
    for severity in ["high", "medium", "low"]:
        lines.append(f"- {severity}: {by_severity.get(severity, 0)}")
    lines.extend(["", "## By Issue Type", ""])
    for issue_type in EXPECTED_ISSUE_TYPES:
        lines.append(f"- {issue_type}: {by_type.get(issue_type, 0)}")
    lines.extend(
        [
            "",
            "## Recommended Fix Order",
            "",
            "1. Fix high-severity duplicate models, missing product URLs, malformed asset URLs, and missing voltage fields.",
            "2. Review missing datasheets and missing category/light-type mappings.",
            "3. Normalize unit parsing and map the highest-volume unmapped fields.",
            "4. Use manual_overrides.yaml only for human-verified corrections that should not alter the source database.",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ISSUES_CSV, SUMMARY_MD, {"total": len(issues), "by_type": dict(by_type), "by_severity": dict(by_severity)}


if __name__ == "__main__":
    csv_path, summary_path, stats = write_outputs()
    print(f"Wrote {csv_path} and {summary_path}")
    print(stats)
