from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import knowledge_engine

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parent
ALLOWLIST_PATH = ROOT / "source_allowlist.yaml"
OUTPUT_DIR = ROOT / "data" / "knowledge" / "edmund"
RAW_OUTPUT = OUTPUT_DIR / "edmund_knowledge_raw.jsonl"
DISCOVERY_OUTPUT = OUTPUT_DIR / "edmund_discovered_urls.json"
ROBOTS_URL = "https://www.edmundoptics.com/robots.txt"
SITEMAP_URL = "https://www.edmundoptics.com/sitemap/SiteMap_EN.xml"
USER_AGENT = "IOO.pro Product Intelligence Test knowledge crawler/0.1"
SOURCE_NAME = "Edmund Optics"
DOMAIN = "www.edmundoptics.com"
DEFAULT_DELAY = 10.0

INCLUDE_PATHS = [
    "/knowledge-center/",
    "/capabilities/imaging-optics/resources",
]
EXCLUDE_PATH_FRAGMENTS = [
    "/my-account/",
    "/cart/",
    "/search/",
    "/solr/",
    "/profile/",
    "/order-history/",
    "/saved-list/",
    "/tools/quickquote",
    "/tools/compliance",
    "/catalog/specsheet/",
    "/catalog/partnumber/_primaryimagesmodal",
    "/catalog/partnumber/_documents",
    "/catalog/partnumber/_relatedproducts",
    "/catalog/partnumber/_accessories",
    "/digital-catalog/",
    "/vip/",
    "/impressum/",
    "/mega-menu/",
    "/modal-windows/",
    "/p/discontinued/",
]
ARTICLE_HINTS = [
    "machine-vision",
    "illumination",
    "lighting",
    "backlight",
    "brightfield",
    "darkfield",
    "telecentric",
    "coaxial",
    "filter",
    "polariz",
    "bandpass",
    "longpass",
    "shortpass",
    "lens",
    "focal",
    "field-of-view",
    "working-distance",
    "depth-of-field",
    "resolution",
    "sensor",
    "camera",
    "line-scan",
    "imaging",
    "metrology",
    "contrast",
]


class CrawlSession:
    def __init__(self, delay: float) -> None:
        self.delay = max(DEFAULT_DELAY, delay)
        self.last_request_at = 0.0

    def get(self, url: str, *, delay: bool = True, timeout: int = 30) -> tuple[int | None, str, str | None, str]:
        if delay:
            elapsed = time.time() - self.last_request_at
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self.last_request_at = time.time()
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.8"}
        try:
            if requests is not None and hasattr(requests, "get"):
                response = requests.get(url, headers=headers, timeout=timeout)
                ctype = response.headers.get("content-type", "")
                if response.status_code >= 400:
                    return response.status_code, "", f"HTTP {response.status_code}", ctype
                return response.status_code, response.text, None, ctype
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - public allowlisted URL
                raw = response.read().decode("utf-8", errors="ignore")
                ctype = response.headers.get("content-type", "")
                status = getattr(response, "status", 200)
                return status, raw, None, ctype
        except Exception as exc:
            return None, "", str(exc), ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_edmund_source() -> dict[str, Any]:
    fallback = {
        "source_name": SOURCE_NAME,
        "domain": "edmundoptics.com",
        "base_urls": [
            "https://www.edmundoptics.com/knowledge-center/",
            "https://www.edmundoptics.com/knowledge-center/application-notes/imaging/",
            "https://www.edmundoptics.com/knowledge-center/application-notes/illumination/",
            "https://www.edmundoptics.com/capabilities/imaging-optics/resources",
        ],
        "source_type": "knowledge_articles",
        "priority": "high",
        "max_pages": 150,
        "crawl_delay_seconds": 10,
        "respect_robots_txt": True,
    }
    if not ALLOWLIST_PATH.exists() or yaml is None or not hasattr(yaml, "safe_load"):
        return fallback
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8")) or {}
    for source in data.get("sources", []):
        if source.get("source_name") == SOURCE_NAME:
            return source
    return fallback


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1] + "/"
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def is_allowed_domain(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower() in {"www.edmundoptics.com", "edmundoptics.com"}


def is_disallowed_path(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return any(fragment in path for fragment in EXCLUDE_PATH_FRAGMENTS)


def is_candidate_article_url(url: str) -> bool:
    if not url.startswith("https://") or not is_allowed_domain(url) or is_disallowed_path(url):
        return False
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if not any(path.startswith(prefix) for prefix in INCLUDE_PATHS):
        return False
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".zip", ".aspx")):
        return False
    if "/products/" in path or "/p/" in path or "/c/" in path:
        return False
    text = path.replace("/", " ")
    return any(hint in text for hint in ARTICLE_HINTS) or "/application-notes/" in path


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def parse_robots(session: CrawlSession) -> tuple[urllib.robotparser.RobotFileParser, float, str | None]:
    status, text, error, _ = session.get(ROBOTS_URL, delay=False, timeout=20)
    parser = urllib.robotparser.RobotFileParser()
    if text:
        parser.parse(text.splitlines())
    else:
        parser.parse([])
    delay = DEFAULT_DELAY
    if text:
        match = re.search(r"Crawl-delay:\s*(\d+(?:\.\d+)?)", text, flags=re.I)
        if match:
            delay = max(DEFAULT_DELAY, float(match.group(1)))
    return parser, delay, error if error else None


