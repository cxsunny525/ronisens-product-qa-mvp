from __future__ import annotations

import argparse
import csv
import hashlib
import mimetypes
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TMS_DB = ROOT / "data" / "tms_lite_full.db"
IOO_DB = ROOT / "data" / "ioo_products.db"
DOWNLOAD_DIR = ROOT / "data" / "downloads"
REAL_IMAGE_DIR = ROOT / "data" / "product_images_real"
PRIVATE_DIR = ROOT / "data" / "internal"
PRIVATE_MANIFEST = PRIVATE_DIR / "ioo_tms_real_image_manifest_private.csv"
PUBLIC_CSV = DOWNLOAD_DIR / "ioo_public_product_catalog_real_images.csv"
PUBLIC_ZIP = DOWNLOAD_DIR / "ioo_public_product_catalog_real_images.zip"
REPORT = ROOT / "IOO_REAL_PRODUCT_IMAGE_CATALOG_REPORT.md"

USER_AGENT = "IOO product image catalog builder (contact: inquiry@ioo.pro)"

PUBLIC_COLUMNS = [
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
    "real_product_image_file",
    "image_status",
    "product_detail_url",
    "spec_sheet_url",
]

PRIVATE_COLUMNS = [
    "public_model",
    "internal_model",
    "original_product_id",
    "product_source_url",
    "raw_html_path",
    "image_source_url",
    "image_alt",
    "image_selection_reason",
    "local_image_file",
    "download_status",
    "download_error",
]


class ImageExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        data = {k.lower(): (v or "") for k, v in attrs}
        for key in ("src", "data-zoom-image", "data-src", "data-original"):
            value = data.get(key)
            if value:
                self.images.append(
                    {
                        "url": value,
                        "src": data.get("src", ""),
                        "data_zoom_image": data.get("data-zoom-image", ""),
                        "id": data.get("id", ""),
                        "class": data.get("class", ""),
                        "alt": data.get("alt", ""),
                        "title": data.get("title", ""),
                        "width": data.get("width", ""),
                        "height": data.get("height", ""),
                        "attr": key,
                    }
                )


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "ioo-product"


def public_urls(public_model: str) -> tuple[str, str]:
    slug = slugify(public_model).lower()
    return f"https://ioo.pro/products/{slug}", f"https://ioo.pro/specs/{slug}.pdf"


def absolutize(url: str, base: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    absolute = urllib.parse.urljoin(base, url)
    parsed = urllib.parse.urlsplit(absolute)
    path = urllib.parse.quote(parsed.path, safe="/%")
    query = urllib.parse.quote(parsed.query, safe="=&%")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))


def image_score(image: dict[str, str], product_title: str) -> tuple[int, str]:
    url = image.get("url", "")
    joined = " ".join([url, image.get("alt", ""), image.get("title", ""), image.get("id", ""), image.get("class", "")]).lower()
    score = 0
    reasons: list[str] = []
    if image.get("id", "").lower() == "image":
        score += 100
        reasons.append("main image id")
    if image.get("attr") == "data-zoom-image":
        score += 35
        reasons.append("zoom image")
    if "product photos master file" in joined or "product%20photos%20master%20file" in joined:
        score += 45
        reasons.append("product photo path")
    if "whole-view" in joined or "black-background" in joined or "top-view" in joined:
        score += 20
        reasons.append("product view")
    if product_title and product_title.lower() in joined:
        score += 15
        reasons.append("title match")
    if re.search(r"\.(png|jpe?g|webp)(\?|$)", url, re.I):
        score += 10
        reasons.append("image extension")
    bad_terms = [
        "logo",
        "icon",
        "empty-cart",
        "facebook",
        "linkedin",
        "google",
        "captcha",
        "menu/",
        "overdrive",
        "rgbw-",
        "controller/",
        "m8-and-m12",
        "dimension",
        "2d%20and%203d",
    ]
    for term in bad_terms:
        if term in joined:
            score -= 80
            reasons.append(f"penalized {term}")
    return score, "; ".join(reasons) or "fallback candidate"


