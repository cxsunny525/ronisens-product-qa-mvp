from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dependency fallback
    yaml = None

import knowledge_engine


VISION_KEYWORDS = [
    "machine vision",
    "vision",
    "lighting",
    "illumination",
    "camera",
    "lens",
    "sensor",
    "backlight",
    "backlighting",
    "bright field",
    "brightfield",
    "dark field",
    "darkfield",
    "coaxial",
    "telecentric",
    "polarizer",
    "polarized",
    "wavelength",
    "shutter",
    "field of view",
    "working distance",
    "inspection",
]

TAG_RULES: dict[str, list[str]] = {
    "backlight": ["backlight", "silhouette", "edge"],
    "bright_field": ["bright field", "front lighting"],
    "dark_field": ["dark field", "low angle", "scratch"],
    "coaxial_light": ["coaxial", "in-line", "inline", "telecentric illumination"],
    "dome_light": ["dome", "diffuse"],
    "ring_light": ["ring light", "ring"],
    "bar_light": ["bar light", "bar"],
    "spot_light": ["spot light", "spot"],
    "polarized_light": ["polarized", "polarizer", "glare"],
    "uv_light": ["uv", "ultraviolet", "fluorescence"],
    "ir_light": ["ir", "infrared"],
    "structured_light": ["structured", "line lighting"],
    "scratch_detection": ["scratch", "surface defect"],
    "surface_inspection": ["surface", "texture", "defect"],
    "edge_detection": ["edge", "silhouette", "outline"],
    "measurement": ["measurement", "gauging", "metrology", "dimension"],
    "ocr": ["ocr", "text"],
    "transparent_object_inspection": ["transparent", "glass", "transmission"],
    "pcb_inspection": ["pcb", "circuit board"],
    "metal": ["metal", "reflective"],
    "glass": ["glass"],
    "transparent_material": ["transparent"],
    "reflective_surface": ["reflective", "glare", "specular"],
    "resolution": ["resolution", "line pair", "pixel"],
    "pixel_size": ["pixel size", "pixel"],
    "sensor_size": ["sensor size", "sensor format"],
    "global_shutter": ["global shutter"],
    "rolling_shutter": ["rolling shutter"],
    "frame_rate": ["frame rate", "fps"],
    "exposure": ["exposure", "strobe"],
    "focal_length": ["focal length"],
    "working_distance": ["working distance"],
    "field_of_view": ["field of view", "fov"],
    "telecentric_lens": ["telecentric"],
    "aperture": ["aperture", "f-number", "f/#"],
    "distortion": ["distortion", "perspective", "parallax"],
}


def _load_taxonomy() -> dict[str, list[str]]:
    path = knowledge_engine.ROOT / "knowledge_taxonomy.yaml"
    if not path.exists() or yaml is None or not hasattr(yaml, "safe_load"):
        return {
            "lighting_type": ["ring_light", "bar_light", "backlight", "coaxial_light", "dome_light", "dark_field", "bright_field", "line_scan_light", "spot_light", "polarized_light", "uv_light", "ir_light", "swir_light", "structured_light"],
            "application": ["scratch_detection", "surface_inspection", "edge_detection", "measurement", "ocr", "barcode", "transparent_object_inspection", "pcb_inspection", "semiconductor_inspection", "food_packaging", "pharmaceutical", "battery_inspection", "web_inspection"],
            "material": ["metal", "glass", "plastic", "paper", "ceramic", "rubber", "transparent_material", "reflective_surface", "matte_surface"],
            "camera_topic": ["sensor_size", "resolution", "frame_rate", "global_shutter", "rolling_shutter", "monochrome_vs_color", "exposure", "gain", "triggering", "interface", "pixel_size"],
            "lens_topic": ["focal_length", "working_distance", "field_of_view", "depth_of_field", "telecentric_lens", "distortion", "aperture", "c_mount"],
        }
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _is_relevant(text: str) -> bool:
    lower = (text or "").lower()
    return sum(1 for keyword in VISION_KEYWORDS if keyword in lower) >= 2


def _tags_for_text(text: str) -> list[str]:
    lower = (text or "").lower()
    tags = []
    for tag, needles in TAG_RULES.items():
        if any(_needle_matches(lower, needle) for needle in needles):
            tags.append(tag)
    return sorted(set(tags))


def _needle_matches(lower_text: str, needle: str) -> bool:
    needle = needle.lower()
    if len(needle) <= 2 or needle in {"fov", "fps"}:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lower_text))
    return needle in lower_text


def _first_tag(tags: list[str], allowed: list[str]) -> str | None:
    for tag in tags:
        if tag in allowed:
            return tag
    return None


def _summary(text: str, existing: str | None = None) -> str:
    if existing and len(existing.strip()) > 40:
        return existing.strip()
    text = re.sub(r"\s+", " ", text or "").strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    output = []
    for sentence in sentences:
        if len(" ".join(output)) + len(sentence) > 480:
            break
        if sentence:
            output.append(sentence)
    return " ".join(output) or text[:480]


