from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import knowledge_engine


SOURCE_NAME = "Edmund Optics"
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "knowledge" / "edmund"
DISCOVERED_PATH = RAW_DIR / "edmund_discovered_urls.json"
RAW_JSONL_PATH = RAW_DIR / "edmund_knowledge_raw.jsonl"
REPORT_PATH = ROOT / "EDMUND_KNOWLEDGE_IMPORT_REPORT.md"
ISSUES_PATH = ROOT / "edmund_knowledge_issues.csv"
INVENTORY_PATH = ROOT / "edmund_knowledge_inventory.csv"


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _json_load(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _load_discovered_count() -> int:
    if not DISCOVERED_PATH.exists():
        return 0
    try:
        data = json.loads(DISCOVERED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data.get("urls") or data.get("discovered_urls") or [])
    except Exception:
        return 0
    return 0


def _raw_record_count() -> int:
    if not RAW_JSONL_PATH.exists():
        return 0
    count = 0
    with RAW_JSONL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _source_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM knowledge_sources WHERE source_name = ?", (SOURCE_NAME,)).fetchone()
    return int(row["id"]) if row else None


def collect() -> dict[str, Any]:
    knowledge_engine.ensure_knowledge_schema()
    with knowledge_engine.connect() as conn:
        source_id = _source_id(conn)
        docs = _rows(
            conn,
            "SELECT * FROM knowledge_documents WHERE source_id = ? ORDER BY quality_score DESC, id",
            (source_id or -1,),
        )
        logs = _rows(conn, "SELECT * FROM knowledge_crawl_log WHERE source_name = ? ORDER BY id", (SOURCE_NAME,))
        all_chunks = _rows(
            conn,
            """
            SELECT kc.*, kd.title, kd.url
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kd.id = kc.document_id
            WHERE kd.source_id = ?
            """,
            (source_id or -1,),
        )
        all_cards = _rows(conn, "SELECT * FROM knowledge_cards ORDER BY id")

    doc_ids = {int(doc["id"]) for doc in docs}
    cards = []
    for card in all_cards:
        ids = [int(item) for item in _json_load(card.get("source_document_ids"), []) if str(item).isdigit()]
        if any(doc_id in doc_ids for doc_id in ids):
            cards.append(card)

    issues: list[dict[str, Any]] = []
    title_seen: Counter[str] = Counter((doc.get("title") or "").strip().lower() for doc in docs if doc.get("title"))
    hash_seen: Counter[str] = Counter((doc.get("content_hash") or "").strip() for doc in docs if doc.get("content_hash"))

    for doc in docs:
        title = doc.get("title") or ""
        url = doc.get("url") or ""
        text = doc.get("raw_text") or doc.get("clean_markdown") or ""
        if not title:
            issues.append(_issue("missing_title", "high", url, title, "Document has no extracted title.", "Review extraction or reject the document."))
        if len(text.strip()) < 500:
            issues.append(_issue("short_content", "medium", url, title, "Extracted content is shorter than 500 characters.", "Review extraction quality."))
        if (doc.get("review_status") or "") == "needs_review":
            issues.append(_issue("needs_review", "medium", url, title, "Document was imported as ambiguous or low-confidence relevance.", "Human review should decide whether to keep it."))
        if (doc.get("review_status") or "") == "rejected":
            issues.append(_issue("rejected", "low", url, title, "Document was rejected by relevance checks.", "No action unless this was expected to be relevant."))
        if title and title_seen[title.strip().lower()] > 1:
            issues.append(_issue("duplicate_title", "low", url, title, "More than one Edmund document has this title.", "Check canonical URL and content hash."))
        if doc.get("content_hash") and hash_seen[doc.get("content_hash")] > 1:
            issues.append(_issue("duplicate_content", "medium", url, title, "More than one Edmund document shares the same content hash.", "Keep one canonical document."))
        if not doc.get("url"):
            issues.append(_issue("missing_source_url", "high", url, title, "Document has no source URL.", "Do not expose without a source URL."))

    for log in logs:
        status = (log.get("status") or "").lower()
        if "robots" in status or "disallowed" in status:
            issues.append(_issue("robots_disallowed", "high", log.get("url") or "", "", "URL was blocked by robots rules.", "Do not crawl or import this URL."))
        if status in {"error", "failed", "fetch_error", "extract_error", "extract_failed", "discover_failed"}:
            issues.append(_issue("crawl_error", "medium", log.get("url") or "", "", log.get("error_message") or "Crawl failed.", "Retry later with crawl-delay respected."))

    tag_counts: Counter[str] = Counter()
    lighting_counts: Counter[str] = Counter()
    lens_counts: Counter[str] = Counter()
    filter_counts: Counter[str] = Counter()
    camera_counts: Counter[str] = Counter()
    for card in cards:
        tags = [str(tag) for tag in _json_load(card.get("tags_json"), [])]
        tag_counts.update(tags)
        if card.get("lighting_type"):
            lighting_counts.update([card["lighting_type"]])
        if card.get("lens_topic"):
            lens_counts.update([card["lens_topic"]])
        if card.get("camera_topic"):
            camera_counts.update([card["camera_topic"]])
        for tag in tags:
            if tag.startswith("filter_topic:"):
                filter_counts.update([tag.split(":", 1)[1]])

    successful_pages = len([log for log in logs if (log.get("status") or "").lower() in {"success", "imported", "updated", "skipped_existing"}])
    failed_pages = len(
        [
            log
            for log in logs
            if (log.get("status") or "").lower()
            in {"error", "failed", "fetch_error", "extract_error", "extract_failed", "discover_failed"}
        ]
    )
    robots_disallowed = len([issue for issue in issues if issue["issue_type"] == "robots_disallowed"])
    rejected_pages = len([doc for doc in docs if (doc.get("review_status") or "") == "rejected"])
    needs_review = len([doc for doc in docs if (doc.get("review_status") or "") == "needs_review"])
    unknown_license = len(docs)

    return {
        "discovered_urls": _load_discovered_count(),
        "raw_records": _raw_record_count(),
        "logs": logs,
        "successful_pages": successful_pages,
        "failed_pages": failed_pages,
        "robots_disallowed": robots_disallowed,
        "docs": docs,
        "chunks": all_chunks,
        "cards": cards,
        "issues": issues,
        "rejected_pages": rejected_pages,
        "needs_review": needs_review,
        "unknown_license": unknown_license,
        "tag_counts": tag_counts,
        "lighting_counts": lighting_counts,
        "lens_counts": lens_counts,
        "filter_counts": filter_counts,
        "camera_counts": camera_counts,
    }


def _issue(issue_type: str, severity: str, url: str, title: str, reason: str, suggested_fix: str) -> dict[str, str]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "url": url,
        "title": title,
        "source_name": SOURCE_NAME,
        "reason": reason,
        "suggested_fix": suggested_fix,
        "status": "open",
    }


