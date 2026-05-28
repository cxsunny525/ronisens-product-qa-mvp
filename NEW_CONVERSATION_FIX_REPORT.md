# New Conversation Fix Report

## Issue

Clicking `New conversation` raised a Streamlit exception after the question input had already appeared on the page.

## Cause

The `start_new_thread()` and `load_thread()` paths were clearing `st.session_state["question"]` during the same render pass in which the `question` input widget had already been instantiated. Streamlit does not allow directly changing an instantiated widget key in that situation.

## Fix

- Updated `app.py` to route those changes through `st.session_state["pending_question"]`.
- `render_search_card()` applies `pending_question` before creating the input widget on the next rerun.
- Conversation history remains in the browser session; starting a new conversation no longer deletes previous left-rail threads.

## Files Changed

- `app.py`
- `TEST_REPORT.md`
- `NEW_CONVERSATION_FIX_REPORT.md`

## Verification

- Python compile check for `app.py`, `answer_engine.py`, and `product_search.py`: passed.
- `test_public_brand_safety.py`: passed, 2/2.
- `test_qa_engine.py`: passed, 23/23.

## Deployment Note

Because `git` is not available in this local runtime, the changed files have been prepared for manual GitHub upload through `IOO_GITHUB_UPLOAD_READY_CLEAN`.
