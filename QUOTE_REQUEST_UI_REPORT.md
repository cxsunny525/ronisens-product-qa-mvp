# Quote Request UI Report

Date: 2026-05-27

## What changed

- Added quote request metadata to `pricing_followup` answers in `answer_engine.py`.
- Added a Streamlit quote request panel in `app.py`.
- Interested IOO public models from the previous recommendation are automatically inserted into the email draft.
- Quote requests are addressed to `inquiry@ioo.pro`.
- The generated email includes:
  - IOO model(s)
  - application / inspection need
  - estimated quantity placeholder
  - timeline placeholder
  - customization / mounting / cable notes placeholder

## Login / registration gate

- If the visitor is not registered in the current demo session, clicking the quote action opens a sign-in / apply panel first.
- The MVP stores contact details in Streamlit session state only.
- After entering contact details, the user can click a prefilled `mailto:inquiry@ioo.pro` link.

## Important behavior

- The website does not invent pricing.
- The quote email is prefilled, but final pricing must be confirmed by IOO based on quantity, timing, and configuration.
- No private supplier information is displayed.

## Tests

- `Inspect transparent bottle edges.` followed by `how much is this model ?` produces `pricing_followup`.
- Quote request payload includes the previous IOO candidate models.
- Quote request payload uses `inquiry@ioo.pro`.
- Python compile check passed for `app.py`, `answer_engine.py`, and `product_search.py`.
- `test_public_brand_safety.py`: passed, 2/2.
- `test_qa_engine.py`: passed, 23/23.
