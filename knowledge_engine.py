from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB_CANDIDATES = [
    ROOT / "data" / "ioo_product_test.db",
    ROOT / "ioo_product_test.db",
    ROOT / "ioo_knowledge.db",
]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    domain TEXT,
    source_type TEXT,
    priority INTEGER DEFAULT 5,
    allowed_to_crawl INTEGER DEFAULT 1,
    license_status TEXT DEFAULT 'unknown',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_name, domain)
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    title TEXT,
    url TEXT UNIQUE,
    author TEXT,
    publisher TEXT,
    published_date TEXT,
    retrieved_at TEXT,
    language TEXT,
    content_type TEXT,
    raw_text TEXT,
    clean_markdown TEXT,
    summary TEXT,
    quality_score REAL DEFAULT 0,
    review_status TEXT DEFAULT 'pending',
    content_hash TEXT,
    FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    chunk_index INTEGER,
    chunk_text TEXT,
    token_count INTEGER,
    embedding_id TEXT,
    tags_json TEXT,
    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
);

CREATE TABLE IF NOT EXISTS knowledge_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    summary TEXT,
    lighting_type TEXT,
    camera_topic TEXT,
    lens_topic TEXT,
    application TEXT,
    material TEXT,
    defect_type TEXT,
    recommendation_logic TEXT,
    cautions TEXT,
    source_document_ids TEXT,
    verified_status TEXT DEFAULT 'pending',
    tags_json TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_crawl_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT,
    source_name TEXT,
    status TEXT,
    http_status INTEGER,
    error_message TEXT,
    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


TERM_EXPANSIONS: dict[str, list[str]] = {
    "metal scratch": ["scratch", "dark field", "low angle", "metal", "surface defect"],
    "金属划痕": ["scratch", "dark field", "low angle", "metal", "surface defect"],
    "划痕": ["scratch", "dark field", "surface defect"],
    "glass scratch": ["scratch", "dark field", "glass", "surface defect", "polarized"],
    "玻璃划痕": ["scratch", "dark field", "glass", "surface defect", "polarized"],
    "transparent edge": ["transparent", "edge", "backlight", "silhouette"],
    "透明": ["transparent", "edge", "backlight", "silhouette"],
    "边缘": ["edge", "backlight", "silhouette"],
    "背光": ["backlight", "edge", "silhouette", "measurement"],
    "同轴": ["coaxial", "in-line", "flat reflective"],
    "暗场": ["dark field", "low angle", "scratch"],
    "明场": ["bright field", "front lighting"],
    "环形": ["ring light", "bright field"],
    "条形": ["bar light", "directional"],
    "偏振": ["polarized", "glare", "reflective"],
    "uv": ["uv", "fluorescence"],
    "ir": ["ir", "infrared"],
    "相机分辨率": ["resolution", "pixel size", "field of view"],
    "global shutter": ["global shutter", "motion"],
    "rolling shutter": ["rolling shutter", "motion distortion"],
    "工作距离": ["working distance", "field of view", "focal length"],
    "视野": ["field of view", "focal length", "sensor size"],
    "pcb": ["pcb", "dome", "coaxial", "backlight", "surface inspection"],
}


