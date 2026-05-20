from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

import answer_engine
import knowledge_engine
import qa_engine
import verifier


APP_TITLE = "IOO.pro Product Database Test"
APP_SUBTITLE = "Machine vision lighting product database test for product search, comparison, and selection support."
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


def save_feedback(question: str, result: dict, feedback: str, rating: str, suspected_issue_type: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    exists = FEEDBACK_PATH.exists()
    matched_models = ", ".join(row.get("model", "") for row in result.get("matched_products", []) if row.get("model"))
    with FEEDBACK_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "question",
                "mode",
                "answer_summary",
                "matched_models",
                "confidence",
                "user_feedback",
                "user_rating",
                "suspected_issue_type",
                "resolved_status",
            ],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "question": question,
                "mode": result.get("mode", ""),
                "answer_summary": answer_summary(result.get("answer", "")),
                "matched_models": matched_models,
                "confidence": result.get("confidence", ""),
                "user_feedback": feedback,
                "user_rating": rating,
                "suspected_issue_type": suspected_issue_type,
                "resolved_status": "open",
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
        "data_source_summary",
        "voltage_source",
        "power_source",
        "category_source",
        "datasheet_url_source",
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
    brand_stats = qa_engine.get_database_stats_by_brand()
    knowledge_stats = knowledge_engine.get_knowledge_stats()
    counts = stats.get("counts", {})
    brands = brand_stats.get("brands", {})
    st.sidebar.header("Database")
    st.sidebar.metric("Total brands", counts.get("brands", 0))
    st.sidebar.metric("TMS Lite products", brands.get("TMS LITE", {}).get("products", 0))
    st.sidebar.metric("Advanced Illumination products", brands.get("Advanced Illumination", {}).get("products", 0))
    st.sidebar.metric("Total products", counts.get("products", 0))
    st.sidebar.metric("Product specs", counts.get("product_specs", 0))
    st.sidebar.metric("Product assets", counts.get("product_assets", 0))
    st.sidebar.metric("Crawl pages", counts.get("crawl_pages", 0))
    st.sidebar.divider()
    st.sidebar.header("Knowledge Base")
    st.sidebar.metric("Knowledge sources", knowledge_stats.get("knowledge_sources", 0))
    st.sidebar.metric("Knowledge documents", knowledge_stats.get("knowledge_documents", 0))
    st.sidebar.metric("Knowledge cards", knowledge_stats.get("knowledge_cards", 0))
    st.sidebar.metric("Knowledge chunks", knowledge_stats.get("knowledge_chunks", 0))
    st.sidebar.metric("Approved documents", knowledge_stats.get("approved_documents", 0))
    st.sidebar.metric("Pending review documents", knowledge_stats.get("pending_review_documents", 0))
    st.sidebar.divider()
    st.sidebar.write(f"Data source: **{stats.get('source_type')}**")
    st.sidebar.write(f"Run mode: **{stats.get('mode')}**")
    st.sidebar.divider()
    st.sidebar.caption("Current MVP limitations")
    st.sidebar.markdown(
        "- Current database covers TMS Lite and Advanced Illumination pilot data.\n"
        "- Answers are based on scraped and normalized product records.\n"
        "- Selection recommendations are preliminary.\n"
        "- Missing values are shown as not available.\n"
        "- This is an IOO.pro internal test system."
    )
    st.sidebar.caption("QA modes")
    st.sidebar.markdown(
        "- **Strict mode**: exact database-backed matches only.\n"
        "- **Exploratory mode**: similar matches allowed, confidence capped at medium."
    )


EXAMPLE_QUESTIONS = [
    "What TMS Lite ring lights are in the database?",
    "Which Advanced Illumination products are backlights?",
    "Which products are 24V?",
    "Compare TMS Lite and Advanced Illumination ring lights.",
    "What lighting is suitable for metal scratch inspection?",
    "How do working distance and field of view affect lens selection?",
]

KNOWLEDGE_QUERY_TERMS = [
    "camera",
    "lens",
    "shutter",
    "resolution",
    "field of view",
    "working distance",
    "focal length",
    "telecentric",
    "exposure",
    "pixel",
    "sensor",
    "why",
    "how",
    "difference",
    "select",
    "\u76f8\u673a",
    "\u955c\u5934",
    "\u5feb\u95e8",
    "\u5206\u8fa8\u7387",
    "\u89c6\u91ce",
    "\u5de5\u4f5c\u8ddd\u79bb",
    "\u7126\u8ddd",
    "\u8fdc\u5fc3",
    "\u66dd\u5149",
    "\u50cf\u7d20",
    "\u4f20\u611f\u5668",
    "\u4e3a\u4ec0\u4e48",
    "\u5982\u4f55",
    "\u600e\u4e48",
    "\u533a\u522b",
    "\u9009\u62e9",
]


def should_use_knowledge_flow(question: str) -> bool:
    text = str(question or "").lower()
    return any(term.lower() in text for term in KNOWLEDGE_QUERY_TERMS)


