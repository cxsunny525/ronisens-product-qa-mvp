# Test Report

## Test Time

2026-05-19 09:25 America/Phoenix

## Test Environment

- Workspace: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai`
- Python: bundled Codex Python 3.12 runtime
- Database: `data/tms_lite_full.db`
- OpenAI API key: not set during tests
- App modes tested: Strict mode and Exploratory mode

## Passed Items

| Test | Result |
| --- | --- |
| `python test_qa_engine.py` | Passed, 23 tests |
| `python eval_runner.py` | Passed, 61/61 golden eval cases |
| `python -m py_compile app.py qa_engine.py verifier.py data_quality_tools.py eval_runner.py strict_qa_adapter.py` | Passed |
| Database loads from SQLite | Passed |
| Strict mode exact model lookup | Passed |
| Strict mode no similar-model substitution | Passed |
| Exploratory mode similar-match warning | Passed |
| Evidence and match_reason fields returned | Passed |
| Verifier checks grounded result | Passed |
| Data issues generation | Passed, 7,132 issue rows |
| Feedback write schema | Passed via direct function smoke test |
| No `OPENAI_API_KEY` local fallback | Passed |

## Evaluation Result

- Golden eval set: `golden_eval_questions.yaml`
- Eval report: `eval_report.md`
- Eval results CSV: `eval_results.csv`
- Total cases: 61
- Passed: 61
- Failed: 0
- Pass rate: 100.0%

## Tested Questions

- What TMS Lite ring lights are in the database?
- Which products are 24V?
- 哪些产品没有电压参数？
- 检测金属划痕应该看什么光源？
- Do you have FAKE-123?
- Compare CAS2-00-010-X-X, BHP1010-X-X, DLQ2-90-050-1-X.
- Which fields are missing most often?
- 有没有适合火星表面检测的光源？

## Fixes Made During Testing

- Added Strict mode and Exploratory mode.
- Added evidence, match_reason, query_interpretation, and warnings to QA results.
- Added `verifier.py` to detect ungrounded models, unverified specs, missing sources, and strict/similar conflicts.
- Added manual override loading without modifying SQLite.
- Added `data_quality_tools.py`, `data_issues.csv`, and `data_issues_summary.md`.
- Added 61-case golden evaluation suite and `eval_runner.py`.
- Prevented similar model substitution such as `CAS2-00-010-X-Y` -> `CAS2-00-010-X-X` in Strict mode.
- Rejected unsupported application questions such as glass scratch or Mars surface inspection.
- Rejected unsupported business/lifecycle fields such as price, inventory, lead time, warranty, and discontinued status.
- Tightened color filtering so Strict mode no longer accepts `search_text` as verified red/blue color evidence when the normalized `color` field is `not available`.

## Failed / Blocked Items

| Item | Status |
| --- | --- |
| Streamlit local HTTP startup from this sandbox | Blocked by local dependency directory access denial for `.runtime_pkgs` / `.packages` Streamlit executable |
| `python -m pytest -q` from bundled runtime | Blocked because bundled runtime has no pytest and project-local pytest package is not executable from this sandbox |

## Unresolved Issues

- The current app only covers TMS Lite.
- Some datasheet URLs are OneDrive/FutureIP redirect URLs rather than resolved final PDF URLs.
- `data_issues.csv` shows high cleanup volume: unmapped fields, unparsed units, duplicate models, and missing voltage/power/color/category fields.
- Manual overrides file exists but currently contains no verified corrections.
- Application selection rules are deliberately narrow; unsupported scenarios should continue to refuse.

## Remote Testing Standard

The QA engine, verifier, data quality tooling, feedback schema, and golden eval
runner meet the current credibility upgrade target. Streamlit Cloud should
redeploy from GitHub normally because runtime dependencies are in
`requirements.txt`; local Streamlit startup was blocked only by this sandbox's
permission issue reading the project-local dependency directories.

## Multi-Brand Advanced Illumination Update

Test time: 2026-05-19 15:16 America/Phoenix

- Database: `data/ioo_product_test.db` preferred; original `data/tms_lite_full.db` preserved.
- Advanced Illumination pilot import: 13 product families/products, 47 specs, 9 assets/datasheet links.
- `python test_qa_engine.py`: passed, 23 tests.
- `python test_multibrand_advanced_illumination.py`: passed, 11 tests.
- `python eval_runner.py`: passed, 92/92 golden eval cases, 100.0% pass rate.
- `advanced_illumination_data_quality_report.md`: generated.
- `advanced_illumination_data_issues.csv`: generated, 62 issue rows.
- Local Streamlit startup remains blocked in this sandbox by `.runtime_pkgs` access denial, but app code compiles and should run on Streamlit Cloud/Render from `requirements.txt`.

Additional tested questions:

- What Advanced Illumination ring lights are in the database?
- Which Advanced Illumination products are backlights?
- Do you have an Advanced Illumination model called FAKE-AI-123?
- Show all brands with coaxial lights.
- Advanced Illumination 有没有 TMS Lite 的 CAS2-00-010-X-X？

Current high-risk limitations:

- Advanced Illumination pilot voltage and power fields are mostly missing because they were not explicitly parsed from verified datasheets.
- Cross-brand equivalence is not guaranteed; results are searchable candidate records, not final substitutions.
- Pilot data should be expanded only after manual review of official datasheets and field mappings.

## IOO Knowledge Base Pilot Update

Test time: 2026-05-19 America/Phoenix

- Knowledge schema created in `data/ioo_product_test.db`.
- `source_allowlist.yaml`: created.
- `knowledge_taxonomy.yaml`: created.
- `crawl_knowledge.py --dry-run --limit 10`: passed.
- `crawl_knowledge.py --limit 30`: completed with 26 pilot documents saved. Live HTTP fetches failed in the local runtime, so the crawler used source-linked curated pilot fallback notes.
- `extract_knowledge.py`: generated 26 knowledge cards and 26 chunks.
- `knowledge_quality_report.py`: generated `knowledge_quality_report.md` and `knowledge_issues.csv`.
- `python test_qa_engine.py`: passed, 23 tests.
- `python test_multibrand_advanced_illumination.py`: passed, 12 tests.
- `python eval_runner.py`: passed, 92/92 golden eval cases, 100.0% pass rate.
- `app.py` imports successfully with the new Knowledge Search and Combined Answer tabs.

Knowledge smoke tests:

- `金属划痕检测用什么光源？`: retrieved 5 knowledge cards and 5 knowledge sources.
- `透明物体边缘检测怎么打光？`: retrieved 5 knowledge cards and 5 knowledge sources.
- `global shutter 和 rolling shutter 有什么区别？`: retrieved shutter-related source cards.
- `透明瓶边缘检测适合什么光源？` in Combined Answer: returned knowledge sources plus Advanced Illumination `BL2-XXYY` and TMS Lite backlight candidates.

Blocked item:

- Full `streamlit run app.py` could not be launched from this sandbox because local Streamlit executable access is denied and `python -m streamlit` is not runnable with the bundled project package. The app module imports successfully and should run in Streamlit Cloud from `requirements.txt`.

Knowledge risks:

- All pilot knowledge documents are pending review.
- All source licenses are currently marked unknown.
- Live crawler behavior should be retested in a network-enabled runtime.
- Rule-based retrieval works for pilot questions but should be upgraded with reviewed embeddings later.

## Investor Demo UI Redesign

Test time: 2026-05-19 America/Phoenix

- Page title changed to `IOO.pro Product Intelligence Test`.
- Main UI reorganized into hero, sidebar control panel, Ask IOO card, unified answer card, sources/evidence, feedback, and recent conversation history.
- Brand selector, Strict/Exploratory mode, and question focus remain available.
- Upload intake added for `png`, `jpg`, `jpeg`, `pdf`, `txt`, and `md`.
- Technical details are now inside a collapsed expander by default.
- Feedback options were simplified to Helpful / Partially helpful / Not helpful.

Validation:

- `python -m py_compile app.py`: passed.
- `python test_qa_engine.py`: passed, 23/23.
- `python test_multibrand_advanced_illumination.py`: passed, 12/12.
- `python eval_runner.py`: passed, 92/92.

Questions checked:

- Which products are suitable for metal scratch inspection?
- Compare TMS Lite and Advanced Illumination ring lights.
- Which products have datasheets?
- Which products are missing voltage information?
- Do you have a model called FAKE-123?
- Advanced Illumination 有没有 TMS Lite 的 CAS2-00-010-X-X？
- 检测透明瓶边缘应该用什么光源？
- 哪些产品有规格书？

Upload checks:

- Uploaded `txt` behavior was smoke-tested with a fake text file object and parsed as text context.
- Uploaded image behavior was smoke-tested with a fake image file object and produced the no-vision-model warning.

Blocked:

- Full local `streamlit run app.py` remains blocked in this Codex sandbox because the available local Streamlit package has no runnable `streamlit.__main__` entry point. The app compiles/imports successfully and should run on Streamlit Cloud from `requirements.txt`.

## Edmund Optics Knowledge Import

Test time: 2026-05-19 America/Phoenix

Commands run:

- `python crawl_edmund_knowledge.py --dry-run --limit 20`
- `python crawl_edmund_knowledge.py --limit 150 --force`
- `python import_edmund_knowledge.py`
- `python extract_edmund_knowledge.py`
- `python knowledge_quality_edmund.py`
- `python test_qa_engine.py`
- `python eval_runner.py`
- `python -m streamlit run app.py --server.headless true --server.port 8501 --server.address 127.0.0.1`

Results:

- Edmund crawler dry-run completed and kept `crawl_delay_seconds = 10.0`.
- The local Codex runtime blocked outbound socket access with WinError 10013, so no new Edmund full pages were downloaded in this environment.
- Existing source-linked Edmund knowledge records in the database: 9.
- Edmund chunks generated: 9.
- Edmund knowledge cards generated: 9.
- `EDMUND_KNOWLEDGE_IMPORT_REPORT.md`, `edmund_knowledge_issues.csv`, and `edmund_knowledge_inventory.csv` were generated.
- `python test_qa_engine.py`: passed, 23/23.
- `python eval_runner.py`: passed, 92/92, 100.0% pass rate.
- Streamlit launch failed only because the bundled Codex runtime cannot execute `streamlit.__main__`; normal deployment should still use `streamlit run app.py`.

## Streamlit Preset Button State Fix

Test time: 2026-05-20 America/Phoenix

Issue:

- Clicking preset question buttons, or clearing the conversation after the
  question box had rendered, could trigger Streamlit's widget state protection:
  `st.session_state["question"]` was being modified after the `Question` widget
  was instantiated.

Fix:

- `app.py` now stores preset and clear actions in `pending_question`.
- The `question` widget state is updated only at the start of the next render,
  before the text area widget is created.

Validation:

- `python -m py_compile app.py`: passed.
- `python test_qa_engine.py`: passed, 23/23.
- `python eval_runner.py`: passed, 92/92, 100.0% pass rate.
