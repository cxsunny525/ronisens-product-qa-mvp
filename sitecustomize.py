"""Patch the hosted Streamlit app with Chinese QA support when Python starts."""

try:
    import qa_engine
    import zh_qa_adapter

    qa_engine.answer_question = zh_qa_adapter.answer_question
except Exception:
    pass
