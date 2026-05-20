from __future__ import annotations

import copy
import re
import sqlite3
from typing import Any

import qa_engine


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())


def _lower_confidence(confidence: str, target: str = "low") -> str:
    current = CONFIDENCE_ORDER.get(str(confidence or "low").lower(), 0)
    wanted = CONFIDENCE_ORDER.get(target, 0)
    for name, rank in CONFIDENCE_ORDER.items():
        if rank == min(current, wanted):
            return name
    return "low"


def _all_models() -> set[str]:
    return {_norm(product.get("model")) for product in qa_engine.load_database().products if product.get("model")}


def _all_source_urls() -> set[str]:
    ds = qa_engine.load_database()
    urls = set()
    for product in ds.products:
        for key in ["product_url", "source_url", "datasheet_url"]:
            value = product.get(key)
            if value:
                urls.add(str(value))
    for spec in ds.specs:
        if spec.get("source_url"):
            urls.add(str(spec["source_url"]))
    for asset in ds.assets:
        for key in ["url", "final_url", "source_url"]:
            if asset.get(key):
                urls.add(str(asset[key]))
    if ds.db_path:
        try:
            conn = sqlite3.connect(ds.db_path)
            for row in conn.execute("SELECT url FROM knowledge_documents WHERE url IS NOT NULL AND url != ''"):
                urls.add(str(row[0]))
            conn.close()
        except Exception:
            pass
    return urls


def _manual_value_exists(model: str, field_name: str, value: Any) -> bool:
    overrides = qa_engine.load_manual_overrides().get("products", {})
    model_entry = None
    for key, entry in overrides.items():
        if _norm(key) == _norm(model) and isinstance(entry, dict):
            model_entry = entry
            break
    if not model_entry:
        return False
    field_entry = model_entry.get(field_name)
    if not isinstance(field_entry, dict):
        return False
    return _norm(field_entry.get("value")) == _norm(value)


def _spec_value_exists(model: str, field_name: str, raw_value: Any, normalized_value: Any) -> bool:
    target_model = _norm(model)
    target_field = _norm(field_name)
    values = {_norm(raw_value), _norm(normalized_value)}
    if _manual_value_exists(model, field_name, raw_value) or _manual_value_exists(model, field_name, normalized_value):
        return True
    for spec in qa_engine.load_database().specs:
        spec_model = spec.get("model_normalized") or _norm(spec.get("model"))
        if _norm(spec_model) != target_model:
            continue
        spec_fields = [_norm(spec.get("spec_name")), _norm(spec.get("raw_field")), _norm(spec.get("canonical_field"))]
        if target_field and not any(target_field in field or field in target_field for field in spec_fields if field):
            continue
        if _norm(spec.get("raw_value")) in values or _norm(spec.get("normalized_value")) in values:
            return True
    return False


def _model_like_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z0-9][A-Z0-9]{1,}(?:-[A-Z0-9]+)+\b", str(text or "").upper())
    skip = {"NO-EXACT", "TMS-LITE"}
    return [
        token
        for token in dict.fromkeys(tokens)
        if token not in skip
        and any(ch.isdigit() for ch in token)
        and not re.fullmatch(r"\d+(?:V|W|MA|MM|NM|G)(?:-\d+)?", token)
    ]


def verify_answer(result: dict[str, Any]) -> dict[str, Any]:
    """Verify that a QA result is backed by the current database or manual overrides."""
    verified = copy.deepcopy(result)
    warnings = list(verified.get("warnings") or [])
    initial_warnings = set(warnings)
    known_models = _all_models()
    source_urls = _all_source_urls()

    matched_products = verified.get("matched_products") or []
    for row in matched_products:
        model = row.get("model")
        if not model or _norm(model) not in known_models:
            warnings.append(f"Matched product is not present in the database: {model}")

    for spec in verified.get("spec_table") or []:
        model = spec.get("model")
        if not model:
            continue
        if not model or _norm(model) not in known_models:
            if spec.get("status") != "not available in the current database":
                warnings.append(f"Spec row model is not present in the database: {model}")
            continue
        raw_value = spec.get("raw_value")
        normalized_value = spec.get("normalized_value")
        field_name = spec.get("spec_name") or spec.get("field") or ""
        if raw_value not in (None, "", "not available") and not _spec_value_exists(model, field_name, raw_value, normalized_value):
            if spec.get("status") != "found":
                warnings.append(f"Spec value not verified from product_specs or manual_overrides: {model} / {field_name} / {raw_value}")

    for source in verified.get("sources") or []:
        url = source.get("url")
        if not url or url == "not available":
            warnings.append("Source entry is missing a URL.")
        elif url not in source_urls:
            warnings.append(f"Source URL is not present in recorded database assets/specs/products: {url}")

    requested_models = {_norm(model) for model in (verified.get("query_interpretation") or {}).get("detected_models", [])}
    answer_lower = str(verified.get("answer", "")).lower()
    answer_is_refusal = "no exact match" in answer_lower or "当前数据库未记录" in answer_lower or "model not found" in answer_lower
    for token in _model_like_tokens(verified.get("answer", "")):
        if answer_is_refusal and _norm(token) in requested_models:
            continue
        if _norm(token) not in known_models:
            warnings.append(f"Answer text contains a model-like token not found in the database: {token}")

    interpretation = verified.get("query_interpretation") or {}
    exact_required = bool(interpretation.get("exact_required") or verified.get("mode") == "strict")
    if exact_required:
        for reason in verified.get("match_reason") or []:
            if reason.get("similarity_reason") and not reason.get("exact_match"):
                warnings.append("Exact-match question returned a similar match.")

    if matched_products and not (verified.get("sources") or []):
        warnings.append("Matched products were returned without source links.")

    warnings = list(dict.fromkeys(warnings))
    verified["warnings"] = warnings
    new_warnings = [warning for warning in warnings if warning not in initial_warnings]
    if warnings:
        verified["missing_or_uncertain"] = list(dict.fromkeys((verified.get("missing_or_uncertain") or []) + warnings))
    if new_warnings:
        severe = any("not present" in warning or "not verified" in warning or "similar match" in warning for warning in new_warnings)
        verified["confidence"] = _lower_confidence(verified.get("confidence", "low"), "low" if severe else "medium")
    return verified
