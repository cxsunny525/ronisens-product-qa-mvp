# IOO Rebrand Database Migration Report

1. Original TMS product count: 654
2. Generated IOO product count: 654
3. One-to-one mapping completed: yes
4. Public model conversion rule: replace TMS/TMS-LITE tokens with IOO; otherwise prefix the original model with `IOO-`; duplicates get stable `-2`, `-3` suffixes.
5. Duplicate model handling count: 108
6. public_products.csv path: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\public_products.csv`
7. data/ioo_products.db path: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\data\ioo_products.db`
8. ioo_sku_mapping.csv path: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\ioo_sku_mapping.csv`
9. Public TMS leakage risk: mitigated by public-text sanitization and public UI source hiding.
10. Query-class handling: list/filter questions are backed by product_search.py and can return counts plus first 20 rows.
11. Recommendation handling: closest-fit recommendations are selected from data/ioo_products.db before any AI response is composed.
12. OpenAI restriction: answer_engine.py only passes retrieved IOO candidates and validates/filters model names.
13. Test status: see IOO_PRODUCT_MAPPING_TEST_REPORT.md and TEST_REPORT.md after test run.
14. Current unresolved issue: source quality still depends on original scraped parameter completeness; missing values remain `not available`.
