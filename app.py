from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

import qa_engine
import zh_qa_adapter


APP_TITLE = "Ronisens Product QA MVP"
APP_SUBTITLE = "TMS Lite product database assistant for machine vision lighting selection and competitive research."
LOG_DIR = Path("logs")
FEEDBACK_PATH = LOG_DIR / "feedback.csv"


def get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)  # type: ignore[attr-defined]
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name)


def check_password() -> bool:
    configured_password = get_secret("APP_PASSWORD")
    if not configured_password:
        st.warning("APP_PASSWORD is not set. Development mode is open; set APP_PASSWORD before sharing a public URL.")
        return True

    if st.session_state.get("authenticated"):
        return True

    with st.form("password_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")
    if submitted:
        if password == configured_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def answer_summary(answer: str, limit: int = 240) -> str:
    text = " ".join(str(answer or "").split())
    return text[:limit]


def save_feedback(question: str, result: dict, feedback: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    exists = FEEDBACK_PATH.exists()
    with FEEDBACK_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "question", "answer_summary", "confidence", "mode", "feedback"],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "question": question,
                "answer_summary": answer_summary(result.get("answer", "")),
                "confidence": result.get("confidence", ""),
                "mode": result.get("mode", ""),
                "feedback": feedback,
            }
        )


def display_dataframe(rows: list[dict], key: str) -> None:
    if not rows:
        st.info("No rows to display.")
        return
    preferred = [
        "model",
        "brand",
        "family",
        "series",
        "category",
        "light_type",
        "color",
        "voltage",
        "power",
        "current",
        "product_url",
        "datasheet_url",
        "score",
        "match_reasons",
    ]
    normalized = []
    for row in rows:
        normalized.append({col: row.get(col, "not available") for col in preferred if col in row})
    column_config = {}
    try:
        column_config = {
            "product_url": st.column_config.LinkColumn("Product URL"),
            "datasheet_url": st.column_config.LinkColumn("Datasheet URL"),
        }
    except Exception:
        column_config = {}
    st.dataframe(normalized, use_container_width=True, hide_index=True, column_config=column_config, key=key)


def sidebar() -> None:
    stats = qa_engine.get_database_stats()
    counts = stats.get("counts", {})
    st.sidebar.header("Database")
    st.sidebar.metric("Brands", counts.get("brands", 0))
    st.sidebar.metric("Product families", counts.get("product_families", 0))
    st.sidebar.metric("Products", counts.get("products", 0))
    st.sidebar.metric("Product specs", counts.get("product_specs", 0))
    st.sidebar.metric("Product assets", counts.get("product_assets", 0))
    st.sidebar.metric("Crawl pages", counts.get("crawl_pages", 0))
    st.sidebar.divider()
    st.sidebar.write(f"Data source: **{stats.get('source_type')}**")
    st.sidebar.write(f"Run mode: **{stats.get('mode')}**")
    st.sidebar.divider()
    st.sidebar.caption("Current MVP limitations")
    st.sidebar.markdown(
        "- Current database only covers TMS Lite.\n"
        "- Answers are based on scraped database records.\n"
        "- Selection recommendations are preliminary.\n"
        "- Missing values are shown as not available."
    )


EXAMPLE_QUESTIONS = [
    "What TMS Lite ring lights are in the database?",
    "Which products are 24V?",
    "\u6761\u5f62\u7684\u5149\u6e90\u6709\u54ea\u4e9b\uff1f",
    "\u54ea\u4e9b\u4ea7\u54c1\u6709\u89c4\u683c\u4e66\uff1f",
    "Compare CAS2-00-010-X-X, BHP1010-X-X, DLQ2-90-050-1-X.",
    "\u54ea\u4e9b\u4ea7\u54c1\u6ca1\u6709\u7535\u538b\u53c2\u6570\uff1f",
    "\u68c0\u6d4b\u91d1\u5c5e\u5212\u75d5\u5e94\u8be5\u770b\u4ec0\u4e48\u5149\u6e90\uff1f",
    "\u900f\u660e\u74f6\u8fb9\u7f18\u68c0\u6d4b\u9002\u5408\u4ec0\u4e48\u5149\u6e90\uff1f",
    "Which fields are missing most often?",
]


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="QA", layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    if not check_password():
        st.stop()

    sidebar()

    st.subheader("Ask a product question")
    if "question" not in st.session_state:
        st.session_state["question"] = EXAMPLE_QUESTIONS[0]

    cols = st.columns(4)
    for i, example in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % 4]:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state["question"] = example

    question = st.text_area("Question", key="question", height=100)
    ask = st.button("Ask", type="primary")

    if ask and question.strip():
        with st.spinner("Searching the current product database..."):
            result = zh_qa_adapter.answer_question(question.strip())
        st.session_state["last_question"] = question.strip()
        st.session_state["last_result"] = result

    result = st.session_state.get("last_result")
    last_question = st.session_state.get("last_question", question)
    if result:
        st.divider()
        st.subheader("Answer")
        st.write(result.get("answer", ""))

        c1, c2 = st.columns(2)
        c1.metric("Confidence", str(result.get("confidence", "not available")).upper())
        c2.metric("Mode", str(result.get("mode", "local")).upper())

        st.subheader("Matched Products")
        display_dataframe(result.get("matched_products", []), "matched_products")

        st.subheader("Key Specs Table")
        specs = result.get("spec_table", [])
        if specs:
            st.dataframe(specs, use_container_width=True, hide_index=True)
        else:
            st.info("No spec table returned for this question.")

        st.subheader("Sources")
        sources = result.get("sources", [])
        if sources:
            for source in sources:
                url = source.get("url") or "not available"
                label = source.get("title") or source.get("type") or "source"
                if url != "not available":
                    st.markdown(f"- **{source.get('type', 'source')}**: [{label}]({url})")
                else:
                    st.markdown(f"- **{source.get('type', 'source')}**: not available")
        else:
            st.info("No sources returned.")

        st.subheader("Missing / Uncertain Information")
        missing = result.get("missing_or_uncertain", [])
        if missing:
            for item in missing:
                st.warning(item)
        else:
            st.success("No additional uncertainty was flagged by the engine.")

        st.subheader("Feedback")
        feedback = st.text_area(
            "Was this answer useful? What is wrong or missing?",
            key="feedback_box",
            height=100,
        )
        if st.button("Save feedback"):
            if feedback.strip():
                save_feedback(last_question, result, feedback.strip())
                st.success(f"Feedback saved to {FEEDBACK_PATH}")
            else:
                st.info("Please write feedback before saving.")


if __name__ == "__main__":
    main()
