from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "brand_config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "brand": {
        "name": "IOO",
        "product_name": "IOO Lighting AI",
        "domain": "ioo.pro",
        "tagline": "AI-powered machine vision lighting selection for industrial inspection.",
        "origin_statement": "Designed in California. Manufactured in Malaysia.",
        "show_origin_statement": True,
        "public_brand_only": True,
        "hide_supplier_names": True,
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "model": "gpt-4.1-mini",
        "fallback_enabled": True,
    },
    "gamification": {
        "enabled": True,
        "points_name": "IOO Insight Points",
        "question_points": 5,
        "upload_points": 10,
        "feedback_points": 5,
        "parameter_detail_points": 5,
        "followup_points": 3,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    try:
        import yaml  # type: ignore

        if hasattr(yaml, "safe_load"):
            loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                return _deep_merge(DEFAULT_CONFIG, loaded)
    except Exception:
        pass
    return DEFAULT_CONFIG


def brand() -> dict[str, Any]:
    return load_config()["brand"]


def openai_config() -> dict[str, Any]:
    return load_config()["openai"]


def gamification() -> dict[str, Any]:
    return load_config()["gamification"]
