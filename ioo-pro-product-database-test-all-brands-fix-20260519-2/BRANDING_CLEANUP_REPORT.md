# Branding Cleanup Report

## Summary

The active website source, project docs, handoff docs, Streamlit metadata, and
test/eval text have been renamed to IOO.pro / IOO branding.

Primary user-visible product name:

`IOO.pro Product Database Test`

Short brand:

`IOO`

Domain expression:

`ioo.pro`

## Files Updated

- `app.py`
- `qa_engine.py`
- `README.md`
- `DEPLOYMENT.md`
- `HANDOFF_TO_PARTNER.md`
- `TEST_REPORT.md`
- `DEPLOYMENT_RESULT.md`
- `eval_questions.md`
- `golden_eval_questions.yaml`
- `GITHUB_HANDOFF.md`
- `UPLOAD_TO_GITHUB_CN.md`
- `start_app.cmd`
- `test_qa_engine.py`
- `data_quality_report.md`
- `eval_report.md`

## Replacement Rules Applied

- Former full MVP title -> `IOO.pro Product Database Test`
- Former product database name -> `IOO.pro Product Database`
- Former product QA name -> `IOO.pro Product QA`
- Former mixed-case brand name -> `IOO`
- Former lowercase brand name -> `ioo`
- Former uppercase brand name -> `IOO`

## Streamlit UI

- Page title is now `IOO.pro Product Database Test`.
- Browser tab title uses `page_title="IOO.pro Product Database Test"`.
- Subtitle is now:
  `Machine vision lighting product database test for product search, comparison, and selection support.`
- Sidebar limitations now show:
  - Current database covers TMS Lite.
  - Answers are based on scraped and normalized product records.
  - Selection recommendations are preliminary.
  - Missing values are shown as not available.
  - This is an IOO.pro internal test system.

## Remaining Old-Brand Residuals

Active source and documentation files checked for old-brand tokens: none found.

Residual old-brand tokens still exist only in non-active historical packaging
artifacts:

- old upload-copy folders generated during earlier deployment handoff attempts
- old zip package filenames generated before this rename

These artifacts are not imported by the app and are not part of the active
Streamlit deployment source. Recursive deletion of those stale folders was
blocked by the current sandbox policy, so they were left in place and excluded
from active-source verification.

Raw crawler HTML under `data/raw/` also contains unrelated substring matches
inside original product/source text. This is original TMS Lite source data and
was not modified.

## Verification

Active-source search command:

```powershell
rg -n -i "<old-brand-pattern>" app.py qa_engine.py README.md DEPLOYMENT.md HANDOFF_TO_PARTNER.md TEST_REPORT.md DEPLOYMENT_RESULT.md eval_questions.md golden_eval_questions.yaml canonical_fields.yaml requirements.txt .env.example .gitignore GITHUB_HANDOFF.md UPLOAD_TO_GITHUB_CN.md start_app.cmd test_qa_engine.py data_quality_report.md eval_report.md
```

Result: no active-source matches.

Workspace search excluding raw data, stale packaging folders, generated zip
files, local dependency folders, caches, and SQLite databases:

```powershell
rg -n -i "<old-brand-pattern>" . -g "!data/raw/**" -g "!*old-brand-upload-copy*/**" -g "!*.zip" -g "!*.db" -g "!.packages/**" -g "!.runtime_pkgs/**" -g "!__pycache__/**" -g "!.pytest_cache/**"
```

Result: no active workspace matches.

## Tests

- `python test_qa_engine.py`: blocked because `python` is not on PATH in this shell.
- Bundled Python equivalent: passed, 23 tests OK.
- `python eval_runner.py`: blocked because `python` is not on PATH in this shell.
- Bundled Python equivalent: passed, 61/61 eval cases, 100.0%.
- Python compile check: passed.
- `streamlit run app.py`: blocked because `streamlit` is not on PATH in this shell.

## Deployment / Push

- Git commit was not created because `git` is not installed or not available on PATH.
- Push was not completed for the same reason.
- Current public test URL should remain unchanged after uploading these files to
  the existing Streamlit-connected repository.

## Upload Package

An IOO-named upload package was created:

`ioo-pro-product-database-test-20260519.zip`