def discover_from_sitemap(session: CrawlSession, robots: urllib.robotparser.RobotFileParser) -> list[str]:
    status, xml_text, error, _ = session.get(SITEMAP_URL, delay=False, timeout=40)
    if error or not xml_text:
        return []
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
        for loc in root.findall(".//{*}loc"):
            if loc.text:
                url = normalize_url(loc.text.strip())
                if is_candidate_article_url(url) and robots.can_fetch(USER_AGENT, url):
                    urls.append(url)
    except Exception:
        for match in re.findall(r"<loc>(.*?)</loc>", xml_text, flags=re.I):
            url = normalize_url(match.strip())
            if is_candidate_article_url(url) and robots.can_fetch(USER_AGENT, url):
                urls.append(url)
    return list(dict.fromkeys(urls))


def discover_from_base_pages(session: CrawlSession, robots: urllib.robotparser.RobotFileParser, base_urls: list[str]) -> list[str]:
    urls: list[str] = []
    for base_url in base_urls:
        if not robots.can_fetch(USER_AGENT, base_url):
            continue
        status, html, error, _ = session.get(base_url, delay=True, timeout=30)
        if error or not html:
            log_crawl(base_url, "discover_failed", status, error)
            continue
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
            absolute = normalize_url(urllib.parse.urljoin(base_url, href))
            if is_candidate_article_url(absolute) and robots.can_fetch(USER_AGENT, absolute):
                urls.append(absolute)
    return list(dict.fromkeys(urls))


def extract_page(url: str, html: str, content_type: str) -> dict[str, Any]:
    canonical_url = canonical_from_html(url, html)
    title = title_from_html(url, html)
    clean_text, clean_markdown = extract_text(url, html)
    author = meta_content(html, ["author", "article:author"])
    published_date = meta_content(html, ["article:published_time", "date", "publishdate", "published_date"])
    outgoing = sorted(set(find_outgoing_links(url, html)))[:40]
    images = sorted(set(find_images(url, html)))[:40]
    return {
        "title": title,
        "url": url,
        "canonical_url": canonical_url,
        "source_name": SOURCE_NAME,
        "publisher": SOURCE_NAME,
        "author": author,
        "published_date": published_date,
        "retrieved_at": utc_now(),
        "language": "en",
        "content_type": content_type or "text/html",
        "raw_html": html,
        "clean_text": clean_text,
        "clean_markdown": clean_markdown,
        "outgoing_source_links": outgoing,
        "images_metadata": [{"url": image_url} for image_url in images],
        "content_hash": content_hash(clean_text or clean_markdown or html),
    }


def canonical_from_html(url: str, html: str) -> str:
    match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, flags=re.I)
    if not match:
        match = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', html, flags=re.I)
    return normalize_url(urllib.parse.urljoin(url, match.group(1))) if match else normalize_url(url)


def title_from_html(url: str, html: str) -> str:
    for pattern in [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
    ]:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            return clean_inline(match.group(1))
    return urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1].replace("-", " ").title()


def meta_content(html: str, names: list[str]) -> str | None:
    for name in names:
        patterns = [
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.I | re.S)
            if match:
                return clean_inline(match.group(1))
    return None


