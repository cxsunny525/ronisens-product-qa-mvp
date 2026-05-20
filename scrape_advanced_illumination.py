from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RAW_JSONL = ROOT / "advanced_illumination_raw_products.jsonl"
PRODUCTS_URL = "https://advancedillumination.com/products/"
CATALOG_URL = "https://advancedillumination.com/advill-visual-product-catalog/"
USER_AGENT = "IOO.pro Product Database Test pilot crawler/0.1 (+https://ioo.pro)"


# High-confidence pilot records from the public Advanced Illumination product
# archive and reachable official series/PDF pages. These are lighting products
# only; controller/camera/accessory entries from the product archive are omitted.
SEEDED_PILOT_PRODUCTS: list[dict[str, Any]] = [
    {
        "product_family": "High Intensity Spot Light",
        "model": "SL246",
        "title": "High Intensity Spot Light",
        "product_category": "lighting",
        "light_type": "spot",
        "product_url": "https://advancedillumination.com/products/high-intensity-spot-light-series-2/",
        "description": "High current rated LEDs; fixed dimensions.",
        "raw_specs": {"Wavelengths": "455nm 470nm 505nm 530nm 590nm 625nm 660nm 730nm 850nm 940nm", "Intensity": "110000 Lux", "Lead Time": "2 Weeks", "Light Conditioning": "N/A"},
        "asset_links": [],
    },
    {
        "product_family": "Modular Bar Lights",
        "model": "AL325",
        "title": "AL325 Modular Bar Lights",
        "product_category": "lighting",
        "light_type": "bar",
        "product_url": "https://advancedillumination.com/products/al325-series/",
        "description": "Modular bar light system with user-swappable optics and embedded control options.",
        "raw_specs": {"Wavelengths": "365nm 375nm 385nm 395nm 405 455nm 470nm 505nm 530nm 590nm 625nm 660nm 730nm 850nm 940nm White", "Intensity": "73,000 Lux", "Lead Time": "In Stock", "Light Conditioning": "Diffuser"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/al325-series/#datasheet"}],
    },
    {
        "product_family": "UltraSeal Ring Light Series",
        "model": "RL322",
        "title": "UltraSeal Ring Light Series",
        "product_category": "lighting",
        "light_type": "ring",
        "product_url": "https://advancedillumination.com/products/ultraseal-ring-light-series/",
        "description": "IP69K certified ring light series with crevice-free design for washdown environments.",
        "raw_specs": {"Wavelengths": "365nm 375nm 385nm 395nm 405 455nm 470nm 530nm 625nm 660nm 730nm 850nm 940nm White", "Light Conditioning": "Polarizer"},
        "asset_links": [],
    },
    {
        "product_family": "Sealed High Intensity Line Lights",
        "model": "LL330",
        "title": "Sealed High Intensity Line Lights",
        "product_category": "lighting",
        "light_type": "line",
        "product_url": "https://advancedillumination.com/products/sealed-high-intensity-line-lights/",
        "description": "High intensity sealed line light with dust and debris protected passively cooled design.",
        "raw_specs": {"Wavelengths": "455nm 625nm White", "Intensity": "1200000 Lux", "Lead Time": "3 Weeks"},
        "asset_links": [],
    },
    {
        "product_family": "High Intensity Back-lit Backlights",
        "model": "BL2-XXYY",
        "title": "High Intensity Back-lit Backlights",
        "product_category": "lighting",
        "light_type": "backlight",
        "product_url": "https://advancedillumination.com/products/high-intensity-back-lit-backlights-2/",
        "description": "Back-lit backlight family with scalable custom sizes and consistent uniformity/intensity.",
        "raw_specs": {"Wavelengths": "470nm 530nm 625nm 850nm White", "Intensity": "86000 Lux", "Lead Time": "2 Weeks", "Light Conditioning": "Collimator Polarizer"},
        "asset_links": [],
    },
    {
        "product_family": "MicroBrite Direct Bright Field Series",
        "model": "RL208",
        "title": "RL208 MicroBrite Direct Bright Field Series",
        "product_category": "lighting",
        "light_type": "bright_field_ring",
        "product_url": "https://advancedillumination.com/products/rl208_series_2/",
        "description": "Compact high-intensity ring light series for directional on-axis and off-axis illumination.",
        "raw_specs": {"Wavelengths": "365nm 375nm 385nm 395nm 455nm 470nm 505nm 530nm 590nm 625nm 660nm 730nm 850nm 940nm White", "Intensity": "41,400 Lux", "Lead Time": "In Stock", "Light Conditioning": "N/A"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/rl208_series_2/#datasheet"}],
    },
    {
        "product_family": "MicroBrite Direct Dark Field Series",
        "model": "DF196",
        "title": "DF196 MicroBrite Direct Dark Field Series",
        "product_category": "lighting",
        "light_type": "dark_field",
        "product_url": "https://advancedillumination.com/products/df196-series_2/",
        "description": "Compact dark field ring light series.",
        "raw_specs": {"Wavelengths": "455nm 530nm 625nm RGB White", "Intensity": "78,000 Lux", "Lead Time": "In Stock", "Light Conditioning": "N/A"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/df196-series_2/#datasheet"}],
    },
    {
        "product_family": "MicroBrite Diffuse Ring Light Series",
        "model": "DF198",
        "title": "DF198 MicroBrite Diffuse Ring Light Series",
        "product_category": "lighting",
        "light_type": "diffuse_ring",
        "product_url": "https://advancedillumination.com/products/df198-series_2/",
        "description": "Compact diffuse ring light series.",
        "raw_specs": {"Wavelengths": "455nm 530nm 625nm RGB White", "Intensity": "47,000 Lux", "Lead Time": "2 Weeks", "Light Conditioning": "N/A"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/df198-series_2/#datasheet"}],
    },
    {
        "product_family": "Compact High Intensity Spot Light",
        "model": "SL164",
        "title": "SL164 Compact High Intensity Spot Light",
        "product_category": "lighting",
        "light_type": "spot",
        "product_url": "https://advancedillumination.com/products/sl164-series-2/",
        "description": "Compact high intensity spot light with high current rated LEDs and fixed dimensions.",
        "raw_specs": {"Wavelengths": "365nm 375nm 385nm 395nm 455nm 470nm 505nm 530nm 590nm 625nm 660nm 730nm 850nm 940nm White", "Intensity": "201,000 Lux", "Lead Time": "In Stock", "Light Conditioning": "Diffuser"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/sl164-series-2/#datasheet"}],
    },
    {
        "product_family": "UltraSeal Spot Light",
        "model": "SL316",
        "title": "UltraSeal Spot Light",
        "product_category": "lighting",
        "light_type": "spot",
        "product_url": "https://advancedillumination.com/products/ultraseal-washdown-spot-light/",
        "description": "IP69K certified UltraSeal spot light for food, beverage, and medical applications.",
        "raw_specs": {"Wavelengths": "455nm 470nm 505nm 530nm 590nm 625nm 660nm 730nm 850nm 940nm Blue Green Red White Yellow", "Intensity": "150000 Lux", "Lead Time": "2 Weeks", "Light Conditioning": "Diffuser"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/ultraseal-washdown-spot-light/#datasheet"}],
    },
    {
        "product_family": "High Intensity Pattern Projecting Spot Light",
        "model": "SL256",
        "title": "High Intensity Pattern Projecting Spot Light",
        "product_category": "lighting",
        "light_type": "pattern_projector",
        "product_url": "https://advancedillumination.com/products/sl256/",
        "description": "Structured pattern projecting spot light.",
        "raw_specs": {"Wavelengths": "455nm 530nm 625nm Blue Green Red White", "Lead Time": "2 Weeks", "Light Conditioning": "N/A"},
        "asset_links": [{"asset_type": "datasheet", "title": "Datasheet", "url": "https://advancedillumination.com/products/sl256/#datasheet"}],
    },
    {
        "product_family": "Linear Coaxial Light",
        "model": "DL110",
        "title": "DL110 Linear Coaxial Light",
        "product_category": "lighting",
        "light_type": "coaxial",
        "product_url": "https://www.advancedillumination.com/wp-content/uploads/2025/03/DL110-Series.pdf",
        "description": "Linear coaxial light for low to moderate speed linescan camera applications; 25mm x 300mm target projection.",
        "raw_specs": {"Wavelengths": "470nm 530nm 625nm 850nm WHI", "Emitting Area": "25mm x 300mm", "Lead Time": "1-2 Week BTO Lead Times Typical"},
        "asset_links": [{"asset_type": "datasheet", "title": "DL110 Series PDF", "url": "https://www.advancedillumination.com/wp-content/uploads/2025/03/DL110-Series.pdf"}],
    },
    {
        "product_family": "Square Coaxial Lights",
        "model": "DL225",
        "title": "DL225 Square Coaxial Lights",
        "product_category": "lighting",
        "light_type": "coaxial",
        "product_url": "https://www.advancedillumination.com/wp-content/uploads/2025/03/DL225-Series.pdf",
        "description": "Square on-axis illuminator series for area scan camera inspections and differential reflection targets.",
        "raw_specs": {"Wavelengths": "365nm 375nm 385nm 395nm 405nm 455nm 470nm 530nm 590nm 625nm 850nm 940nm WHI", "Sizes": "25mm 50mm 75mm 100mm 150mm", "IP Rating": "IP50", "Lead Time": "1-2 Week BTO Lead Times"},
        "asset_links": [{"asset_type": "datasheet", "title": "DL225 Series PDF", "url": "https://www.advancedillumination.com/wp-content/uploads/2025/03/DL225-Series.pdf"}],
    },
]


def fetch_url(url: str, delay_seconds: float = 1.5) -> str:
    time.sleep(delay_seconds)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def discover_from_products_archive(html: str) -> list[dict[str, Any]]:
    """Best-effort product-card extraction for public archive pages.

    The site currently renders the first product batch in static HTML. This
    parser intentionally stays conservative; if extraction fails, the curated
    seed records above are still used.
    """
    records: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*x\s*\n", html)
    lighting_terms = ["light", "backlight", "illumination"]
    skip_terms = ["controller", "accessor", "camera", "software", "sensor", "hub"]
    for block in blocks:
        if "Quick Specs" not in block:
            continue
        lines = [re.sub(r"\s+", " ", line).strip() for line in block.splitlines() if line.strip()]
        text = " ".join(lines)
        if any(term in text.lower() for term in skip_terms):
            continue
        if not any(term in text.lower() for term in lighting_terms):
            continue
        model = next((line for line in lines if re.fullmatch(r"[A-Z]{1,4}\d{2,4}(?:-[A-Z0-9]+)?|BL2-XXYY", line)), "")
        if not model:
            continue
        title = ""
        for line in lines:
            if "Light" in line or "Backlight" in line or "Projecting" in line:
                title = line
                break
        raw_specs = {}
        for field in ["Wavelengths", "Intensity", "Lead Time", "Light Conditioning"]:
            match = re.search(field + r".{0,80}?((?:\d|White|RGB|Blue|Green|Red|Yellow|In Stock|Weeks|N/A|Diffuser|Polarizer|Collimator)[^#]*)", text, flags=re.I)
            if match:
                raw_specs[field] = match.group(1).strip()
        if title and model:
            records.append(
                {
                    "brand": "Advanced Illumination",
                    "product_family": title,
                    "model": model,
                    "title": title,
                    "product_category": "lighting",
                    "light_type": infer_light_type(title),
                    "product_url": PRODUCTS_URL,
                    "description": title,
                    "raw_specs": raw_specs,
                    "asset_links": [],
                    "source_url": PRODUCTS_URL,
                }
            )
    return records


def infer_light_type(text: str) -> str:
    low = text.lower()
    if "backlight" in low or "back-lit" in low:
        return "backlight"
    if "bar" in low:
        return "bar"
    if "coaxial" in low or "on-axis" in low:
        return "coaxial"
    if "dark field" in low:
        return "dark_field"
    if "bright field" in low or "ring" in low:
        return "ring"
    if "diffuse" in low:
        return "diffuse"
    if "line" in low:
        return "line"
    if "spot" in low:
        return "spot"
    return "lighting"


def build_records(limit: int | None = None, live: bool = False) -> list[dict[str, Any]]:
    records = [dict(item) for item in SEEDED_PILOT_PRODUCTS]
    if live:
        try:
            html = fetch_url(PRODUCTS_URL)
            discovered = discover_from_products_archive(html)
            seen = {record["model"] for record in records}
            for record in discovered:
                if record["model"] not in seen:
                    records.append(record)
                    seen.add(record["model"])
        except Exception as exc:
            print(f"Live discovery failed; using curated pilot records only: {exc}")
    for record in records:
        record.setdefault("brand", "Advanced Illumination")
        record.setdefault("source_url", record.get("product_url") or PRODUCTS_URL)
        record.setdefault("crawl_sources", [PRODUCTS_URL, CATALOG_URL, record["source_url"]])
        record["scraped_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return records[:limit] if limit else records


def write_jsonl(records: list[dict[str, Any]], path: Path = RAW_JSONL) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Advanced Illumination lighting products for IOO.pro pilot import.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records to write.")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing JSONL.")
    parser.add_argument("--live", action="store_true", help="Attempt polite live archive fetch before falling back to seed records.")
    args = parser.parse_args()

    records = build_records(args.limit, live=args.live)
    if args.dry_run:
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
        print(f"Dry run records: {len(records)}")
        return
    write_jsonl(records)
    print(f"Wrote {len(records)} Advanced Illumination pilot records to {RAW_JSONL}")


if __name__ == "__main__":
    main()
