from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import knowledge_engine


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "knowledge_quality_report.md"
ISSUES_PATH = ROOT / "knowledge_issues.csv"


def _issue(issue_type: str, severity: str, document_id: Any, title: str, url: str, detail: str, suggested_fix: str) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "document_id": document_id,
        "title": title,
        "url": url,
        "detail": detail,
        "suggested_fix": suggested_fix,
        "status": "open",
    }


def generate() -> dict[str, Any]:
    knowledge_engine.ensure_knowledge_schema()
    issues: list[dict[str, Any]] = []
    with knowledge_engine.connect() as conn:
        docs = [dict(row) for row in conn.execute(
            """
            SELECT kd.*, ks.source_name, ks.license_status
            FROM knowledge_documents kd
            LEFT JOIN knowledge_sources ks ON ks.id = kd.source_id
            ORDER BY kd.id
            """
        ).fetchall()]
        cards = [dict(row) for row in conn.execute("SELECT * FROM knowledge_cards").fetchall()]
        chunks = [dict(row) for row in conn.execute("SELECT * FROM knowledge_chunks").fetchall()]
        sources = [dict(row) for row in conn.execute("SELECT * FROM knowledge_sources").fetchall()]
        logs = [dict(row) for row in conn.execute("SELECT * FROM knowledge_crawl_log").fetchall()]

    doc_ids_with_cards = set()
    for card in cards:
        try:
            doc_ids_with_cards.update(json.loads(card.get("source_document_ids") or "[]"))
        except Exception:
            pass
    seen_hashes: dict[str, int] = {}
    for doc in docs:
        doc_id = doc.get("id")
        title = doc.get("title") or ""
        url = doc.get("url") or ""
        text = doc.get("clean_markdown") or doc.get("raw_text") or ""
        if not url:
            issues.append(_issue("missing_source_url", "high", doc_id, title, url, "Document has no source URL.", "Add source_url or remove the document."))
        if not title:
            issues.append(_issue("missing_title", "medium", doc_id, title, url, "Document has no title.", "Extract or manually add a title."))
        if len(text.strip()) < 200:
            issues.append(_issue("short_body", "medium", doc_id, title, url, f"Body length is {len(text.strip())}.", "Re-crawl with better extraction or mark as source-link-only."))
        if doc.get("review_status") == "rejected_irrelevant":
            issues.append(_issue("irrelevant_content", "high", doc_id, title, url, "Document was marked irrelevant by rules.", "Remove from knowledge base or adjust allowlist."))
        content_hash = doc.get("content_hash")
        if content_hash:
            if content_hash in seen_hashes:
                issues.append(_issue("duplicate_document", "medium", doc_id, title, url, f"Duplicate of document {seen_hashes[content_hash]}.", "Keep one canonical URL."))
            seen_hashes[content_hash] = doc_id
        if (doc.get("license_status") or "unknown") == "unknown":
            issues.append(_issue("license_unknown", "low", doc_id, title, url, "License status is unknown.", "Review source license before external use."))
        tags_missing = True
        for chunk in chunks:
            if chunk.get("document_id") == doc_id and chunk.get("tags_json") not in (None, "", "[]"):
                tags_missing = False
                break
        if tags_missing:
            issues.append(_issue("missing_tags", "medium", doc_id, title, url, "No tags were generated.", "Review taxonomy rules or manually tag."))
        if doc_id not in doc_ids_with_cards:
            issues.append(_issue("missing_knowledge_card", "medium", doc_id, title, url, "No knowledge card points to this document.", "Run extract_knowledge.py or create a manual card."))
        try:
            if float(doc.get("quality_score") or 0) < 40:
                issues.append(_issue("low_quality_score", "medium", doc_id, title, url, f"quality_score={doc.get('quality_score')}", "Review extraction quality and relevance."))
        except Exception:
            issues.append(_issue("low_quality_score", "medium", doc_id, title, url, "quality_score unavailable.", "Set quality score during extraction."))

    for log in logs:
        if log.get("status") == "robots_disallowed":
            issues.append(_issue("robots_disallowed", "high", "", "", log.get("url") or "", log.get("error_message") or "Robots disallowed.", "Do not crawl this URL unless policy changes."))

    issue_counts = Counter(issue["issue_type"] for issue in issues)
    severity_counts = Counter(issue["severity"] for issue in issues)
    topic_counts: Counter[str] = Counter()
    for card in cards:
        try:
            topic_counts.update(json.loads(card.get("tags_json") or "[]"))
        except Exception:
            pass

    with ISSUES_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["issue_type", "severity", "document_id", "title", "url", "detail", "suggested_fix", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

    report = [
        "# IOO Knowledge Base Quality Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        f"- Knowledge sources: {len(sources)}",
        f"- Knowledge documents: {len(docs)}",
        f"- Knowledge cards: {len(cards)}",
        f"- Knowledge chunks: {len(chunks)}",
        f"- Issues: {len(issues)}",
        "",
        "## Issues By Severity",
        "",
    ]
    for severity, count in sorted(severity_counts.items()):
        report.append(f"- {severity}: {count}")
    report.extend(["", "## Issues By Type", ""])
    for issue_type, count in issue_counts.most_common():
        report.append(f"- {issue_type}: {count}")
    report.extend(["", "## Top Tags", ""])
    for tag, count in topic_counts.most_common(20):
        report.append(f"- {tag}: {count}")
    report.extend(["", "## Notes", "", "- Pilot documents remain pending review until a human verifies source suitability and licensing.", "- Answers must cite source URLs and should not republish full third-party articles."])
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    return {
        "sources": len(sources),
        "documents": len(docs),
        "cards": len(cards),
        "chunks": len(chunks),
        "issues": len(issues),
        "issue_counts": dict(issue_counts),
        "severity_counts": dict(severity_counts),
    }


def main() -> None:
    print(json.dumps(generate(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