def render_product_qa() -> None:
    st.subheader("Ask a product question")
    if "question" not in st.session_state:
        st.session_state["question"] = EXAMPLE_QUESTIONS[0]

    qa_mode = st.radio(
        "Answer mode",
        ["Strict mode", "Exploratory mode"],
        index=0,
        horizontal=True,
        help="Strict mode only returns explicit database matches. Exploratory mode can show similar matches and will label them.",
    )
    engine_mode = "strict" if qa_mode == "Strict mode" else "exploratory"
    brand_choice = st.selectbox(
        "Brand selector",
        ["All Brands", "TMS Lite", "Advanced Illumination"],
        index=0,
        help="Choose one brand to prevent cross-brand mixing, or All Brands for cross-brand lookup.",
    )
    brand_filter = None if brand_choice == "All Brands" else brand_choice

    column_count = 3
    cols = st.columns(column_count)
    for i, example in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % column_count]:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state["question"] = example

    question = st.text_area("Question", key="question", height=100)
    ask = st.button("Ask", type="primary")

    if ask and question.strip():
        use_knowledge = should_use_knowledge_flow(question)
        spinner_text = "Searching knowledge base and product database..." if use_knowledge else "Searching the current product database..."
        with st.spinner(spinner_text):
            if use_knowledge:
                result = answer_engine.answer_question(question.strip(), brand_filter=brand_filter, mode=engine_mode)
                result = verifier.verify_answer(result)
            else:
                result = qa_engine.answer_question(question.strip(), brand_filter=brand_filter, mode=engine_mode)
                result = verifier.verify_answer(result)
        st.session_state["last_question"] = question.strip()
        st.session_state["last_result"] = result

    result = st.session_state.get("last_result")
    last_question = st.session_state.get("last_question", question)
    if result:
        st.divider()
        st.subheader("Answer")
        st.write(result.get("answer", ""))

        if result.get("knowledge_answer"):
            with st.expander("Knowledge Answer", expanded=True):
                st.write(result.get("knowledge_answer", ""))

        c1, c2 = st.columns(2)
        c1.metric("Confidence", str(result.get("confidence", "not available")).upper())
        c2.metric("Mode", str(result.get("mode", "local")).upper())

        warnings = result.get("warnings", [])
        if warnings:
            for warning in warnings[:3]:
                st.warning(warning)

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

        with st.expander("Debug / Evidence", expanded=False):
            st.markdown("**Query interpretation**")
            st.json(result.get("query_interpretation", {}))

            st.markdown("**Match reason**")
            match_reason = result.get("match_reason", [])
            if match_reason:
                st.dataframe(match_reason, use_container_width=True, hide_index=True)
            else:
                st.info("No match reason returned.")

            st.markdown("**Evidence table**")
            evidence = result.get("evidence", [])
            if evidence:
                st.dataframe(evidence, use_container_width=True, hide_index=True)
            else:
                st.info("No evidence rows returned.")

            st.markdown("**Verification warnings**")
            if result.get("warnings"):
                for warning in result.get("warnings", []):
                    st.warning(warning)
            else:
                st.success("Verifier did not flag unsupported claims.")

            st.markdown("**Raw sources**")
            st.code(json.dumps(result.get("sources", []), ensure_ascii=False, indent=2), language="json")

            st.markdown("**Missing fields / uncertainty**")
            st.code(json.dumps(result.get("missing_or_uncertain", []), ensure_ascii=False, indent=2), language="json")

            similar_warnings = [
                item for item in result.get("match_reason", [])
                if item.get("similarity_reason") or not item.get("exact_match", True)
            ]
            st.markdown("**Similar matches warning**")
            if similar_warnings:
                st.warning("These are similar matches, not exact matches.")
                st.dataframe(similar_warnings, use_container_width=True, hide_index=True)
            else:
                st.info("No similar-match warning for this answer.")

        st.subheader("Feedback")
        rating = st.radio("Quick rating", ["Helpful", "Not helpful"], horizontal=True, key="feedback_rating")
        suspected_issue_type = st.selectbox(
            "Suspected issue type",
            ["Other", "Wrong answer", "Missing product", "Bad source", "Bad recommendation"],
            key="feedback_issue_type",
        )
        feedback = st.text_area(
            "Was this answer useful? What is wrong or missing?",
            key="feedback_box",
            height=100,
        )
        if st.button("Save feedback"):
            if feedback.strip():
                save_feedback(last_question, result, feedback.strip(), rating, suspected_issue_type)
                st.success(f"Feedback saved to {FEEDBACK_PATH}")
            else:
                st.info("Please write feedback before saving.")


def display_knowledge_sources(sources: list[dict]) -> None:
    if not sources:
        st.info("No knowledge sources returned.")
        return
    for source in sources:
        url = source.get("url") or "not available"
        title = source.get("title") or source.get("source_name") or "knowledge source"
        license_status = source.get("license_status") or "unknown"
        review_status = source.get("review_status") or "pending"
        if url != "not available":
            st.markdown(f"- [{title}]({url}) | review: `{review_status}` | license: `{license_status}`")
        else:
            st.markdown(f"- {title} | review: `{review_status}` | license: `{license_status}`")


