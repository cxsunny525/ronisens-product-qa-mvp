"""Patch the hosted Streamlit app when Python starts."""

try:
    import qa_engine
    import zh_qa_adapter

    qa_engine.answer_question = zh_qa_adapter.answer_question
except Exception:
    pass

try:
    import streamlit as _st

    _original_markdown = _st.markdown

    def _ioo_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("Industrial Optics Online", "Industrial Options Online")
        return _original_markdown(body, *args, **kwargs)

    _st.markdown = _ioo_markdown
except Exception:
    pass