def write_issues(issues: list[dict[str, Any]]) -> None:
    fieldnames = ["issue_type", "severity", "url", "title", "source_name", "reason", "suggested_fix", "status"]
    with ISSUES_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)


def write_inventory(docs: list[dict[str, Any]], cards: list[dict[str, Any]]) -> None:
    card_doc_ids: Counter[int] = Counter()
    for card in cards:
        for item in _json_load(card.get("source_document_ids"), []):
            if str(item).isdigit():
                card_doc_ids.update([int(item)])
    fieldnames = [
        "id",
        "title",
        "url",
        "publisher",
        "review_status",
        "quality_score",
        "content_length",
        "knowledge_cards",
        "retrieved_at",
    ]
    with INVENTORY_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for doc in docs:
            writer.writerow(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "url": doc.get("url"),
                    "publisher": doc.get("publisher") or SOURCE_NAME,
                    "review_status": doc.get("review_status"),
                    "quality_score": doc.get("quality_score"),
                    "content_length": len(doc.get("raw_text") or doc.get("clean_markdown") or ""),
                    "knowledge_cards": card_doc_ids[int(doc["id"])],
                    "retrieved_at": doc.get("retrieved_at"),
                }
            )


def _md_counter(counter: Counter[str], limit: int = 20) -> str:
    if not counter:
        return "- No entries recorded.\n"
    return "".join(f"- {name}: {count}\n" for name, count in counter.most_common(limit))


