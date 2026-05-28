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
- Enlarged the IOO brand lockup into a proper wordmark and replaced the first
  `O` with the target-style optic mark so the brand feels more confident and
  less tucked into the corner.
- Added a left rail for account snapshot, dialog history, and field shortcuts.
- Kept the AI question box in the center.
- Added a right-side recommended product rail for desktop.
- Added a mobile sticky recommendation tab for smaller screens.
- Added product-card illustrations using the provided design assets.
- Added placeholder Details / Spec sheet / Save / Compare actions.
- Changed the question input to an Enter-to-submit form so engineers do not
  need to click the Ask button for normal use.
- Reworked the first-screen hierarchy so the home view focuses on one clear
  inspection-question entry point instead of competing hero, history, product,
  and reward blocks.
- Replaced the opening headline with "Turn an inspection problem into a
  lighting test plan." and reduced the right rail to a quiet product shortlist.
- Restyled the submit control as a soft teal `Ask IOO` button inside the input
  row instead of a dark `Send` button.
- Strengthened answer-page typography contrast for headings, body text,
  captions, alerts, and advanced-detail expanders so text remains legible on
  the soft light background.
- Removed the visible "Was this useful?" feedback/rating block from the answer
  area to reduce clutter.
- Fixed the left dialog-history rail so conversation items render as safe UI
  cards instead of occasionally leaking raw HTML/code.
- Forced the upload expander and uploaded-file chip back to a light, readable
  style after an answer is shown.
- Added a conversation state: after the first question, the large welcome hero
  is hidden, example prompts are removed from the main path, upload moves into
  a collapsed control, and the latest answer appears directly below the input.
- Replaced raw HTML product recommendation snippets with native Streamlit
  product cards so the page no longer displays `<article class=...>` code.
- Added mobile-first polish:
  - The left rail is hidden on phone-width screens.
  - The desktop product rail is hidden on phone-width screens.
  - The center question workflow becomes the primary mobile view.
  - Example prompt buttons use a wider two-column layout instead of cramped
    five-column chips.
  - A fixed bottom product tab links to a mobile product drawer.
  - The mobile product drawer shows public IOO product cards below the answer.

## Mock / Placeholder Data

- `8-day engineer streak` is a UI placeholder.
- Sign in / Apply is a UI placeholder.
- Reward target is currently a local placeholder in `reward_target()`.
- Details, Spec sheet, Save, and Compare actions are UI placeholders.
- Product illustrations are category-style SVG visuals, not final SKU photos.
- Mobile product drawer open behavior uses a simple in-page anchor, not a
  JavaScript bottom sheet.

## Preserved Logic

- Existing answer engine is still called through `answer_engine.answer_question()`.
- Existing public SKU data is still read from `public_products.csv`.
- Existing IOO-only recommendation behavior is preserved.
- Existing upload, feedback, points, and conversation logging remain in place.
- No product crawler or database schema rewrite was introduced.
- The app still uses the same answer engine and product recommendation data;
  this update only changes the interaction flow and rendering.

## Brand / Supply Chain Protection

- Public UI scans found no old public brand wording or internal supplier-field
  names in `app.py`.
- Product cards show IOO public-facing models only.
- Private traceability fields remain hidden from the public UI.

## Tests

- `python -m py_compile app.py`: passed.
- `python test_qa_engine.py`: passed, 23/23.
- Upload-ready `app.py` import check: passed.
- Public UI scan found no old supplier/brand leakage in `app.py`.
- Public UI scan found no raw `<article>` product card output in `app.py` or
  `IOO_GITHUB_UPLOAD_READY/app.py`.

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

