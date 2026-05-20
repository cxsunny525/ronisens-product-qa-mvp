from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import knowledge_engine


ROOT = Path(__file__).resolve().parent
RAW_PATH = ROOT / "data" / "knowledge" / "edmund" / "edmund_knowledge_raw.jsonl"
SOURCE_NAME = "Edmund Optics"
DOMAIN = "edmundoptics.com"

RELEVANCE_TERMS = [
    "machine vision",
    "imaging",
    "illumination",
    "lighting",
    "backlight",
    "brightfield",
    "darkfield",
    "coaxial",
    "telecentric",
    "lens",
    "focal length",
    "field of view",
    "working distance",
    "depth of field",
    "filter",
    "bandpass",
    "longpass",
    "shortpass",
    "polarization",
    "sensor",
    "camera",
    "resolution",
    "line scan",
    "inspection",
    "metrology",
    "contrast",
]

AMBIGUOUS_TERMS = ["optics", "image", "color", "light", "wavelength", "aperture", "distortion"]


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def make_summary(text: str, limit: int = 520) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    summary = ""
    for part in parts:
        if len(summary) + len(part) > limit:
            break
        summary = (summary + " " + part).strip()
    return summary or text[:limit]


def relevance_status(record: dict[str, Any]) -> tuple[str, float, str]:
    text = " ".join(
        str(record.get(key) or "")
        for key in ["title", "clean_text", "clean_markdown", "url", "canonical_url"]
    ).lower()
    strong = sum(1 for term in RELEVANCE_TERMS if term in text)
    weak = sum(1 for term in AMBIGUOUS_TERMS if term in text)
    length = len(record.get("clean_text") or record.get("clean_markdown") or "")
    if strong >= 2 and length >= 500:
        return "pending", min(100.0, 50 + strong * 6 + min(length, 4000) / 160), "Relevant machine vision/imaging knowledge article."
    if strong >= 1 or weak >= 3:
        return "needs_review", min(70.0, 30 + strong * 8 + weak * 3 + min(length, 2000) / 200), "Ambiguous but potentially relevant Edmund knowledge article."
    return "rejected", min(30.0, 10 + weak * 2), "Rejected by local relevance rules."


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def ensure_source(conn) -> int:
    conn.execute(
        """
        INSERT INTO knowledge_sources
            (source_name, domain, source_type, priority, allowed_to_crawl, license_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name, domain) DO UPDATE SET
            source_type=excluded.source_type,
            priority=excluded.priority,
            allowed_to_crawl=excluded.allowed_to_crawl,
            license_status=excluded.license_status,
            notes=excluded.notes
        """,
        (
            SOURCE_NAME,
            DOMAIN,
            "knowledge_articles",
            1,
            1,
            "unknown",
            "Edmund Optics public Knowledge Center and application notes. Crawl-delay 10 seconds respected by crawler.",
        ),
    )
    row = conn.execute(
        "SELECT id FROM knowledge_sources WHERE source_name = ? AND domain = ?",
        (SOURCE_NAME, DOMAIN),
    ).fetchone()
    return int(row[0])


def import_records(path: Path = RAW_PATH, force: bool = False) -> dict[str, Any]:
    knowledge_engine.ensure_knowledge_schema()
    records = load_records(path)
    inserted = 0
    updated = 0
    skipped_reviewed = 0
    rejected = 0
    needs_review = 0
    duplicates = 0
    with knowledge_engine.connect() as conn:
        source_id = ensure_source(conn)
        seen_hashes: set[str] = set()
        existing_hashes = {
            row[0]
            for row in conn.execute(
                "SELECT content_hash FROM knowledge_documents WHERE content_hash IS NOT NULL AND content_hash != ''"
            ).fetchall()
        }
        for record in records:
            url = record.get("canonical_url") or record.get("url")
            clean_text = record.get("clean_text") or record.get("clean_markdown") or ""
            clean_markdown = record.get("clean_markdown") or clean_text
            if not url or not clean_text.strip():
                continue
            digest = record.get("content_hash") or sha256_text(clean_text)
            if digest in seen_hashes:
                duplicates += 1
                continue
            seen_hashes.add(digest)
            review_status, quality, reason = relevance_status(record)
            if review_status == "rejected":
                rejected += 1
            elif review_status == "needs_review":
                needs_review += 1
            existing = conn.execute("SELECT id, review_status, content_hash FROM knowledge_documents WHERE url = ?", (url,)).fetchone()
            if existing and existing["review_status"] in {"approved", "verified"} and not force:
                skipped_reviewed += 1
                continue
            if existing is None and digest in existing_hashes:
                duplicates += 1
                continue
            params = (
                source_id,
                record.get("title") or url,
                url,
                record.get("author"),
                record.get("publisher") or SOURCE_NAME,
                record.get("published_date"),
                record.get("retrieved_at"),
                record.get("language") or "en",
                record.get("content_type") or "text/html",
                clean_text,
                clean_markdown,
                make_summary(clean_text),
                quality,
                review_status,
                digest,
            )
            conn.execute(
                """
                INSERT INTO knowledge_documents
                    (source_id, title, url, author, publisher, published_date, retrieved_at, language,
                     content_type, raw_text, clean_markdown, summary, quality_score, review_status, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source_id=excluded.source_id,
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
                params,
            )
            if existing:
                updated += 1
            else:
                inserted += 1
            conn.execute(
                """
                INSERT INTO knowledge_crawl_log (url, source_name, status, http_status, error_message, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (url, SOURCE_NAME, f"imported_{review_status}", None, reason, record.get("retrieved_at")),
            )
        conn.commit()
    return {
        "raw_records": len(records),
        "inserted_documents": inserted,
        "updated_documents": updated,
        "skipped_reviewed": skipped_reviewed,
        "duplicates": duplicates,
        "rejected": rejected,
        "needs_review": needs_review,
        "raw_path": str(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import raw Edmund Optics knowledge records into SQLite knowledge tables.")
    parser.add_argument("--raw", default=str(RAW_PATH))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(json.dumps(import_records(Path(args.raw), force=args.force), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
