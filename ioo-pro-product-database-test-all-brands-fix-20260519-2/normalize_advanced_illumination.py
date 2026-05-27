from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
UNMAPPED_PATH = ROOT / "unmapped_fields.md"


@dataclass(frozen=True)
class NormalizedSpec:
    raw_field: str
    raw_value: str
    canonical_field: str
    normalized_value: str
    unit: str
    confidence: str
    mapped: bool


FIELD_MAP = {
    "wavelengths": ("wavelength_nm", "nm", "high"),
    "wavelength": ("wavelength_nm", "nm", "high"),
    "emitting area": ("emitting_area_mm", "mm", "medium"),
    "emission area": ("emitting_area_mm", "mm", "medium"),
    "illumination area": ("illumination_area_mm", "mm", "medium"),
    "ip rating": ("ip_rating", "", "high"),
    "ingress protection": ("ip_rating", "", "high"),
    "voltage": ("voltage_v", "V", "high"),
    "input voltage": ("voltage_v", "V", "high"),
    "power": ("power_w", "W", "high"),
    "current": ("current_a", "A", "high"),
    "connector": ("connector", "", "high"),
    "cable length": ("cable_length_mm", "mm", "medium"),
    "mounting": ("mounting", "", "medium"),
    "strobe": ("strobe_mode", "", "medium"),
    "controller compatibility": ("controller_compatibility", "", "medium"),
}


KNOWN_UNMAPPED_FIELDS = {
    "intensity",
    "lead time",
    "light conditioning",
    "sizes",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_wavelengths(value: str) -> str:
    values = []
    for number in re.findall(r"\b(\d{3,4})\s*nm\b|\b(365|375|385|395|405|455|470|505|530|590|625|660|730|850|940)\b", value, flags=re.I):
        token = next((part for part in number if part), "")
        if token:
            values.append(token)
    if re.search(r"\b(white|whi)\b", value, flags=re.I):
        values.append("white")
    if re.search(r"\brgb\b", value, flags=re.I):
        values.append("rgb")
    return " / ".join(dict.fromkeys(values)) or value


def normalize_dimension(value: str) -> str:
    parts = re.findall(r"\d+(?:\.\d+)?\s*mm", value, flags=re.I)
    if parts:
        return " x ".join(part.replace(" ", "") for part in parts)
    return value


def normalize_spec(raw_field: str, raw_value: Any) -> NormalizedSpec:
    field = clean(raw_field)
    value = clean(raw_value)
    key = field.lower()
    canonical_field = ""
    unit = ""
    confidence = "low"
    mapped = False

    if key in FIELD_MAP:
        canonical_field, unit, confidence = FIELD_MAP[key]
        mapped = True
    elif any(term in key for term in ["wavelength", "wave length"]):
        canonical_field, unit, confidence, mapped = "wavelength_nm", "nm", "medium", True
    elif "ip" in key and "rating" in key:
        canonical_field, unit, confidence, mapped = "ip_rating", "", "medium", True
    elif any(term in key for term in ["area", "projection"]) and "mm" in value.lower():
        canonical_field, unit, confidence, mapped = "emitting_area_mm", "mm", "low", True

    normalized_value = value
    if canonical_field == "wavelength_nm":
        normalized_value = normalize_wavelengths(value)
    elif canonical_field in {"emitting_area_mm", "illumination_area_mm"}:
        normalized_value = normalize_dimension(value)

    if key in KNOWN_UNMAPPED_FIELDS:
        mapped = False
        canonical_field = ""
        unit = ""
        confidence = "low"
        normalized_value = value

    return NormalizedSpec(
        raw_field=field,
        raw_value=value,
        canonical_field=canonical_field,
        normalized_value=normalized_value,
        unit=unit,
        confidence=confidence,
        mapped=mapped,
    )


def normalize_specs(raw_specs: dict[str, Any]) -> list[NormalizedSpec]:
    return [normalize_spec(field, value) for field, value in (raw_specs or {}).items()]


def append_unmapped_fields(fields: set[str]) -> None:
    if not fields:
        return
    existing = UNMAPPED_PATH.read_text(encoding="utf-8") if UNMAPPED_PATH.exists() else ""
    section_title = "\n\n## Advanced Illumination pilot unmapped fields\n"
    lines = []
    for field in sorted(fields):
        marker = f"- Advanced Illumination: {field}"
        if marker not in existing:
            lines.append(marker)
    if not lines:
        return
    with UNMAPPED_PATH.open("a", encoding="utf-8") as f:
        if "## Advanced Illumination pilot unmapped fields" not in existing:
            f.write(section_title)
        for line in lines:
            f.write(line + "\n")