def write_report(data: dict[str, Any]) -> None:
    docs = data["docs"]
    cards = data["cards"]
    issues = data["issues"]
    high_value = sorted(docs, key=lambda row: float(row.get("quality_score") or 0), reverse=True)[:20]
    report = [
        "# Edmund Optics Knowledge Import Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        f"- Total discovered URLs: {data['discovered_urls']}",
        f"- Total raw crawl records: {data['raw_records']}",
        f"- Total crawl log rows: {len(data['logs'])}",
        f"- Successful crawl/import log rows: {data['successful_pages']}",
        f"- Failed crawl pages: {data['failed_pages']}",
        f"- Rejected pages: {data['rejected_pages']}",
        f"- Imported Edmund documents: {len(docs)}",
        f"- Generated chunks: {len(data['chunks'])}",
        f"- Generated knowledge cards: {len(cards)}",
        f"- Unknown license count: {data['unknown_license']}",
        f"- Robots-disallowed pages: {data['robots_disallowed']}",
        f"- Pages needing review: {data['needs_review']}",
        "",
        "## Top 20 Imported Edmund Articles By Estimated Relevance",
        "",
    ]
    if high_value:
        for doc in high_value:
            report.append(f"- {doc.get('title') or 'Untitled'} ({doc.get('quality_score') or 0}): {doc.get('url') or 'no URL'}")
    else:
        report.append("- No Edmund Optics documents are currently imported.")
    report.extend(
        [
            "",
            "## Topic Distribution",
            "",
            _md_counter(data["tag_counts"]),
            "## Lighting Topics Coverage",
            "",
            _md_counter(data["lighting_counts"]),
            "## Lens Topics Coverage",
            "",
            _md_counter(data["lens_counts"]),
            "## Filter Topics Coverage",
            "",
            _md_counter(data["filter_counts"]),
            "## Camera Topics Coverage",
            "",
            _md_counter(data["camera_counts"]),
            "## Rejected / Skipped Pages",
            "",
        ]
    )
    rejected = [doc for doc in docs if (doc.get("review_status") or "") == "rejected"][:20]
    if rejected:
        for doc in rejected:
            report.append(f"- {doc.get('title') or 'Untitled'}: {doc.get('url') or 'no URL'}")
    else:
        report.append("- No rejected Edmund documents recorded in the database.")
    report.extend(
        [
            "",
            "## Robots-Disallowed Pages",
            "",
        ]
    )
    robots = [issue for issue in issues if issue["issue_type"] == "robots_disallowed"]
    if robots:
        for issue in robots[:20]:
            report.append(f"- {issue['url']}")
    else:
        report.append("- No robots-disallowed Edmund pages were imported or crawled.")
    report.extend(
        [
            "",
            "## Pages Needing Review",
            "",
        ]
    )
    needs_review = [doc for doc in docs if (doc.get("review_status") or "") == "needs_review"][:20]
    if needs_review:
        for doc in needs_review:
            report.append(f"- {doc.get('title') or 'Untitled'}: {doc.get('url') or 'no URL'}")
    else:
        report.append("- No Edmund pages are currently marked needs_review.")
    report.extend(
        [
            "",
            "## Main Limitations",
            "",
            "- The crawler respects Edmund Optics robots.txt and a minimum 10 second crawl delay, so a full 150-page crawl takes at least 25 minutes.",
            "- Documents are stored for internal testing with `license_status = unknown` unless reviewed.",
            "- The Streamlit app displays summaries, tags, and source links; it does not present full Edmund articles as IOO-authored content.",
            "- If the local runtime has no outbound network access, the implemented crawler can be reviewed and run later from a network-enabled machine.",
            "",
            "## Investor Demo Readiness",
            "",
            "- Ready if at least several Edmund documents and source-linked cards are present and search returns Edmund sources.",
            "- Not ready as an Edmund-specific demo if zero Edmund documents were crawled in the current runtime.",
            "",
            "## Recommended Next Sources After Edmund",
            "",
            "- Smart Vision Lights technical notes",
            "- Cognex lighting and imaging fundamentals",
            "- Basler camera basics",
            "- LUCID Vision Labs technical articles",
        ]
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Edmund Optics knowledge quality reports.")
    parser.parse_args()
    data = collect()
    write_issues(data["issues"])
    write_inventory(data["docs"], data["cards"])
    write_report(data)
    print(
        json.dumps(
            {
                "report": str(REPORT_PATH),
                "issues": str(ISSUES_PATH),
                "inventory": str(INVENTORY_PATH),
                "documents": len(data["docs"]),
                "cards": len(data["cards"]),
                "issues_count": len(data["issues"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