def render_knowledge_search() -> None:
    st.subheader("Knowledge Search")
    st.caption("Search the IOO Knowledge Base pilot. Results are source-linked and pending human review unless marked otherwise.")
    if "knowledge_question" not in st.session_state:
        st.session_state["knowledge_question"] = "How do working distance and field of view affect lens selection?"
    question = st.text_area("Knowledge question", key="knowledge_question", height=90)
    if st.button("Search knowledge", type="primary"):
        with st.spinner("Searching knowledge cards and source documents..."):
            st.session_state["knowledge_result"] = knowledge_engine.retrieve_knowledge_for_question(question, limit=8)
    result = st.session_state.get("knowledge_result")
    if not result:
        return
    st.subheader("Knowledge Answer")
    st.write(result.get("knowledge_answer", ""))
    cards = result.get("cards", [])
    st.subheader("Knowledge Cards")
    if cards:
        st.dataframe(
            [
                {
                    "topic": card.get("topic"),
                    "summary": card.get("summary"),
                    "lighting_type": card.get("lighting_type"),
                    "camera_topic": card.get("camera_topic"),
                    "lens_topic": card.get("lens_topic"),
                    "application": card.get("application"),
                    "material": card.get("material"),
                    "review_status": card.get("verified_status"),
                    "tags": ", ".join(card.get("tags") or []),
                    "score": card.get("score"),
                }
                for card in cards
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No knowledge cards matched. Showing document-level matches if available.")
        docs = result.get("documents", [])
        if docs:
            st.dataframe(
                [
                    {
                        "title": doc.get("title"),
                        "source_name": doc.get("source_name"),
                        "summary": doc.get("summary"),
                        "review_status": doc.get("review_status"),
                        "score": doc.get("score"),
                    }
                    for doc in docs
                ],
                use_container_width=True,
                hide_index=True,
            )
    st.subheader("Knowledge Sources")
    display_knowledge_sources(result.get("sources", []))


def render_combined_answer() -> None:
    st.subheader("Combined Answer")
    st.caption("The system retrieves knowledge first, then product candidates from the current product database.")
    if "combined_question" not in st.session_state:
        st.session_state["combined_question"] = "How do working distance and field of view affect lens selection?"
    qa_mode = st.radio(
        "Combined answer mode",
        ["Strict mode", "Exploratory mode"],
        index=0,
        horizontal=True,
        key="combined_mode",
    )
    engine_mode = "strict" if qa_mode == "Strict mode" else "exploratory"
    brand_choice = st.selectbox(
        "Combined brand selector",
        ["All Brands", "TMS Lite", "Advanced Illumination"],
        index=0,
        key="combined_brand",
    )
    brand_filter = None if brand_choice == "All Brands" else brand_choice
    question = st.text_area("Combined question", key="combined_question", height=100)
    if st.button("Ask combined engine", type="primary"):
        with st.spinner("Retrieving knowledge and product candidates..."):
            result = answer_engine.answer_question(question.strip(), brand_filter=brand_filter, mode=engine_mode)
        st.session_state["combined_result"] = result
    result = st.session_state.get("combined_result")
    if not result:
        return
    st.subheader("Knowledge Answer")
    st.write(result.get("knowledge_answer", ""))
    st.subheader("Product Candidates")
    display_dataframe(result.get("product_recommendations", []), "combined_products")
    c1, c2 = st.columns(2)
    c1.metric("Confidence", str(result.get("confidence", "not available")).upper())
    c2.metric("Mode", str(result.get("mode", "local")).upper())
    st.subheader("Knowledge Sources")
    display_knowledge_sources(result.get("knowledge_sources", []))
    st.subheader("Product Sources")
    product_sources = result.get("product_sources", [])
    if product_sources:
        for source in product_sources:
            url = source.get("url") or "not available"
            label = source.get("title") or source.get("type") or "product source"
            if url != "not available":
                st.markdown(f"- **{source.get('type', 'source')}**: [{label}]({url})")
            else:
                st.markdown(f"- **{source.get('type', 'source')}**: not available")
    else:
        st.info("No product sources returned.")
    st.subheader("Missing / Uncertain")
    missing = result.get("missing_or_uncertain", [])
    if missing:
        for item in missing:
            st.warning(item)
    else:
        st.success("No additional uncertainty flagged.")
    with st.expander("Combined Debug / Evidence", expanded=False):
        st.json(
            {
                "query_interpretation": result.get("query_interpretation", {}),
                "warnings": result.get("warnings", []),
                "knowledge_cards": result.get("knowledge_cards", []),
                "match_reason": result.get("match_reason", []),
            }
        )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="QA", layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    if not check_password():
        st.stop()

    sidebar()
    product_tab, knowledge_tab, combined_tab = st.tabs(["Product QA", "Knowledge Search", "Combined Answer"])
    with product_tab:
        render_product_qa()
    with knowledge_tab:
        render_knowledge_search()
    with combined_tab:
        render_combined_answer()


if __name__ == "__main__":
    main()
