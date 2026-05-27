from __future__ import annotations

import unittest

import qa_engine


class MultiBrandAdvancedIlluminationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        qa_engine.load_database(force=True)

    def test_database_has_two_brands(self) -> None:
        brands = {row["brand"]: row["products"] for row in qa_engine.get_brands()}
        self.assertGreaterEqual(brands.get("TMS LITE", 0), 1)
        self.assertGreaterEqual(brands.get("Advanced Illumination", 0), 1)

    def test_advanced_query_does_not_return_tms_lite(self) -> None:
        result = qa_engine.answer_question("What Advanced Illumination ring lights are in the database?", mode="strict")
        self.assertTrue(result["matched_products"])
        self.assertTrue(all(row.get("brand") == "Advanced Illumination" for row in result["matched_products"]))

    def test_tms_query_does_not_return_advanced_illumination(self) -> None:
        result = qa_engine.answer_question("What TMS Lite ring lights are in the database?", mode="strict")
        self.assertTrue(result["matched_products"])
        self.assertTrue(all(row.get("brand") == "TMS LITE" for row in result["matched_products"]))

    def test_all_brands_rows_show_brand(self) -> None:
        result = qa_engine.answer_question("Show all brands with coaxial lights.", brand_filter=None, mode="strict")
        self.assertTrue(result["matched_products"])
        self.assertTrue(all(row.get("brand") for row in result["matched_products"]))

    def test_fake_advanced_model_not_replaced_by_tms(self) -> None:
        result = qa_engine.answer_question("Do you have an Advanced Illumination model called FAKE-AI-123?", mode="strict")
        self.assertFalse(result["matched_products"])
        self.assertIn("No exact match", result["answer"])
        self.assertNotIn("TMS LITE", str(result["matched_products"]))

    def test_tms_model_not_treated_as_advanced_product(self) -> None:
        result = qa_engine.answer_question("Advanced Illumination 有没有 TMS Lite 的 CAS2-00-010-X-X？", mode="strict")
        self.assertFalse(result["matched_products"])
        self.assertTrue("No exact match" in result["answer"] or "当前数据库未记录" in result["answer"])

    def test_advanced_specs_include_source_url(self) -> None:
        specs = qa_engine.get_product_specs("RL322", brand_filter="Advanced Illumination")
        self.assertTrue(specs)
        self.assertTrue(any(spec.get("source_url") for spec in specs))

    def test_advanced_sources_include_datasheet_or_product_url(self) -> None:
        sources = qa_engine.get_product_sources("RL208", brand_filter="Advanced Illumination")
        urls = [source.get("url") for source in sources]
        self.assertTrue(any(url and url.startswith("http") for url in urls))

    def test_ui_brand_selector_parameter_path(self) -> None:
        result = qa_engine.answer_question(
            "Which products are backlights?",
            brand_filter="Advanced Illumination",
            mode="strict",
        )
        self.assertTrue(result["matched_products"])
        self.assertTrue(all(row.get("brand") == "Advanced Illumination" for row in result["matched_products"]))

    def test_strict_advanced_no_result_does_not_guess(self) -> None:
        result = qa_engine.answer_question("Advanced Illumination products with 999V input?", mode="strict")
        self.assertFalse(result["matched_products"])
        self.assertIn("No exact match", result["answer"])

    def test_compare_products_shows_brand(self) -> None:
        table = qa_engine.compare_products(["RL322", "CAS2-00-010-X-X"])
        self.assertTrue(all("brand" in row for row in table))


if __name__ == "__main__":
    unittest.main()
