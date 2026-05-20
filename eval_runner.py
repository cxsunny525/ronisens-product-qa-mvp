from __future__ import annotations

import csv
import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import qa_engine
import verifier

try:
    import yaml
except Exception:  # pragma: no cover - fallback parser keeps eval runnable without PyYAML.
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parent
EVAL_SET = ROOT / "golden_eval_questions.yaml"
EVAL_CSV = ROOT / "eval_results.csv"
EVAL_REPORT = ROOT / "eval_report.md"


def _load_cases() -> list[dict[str, Any]]:
    text = EVAL_SET.read_text(encoding="utf-8")
    if yaml is not None and hasattr(yaml, "safe_load"):
        payload = yaml.safe_load(text) or {}
        return list(payload.get("tests") or [])

    cases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.strip() == "tests:":
            continue
        if line.startswith("  - "):
            if current:
                cases.append(current)
            current = {}
            key, value = line[4:].split(":", 1)
            current[key.strip()] = _parse_scalar(value.strip())
        elif current is not None and line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key.strip()] = _parse_scalar(value.strip())
    if current:
        cases.append(current)
    return cases


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "[]":
        return []
    if value.startswith("[") or value.startswith('"') or value.startswith("'"):
        try:
            return ast.literal_eval(value)
        except Exception:
            return value.strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _contains_all(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    missing = [needle for needle in needles if needle and needle.lower() not in text.lower()]
    return not missing, missing


def _contains_none(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    present = [needle for needle in needles if needle and needle.lower() in text.lower()]
    return not present, present


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    mode = case.get("mode") or "strict"
    brand_filter = case.get("brand_filter")
    result = qa_engine.answer_question(case["question"], brand_filter=brand_filter, mode=mode)
    verified = verifier.verify_answer(result)
    answer_text = str(verified.get("answer") or "")
    must_include_ok, missing_includes = _contains_all(answer_text, case.get("must_include") or [])
    must_not_ok, forbidden_hits = _contains_none(answer_text, case.get("must_not_include") or [])
    expected_confidence = str(case.get("expected_confidence") or "").lower()
    actual_confidence = str(verified.get("confidence") or "").lower()
    confidence_ok = not expected_confidence or actual_confidence == expected_confidence
    no_source_answer = bool(verified.get("matched_products")) and not bool(verified.get("sources"))
    possible_hallucination = any(
        "not present in the database" in warning
        or "not verified" in warning
        or ("similar match" in warning and mode != "exploratory")
        for warning in verified.get("warnings") or []
    )
    passed = must_include_ok and must_not_ok and confidence_ok and not possible_hallucination and not no_source_answer
    return {
        "id": case.get("id"),
        "question": case.get("question"),
        "mode": mode,
        "brand_filter": brand_filter or "",
        "passed": passed,
        "expected_behavior": case.get("expected_behavior"),
        "expected_confidence": expected_confidence,
        "actual_confidence": actual_confidence,
        "must_include_missing": "; ".join(missing_includes),
        "must_not_include_hit": "; ".join(forbidden_hits),
        "matched_count": len(verified.get("matched_products") or []),
        "source_count": len(verified.get("sources") or []),
        "warning_count": len(verified.get("warnings") or []),
        "possible_hallucination": possible_hallucination,
        "no_source_answer": no_source_answer,
        "answer_summary": " ".join(answer_text.split())[:300],
        "warnings": " | ".join(verified.get("warnings") or []),
        "result_json": json.dumps(verified, ensure_ascii=False)[:4000],
    }


def run_eval() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = _load_cases()
    rows = [_run_case(case) for case in cases]
    passed = sum(1 for row in rows if row["passed"])
    stats = {
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows) * 100, 2) if rows else 0.0,
    }
    return rows, stats


def write_outputs() -> tuple[Path, Path, dict[str, Any]]:
    rows, stats = run_eval()
    fieldnames = [
        "id",
        "question",
        "mode",
        "brand_filter",
        "passed",
        "expected_behavior",
        "expected_confidence",
        "actual_confidence",
        "must_include_missing",
        "must_not_include_hit",
        "matched_count",
        "source_count",
        "warning_count",
        "possible_hallucination",
        "no_source_answer",
        "answer_summary",
        "warnings",
        "result_json",
    ]
    with EVAL_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    failures = [row for row in rows if not row["passed"]]
    lines = [
        "# Evaluation Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Total cases: {stats['total']}",
        f"Passed: {stats['passed']}",
        f"Failed: {stats['failed']}",
        f"Pass rate: {stats['pass_rate']}%",
        "",
        "## Failure Summary",
        "",
    ]
    if failures:
        for row in failures:
            lines.append(f"- `{row['id']}`: {row['question']}")
            if row["must_include_missing"]:
                lines.append(f"  - Missing required text: {row['must_include_missing']}")
            if row["must_not_include_hit"]:
                lines.append(f"  - Forbidden text appeared: {row['must_not_include_hit']}")
            if row["expected_confidence"] != row["actual_confidence"]:
                lines.append(f"  - Confidence: expected {row['expected_confidence']}, got {row['actual_confidence']}")
            if row["possible_hallucination"]:
                lines.append("  - Possible hallucination flagged by verifier.")
            if row["no_source_answer"]:
                lines.append("  - Matched products returned without source links.")
    else:
        lines.append("All golden evaluation cases passed.")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The evaluator checks answer text for required and forbidden phrases.",
            "- The verifier checks database presence, source links, spec provenance, and strict/similar match conflicts.",
            "- A failure does not always mean the product answer is wrong; it may mean the golden wording should be updated after deliberate product-rule changes.",
        ]
    )
    EVAL_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EVAL_CSV, EVAL_REPORT, stats


if __name__ == "__main__":
    csv_path, report_path, stats = write_outputs()
    print(f"Wrote {csv_path} and {report_path}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
