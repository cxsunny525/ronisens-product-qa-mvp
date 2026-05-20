from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import knowledge_engine


SOURCE_NAME = "Edmund Optics"

TAG_RULES: dict[str, list[str]] = {
    "backlight": ["backlight", "backlighting", "silhouette"],
    "brightfield": ["brightfield", "bright field"],
    "darkfield": ["darkfield", "dark field", "low angle"],
    "coaxial_light": ["coaxial"],
    "inline_illumination": ["in-line", "inline illumination", "in line illumination"],
    "telecentric_illumination": ["telecentric illumination", "in-line telecentric"],
    "ring_light": ["ring light", "ring illumination"],
    "dome_light": ["dome light", "dome illumination", "diffuse dome"],
    "bar_light": ["bar light", "bar illumination"],
    "line_scan_light": ["line scan", "line-scan"],
    "polarized_light": ["polarized", "polarizer", "polarization"],
    "uv_light": ["uv", "ultraviolet"],
    "ir_light": ["ir ", "infrared"],
    "structured_light": ["structured light"],
    "scratch_detection": ["scratch", "scratches"],
    "surface_inspection": ["surface inspection", "surface defect", "surface"],
    "edge_detection": ["edge", "outline", "silhouette"],
    "measurement": ["measurement", "measure"],
    "metrology": ["metrology", "gauging"],
    "ocr": ["ocr", "optical character"],
    "barcode": ["barcode", "bar code"],
    "transparent_object_inspection": ["transparent", "glass edge"],
    "reflective_surface_inspection": ["reflective", "glare", "specular"],
    "line_scan_inspection": ["line scan", "web inspection"],
    "metal": ["metal", "metallic"],
    "glass": ["glass"],
    "plastic": ["plastic"],
    "transparent_material": ["transparent"],
    "reflective_surface": ["reflective", "specular", "glare"],
    "matte_surface": ["matte"],
    "color_filter": ["color filter", "colored glass"],
    "bandpass_filter": ["bandpass", "band-pass"],
    "longpass_filter": ["longpass", "long-pass"],
    "shortpass_filter": ["shortpass", "short-pass"],
    "notch_filter": ["notch filter"],
    "neutral_density_filter": ["neutral density", "nd filter"],
    "polarization_filter": ["polarization filter", "polarizing filter", "polarizer"],
    "ir_cut_filter": ["ir cut", "infrared cut"],
    "interference_filter": ["interference filter"],
    "coated_filter": ["coated filter", "hard coated"],
    "colored_glass_filter": ["colored glass filter"],
    "sensor_size": ["sensor size", "sensor format"],
    "resolution": ["resolution", "resolving"],
    "frame_rate": ["frame rate", "fps"],
    "global_shutter": ["global shutter"],
    "rolling_shutter": ["rolling shutter"],
    "monochrome_vs_color": ["monochrome", "color camera"],
    "exposure": ["exposure", "exposure time"],
    "gain": ["gain"],
    "triggering": ["trigger", "triggering"],
    "pixel_size": ["pixel size", "pixel"],
    "focal_length": ["focal length"],
    "working_distance": ["working distance"],
    "field_of_view": ["field of view", "fov"],
    "depth_of_field": ["depth of field", "dof"],
    "telecentric_lens": ["telecentric lens", "telecentricity"],
    "fixed_focal_length_lens": ["fixed focal length", "fixed focal"],
    "variable_magnification_lens": ["variable magnification", "zoom lens"],
    "distortion": ["distortion"],
    "aperture": ["aperture"],
    "f_number": ["f-number", "f/#", "f number"],
    "c_mount": ["c-mount", "c mount"],
}