def clean_inline(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def extract_text(url: str, html: str) -> tuple[str, str]:
    try:
        import trafilatura  # type: ignore

        markdown = trafilatura.extract(html, url=url, output_format="markdown", include_links=False, favor_precision=True)
        text = trafilatura.extract(html, url=url, output_format="txt", include_links=False, favor_precision=True)
        if text or markdown:
            return (text or markdown or "").strip(), (markdown or text or "").strip()
    except Exception:
        pass
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.extract()
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = re.sub(r"\s+", " ", main.get_text(" ")).strip()
        return text, text
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text, text


def find_outgoing_links(url: str, html: str) -> list[str]:
    links = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        absolute = normalize_url(urllib.parse.urljoin(url, href))
        if absolute.startswith("http"):
            links.append(absolute)
    return links


def find_images(url: str, html: str) -> list[str]:
    images = []
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.I):
        absolute = urllib.parse.urljoin(url, src)
        if absolute.startswith("http"):
            images.append(absolute)
    return images


def existing_output_urls(output_path: Path) -> set[str]:
    urls: set[str] = set()
    if not output_path.exists():
        return urls
    for line in output_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            urls.add(record.get("canonical_url") or record.get("url"))
        except Exception:
            continue
    return {url for url in urls if url}


def log_crawl(url: str, status: str, http_status: int | None = None, error_message: str | None = None) -> None:
    try:
        knowledge_engine.ensure_knowledge_schema()
        with knowledge_engine.connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_crawl_log (url, source_name, status, http_status, error_message, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (url, SOURCE_NAME, status, http_status, error_message, utc_now()),
            )
            conn.commit()
    except Exception:
        pass


def crawl(limit: int, dry_run: bool, resume: bool, force: bool, output_path: Path) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_edmund_source()
    session = CrawlSession(float(source.get("crawl_delay_seconds") or DEFAULT_DELAY))
    robots, crawl_delay, robots_error = parse_robots(session)
    session.delay = max(DEFAULT_DELAY, crawl_delay)

    sitemap_urls = discover_from_sitemap(session, robots)
    base_urls = [str(url) for url in source.get("base_urls", [])]
    base_discovered = discover_from_base_pages(session, robots, base_urls) if not sitemap_urls else []
    discovered = list(dict.fromkeys(sitemap_urls + base_discovered + [normalize_url(url) for url in base_urls if is_candidate_article_url(normalize_url(url))]))
    discovered = [url for url in discovered if robots.can_fetch(USER_AGENT, url) and not is_disallowed_path(url)]
    discovered = discovered[:limit]
    DISCOVERY_OUTPUT.write_text(json.dumps({"discovered_at": utc_now(), "count": len(discovered), "urls": discovered}, indent=2), encoding="utf-8")

    if dry_run:
        return {
            "robots_error": robots_error,
            "crawl_delay_seconds": session.delay,
            "discovered_urls": len(discovered),
            "sample_urls": discovered[:20],
            "output": str(output_path),
        }

    done = existing_output_urls(output_path) if resume and not force else set()
    mode = "a" if resume and output_path.exists() and not force else "w"
    crawled = 0
    successful = 0
    failed = 0
    skipped = 0
    with output_path.open(mode, encoding="utf-8") as f:
        for url in discovered:
            if url in done:
                skipped += 1
                continue
            if not robots.can_fetch(USER_AGENT, url):
                log_crawl(url, "robots_disallowed", None, "Blocked by robots.txt")
                skipped += 1
                continue
            status, html, error, content_type = session.get(url, delay=True, timeout=35)
            crawled += 1
            if error or not html:
                log_crawl(url, "failed", status, error)
                failed += 1
                continue
            try:
                record = extract_page(url, html, content_type)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                log_crawl(url, "success", status, None)
                successful += 1
            except Exception as exc:
                log_crawl(url, "extract_failed", status, str(exc))
                failed += 1
    return {
        "robots_error": robots_error,
        "crawl_delay_seconds": session.delay,
        "discovered_urls": len(discovered),
        "crawled_pages": crawled,
        "successful_pages": successful,
        "failed_pages": failed,
        "skipped_pages": skipped,
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl Edmund Optics public knowledge articles into raw JSONL.")
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", default=str(RAW_OUTPUT))
    args = parser.parse_args()
    result = crawl(args.limit, args.dry_run, args.resume, args.force, Path(args.output))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
