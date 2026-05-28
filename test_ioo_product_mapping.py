from __future__ import annotations

import csv
import hashlib
import sqlite3
import unittest
from pathlib import Path

import generate_ioo_product_db


ROOT = Path(__file__).resolve().parent
SOURCE_DB = ROOT / "data" / "tms_lite_full.db"
IOO_DB = ROOT / "data" / "ioo_products.db"
PUBLIC_PRODUCTS = ROOT / "public_products.csv"
SKU_MAPPING = ROOT / "ioo_sku_mapping.csv"
REPORT = ROOT / "IOO_PRODUCT_MAPPING_TEST_REPORT.md"


def count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class IOOProductMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        generate_ioo_product_db.build_database()
        cls.source_count = count_rows(SOURCE_DB, "products")
        cls.ioo_count = count_rows(IOO_DB, "products")
        cls.mapping_count = count_rows(IOO_DB, "internal_mapping")
        cls.public_rows = csv_rows(PUBLIC_PRODUCTS)
        cls.mapping_rows = csv_rows(SKU_MAPPING)

    @classmethod
    def tearDownClass(cls) -> None:
        lines = [
            "# IOO Product Mapping Test Report",
            "",
            f"- Source products: {cls.source_count}",
            f"- IOO products: {cls.ioo_count}",
            f"- DB mapping rows: {cls.mapping_count}",
            f"- public_products.csv rows: {len(cls.public_rows)}",
            f"- ioo_sku_mapping.csv rows: {len(cls.mapping_rows)}",
            "- Result: passed when this test suite exits successfully.",
        ]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_one_to_one_product_count(self) -> None:
        self.assertEqual(self.source_count, self.ioo_count)
        self.assertEqual(self.source_count, self.mapping_count)

    def test_every_public_model_is_ioo_and_not_private_brand(self) -> None:
        forbidden = ("TMS", "tms", "TMS-LITE", "tms-lite")
        for row in self.public_rows:
            model = row["public_model"]
            self.assertTrue(model.startswith("IOO"), model)
            self.assertFalse(any(term in model for term in forbidden), model)

    def test_public_model_uniqueness_and_traceability(self) -> None:
        public_models = [row["public_model"] for row in self.public_rows]
        mapped_models = [row["public_model"] for row in self.mapping_rows]
        self.assertEqual(len(public_models), len(set(public_models)))
        self.assertEqual(set(public_models), set(mapped_models))
        for row in self.mapping_rows:
            self.assertTrue(row["internal_model"])
            self.assertTrue(row["original_product_id"])

    def test_csv_counts_match_database(self) -> None:
        self.assertEqual(len(self.public_rows), self.ioo_count)
        self.assertEqual(len(self.mapping_rows), self.source_count)

    def test_no_empty_public_model(self) -> None:
        self.assertTrue(all(row["public_model"].strip() for row in self.public_rows))

    def test_conversion_is_stable(self) -> None:
        before_public = file_hash(PUBLIC_PRODUCTS)
        before_mapping = file_hash(SKU_MAPPING)
        generate_ioo_product_db.build_database()
        self.assertEqual(before_public, file_hash(PUBLIC_PRODUCTS))
        self.assertEqual(before_mapping, file_hash(SKU_MAPPING))


if __name__ == "__main__":
    unittest.main()
