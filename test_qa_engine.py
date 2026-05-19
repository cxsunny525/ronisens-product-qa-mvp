from __future__ import annotations

import os
import unittest

import qa_engine
import strict_qa_adapter
import verifier


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
        product = qa_engine.get_product_by_model("NOT-A-REAL-IOO-MODEL-999")
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
        self.assertEqual(result["mode"], "strict")
        self.assertGreater(len(result["evidence"]), 0)

    def test_chinese_bar_light_question(self) -> None:
        result = qa_engine.answer_question("\u6761\u5f62\u7684\u5149\u6e90\u6709\u54ea\u4e9b\uff1f")
        self.assertGreater(len(result["matched_products"]), 0)
        self.assertIn("\u5f53\u524d\u6570\u636e\u5e93", result["answer"])

    def test_chinese_datasheet_question(self) -> None:
        result = qa_engine.answer_question("\u54ea\u4e9b\u4ea7\u54c1\u6709\u89c4\u683c\u4e66\uff1f")
        self.assertGreater(len(result["matched_products"]), 0)
        self.assertTrue(all(row.get("datasheet_url") != "not available" for row in result["matched_products"]))

    def test_chinese_selection_question(self) -> None:
        result = qa_engine.answer_question("\u68c0\u6d4b\u91d1\u5c5e\u5212\u75d5\u5e94\u8be5\u770b\u4ec0\u4e48\u5149\u6e90\uff1f")
        self.assertGreater(len(result["matched_products"]), 0)
        self.assertIn("\u521d\u6b65\u9009\u578b", result["answer"])
        self.assertEqual(result["mode"], "strict")

    def test_chinese_glass_scratch_is_not_metal_scratch(self) -> None:
        result = strict_qa_adapter.answer_question("\u68c0\u6d4b\u73bb\u7483\u5212\u75d5\u5e94\u8be5\u770b\u4ec0\u4e48\u5149\u6e90\uff1f")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("\u76ee\u524d\u7cfb\u7edf\u5c1a\u672a\u6709\u8fd9\u4e2a\u7b54\u6848", result["answer"])
        self.assertNotIn("\u91d1\u5c5e\u5212\u75d5\u68c0\u6d4b\u901a\u5e38", result["answer"])

    def test_chinese_generic_scratch_refuses_to_guess(self) -> None:
        result = strict_qa_adapter.answer_question("\u68c0\u6d4b\u5212\u75d5\u5e94\u8be5\u770b\u4ec0\u4e48\u5149\u6e90\uff1f")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("\u76ee\u524d\u7cfb\u7edf\u5c1a\u672a\u6709\u8fd9\u4e2a\u7b54\u6848", result["answer"])

    def test_english_glass_scratch_refuses_to_guess(self) -> None:
        result = strict_qa_adapter.answer_question("What lighting type is suitable for glass scratch inspection?")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("does not have this answer yet", result["answer"])

    def test_answer_data_quality(self) -> None:
        result = qa_engine.answer_question("Which fields are missing most often?")
        self.assertGreater(len(result["spec_table"]), 0)
        self.assertIn("missing", result["answer"].lower())

    def test_no_openai_key_still_runs(self) -> None:
        os.environ.pop("OPENAI_API_KEY", None)
        result = qa_engine.answer_question("What lighting type is suitable for metal scratch inspection?")
        self.assertEqual(result["mode"], "strict")
        self.assertIn(result["confidence"], {"medium", "low", "high"})

    def test_nonexistent_model_answer_is_grounded(self) -> None:
        result = qa_engine.answer_question("Does TMS Lite have FAKE-ABC-9999?")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("No exact match", result["answer"])

    def test_sources_output_for_model(self) -> None:
        result = qa_engine.answer_question(f"Does {REAL_MODEL} have datasheet?")
        self.assertGreater(len(result["sources"]), 0)
        self.assertTrue(any(source.get("url") for source in result["sources"]))

    def test_product_comparison_question(self) -> None:
        result = qa_engine.answer_question(f"Compare {REAL_MODEL}, {SECOND_MODEL}, {THIRD_MODEL}.")
        self.assertGreaterEqual(len(result["spec_table"]), 3)
        self.assertGreater(len(result["sources"]), 0)

    def test_exploratory_mode_labels_similar_matches(self) -> None:
        result = qa_engine.answer_question("Do you have CAS2-00-010-X-Y?", mode="exploratory")
        self.assertEqual(result["mode"], "exploratory")
        self.assertIn("similar matches", result["answer"])
        self.assertLessEqual({"low": 0, "medium": 1, "high": 2}[result["confidence"]], 1)

    def test_strict_mode_does_not_substitute_similar_model(self) -> None:
        result = qa_engine.answer_question("Do you have CAS2-00-010-X-Y?", mode="strict")
        self.assertEqual(result["matched_products"], [])
        self.assertIn("No exact match", result["answer"])

    def test_verifier_keeps_grounded_answer(self) -> None:
        result = qa_engine.answer_question(f"What are the specs for {REAL_MODEL}?")
        checked = verifier.verify_answer(result)
        self.assertEqual(checked["matched_products"][0]["model"], REAL_MODEL)
        self.assertIn(checked["confidence"], {"medium", "high"})

    def test_answer_has_new_traceability_fields(self) -> None:
        result = qa_engine.answer_question("Which products are 24V?")
        for key in ["evidence", "match_reason", "query_interpretation", "warnings"]:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