def extract_best_image(raw_html_path: str, product_url: str, product_title: str) -> tuple[str, str, str]:
    if not raw_html_path:
        return "", "", "raw HTML not found"
    path = Path(raw_html_path)
    if not path.exists() or not path.is_file():
        return "", "", "raw HTML not found"
    html = path.read_text(encoding="utf-8", errors="ignore")
    parser = ImageExtractor()
    parser.feed(html)
    best: tuple[int, str, dict[str, str]] | None = None
    for image in parser.images:
        url = absolutize(image.get("url", ""), product_url)
        if not url:
            continue
        image["url"] = url
        score, reason = image_score(image, product_title)
        if best is None or score > best[0]:
            best = (score, reason, image)
    if not best or best[0] < 0:
        return "", "", "no product-like image found"
    image = best[2]
    alt = image.get("alt") or image.get("title") or product_title
    return image["url"], alt, best[1]


def connect_rows() -> list[dict[str, Any]]:
    tms = sqlite3.connect(TMS_DB)
    tms.row_factory = sqlite3.Row
    ioo = sqlite3.connect(IOO_DB)
    ioo.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    query = """
        SELECT
          p.id,
          p.model,
          p.title,
          p.source_url
        FROM products p
        ORDER BY p.id
    """
    crawl_pages = [dict(row) for row in tms.execute("SELECT url, final_url, raw_path FROM crawl_pages WHERE raw_path IS NOT NULL").fetchall()]
    mapping = {
        row["original_product_id"]: dict(row)
        for row in ioo.execute("SELECT * FROM internal_mapping").fetchall()
    }
    public_products = {
        row["public_model"]: dict(row)
        for row in ioo.execute("SELECT * FROM products").fetchall()
    }
    for product in tms.execute(query).fetchall():
        map_row = mapping.get(product["id"])
        if not map_row:
            continue
        public_model = map_row["public_model"]
        public_row = public_products.get(public_model, {})
        raw_path = find_raw_path(product["source_url"] or "", crawl_pages)
        image_url, alt, reason = extract_best_image(raw_path, product["source_url"] or "", product["title"] or product["model"] or "")
        rows.append(
            {
                **public_row,
                "public_model": public_model,
                "internal_model": product["model"],
                "original_product_id": product["id"],
                "product_source_url": product["source_url"],
                "raw_html_path": raw_path,
                "image_source_url": image_url,
                "image_alt": alt,
                "image_selection_reason": reason,
                "local_image_file": "",
                "download_status": "pending_download" if image_url else "missing_image_url",
                "download_error": "",
            }
        )
    tms.close()
    ioo.close()
    return rows


