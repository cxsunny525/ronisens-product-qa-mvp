from __future__ import annotations

import csv
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "ioo_products.db"
DOWNLOAD_DIR = ROOT / "data" / "downloads"
IMAGE_DIR = ROOT / "data" / "product_images"
CSV_PATH = DOWNLOAD_DIR / "ioo_public_product_catalog.csv"
ZIP_PATH = DOWNLOAD_DIR / "ioo_public_product_catalog_with_images.zip"
REPORT_PATH = ROOT / "IOO_PRODUCT_CATALOG_EXPORT_REPORT.md"

BANNED_PUBLIC_TERMS = [
    "TMS",
    "TMS Lite",
    "TMS-LITE",
    "tms-lite",
    "Advanced Illumination",
    "supplier",
    "internal_model",
    "internal_supplier",
]

EXPORT_COLUMNS = [
    "public_brand",
    "public_model",
    "product_family",
    "series",
    "product_category",
    "light_type",
    "color",
    "wavelength_nm",
    "voltage_v",
    "current_a",
    "power_w",
    "dimensions",
    "key_specs",
    "public_description",
    "recommendation_tags",
    "product_image_file",
    "product_image_alt",
    "product_detail_url",
    "spec_sheet_url",
    "catalog_exported_at",
]


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "ioo-product"


