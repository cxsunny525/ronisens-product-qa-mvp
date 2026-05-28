# TEST_REPORT

Date: 2026-05-27

## Scope

This report covers the IOO one-to-one product database migration and grounded
product search regression checks.

## Test Environment

- Workspace: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai`
- Runtime: bundled Codex Python
- Product database: `data/ioo_products.db`
- Public product CSV: `public_products.csv`

## Database Verification

- Source product count: 654
- Generated IOO product count: 654
- Product specs: 6712
- Product assets imported into IOO DB: 2783 linked assets
- Internal mapping rows: 654
- Public products CSV rows: 654
- SKU mapping rows: 654
- Public model leakage check: 0 public models contain TMS tokens

## Automated Tests

- `test_ioo_product_mapping.py`: passed, 6/6
- `test_public_brand_safety.py`: passed, 2/2
- `test_qa_engine.py`: passed, 23/23
- Python compile check for updated modules: passed

## Query Regression Checks

1. `List all red lights.`
   - Intent: list/search
   - Total matched: 200
   - Showing: first 20
   - Result source: IOO product database

2. `Which IOO products are red lights?`
   - Intent: list/search
   - Total matched: 200
   - Showing: first 20

3. `Which IOO products are 24V?`
   - Intent: list/search
   - Total matched: 438
   - Showing: first 20

4. `Show all IOO ring lights.`
   - Intent: list/search
   - Total matched: 56
   - Showing: first 20

5. `Show all IOO backlights.`
   - Intent: list/search
   - Total matched: 74
   - Showing: first 20

6. `Inspect transparent bottle edges.`
   - Intent: recommendation
   - Returns closest IOO candidates from the database
   - Does not invent product models

7. `Detect scratches on reflective metal.`
   - Intent: recommendation
   - Returns closest IOO candidates from the database
   - Uses workaround language when not an exact fit

8. `Do you have IOO-CAS2-00-010-X-X?`
   - Intent: model lookup
   - Exact public IOO model found

9. `Do you have CAS2-00-010-X-X?`
   - Intent: model lookup
   - Bare/internal-style user input resolves to the public IOO model

10. `Compare IOO-CAS2-00-010-X-X and IOO-BHP1010-X-X.`
    - Intent: comparison
    - Only database-backed IOO models are compared

11. `Do you have a fake product called IOO-FAKE-123?`
    - Intent: model lookup
    - Correctly reports no exact IOO product match
    - No fake model is recommended

12. `What if no IOO product exactly matches my application?`
    - Intent: recommendation
    - Uses closest-fit / workaround language

## Public Brand Safety

Checked public-facing surfaces:

- `public_products.csv`
- `app.py`
- `README.md`
- representative answer outputs

Result: no public-facing TMS, TMS Lite, Advanced Illumination, supplier,
internal_model, or internal_supplier leakage was detected by the automated test.

## Notes

- Internal mapping is preserved in `data/ioo_products.db` and
  `internal_sku_mapping.csv` for traceability, but the public UI and public CSV
  use IOO-only product names.
- Product assets in the IOO database include linked product assets. The source
  database has additional catalog/family assets that are not linked to a product
  row.
- The app should be deployed from `IOO_GITHUB_UPLOAD_READY_CLEAN`, not the older
  upload folder.

## Bilingual UX / Color Intent Regression

Date: 2026-05-27

### Chinese

1. `有没有紫色光源？`
   - Language: zh
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

2. `有紫光吗？`
   - Language: zh
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

3. `有没有 UV 光源？`
   - Language: zh
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

4. `有没有 365nm 光源？`
   - Language: zh
   - Intent: attribute_search
   - Total matched: 12
   - Showing: 12

5. `有哪些红光光源？`
   - Language: zh
   - Intent: list_search
   - Returns count and product list, not a generic recommendation

6. `哪些 IOO 产品是 24V？`
   - Language: zh
   - Intent: list_search
   - Total matched: 438
   - Showing: 20

7. `检测金属划痕应该用什么光源？`
   - Language: zh
   - Intent: recommendation
   - Returns database-backed IOO candidates

8. `透明瓶边缘检测应该怎么打光？`
   - Language: zh
   - Intent: recommendation
   - Returns backlight-oriented IOO candidates from the database

### English

1. `Do you have purple lights?`
   - Language: en
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

2. `Do you have violet lights?`
   - Language: en
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

3. `Do you have UV lights?`
   - Language: en
   - Intent: attribute_search
   - Total matched: 33
   - Showing: 20

4. `Do you have 365nm lights?`
   - Language: en
   - Intent: attribute_search
   - Total matched: 12
   - Showing: 12

5. `Which IOO products are red lights?`
   - Language: en
   - Intent: list_search
   - Returns count and product list

6. `Which IOO products are 24V?`
   - Language: en
   - Intent: list_search
   - Total matched: 438
   - Showing: 20

7. `What lighting is suitable for transparent bottle edge detection?`
   - Language: en
   - Intent: recommendation
   - Returns database-backed IOO candidates

## Additional Verification

- `test_public_brand_safety.py`: passed, 2/2
- `test_qa_engine.py`: passed, 23/23
- Python compile check: passed for `app.py`, `answer_engine.py`, `product_search.py`, and `sku_mapping.py`

## Conversation History Persistence Update

- Changed the former clear action into a new conversation action. Starting a new conversation no longer deletes the left-side conversation history.
- Added browser-session conversation threads in Streamlit session state.
- Added clickable left-side thread history so a previous conversation can be reopened and continued.
- Added active-thread export as JSON for reviewing or sharing prior conversations.
- Current persistence level: browser-session Streamlit state. Future logged-in member persistence should store the same thread payloads in a server-side user table.
- Lightweight verification on 2026-05-27:
  - `app.py` compile check: passed
  - `test_public_brand_safety.py`: passed, 2/2
  - `test_qa_engine.py`: passed, 23/23

## Intent Routing Fix For English Selection Questions

- Fixed an intent-routing bug where English questions beginning with `which` could be treated as list searches even when the user was asking for lighting selection guidance.
- Regression example: `which light I should consider if I want to detect the scratch on the metal ?`
  - Before: `list_search`, no matched products.
  - After: `recommendation`, returns IOO dark-field candidates from the product database.
  - Example candidates: `IOO-F-DLC3-00-070-DIFFUSER`, `IOO-F-DLC3-00-100-DIFFUSER`, `IOO-F-DLC3-00-120-DIFFUSER`.
- Verified list/availability searches still work:
  - `Which IOO products are red lights?`: `list_search`, 413 matches, showing first 20.
  - `Do you have purple lights?`: `attribute_search`, 33 matches, showing first 20.

## Semantic Router And Off-Topic Handling Update

- Added a semantic routing layer in `answer_engine.py`.
- If `OPENAI_API_KEY` is available, IOO first asks OpenAI to classify the current user turn as product availability search, product list search, model lookup, comparison, lighting selection, knowledge explanation, identification help, or off-topic.
- If OpenAI is unavailable, local fallback rules perform the same routing.
- Current-turn product retrieval now prioritizes the user's latest question; prior conversation context is only merged for ambiguous follow-ups or uploaded text notes. This prevents a previous product search, such as `有没有绿色光源`, from trapping the next turn in product-search mode.
- Regression test:
  - First question: `有没有绿色光源` -> `attribute_search`, 375 matches.
  - Second question: `which light I should consider if I want to detect the scratch on the metal ?` -> `recommendation`, 5 IOO dark-field candidates.
- Off-topic tests:
  - `今天天气怎么样？` -> `off_topic`, no product recommendation.
  - `Can you recommend a good pizza recipe?` -> `off_topic`, no product recommendation.
- Knowledge test:
  - `What is global shutter in machine vision?` -> `knowledge_explanation`.

## Contextual Product Follow-Up Update

- Added support for follow-up questions that refer to the previous IOO shortlist with phrases such as `this model`, `that one`, `这个型号`, or short questions such as `what voltage?`.
- Pricing follow-ups now connect to the previously recommended IOO model(s), but clearly state that pricing is not stored in the current IOO product database and must go through quote confirmation.
- Spec/detail follow-ups now return public database details for the previous candidate models instead of treating `this model` as a missing model.
- Regression sequence:
  - First question: `Inspect transparent bottle edges.` -> recommendation with IOO candidates.
  - Follow-up: `how much is this model ?` -> `pricing_followup`, uses previous candidates, no invented price.
  - Follow-up: `what voltage?` -> `product_detail_followup`, uses previous candidates.
  - Follow-up: `what are the specs of this model?` -> `product_detail_followup`.
  - Follow-up: `datasheet for this model?` -> `product_detail_followup`.
- Verification:
  - `test_public_brand_safety.py`: passed, 2/2.
  - `test_qa_engine.py`: passed, 23/23.
  - Python compile check passed for `answer_engine.py`, `app.py`, and `product_search.py`.

## Quote Request UI Update

- Pricing follow-up answers now include a quote request payload with:
  - `email`: `inquiry@ioo.pro`
  - prefilled subject
  - prefilled email body
  - interested IOO public models from the previous recommendation
- Streamlit now renders a quote request panel for `pricing_followup` answers.
- If the visitor is not registered in the current demo session, clicking the quote action opens a sign-in / apply panel first.
- After the visitor enters contact details, the page shows a `mailto:inquiry@ioo.pro` send button with the interested IOO models already included in the email draft.
- No pricing is invented on-page; the quote email asks the IOO team to confirm pricing based on quantity, timing, and configuration.
- Verification:
  - `Inspect transparent bottle edges.` -> recommendation with IOO candidates.
  - `how much is this model ?` -> `pricing_followup`.
  - Generated quote request includes `inquiry@ioo.pro` and the previous IOO candidate models.
  - `test_public_brand_safety.py`: passed, 2/2.
  - `test_qa_engine.py`: passed, 23/23.
