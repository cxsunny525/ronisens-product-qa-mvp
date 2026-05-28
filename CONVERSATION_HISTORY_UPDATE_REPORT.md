# Conversation History Update Report

Date: 2026-05-27

## What changed

- `Clear conversation` behavior was replaced with `New conversation` behavior.
- Starting a new conversation no longer deletes previous Q&A history in the browser session.
- Conversations are now stored as session-based threads in `st.session_state["threads"]`.
- The left rail now lists prior conversation threads and lets the user reopen one.
- Reopened threads restore the last answer and conversation context so follow-up questions can continue from that case.
- The active conversation can be exported as a JSON file from the left rail.

## Persistence scope

- Current implementation persists history until the Streamlit browser session ends.
- For future member accounts, the same thread payload should be saved to a database table keyed by user ID.

## Tests

- `app.py` Python compile check: passed.
- `test_public_brand_safety.py`: passed, 2/2.
- `test_qa_engine.py`: passed, 23/23.

## Notes

- No product database logic was changed.
- No supplier or internal product source fields were added to the public UI.
- The update is UI/session-state only and keeps existing IOO product search behavior intact.
