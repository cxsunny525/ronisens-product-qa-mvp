from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import answer_engine


ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "PUBLIC_BRAND_SAFETY_REPORT.md"

FORBIDDEN = [
    "TMS",
    "TMS Lite",
    "TMS-LITE",
    "tms-lite",
    "Advanced Illumination",
    "supplier",
    "internal_model",
    "internal_supplier",
]

PUBLIC_FILES = [
    ROOT / "public_products.csv",
    ROOT / "app.py",
    ROOT / "README.md",
]

TEST_QUESTIONS = [
    "Which IOO products are red lights?",
    "Do you have CAS2-00-010-X-X?",
    "Detect scratches on reflective metal.",
    "Do you have a fake product called IOO-FAKE-123?",
]


def contains_forbidden(text: str) -> list[str]:
    hits = []
    for term in FORBIDDEN:
        if re.search(re.escape(term), text, flags=re.I):
            hits.append(term)
    return sorted(set(hits))


class PublicBrandSafetyTests(unittest.TestCase):
    findings: list[str] = []

    @classmethod
    def tearDownClass(cls) -> None:
        lines = [
            "# Public Brand Safety Report",
            "",
            "Scope: public product CSV, Streamlit app text, and representative answer outputs.",
            "",
        ]
        if cls.findings:
            lines.append("## Findings")
            lines.extend(f"- {finding}" for finding in cls.findings)
        else:
            lines.append("No forbidden public brand or private-field leakage detected in the tested public surfaces.")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_public_files_do_not_expose_private_brand_terms(self) -> None:
        for path in PUBLIC_FILES:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
            hits = contains_forbidden(text)
            if hits:
                self.findings.append(f"{path.name}: {', '.join(hits)}")
            self.assertFalse(hits, f"{path} contains {hits}")

    def test_answer_outputs_do_not_expose_private_brand_terms(self) -> None:
        for question in TEST_QUESTIONS:
            result = answer_engine.answer_question(question)
            public_text = json.dumps(
                {
                    "answer": result.get("answer"),
                    "direct_recommendation": result.get("direct_recommendation"),
                    "lighting_strategy": result.get("lighting_strategy"),
                    "product_results": result.get("product_results", []),
                    "closest_ioo_products": result.get("closest_ioo_products", []),
                    "sources": result.get("sources", []),
                    "warnings": result.get("warnings", []),
                },
                ensure_ascii=False,
            )
            hits = contains_forbidden(public_text)
            if hits:
                self.findings.append(f"answer for {question!r}: {', '.join(hits)}")
            self.assertFalse(hits, f"answer for {question!r} contains {hits}")


if __name__ == "__main__":
    unittest.main()