def _recommendation_logic(tags: list[str], summary: str) -> str:
    if "dark_field" in tags and "scratch_detection" in tags:
        return "Use low-angle dark-field lighting to make scratches, texture, and small height changes scatter light into the camera; verify glare and working distance on the real sample."
    if "backlight" in tags:
        return "Use backlighting when the target feature is an outline, edge, hole, gap, or dimensional silhouette; avoid it for front-surface print or texture unless combined with another light."
    if "coaxial_light" in tags:
        return "Use coaxial or in-line illumination for flat reflective surfaces, etched marks, low-contrast surface features, or shadow-sensitive inspection geometries."
    if "dome_light" in tags:
        return "Use diffuse dome lighting to reduce harsh reflections and shadows on curved or glossy surfaces, while checking that defect contrast remains sufficient."
    if "global_shutter" in tags:
        return "Prefer global shutter when the object or camera moves during exposure and geometric distortion must be avoided."
    if "rolling_shutter" in tags:
        return "Rolling shutter can be suitable for static or slow scenes, but moving targets may show skew or distortion."
    if "telecentric_lens" in tags:
        return "Use telecentric optics for high-accuracy measurement where perspective error or object height variation would hurt repeatability."
    return summary[:500]


def _chunk_text(text: str, max_words: int = 180) -> list[str]:
    words = (text or "").split()
    chunks = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start:start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks or ([text[:1200]] if text else [])


def extract(reset: bool = True) -> dict[str, Any]:
    taxonomy = _load_taxonomy()
    knowledge_engine.ensure_knowledge_schema()
    with knowledge_engine.connect() as conn:
        docs = [dict(row) for row in conn.execute("SELECT * FROM knowledge_documents ORDER BY id").fetchall()]
        if reset:
            conn.execute("DELETE FROM knowledge_chunks")
            conn.execute("DELETE FROM knowledge_cards")
        generated_cards = 0
        generated_chunks = 0
        skipped = 0
        topic_counts: dict[str, int] = defaultdict(int)
        for doc in docs:
            text = doc.get("clean_markdown") or doc.get("raw_text") or ""
            relevance_text = " ".join([doc.get("title") or "", doc.get("summary") or "", text])
            if not _is_relevant(relevance_text):
                conn.execute("UPDATE knowledge_documents SET review_status = ?, quality_score = ? WHERE id = ?", ("rejected_irrelevant", 10, doc["id"]))
                skipped += 1
                continue
            tags = _tags_for_text(relevance_text)
            summary = _summary(text, doc.get("summary"))
            quality = max(float(doc.get("quality_score") or 0), min(100.0, 35 + len(tags) * 7 + min(len(text), 2000) / 80))
            status = "pending" if doc.get("content_type") == "curated_source_note" else "pending"
            conn.execute(
                "UPDATE knowledge_documents SET summary = ?, quality_score = ?, review_status = ? WHERE id = ?",
                (summary, quality, status, doc["id"]),
            )
            for idx, chunk in enumerate(_chunk_text(text)):
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks (document_id, chunk_index, chunk_text, token_count, embedding_id, tags_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (doc["id"], idx, chunk, len(chunk.split()), None, json.dumps(tags)),
                )
                generated_chunks += 1
            lighting_type = _first_tag(tags, taxonomy.get("lighting_type", []))
            camera_topic = _first_tag(tags, taxonomy.get("camera_topic", []))
            lens_topic = _first_tag(tags, taxonomy.get("lens_topic", []))
            application = _first_tag(tags, taxonomy.get("application", []))
            material = _first_tag(tags, taxonomy.get("material", []))
            defect_type = "scratch" if "scratch_detection" in tags else None
            topic = doc.get("title") or "Untitled knowledge card"
            conn.execute(
                """
                INSERT INTO knowledge_cards
                    (topic, summary, lighting_type, camera_topic, lens_topic, application, material,
                     defect_type, recommendation_logic, cautions, source_document_ids, verified_status, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic,
                    summary,
                    lighting_type,
                    camera_topic,
                    lens_topic,
                    application,
                    material,
                    defect_type,
                    _recommendation_logic(tags, summary),
                    "Internal pilot card. Verify source details and sample images before using for final product selection.",
                    json.dumps([doc["id"]]),
                    "pending",
                    json.dumps(tags),
                ),
            )
            generated_cards += 1
            for tag in tags:
                topic_counts[tag] += 1
        conn.commit()
    return {
        "documents_seen": len(docs),
        "cards_generated": generated_cards,
        "chunks_generated": generated_chunks,
        "skipped_irrelevant": skipped,
        "top_tags": dict(sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))[:20]),
        "openai_available": bool(os.getenv("OPENAI_API_KEY")),
        "mode": "local_fallback",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract cards and chunks from IOO knowledge documents.")
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    print(json.dumps(extract(reset=not args.no_reset), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
