# Test Report

## Test Time

2026-05-18 18:00 America/Phoenix

## Test Environment

- Workspace: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai`
- Python: bundled Codex Python 3.12 runtime
- Database: `data/tms_lite_full.db`
- Local dependency install: `.packages/`
- OpenAI API key: not set during tests
- App mode tested: local fallback mode

## Passed Items

| Test | Result |
| --- | --- |
| `python test_qa_engine.py` | Passed, 13 tests |
| `python -m pytest -q` | Passed, 13 tests |
| Database loads from SQLite | Passed |
| CSV fallback path exists in code | Passed by implementation review |
| Search returns products | Passed |
| Real model lookup works | Passed |
| Missing model does not fabricate | Passed |
| Product comparison works | Passed |
| Missing fields summary works | Passed |
| Datasheet/source output works | Passed |
| No `OPENAI_API_KEY` local fallback works | Passed |
| 10 evaluation-style questions executed | Passed |
| Feedback write to `logs/feedback.csv` | Passed |
| Streamlit HTTP startup | Passed, HTTP 200 at `http://127.0.0.1:8501` |
| Password unset development mode | Passed by implementation and local startup; warning is shown in app |

## Streamlit Startup Details

Command used for local verification:

```powershell
$env:PYTHONPATH='.packages'
python -m streamlit run app.py --global.developmentMode=false --server.headless=true --server.port=8501 --server.address=127.0.0.1
```

Result:

```text
STATUS 200
URL: http://127.0.0.1:8501
```

## Tested Questions

- Does TMS Lite have CAS2-00-010-X-X?
- Which products are 24V?
- Find red lights with datasheets.
- Compare CAS2-00-010-X-X, BHP1010-X-X, DLQ2-90-050-1-X.
- Which products are missing datasheets?
- Which fields are missing most often?
- What lighting type is suitable for metal scratch inspection?
- Transparent bottle edge detection: what products may be useful?
- Does TMS Lite have FAKE-ABC-9999?
- What is the price of CAS2-00-010-X-X?

## Fixes Made During Testing

- Prevented short noisy model values such as `R` from matching arbitrary English text.
- Added explicit unsupported commercial-field handling for price, stock, lead time, inventory, availability, and warranty.
- Added brand-scope guardrails for non-TMS brands such as Basler, CCS, OPT, Smart Vision Lights, and Cognex.
- Added `no voltage` data-quality handling.
- Adjusted local Streamlit verification to disable Streamlit development mode when using the project-local `.packages/` dependency directory.

## Failed Items

| Item | Status |
| --- | --- |
| Public deployment URL | Not completed; account/GitHub/Streamlit Cloud authorization unavailable |
| GitHub push | Not completed; `git` and `gh` not available on PATH |

## Unresolved Issues

- The current app only covers TMS Lite.
- Some datasheet URLs are OneDrive/FutureIP redirect URLs rather than resolved final PDF URLs.
- Some dimension fields such as `A (mm)` and `ØA (mm)` need family-level semantic mapping.
- Noisy extracted records such as normalized model `R` should be cleaned in the next database refresh.

## Remote Testing Standard

The code meets the local readiness standard for remote testing. A public URL can
be produced after pushing to GitHub and deploying through Streamlit Cloud or
Render with `APP_PASSWORD` configured.