def safe_public_text(value: Any) -> str:
    text = "" if value is None else str(value)
    for term in BANNED_PUBLIC_TERMS:
        text = re.sub(re.escape(term), "IOO" if "TMS" in term.upper() else "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_products() -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Missing IOO product database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
              public_brand,
              public_model,
              product_family,
              series,
              product_category,
              light_type,
              color,
              wavelength_nm,
              voltage_v,
              current_a,
              power_w,
              dimensions,
              key_specs,
              public_description,
              recommendation_tags
            FROM products
            ORDER BY public_model
            """
        ).fetchall()
    ]
    conn.close()
    return rows


def light_type_label(light_type: str) -> str:
    labels = {
        "bar_light": "bar light",
        "ring_light": "ring light",
        "backlight": "backlight",
        "coaxial_light": "coaxial light",
        "dark_field": "dark-field light",
        "dome_light": "dome light",
        "line_scan_light": "line-scan light",
        "spot_light": "spot light",
        "uv_light": "UV light",
        "ir_light": "IR light",
    }
    return labels.get((light_type or "").strip(), (light_type or "machine vision light").replace("_", " "))


def svg_shape(light_type: str) -> str:
    lt = (light_type or "").lower()
    if "ring" in lt or "coaxial" in lt:
        return """
        <circle cx="160" cy="112" r="58" fill="#E8F7F4" stroke="#2CA9A6" stroke-width="8"/>
        <circle cx="160" cy="112" r="26" fill="#FFFFFF" stroke="#CCDDD9" stroke-width="6"/>
        <circle cx="160" cy="112" r="8" fill="#D58A23"/>
        """
    if "back" in lt:
        return """
        <rect x="80" y="58" width="160" height="108" rx="18" fill="#E8F7F4" stroke="#2CA9A6" stroke-width="6"/>
        <line x1="104" y1="86" x2="216" y2="86" stroke="#BFE7E1" stroke-width="8" stroke-linecap="round"/>
        <line x1="104" y1="116" x2="216" y2="116" stroke="#BFE7E1" stroke-width="8" stroke-linecap="round"/>
        <line x1="104" y1="146" x2="216" y2="146" stroke="#BFE7E1" stroke-width="8" stroke-linecap="round"/>
        """
    if "bar" in lt or "line" in lt:
        return """
        <rect x="66" y="86" width="188" height="52" rx="18" fill="#E8F7F4" stroke="#2CA9A6" stroke-width="6"/>
        <line x1="94" y1="112" x2="226" y2="112" stroke="#D58A23" stroke-width="10" stroke-linecap="round"/>
        """
    if "dark" in lt:
        return """
        <path d="M80 150 L160 58 L240 150" fill="none" stroke="#2CA9A6" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="86" y1="158" x2="234" y2="158" stroke="#D58A23" stroke-width="8" stroke-linecap="round"/>
        <circle cx="160" cy="58" r="10" fill="#2CA9A6"/>
        """
    if "dome" in lt:
        return """
        <path d="M76 150 C84 86 116 56 160 56 C204 56 236 86 244 150" fill="#E8F7F4" stroke="#2CA9A6" stroke-width="6"/>
        <rect x="96" y="146" width="128" height="18" rx="9" fill="#D58A23"/>
        """
    return """
    <rect x="96" y="58" width="128" height="108" rx="26" fill="#E8F7F4" stroke="#2CA9A6" stroke-width="6"/>
    <circle cx="160" cy="112" r="28" fill="#FFFFFF" stroke="#D58A23" stroke-width="6"/>
    """


def write_product_svg(product: dict[str, Any]) -> str:
    model = safe_public_text(product.get("public_model"))
    light = safe_public_text(product.get("light_type"))
    family = safe_public_text(product.get("product_family"))
    filename = f"{slugify(model)}.svg"
    out_path = IMAGE_DIR / filename
    label = light_type_label(light)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420" role="img" aria-label="{model} {label}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#F8FAFC"/>
      <stop offset="1" stop-color="#E8F7F4"/>
    </linearGradient>
  </defs>
  <rect width="640" height="420" rx="34" fill="url(#bg)"/>
  <rect x="34" y="34" width="572" height="352" rx="28" fill="#FFFFFF" opacity="0.86" stroke="#D5E7E4"/>
  <g transform="translate(160 36)">
    {svg_shape(light)}
  </g>
  <text x="52" y="296" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#22323A">{model}</text>
  <text x="52" y="334" font-family="Arial, Helvetica, sans-serif" font-size="22" fill="#536B74">IOO {label}</text>
  <text x="52" y="366" font-family="Arial, Helvetica, sans-serif" font-size="17" fill="#6E828A">{family[:72]}</text>
</svg>
"""
    out_path.write_text(svg, encoding="utf-8")
    return f"images/{filename}"


def public_urls(public_model: str) -> tuple[str, str]:
    slug = slugify(public_model).lower()
    return f"https://ioo.pro/products/{slug}", f"https://ioo.pro/specs/{slug}.pdf"


def build_export() -> dict[str, Any]:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    products = fetch_products()
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []
    for product in products:
        model = safe_public_text(product.get("public_model"))
        image_file = write_product_svg(product)
        detail_url, spec_url = public_urls(model)
        row = {
            "public_brand": "IOO",
            "public_model": model,
            "product_family": safe_public_text(product.get("product_family")),
            "series": safe_public_text(product.get("series")),
            "product_category": safe_public_text(product.get("product_category")),
            "light_type": safe_public_text(product.get("light_type")),
            "color": safe_public_text(product.get("color")),
            "wavelength_nm": safe_public_text(product.get("wavelength_nm")),
            "voltage_v": safe_public_text(product.get("voltage_v")),
            "current_a": safe_public_text(product.get("current_a")),
            "power_w": safe_public_text(product.get("power_w")),
            "dimensions": safe_public_text(product.get("dimensions")),
            "key_specs": safe_public_text(product.get("key_specs")),
            "public_description": safe_public_text(product.get("public_description")),
            "recommendation_tags": safe_public_text(product.get("recommendation_tags")),
            "product_image_file": image_file,
            "product_image_alt": f"{model} IOO {light_type_label(str(product.get('light_type') or ''))}",
            "product_detail_url": detail_url,
            "spec_sheet_url": spec_url,
            "catalog_exported_at": exported_at,
        }
        rows.append(row)

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(CSV_PATH, arcname="ioo_public_product_catalog.csv")
        for image_path in sorted(IMAGE_DIR.glob("*.svg")):
            zf.write(image_path, arcname=f"images/{image_path.name}")

    csv_text = CSV_PATH.read_text(encoding="utf-8-sig", errors="ignore")
    leakage = [term for term in BANNED_PUBLIC_TERMS if re.search(re.escape(term), csv_text, re.IGNORECASE)]
    image_count = len(list(IMAGE_DIR.glob("*.svg")))
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# IOO Product Catalog Export Report",
                "",
                f"- Export time: {exported_at}",
                f"- Source database: `{DB_PATH}`",
                f"- Products exported: {len(rows)}",
                f"- Product images generated: {image_count}",
                f"- CSV output: `{CSV_PATH}`",
                f"- ZIP output: `{ZIP_PATH}`",
                f"- Public leakage check: {'passed' if not leakage else 'failed: ' + ', '.join(leakage)}",
                "",
                "## Notes",
                "",
                "- Each IOO public model has a deterministic SVG image file in the ZIP `images/` folder.",
                "- The export intentionally omits internal supplier fields and private source URLs.",
                "- Product detail and spec sheet links use IOO public placeholder URLs for sandbox testing.",
            ]
        ),
        encoding="utf-8",
    )
    if leakage:
        raise RuntimeError(f"Public catalog contains blocked terms: {leakage}")
    return {
        "products": len(rows),
        "images": image_count,
        "csv": str(CSV_PATH),
        "zip": str(ZIP_PATH),
    }


if __name__ == "__main__":
    result = build_export()
    print(result)
