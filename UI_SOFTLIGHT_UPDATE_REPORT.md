# IOO Soft Light Lab UI Update Report

Date: 2026-05-27

## Summary

The current Streamlit app was updated to follow the uploaded Soft Light Lab
visual direction while preserving the existing IOO question-answering,
knowledge retrieval, product recommendation, public SKU, CSV/database, and
deployment logic.

## Files Changed

- `app.py`
  - Updated UI styling, layout, responsive behavior, header, history area,
    account/credit presentation, and product recommendation rail.
- `docs/design/ioo-softlight/`
  - Added the uploaded Soft Light Lab reference package and assets.
- `IOO_GITHUB_UPLOAD_READY/app.py`
  - Synced the deploy-ready copy.
- `IOO_GITHUB_UPLOAD_READY/docs/design/ioo-softlight/`
  - Synced the design assets needed by the product recommendation cards.

## Pure UI Changes

- Replaced the previous dark/technical look with Soft Light Lab colors:
  mist white, pale blue-green, soft teal, amber credits, and graphite text.
- Added a clearer IOO top bar with logo mark, credits, streak, and sign-in/apply
  entry.
- Added a left rail for account snapshot, dialog history, and field shortcuts.
- Kept the AI question box in the center.
- Added a right-side recommended product rail for desktop.
- Added a mobile sticky recommendation tab for smaller screens.
- Added product-card illustrations using the provided design assets.
- Added placeholder Details / Spec sheet / Save / Compare actions.

## Mock / Placeholder Data

- `8-day engineer streak` is a UI placeholder.
- Sign in / Apply is a UI placeholder.
- Reward target is currently a local placeholder in `reward_target()`.
- Details, Spec sheet, Save, and Compare actions are UI placeholders.
- Product illustrations are category-style SVG visuals, not final SKU photos.

## Preserved Logic

- Existing answer engine is still called through `answer_engine.answer_question()`.
- Existing public SKU data is still read from `public_products.csv`.
- Existing IOO-only recommendation behavior is preserved.
- Existing upload, feedback, points, and conversation logging remain in place.
- No product crawler or database schema rewrite was introduced.

## Brand / Supply Chain Protection

- Public UI scans found no old public brand wording or internal supplier-field
  names in `app.py`.
- Product cards show IOO public-facing models only.
- Private traceability fields remain hidden from the public UI.

## Tests

- `python -m py_compile app.py`: passed.
- `python test_qa_engine.py`: passed, 23/23.
- Upload-ready `app.py` import check: passed.

## Local Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Possible Impact

- This is primarily a UI update.
- The product recommendation rail now shows product cards beside the answer, but
  it uses the same existing `closest_ioo_products` result data.
- The product action buttons are placeholders until account, save, compare, and
  spec-sheet routing are implemented.
