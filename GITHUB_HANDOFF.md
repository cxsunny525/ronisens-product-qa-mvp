# GitHub Handoff

## Current Status

The multi-brand Advanced Illumination pilot update is complete locally. The
current workspace contains all updated code, reports, database files, and
generated eval/data-quality outputs.

The Streamlit Cloud app will only show these changes after the GitHub repo is
updated and Streamlit redeploys.

## Prepared Upload ZIP

Upload this ZIP to the existing GitHub repository if direct push is not
available:

`C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\ioo-pro-product-database-test-advanced-illumination-20260519.zip`

Recommended GitHub path:

Use the existing GitHub repository for this test system, or create a new
repository named `ioo-pro-product-database-test`.

Known existing repo: use the GitHub repository you already opened for this
Streamlit test app. The user-facing app name is `IOO.pro Product Database Test`.

Important: include `data/ioo_product_test.db` in the upload. Without it, the
hosted app will continue to show only the old TMS Lite database.

## Manual Upload Steps

1. Open the GitHub repository.
2. Click `Add file` -> `Upload files`.
3. Drag the files from the ZIP into the repo root.
4. Confirm overwrite for existing files.
5. Commit directly to `main` with this message:

`Add Advanced Illumination pilot data`

6. Open Streamlit Cloud.
7. Reboot/redeploy the app.

## Expected After Redeploy

- App shows `Strict mode` and `Exploratory mode`.
- Strict mode is default.
- Debug / Evidence expander is available.
- Unsupported questions return no-answer messages instead of guessed answers.
- Sidebar shows two brands, including 13 Advanced Illumination pilot products.
- Brand selector includes `All Brands`, `TMS Lite`, and `Advanced Illumination`.
- `eval_report.md` shows 92/92 golden eval cases passing.