def source_slug(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    return parsed.path.rstrip("/").split("/")[-1].lower()


def find_raw_path(source_url: str, crawl_pages: list[dict[str, Any]]) -> str:
    if not source_url:
        return ""
    normalized = source_url.rstrip("/")
    slug = source_slug(source_url)
    exact_matches: list[dict[str, Any]] = []
    slug_matches: list[dict[str, Any]] = []
    for page in crawl_pages:
        url = str(page.get("url") or "").rstrip("/")
        final_url = str(page.get("final_url") or "").rstrip("/")
        if url == normalized or final_url == normalized:
            exact_matches.append(page)
        elif slug and (slug in url.lower() or slug in final_url.lower()):
            slug_matches.append(page)
    candidates = exact_matches or slug_matches
    if not candidates:
        return ""
    # Prefer short, direct pages over search/category duplicates.
    candidates.sort(key=lambda p: (("?" in str(p.get("url") or "")) + ("search" in str(p.get("url") or "").lower()), len(str(p.get("url") or ""))))
    return str(candidates[0].get("raw_path") or "")


def extension_from_response(url: str, content_type: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    if guessed in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return guessed
    return ".jpg"


def download_image(url: str, public_model: str, delay: float) -> tuple[str, str, str]:
    if not url:
        return "", "missing_image_url", ""
    time.sleep(max(0.0, delay))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        if not data or not (content_type.startswith("image/") or data[:8].startswith(b"\x89PNG") or data[:3] == b"\xff\xd8\xff"):
            return "", "failed", f"not an image response: {content_type}"
        ext = extension_from_response(url, content_type)
        digest = hashlib.sha256(data).hexdigest()[:10]
        filename = f"{slugify(public_model)}-{digest}{ext}"
        out = REAL_IMAGE_DIR / filename
        out.write_bytes(data)
        return f"images/{filename}", "downloaded", ""
    except Exception as exc:
        return "", "failed", f"{type(exc).__name__}: {exc}"


def write_outputs(rows: list[dict[str, Any]]) -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with PRIVATE_MANIFEST.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PRIVATE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    public_rows = []
    for row in rows:
        detail_url, spec_url = public_urls(str(row.get("public_model") or ""))
        public_rows.append(
            {
                "public_brand": "IOO",
                "public_model": row.get("public_model", ""),
                "product_family": row.get("product_family", ""),
                "series": row.get("series", ""),
                "product_category": row.get("product_category", ""),
                "light_type": row.get("light_type", ""),
                "color": row.get("color", ""),
                "wavelength_nm": row.get("wavelength_nm", ""),
                "voltage_v": row.get("voltage_v", ""),
                "current_a": row.get("current_a", ""),
                "power_w": row.get("power_w", ""),
                "dimensions": row.get("dimensions", ""),
                "key_specs": row.get("key_specs", ""),
                "public_description": row.get("public_description", ""),
                "recommendation_tags": row.get("recommendation_tags", ""),
                "real_product_image_file": row.get("local_image_file") or "",
                "image_status": row.get("download_status") or "",
                "product_detail_url": detail_url,
                "spec_sheet_url": spec_url,
            }
        )

    with PUBLIC_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PUBLIC_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(public_rows)

    with zipfile.ZipFile(PUBLIC_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(PUBLIC_CSV, arcname="ioo_public_product_catalog_real_images.csv")
        for image in sorted(REAL_IMAGE_DIR.glob("*")):
            if image.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                zf.write(image, arcname=f"images/{image.name}")

    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row.get("download_status") or "unknown"] = statuses.get(row.get("download_status") or "unknown", 0) + 1
    with zipfile.ZipFile(PUBLIC_ZIP) as zf:
        zip_image_count = sum(1 for n in zf.namelist() if n.startswith("images/"))
    REPORT.write_text(
        "\n".join(
            [
                "# IOO Real Product Image Catalog Report",
                "",
                f"- Products mapped: {len(rows)}",
                f"- Image URLs discovered: {sum(1 for r in rows if r.get('image_source_url'))}",
                f"- Real image files downloaded: {sum(1 for r in rows if r.get('download_status') == 'downloaded')}",
                f"- Images included in public ZIP: {zip_image_count}",
                f"- Public CSV: `{PUBLIC_CSV}`",
                f"- Public ZIP: `{PUBLIC_ZIP}`",
                f"- Private source manifest: `{PRIVATE_MANIFEST}`",
                "",
                "## Download Status",
                "",
                *[f"- {key}: {value}" for key, value in sorted(statuses.items())],
                "",
                "## Notes",
                "",
                "- Public CSV and ZIP do not expose source website URLs or internal supplier fields.",
                "- The private manifest keeps source URLs for internal traceability only.",
                "- If downloads fail due local network restrictions, rerun this script in a network-enabled environment.",
                "",
                "Command:",
                "",
                "`python build_ioo_real_image_catalog.py --download --delay 1.5`",
            ]
        ),
        encoding="utf-8",
    )


def build_catalog(download: bool = False, limit: int | None = None, delay: float = 1.5) -> dict[str, str | int]:
    rows = connect_rows()
    if limit:
        rows = rows[:limit]
    REAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    if download:
        for idx, row in enumerate(rows, start=1):
            local_file, status, error = download_image(str(row.get("image_source_url") or ""), str(row.get("public_model") or ""), delay)
            row["local_image_file"] = local_file
            row["download_status"] = status
            row["download_error"] = error
            print(f"{idx}/{len(rows)} {row.get('public_model')} {status} {local_file or error}")
    write_outputs(rows)
    return {
        "rows": len(rows),
        "public_csv": str(PUBLIC_CSV),
        "public_zip": str(PUBLIC_ZIP),
        "private_manifest": str(PRIVATE_MANIFEST),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download real images from discovered source URLs.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    print(build_catalog(download=args.download, limit=args.limit, delay=args.delay))


if __name__ == "__main__":
    main()
