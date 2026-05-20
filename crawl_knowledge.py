from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dependency fallback
    yaml = None

import knowledge_engine


ROOT = Path(__file__).resolve().parent
ALLOWLIST_PATH = ROOT / "source_allowlist.yaml"
SEED_PATH = ROOT / "knowledge_seed_documents.jsonl"
USER_AGENT = "IOO.pro Product Database Test knowledge pilot/0.1"

FALLBACK_SOURCES = [
    {
        "source_name": "Advanced Illumination",
        "domain": "advancedillumination.com",
        "base_urls": ["https://www.advancedillumination.com/wp-content/uploads/2023/05/A-Practical-Guide-to-Machine-Vision-Lighting-Second-Edition.pdf"],
        "source_type": "application_guide",
        "priority": 1,
        "crawl_strategy": "seed_urls",
        "max_pages": 4,
        "notes": "Fallback allowlist entry used when PyYAML is unavailable.",
    },
    {"source_name": "Smart Vision Lights", "domain": "smartvisionlights.com", "base_urls": ["https://smartvisionlights.com/resources/training/training-bright-field-lighting/"], "source_type": "tech_note", "priority": 2, "crawl_strategy": "seed_urls", "max_pages": 6, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
    {"source_name": "Edmund Optics", "domain": "edmundoptics.com", "base_urls": ["https://www.edmundoptics.com/knowledge-center/application-notes/illumination/backlight-illumination-for-machine-vision/"], "source_type": "application_note", "priority": 1, "crawl_strategy": "seed_urls", "max_pages": 10, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
    {"source_name": "Cognex", "domain": "cognex.com", "base_urls": ["https://www.cognex.com/what-is/machine-vision/components/lighting"], "source_type": "vision_basics", "priority": 2, "crawl_strategy": "seed_urls", "max_pages": 6, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
    {"source_name": "Basler", "domain": "baslerweb.com", "base_urls": ["https://www.baslerweb.com/en-us/learning/cmos-rolling-shutter-cameras/"], "source_type": "camera_basics", "priority": 3, "crawl_strategy": "seed_urls", "max_pages": 5, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
    {"source_name": "LUCID Vision Labs", "domain": "thinklucid.com", "base_urls": ["https://thinklucid.com/tech-briefs/understanding-image-sensors/"], "source_type": "camera_basics", "priority": 3, "crawl_strategy": "seed_urls", "max_pages": 4, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
    {"source_name": "STEMMER IMAGING", "domain": "stemmer-imaging.com", "base_urls": ["https://www.stemmer-imaging.com/en/products/illumination"], "source_type": "knowledge_base", "priority": 3, "crawl_strategy": "seed_urls", "max_pages": 6, "notes": "Fallback allowlist entry used when PyYAML is unavailable."},
]


def load_allowlist(path: Path = ALLOWLIST_PATH) -> list[dict[str, Any]]:
    if not path.exists() or yaml is None or not hasattr(yaml, "safe_load"):
        return FALLBACK_SOURCES
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("sources", []))


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _upsert_source(conn, source: dict[str, Any]) -> int:
    allowed = 0 if source.get("crawl_strategy") == "manual_review_only" else 1
    conn.execute(
        """
        INSERT INTO knowledge_sources
            (source_name, domain, source_type, priority, allowed_to_crawl, license_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name, domain) DO UPDATE SET
            source_type=excluded.source_type,
            priority=excluded.priority,
            allowed_to_crawl=excluded.allowed_to_crawl,
            notes=excluded.notes
        """,
        (
            source.get("source_name"),
            source.get("domain"),
            source.get("source_type"),
            int(source.get("priority") or 5),
            allowed,
            "unknown",
            source.get("notes"),
        ),
    )
    row = conn.execute(
        "SELECT id FROM knowledge_sources WHERE source_name = ? AND domain = ?",
        (source.get("source_name"), source.get("domain")),
    ).fetchone()
    return int(row[0])


def _insert_log(conn, url: str, source_name: str, status: str, http_status: int | None = None, error_message: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO knowledge_crawl_log (url, source_name, status, http_status, error_message, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (url, source_name, status, http_status, error_message, _now()),
    )


def _insert_document(conn, source_id: int, source_name: str, doc: dict[str, Any]) -> bool:
    clean = (doc.get("clean_markdown") or doc.get("raw_text") or "").strip()
    if not clean:
        return False
    content_hash = _content_hash(clean)
    existing = conn.execute(
        "SELECT id, content_hash FROM knowledge_documents WHERE url = ?",
        (doc.get("url"),),
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        _insert_log(conn, doc.get("url"), source_name, "duplicate", None, "URL and content hash already present")
        return False
    conn.execute(
        """
        INSERT INTO knowledge_documents
            (source_id, title, url, author, publisher, published_date, retrieved_at, language,
             content_type, raw_text, clean_markdown, summary, quality_score, review_status, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            author=excluded.author,
            publisher=excluded.publisher,
            published_date=excluded.published_date,
            retrieved_at=excluded.retrieved_at,
            language=excluded.language,
            content_type=excluded.content_type,
            raw_text=excluded.raw_text,
            clean_markdown=excluded.clean_markdown,
            summary=excluded.summary,
            quality_score=excluded.quality_score,
            review_status=excluded.review_status,
            content_hash=excluded.content_hash
        """,
        (
            source_id,
            doc.get("title"),
            doc.get("url"),
            doc.get("author"),
            doc.get("publisher") or source_name,
            doc.get("published_date"),
            doc.get("retrieved_at") or _now(),
            doc.get("language") or "en",
            doc.get("content_type") or "html",
            doc.get("raw_text") or clean,
            clean,
            doc.get("summary") or _make_summary(clean),
            float(doc.get("quality_score") or _quality_score(clean)),
            doc.get("review_status") or "pending",
            content_hash,
        ),
    )
    _insert_log(conn, doc.get("url"), source_name, "saved", None, None)
    return True


def _quality_score(text: str) -> float:
    length = len(text or "")
    score = min(70.0, length / 40.0)
    keywords = ["lighting", "illumination", "camera", "lens", "vision", "backlight", "shutter", "光"]
    score += sum(4 for keyword in keywords if keyword.lower() in (text or "").lower())
    return min(100.0, score)


def _make_summary(text: str, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) > limit:
            break
        summary = (summary + " " + sentence).strip()
    return summary or text[:limit]


def _robots_allowed(url: str) -> tuple[bool, str | None]:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, "invalid url"
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        with urllib.request.urlopen(urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT}), timeout=8) as response:
            content = response.read().decode("utf-8", errors="ignore").splitlines()
        parser.parse(content)
        return bool(parser.can_fetch(USER_AGENT, url)), None
    except Exception as exc:
        return True, f"robots check failed, allowed cautiously: {exc}"


def _fetch_url(url: str) -> tuple[int | None, str, str | None]:
    try:
        import requests  # type: ignore

        firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        if firecrawl_key:
            fc_response = requests.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"Authorization": f"Bearer {firecrawl_key}", "Content-Type": "application/json"},
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": 60000},
                timeout=80,
            )
            if fc_response.status_code < 400:
                data = fc_response.json()
                markdown = ""
                if isinstance(data.get("data"), dict):
                    markdown = data["data"].get("markdown") or ""
                markdown = markdown or data.get("markdown") or ""
                if markdown:
                    return fc_response.status_code, markdown, None
            return fc_response.status_code, "", f"Firecrawl scrape failed: {fc_response.text[:300]}"

        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400:
            return response.status_code, "", f"HTTP {response.status_code}"
        if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
            return response.status_code, "", "PDF extraction skipped in pilot crawler"
        return response.status_code, response.text, None
    except Exception as exc:
        return None, "", str(exc)


def _extract_html(url: str, html: str, source_name: str) -> dict[str, Any]:
    title = None
    clean = ""
    try:
        import trafilatura  # type: ignore

        extracted = trafilatura.extract(html, url=url, output_format="markdown", include_links=False, favor_precision=True)
        if extracted:
            clean = extracted.strip()
    except Exception:
        clean = ""
    if not clean:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.text:
                title = soup.title.text.strip()
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.extract()
            clean = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        except Exception:
            clean = re.sub(r"<[^>]+>", " ", html)
            clean = re.sub(r"\s+", " ", clean).strip()
    if not title:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", match.group(1)).strip() if match else urllib.parse.urlparse(url).path.strip("/").split("/")[-1]
    return {
        "title": title or url,
        "url": url,
        "publisher": source_name,
        "language": "en",
        "content_type": "html",
        "raw_text": clean,
        "clean_markdown": clean,
        "summary": _make_summary(clean),
        "quality_score": _quality_score(clean),
        "review_status": "pending",
    }


def _candidate_urls(source: dict[str, Any]) -> list[str]:
    urls = [str(url) for url in source.get("base_urls", []) if str(url).startswith("http")]
    return urls[: int(source.get("max_pages") or len(urls) or 1)]


def _load_seed_docs(limit: int | None = None, source_name: str | None = None) -> list[dict[str, Any]]:
    if not SEED_PATH.exists():
        return []
    docs = []
    for line in SEED_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        if source_name and doc.get("source_name") != source_name:
            continue
        doc["retrieved_at"] = _now()
        doc["review_status"] = "pending"
        doc["quality_score"] = doc.get("quality_score") or _quality_score(doc.get("clean_markdown", ""))
        docs.append(doc)
        if limit and len(docs) >= limit:
            break
    return docs


def crawl(limit: int | None = None, source_filter: str | None = None, dry_run: bool = False, seed_fallback: bool = True) -> dict[str, Any]:
    db_path = knowledge_engine.ensure_knowledge_schema()
    allowlist = load_allowlist()
    if source_filter:
        allowlist = [source for source in allowlist if source_filter.lower() in str(source.get("source_name", "")).lower()]
    planned: list[tuple[dict[str, Any], str]] = []
    for source in allowlist:
        if source.get("crawl_strategy") == "manual_review_only":
            continue
        for url in _candidate_urls(source):
            if _domain(url) != str(source.get("domain", "")).lower().replace("www.", "") and not _domain(url).endswith(str(source.get("domain", "")).lower().replace("www.", "")):
                continue
            planned.append((source, url))
            if limit and len(planned) >= limit:
                break
        if limit and len(planned) >= limit:
            break

    if dry_run:
        return {
            "db_path": str(db_path),
            "planned_urls": [url for _, url in planned],
            "planned_count": len(planned),
            "seed_fallback_available": SEED_PATH.exists(),
        }

    saved = 0
    failed = 0
    with knowledge_engine.connect(db_path) as conn:
        source_ids = {source.get("source_name"): _upsert_source(conn, source) for source in allowlist}
        for source, url in planned:
            source_name = source.get("source_name")
            source_id = source_ids[source_name]
            allowed, robots_note = _robots_allowed(url)
            if not allowed:
                _insert_log(conn, url, source_name, "robots_disallowed", None, robots_note)
                failed += 1
                continue
            status, html, error = _fetch_url(url)
            if error or not html:
                _insert_log(conn, url, source_name, "fetch_failed", status, error)
                failed += 1
            else:
                doc = _extract_html(url, html, source_name)
                if _insert_document(conn, source_id, source_name, doc):
                    saved += 1
                else:
                    failed += 1
            conn.commit()
            time.sleep(1.0 + random.random())

        if saved == 0 and seed_fallback:
            seed_docs = _load_seed_docs(limit=limit, source_name=source_filter)
            source_lookup = {source.get("source_name"): _upsert_source(conn, source) for source in load_allowlist()}
            for doc in seed_docs:
                source_name = doc.get("source_name")
                source_id = source_lookup.get(source_name)
                if source_id and _insert_document(conn, source_id, source_name, doc):
                    saved += 1
            conn.commit()

    return {"db_path": str(db_path), "planned_count": len(planned), "saved_documents": saved, "failed_or_skipped": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl allowlisted machine vision knowledge sources.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-seed-fallback", action="store_true")
    args = parser.parse_args()
    result = crawl(limit=args.limit, source_filter=args.source, dry_run=args.dry_run, seed_fallback=not args.no_seed_fallback)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