def get_db_path() -> Path:
    for candidate in DB_CANDIDATES:
        if candidate.exists():
            return candidate
    return ROOT / "ioo_knowledge.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_knowledge_schema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else get_db_path()
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    return path


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def get_knowledge_stats(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_knowledge_schema(db_path)
    with connect(db_path) as conn:
        counts = {}
        for table in [
            "knowledge_sources",
            "knowledge_documents",
            "knowledge_chunks",
            "knowledge_cards",
            "knowledge_crawl_log",
        ]:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM knowledge_documents WHERE review_status = 'approved'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM knowledge_documents WHERE review_status != 'approved' OR review_status IS NULL").fetchone()[0]
    counts["approved_documents"] = approved
    counts["pending_review_documents"] = pending
    counts["db_path"] = str(get_db_path())
    return counts


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    words = re.findall(r"[a-z0-9][a-z0-9_+-]{1,}|[\u4e00-\u9fff]{2,}", text)
    expanded = list(words)
    for key, values in TERM_EXPANSIONS.items():
        if key.lower() in text:
            expanded.extend(values)
    return expanded


def _score(query_tokens: list[str], row: dict[str, Any]) -> float:
    haystack = " ".join(
        str(row.get(field) or "")
        for field in [
            "topic",
            "title",
            "summary",
            "recommendation_logic",
            "cautions",
            "tags_json",
            "clean_markdown",
            "chunk_text",
            "lighting_type",
            "camera_topic",
            "lens_topic",
            "application",
            "material",
            "defect_type",
        ]
    ).lower()
    if not haystack or not query_tokens:
        return 0.0
    counts = Counter(query_tokens)
    score = 0.0
    for token, count in counts.items():
        if token and token in haystack:
            score += 3.0 * count if len(token) > 3 else 1.0 * count
    for phrase in TERM_EXPANSIONS.values():
        phrase_text = " ".join(phrase).lower()
        if phrase_text and phrase_text in haystack:
            score += 1.0
    quality = row.get("quality_score")
    try:
        score += min(float(quality or 0), 100.0) / 50.0
    except Exception:
        pass
    return score


def _parse_json_list(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def search_knowledge(query: str, limit: int = 8) -> list[dict[str, Any]]:
    ensure_knowledge_schema()
    query_tokens = _tokenize(query)
    with connect() as conn:
        rows = _rows(
            conn,
            """
            SELECT kd.*, ks.source_name, ks.domain, ks.license_status
            FROM knowledge_documents kd
            LEFT JOIN knowledge_sources ks ON ks.id = kd.source_id
            """,
        )
    scored = []
    for row in rows:
        score = _score(query_tokens, row)
        if score > 0:
            row["score"] = round(score, 2)
            scored.append(row)
    scored.sort(key=lambda item: (-item["score"], -(item.get("quality_score") or 0), item.get("title") or ""))
    return scored[:limit]


def get_knowledge_cards(query: str, limit: int = 5) -> list[dict[str, Any]]:
    ensure_knowledge_schema()
    query_tokens = _tokenize(query)
    with connect() as conn:
        rows = _rows(conn, "SELECT * FROM knowledge_cards")
    scored = []
    for row in rows:
        score = _score(query_tokens, row)
        if score > 0:
            row["score"] = round(score, 2)
            row["tags"] = _parse_json_list(row.get("tags_json"))
            scored.append(row)
    scored.sort(key=lambda item: (-item["score"], item.get("topic") or ""))
    return scored[:limit]


def get_knowledge_sources(card_ids: list[int] | None = None) -> list[dict[str, Any]]:
    ensure_knowledge_schema()
    with connect() as conn:
        if card_ids:
            placeholders = ",".join("?" for _ in card_ids)
            cards = _rows(conn, f"SELECT source_document_ids FROM knowledge_cards WHERE id IN ({placeholders})", tuple(card_ids))
            doc_ids: list[int] = []
            for card in cards:
                doc_ids.extend(int(item) for item in _parse_json_list(card.get("source_document_ids")) if str(item).isdigit())
            if not doc_ids:
                return []
            placeholders = ",".join("?" for _ in doc_ids)
            rows = _rows(
                conn,
                f"""
                SELECT kd.id, kd.title, kd.url, kd.publisher, kd.review_status, ks.source_name, ks.license_status
                FROM knowledge_documents kd
                LEFT JOIN knowledge_sources ks ON ks.id = kd.source_id
                WHERE kd.id IN ({placeholders})
                """,
                tuple(doc_ids),
            )
        else:
            rows = _rows(
                conn,
                """
                SELECT kd.id, kd.title, kd.url, kd.publisher, kd.review_status, ks.source_name, ks.license_status
                FROM knowledge_documents kd
                LEFT JOIN knowledge_sources ks ON ks.id = kd.source_id
                ORDER BY kd.quality_score DESC, kd.id
                LIMIT 10
                """,
            )
    seen = set()
    sources = []
    for row in rows:
        url = row.get("url")
        if url and url not in seen:
            sources.append(
                {
                    "type": "knowledge_source",
                    "title": row.get("title") or row.get("source_name") or "knowledge source",
                    "url": url,
                    "source_name": row.get("source_name"),
                    "review_status": row.get("review_status") or "pending",
                    "license_status": row.get("license_status") or "unknown",
                }
            )
            seen.add(url)
    return sources


def retrieve_knowledge_for_question(question: str, limit: int = 5) -> dict[str, Any]:
    cards = get_knowledge_cards(question, limit=limit)
    if not cards:
        docs = search_knowledge(question, limit=limit)
        sources = [
            {
                "type": "knowledge_source",
                "title": row.get("title") or row.get("source_name") or "knowledge source",
                "url": row.get("url"),
                "source_name": row.get("source_name"),
                "review_status": row.get("review_status") or "pending",
                "license_status": row.get("license_status") or "unknown",
            }
            for row in docs
            if row.get("url")
        ]
        return {"cards": [], "documents": docs, "sources": sources, "knowledge_answer": _compose_doc_answer(question, docs)}
    sources = get_knowledge_sources([int(card["id"]) for card in cards if card.get("id")])
    return {"cards": cards, "documents": [], "sources": sources, "knowledge_answer": _compose_card_answer(question, cards)}


def _is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _compose_card_answer(question: str, cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "当前知识库还没有可引用的资料。" if _is_chinese(question) else "No relevant knowledge source is available in the current knowledge base."
    top = cards[:3]
    if _is_chinese(question):
        parts = ["知识库检索到的选型逻辑："]
        for card in top:
            logic = card.get("recommendation_logic") or card.get("summary") or ""
            parts.append(f"- {card.get('topic')}: {logic}")
        parts.append("以上内容需要结合样品、几何结构、工作距离、相机/镜头和实际成像验证。")
        return "\n".join(parts)
    parts = ["Knowledge-base selection logic:"]
    for card in top:
        logic = card.get("recommendation_logic") or card.get("summary") or ""
        parts.append(f"- {card.get('topic')}: {logic}")
    parts.append("Validate this with sample parts, geometry, working distance, camera/lens setup, and actual images.")
    return "\n".join(parts)


def _compose_doc_answer(question: str, docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "当前知识库还没有可引用的资料。" if _is_chinese(question) else "No relevant knowledge source is available in the current knowledge base."
    if _is_chinese(question):
        parts = ["知识库找到相关资料，但还没有生成完整知识卡："]
        for doc in docs[:3]:
            parts.append(f"- {doc.get('title')}: {doc.get('summary') or 'summary not available'}")
        return "\n".join(parts)
    parts = ["Relevant knowledge documents found, but no reviewed card has been generated yet:"]
    for doc in docs[:3]:
        parts.append(f"- {doc.get('title')}: {doc.get('summary') or 'summary not available'}")
    return "\n".join(parts)


def explain_lighting_selection(question: str) -> dict[str, Any]:
    return retrieve_knowledge_for_question(question, limit=5)


def explain_camera_selection(question: str) -> dict[str, Any]:
    return retrieve_knowledge_for_question(question, limit=5)


if __name__ == "__main__":
    ensure_knowledge_schema()
    print(json.dumps(get_knowledge_stats(), indent=2))