LIGHTING_TYPES = {
    "backlight",
    "brightfield",
    "darkfield",
    "coaxial_light",
    "inline_illumination",
    "telecentric_illumination",
    "ring_light",
    "dome_light",
    "bar_light",
    "line_scan_light",
    "polarized_light",
    "uv_light",
    "ir_light",
    "swir_light",
    "structured_light",
}
APPLICATIONS = {
    "scratch_detection",
    "surface_inspection",
    "edge_detection",
    "measurement",
    "metrology",
    "ocr",
    "barcode",
    "transparent_object_inspection",
    "reflective_surface_inspection",
    "pcb_inspection",
    "semiconductor_inspection",
    "food_packaging",
    "pharmaceutical",
    "battery_inspection",
    "web_inspection",
    "line_scan_inspection",
}
MATERIALS = {"metal", "glass", "plastic", "paper", "ceramic", "rubber", "transparent_material", "reflective_surface", "matte_surface"}
FILTER_TOPICS = {
    "color_filter",
    "bandpass_filter",
    "longpass_filter",
    "shortpass_filter",
    "notch_filter",
    "neutral_density_filter",
    "polarization_filter",
    "ir_cut_filter",
    "interference_filter",
    "coated_filter",
    "colored_glass_filter",
}
CAMERA_TOPICS = {
    "sensor_size",
    "resolution",
    "frame_rate",
    "global_shutter",
    "rolling_shutter",
    "monochrome_vs_color",
    "exposure",
    "gain",
    "triggering",
    "interface",
    "pixel_size",
}
LENS_TOPICS = {
    "focal_length",
    "working_distance",
    "field_of_view",
    "depth_of_field",
    "telecentric_lens",
    "fixed_focal_length_lens",
    "variable_magnification_lens",
    "distortion",
    "aperture",
    "f_number",
    "c_mount",
}


def tag_text(text: str) -> list[str]:
    lower = (text or "").lower()
    tags = []
    for tag, needles in TAG_RULES.items():
        for needle in needles:
            if len(needle.strip()) <= 3:
                if re.search(rf"(?<![a-z0-9]){re.escape(needle.strip())}(?![a-z0-9])", lower):
                    tags.append(tag)
                    break
            elif needle in lower:
                tags.append(tag)
                break
    return sorted(set(tags))


def first(tags: list[str], allowed: set[str]) -> str | None:
    for tag in tags:
        if tag in allowed:
            return tag
    return None


def summary_from_text(text: str, existing: str | None = None, limit: int = 700) -> str:
    if existing and len(existing.strip()) >= 120:
        return existing.strip()
    text = re.sub(r"\s+", " ", text or "").strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = ""
    for sentence in sentences:
        if len(result) + len(sentence) > limit:
            break
        result = (result + " " + sentence).strip()
    return result or text[:limit]


def chunk_text(text: str, max_words: int = 220) -> list[str]:
    words = (text or "").split()
    chunks = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start : start + max_words]).strip()
        if len(chunk) > 80:
            chunks.append(chunk)
    return chunks or ([text[:1600]] if text else [])


def recommendation_logic(tags: list[str], summary: str) -> str:
    if "backlight" in tags:
        return "Backlight illumination may be suitable when the inspection target is an outline, edge, hole, gap, or dimensional silhouette. Verify part translucency, working distance, and required contrast."
    if "darkfield" in tags:
        return "Darkfield or low-angle illumination may help reveal scratches, texture, edges, and shallow surface defects by scattering light into the camera."
    if "brightfield" in tags:
        return "Brightfield illumination may be suitable for front-surface features when geometry reflects useful light toward the camera; glare and shadows should be tested."
    if "coaxial_light" in tags or "inline_illumination" in tags:
        return "Coaxial or in-line illumination may help with flat reflective surfaces, etched marks, and shadow-sensitive inspection geometries."
    if "polarization_filter" in tags or "polarized_light" in tags:
        return "Polarization may improve contrast by reducing specular glare or isolating material response; validate with sample parts."
    if "bandpass_filter" in tags or "longpass_filter" in tags or "shortpass_filter" in tags:
        return "Optical filters may improve contrast by selecting useful wavelengths and rejecting unwanted ambient or source light."
    if "telecentric_lens" in tags:
        return "Telecentric lenses may be suitable for metrology where perspective error, magnification change, or object height variation affects measurement repeatability."
    if "focal_length" in tags or "field_of_view" in tags or "working_distance" in tags:
        return "Lens selection should start from field of view, working distance, sensor size, and smallest feature size; verify distortion, aperture, and depth of field."
    if "line_scan_inspection" in tags:
        return "Line scan imaging may be suitable for continuous web or moving-part inspection when illumination and synchronization are controlled."
    return summary[:620]


def openai_enhance_if_available(text: str, local_summary: str, tags: list[str]) -> tuple[str, list[str]]:
    if not os.getenv("OPENAI_API_KEY"):
        return local_summary, tags
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_KB_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Summarize Edmund Optics machine vision knowledge into concise technical notes. Do not invent facts."},
                {"role": "user", "content": text[:6000]},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or local_summary
        return content.strip(), tags
    except Exception:
        return local_summary, tags


