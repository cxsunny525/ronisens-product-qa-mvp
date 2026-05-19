from __future__ import annotations

import os
import unittest

import qa_engine


REAL_MODEL = "CAS2-00-010-X-X"
SECOND_MODEL = "BHP1010-X-X"
THIRD_MODEL = "DLQ2-90-050-1-X"


class QAEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.pop("OPENAI_API_KEY", None)
        cls.dataset = qa_engine.load_database(force=True)

    def test_database_loads(self) -> None:
        stats = qa_engine.get_database_stats()
        self.assertGreater(stats["counts"].get("products", 0), 0)
        self.assertIn(stats["source_type"], {"SQLite", "CSV fallback"})

    def test_search_products_returns_results(self) -> None:
        results = qa_engine.search_products("24V backlight", limit=10)
        self.assertGreater(len(results), 0)
        self.assertIn("model", results[0])

    def test_get_product_by_real_model(self) -> None:
        product = qa_engine.get_product_by_model(REAL_MODEL)
        self.assertIsNotNone(product)
        self.assertEqual(product["model"], REAL_MODEL)

    def test_get_product_by_missing_model_does_not_invent(self) -> None:
        product = qa_engine.get_product_by_model("NOT-A-REAL-RONISENS-MODEL-999")
        self.assertIsNone(product)

    def test_compare_products(self) -> None:
        comparison = qa_engine.compare_products([REAL_MODEL, SECOND_MODEL, "NO-SUCH-MODEL-123"])
        self.assertEqual(len(comparison), 3)
        statuses = {row["model"]: row["status"] for row in comparison}
        self.assertEqual(statuses["NO-SUCH-MODEL-123"], "not available in the current database")

    def test_find_missing_fields(self) -> None:
        missing = qa_engine.find_missing_fields()
        self.assertIn("summary", missing)
        self.assertGreater(len(missing["summary"]), 0)

    def test_answer_model_lookup(self) -> None:
        result = qa_engine.answer_question(f"What are the specs for {REAL_MODEL}?")
        self.assertEqual(result["confidence"], "high")
        self.assertGreaterEqual(len(result["matched_products"]), 1)
        self.assertIn(REAL_MODEL, result["matched_products"][0]["model"])

    def test_answer_parameter_filter(self) -> None:
        result = qa_engine.answer_question("Which products are 24V?")
        self.assertGreater(len(result["matched_products"]), 0)
        self.assertEqual(result["mode"], "local")

    def test_answer_data_quality(self) -> None:
        result = qa_engine.answer_question("Which fields are missing most often?")
        self.assertGreater(len(result["spec_table"]), 0)
        self.assertIn("missing", result["answer"].lower())

    def test_no_openai_key_still_runs(self) -> None:
        os.environ.pop("OPENAI_API_KEY", None)
        result = qa_engine.answer_question("What lighting type is suitable for metal scratch inspection?")
        self.assertEqual(result["mode"], "local")
        self.assertIn(result["confidence"], {"medium", "low", "high"})

    def test_nonexistent_model_answer_is_grounded(self) -> None:
        result = qa_engine.answer_question("Does TMS Lite have FAKE-ABC-9999?")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("not available in the current database", result["answer"])

    def test_sources_output_for_model(self) -> None:
        result = qa_engine.answer_question(f"Does {REAL_MODEL} have datasheet?")
        self.assertGreater(len(result["sources"]), 0)
        self.assertTrue(any(source.get("url") for source in result["sources"]))

    def test_product_comparison_question(self) -> None:
        result = qa_engine.answer_question(f"Compare {REAL_MODEL}, {SECOND_MODEL}, {THIRD_MODEL}.")
        self.assertGreaterEqual(len(result["spec_table"]), 3)
        self.assertGreater(len(result["sources"]), 0)


if __name__ == "__main__":
    unittest.main()