def delete_existing_outputs(conn, doc_ids: list[int]) -> None:
    if not doc_ids:
        return
    placeholders = ",".join("?" for _ in doc_ids)
    conn.execute(f"DELETE FROM knowledge_chunks WHERE document_id IN ({placeholders})", tuple(doc_ids))
    card_ids = []
    for row in conn.execute("SELECT id, source_document_ids FROM knowledge_cards").fetchall():
        try:
            ids = json.loads(row["source_document_ids"] or "[]")
        except Exception:
            ids = []
        if any(int(doc_id) in set(int(item) for item in ids if str(item).isdigit()) for doc_id in doc_ids):
            card_ids.append(row["id"])
    if card_ids:
        placeholders = ",".join("?" for _ in card_ids)
        conn.execute(f"DELETE FROM knowledge_cards WHERE id IN ({placeholders})", tuple(card_ids))


def extract(reset: bool = True) -> dict[str, Any]:
    knowledge_engine.ensure_knowledge_schema()
    with knowledge_engine.connect() as conn:
        source = conn.execute("SELECT id FROM knowledge_sources WHERE source_name = ?", (SOURCE_NAME,)).fetchone()
        if not source:
            return {"documents_seen": 0, "chunks_created": 0, "cards_created": 0, "message": "Edmund Optics source not found."}
        source_id = source["id"]
        docs = [dict(row) for row in conn.execute("SELECT * FROM knowledge_documents WHERE source_id = ? ORDER BY id", (source_id,)).fetchall()]
        doc_ids = [int(doc["id"]) for doc in docs]
        if reset:
            delete_existing_outputs(conn, doc_ids)
        chunks_created = 0
        cards_created = 0
        skipped = 0
        topic_counts: Counter[str] = Counter()
        for doc in docs:
            if doc.get("review_status") == "rejected":
                skipped += 1
                continue
            text = doc.get("clean_markdown") or doc.get("raw_text") or ""
            combined = " ".join([doc.get("title") or "", doc.get("summary") or "", text])
            tags = tag_text(combined)
            if not tags:
                conn.execute("UPDATE knowledge_documents SET review_status = ? WHERE id = ?", ("needs_review", doc["id"]))
                skipped += 1
                continue
            local_summary = summary_from_text(text, doc.get("summary"))
            summary, tags = openai_enhance_if_available(combined, local_summary, tags)
            quality_score = max(float(doc.get("quality_score") or 0), min(100.0, 40 + len(tags) * 5 + min(len(text), 4000) / 180))
            conn.execute(
                "UPDATE knowledge_documents SET summary = ?, quality_score = ? WHERE id = ?",
                (summary, quality_score, doc["id"]),
            )
            for idx, chunk in enumerate(chunk_text(text)):
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks (document_id, chunk_index, chunk_text, token_count, embedding_id, tags_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (doc["id"], idx, chunk, len(chunk.split()), None, json.dumps(tags)),
                )
                chunks_created += 1
            topic_counts.update(tags)
            rec_logic = recommendation_logic(tags, summary)
            filter_topic = first(tags, FILTER_TOPICS)
            tag_payload = sorted(set(tags + (["filter_topic:" + filter_topic] if filter_topic else []) + ["source:edmund_optics"]))
            conn.execute(
                """
                INSERT INTO knowledge_cards
                    (topic, summary, lighting_type, camera_topic, lens_topic, application, material,
                     defect_type, recommendation_logic, cautions, source_document_ids, verified_status, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.get("title") or "Edmund Optics knowledge article",
                    summary,
                    first(tags, LIGHTING_TYPES),
                    first(tags, CAMERA_TOPICS),
                    first(tags, LENS_TOPICS),
                    first(tags, APPLICATIONS),
                    first(tags, MATERIALS),
                    "scratch" if "scratch_detection" in tags else None,
                    rec_logic,
                    "Edmund Optics source article imported for internal IOO knowledge-base testing. Verify article context, sample geometry, and product fit before customer use.",
                    json.dumps([doc["id"]]),
                    "pending",
                    json.dumps(tag_payload),
                ),
            )
            cards_created += 1
        conn.commit()
    return {
        "documents_seen": len(docs),
        "chunks_created": chunks_created,
        "cards_created": cards_created,
        "skipped": skipped,
        "top_tags": dict(topic_counts.most_common(30)),
        "openai_available": bool(os.getenv("OPENAI_API_KEY")),
        "mode": "openai_optional_local_fallback",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Edmund Optics documents into chunks and knowledge cards.")
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    print(json.dumps(extract(reset=not args.no_reset), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
