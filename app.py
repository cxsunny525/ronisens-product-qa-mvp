from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

import answer_engine
import knowledge_engine
import qa_engine
import verifier


APP_TITLE = "IOO.pro Product Intelligence Test"
APP_SUBTITLE = "AI-assisted machine vision lighting knowledge base and product selection workspace."
LOG_DIR = Path("logs")
FEEDBACK_PATH = LOG_DIR / "feedback.csv"

BRAND_OPTIONS = ["All Brands", "TMS Lite", "Advanced Illumination"]
MODE_OPTIONS = ["Strict", "Exploratory"]
FOCUS_OPTIONS = [
    "Product search",
    "Product comparison",
    "Lighting selection",
    "Data quality",
    "Knowledge explanation",
    "Uploaded material review",
]

EXAMPLE_QUESTIONS = [
    ("Metal scratch inspection lighting", "Which products are suitable for metal scratch inspection?"),
    ("Transparent object edge detection", "What lighting type works for transparent edge detection?"),
    ("Compare ring lights", "Compare TMS Lite and Advanced Illumination ring lights."),
    ("Show products with datasheets", "Which products have datasheets?"),
    ("Find missing voltage fields", "Which products are missing voltage information?"),
    ("TMS Lite products", "What TMS Lite ring lights are in the database?"),
    ("Advanced Illumination products", "Which Advanced Illumination products are backlights?"),
    ("Backlight selection logic", "What applications are backlights suitable for?"),
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
    "suitable",
    "inspection",
    "scratch",
    "transparent",
    "edge",
    "lighting type",
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
    "\u9002\u5408",
    "\u68c0\u6d4b",
    "\u5212\u75d5",
    "\u900f\u660e",
    "\u8fb9\u7f18",
]


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
        st.error("Incorrect password.")
    return False


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ioo-bg: #F8FAFC;
          --ioo-card: #FFFFFF;
          --ioo-text: #1F2937;
          --ioo-muted: #6B7280;
          --ioo-border: #E5E7EB;
          --ioo-blue: #2563EB;
          --ioo-teal: #0F766E;
          --ioo-amber-bg: #FFFBEB;
          --ioo-amber-text: #92400E;
        }
        .stApp { background: var(--ioo-bg); color: var(--ioo-text); }
        .block-container { padding-top: 2rem; max-width: 1280px; }
        h1, h2, h3 { color: var(--ioo-text); letter-spacing: 0; }
        .ioo-hero {
          background: var(--ioo-card);
          border: 1px solid var(--ioo-border);
          border-radius: 12px;
          padding: 28px 30px 24px 30px;
          margin-bottom: 18px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .ioo-hero h1 { margin: 0 0 8px 0; font-size: 2.05rem; line-height: 1.15; }
        .ioo-subtitle { color: var(--ioo-muted); font-size: 1rem; margin-bottom: 18px; }
        .ioo-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
        .ioo-chip {
          display: inline-flex;
          align-items: center;
          border: 1px solid #BFDBFE;
          background: #EFF6FF;
          color: #1D4ED8;
          padding: 5px 10px;
          border-radius: 999px;
          font-size: 0.78rem;
          font-weight: 600;
        }
        .ioo-note { color: var(--ioo-muted); margin: 0; }
        .ioo-card {
          background: var(--ioo-card);
          border: 1px solid var(--ioo-border);
          border-radius: 12px;
          padding: 20px 22px;
          margin-bottom: 16px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .ioo-card-title { font-size: 1.18rem; font-weight: 700; margin-bottom: 4px; }
        .ioo-card-subtitle { color: var(--ioo-muted); margin-bottom: 14px; font-size: 0.92rem; }
        .ioo-status-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
          margin-top: 10px;
        }
        .ioo-status {
          border: 1px solid var(--ioo-border);
          border-radius: 10px;
          padding: 10px 12px;
          background: #F9FAFB;
        }
        .ioo-status-label { color: var(--ioo-muted); font-size: 0.74rem; }
        .ioo-status-value { color: var(--ioo-text); font-weight: 700; font-size: 1rem; margin-top: 2px; }
        .ioo-pill {
          display: inline-flex;
          border-radius: 999px;
          padding: 4px 9px;
          font-weight: 700;
          font-size: 0.74rem;
          margin-right: 6px;
          border: 1px solid var(--ioo-border);
          background: #F9FAFB;
        }
        .ioo-pill-blue { color: #1D4ED8; background: #EFF6FF; border-color: #BFDBFE; }
        .ioo-pill-teal { color: #0F766E; background: #ECFDF5; border-color: #A7F3D0; }
        .ioo-pill-amber { color: var(--ioo-amber-text); background: var(--ioo-amber-bg); border-color: #FDE68A; }
        .ioo-upload-context {
          border: 1px dashed #CBD5E1;
          border-radius: 10px;
          padding: 12px 14px;
          background: #F8FAFC;
          color: var(--ioo-muted);
          margin-top: 8px;
        }
        .ioo-conversation {
          border-left: 3px solid #CBD5E1;
          padding: 8px 0 8px 14px;
          margin-bottom: 10px;
        }
        .ioo-speaker { font-weight: 700; color: var(--ioo-text); }
        .ioo-small { color: var(--ioo-muted); font-size: 0.84rem; }
        div.stButton > button[kind="primary"] {
          background: var(--ioo-blue);
          border-color: var(--ioo-blue);
          color: white;
        }
        div.stButton > button {
          border-radius: 9px;
          border-color: #CBD5E1;
        }
        [data-testid="stSidebar"] { background: #F1F5F9; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def answer_summary(answer: str, limit: int = 240) -> str:
    return " ".join(str(answer or "").split())[:limit]


def save_feedback(question: str, result: dict[str, Any], feedback: str, rating: str, suspected_issue_type: str) -> None:
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


def init_session_state() -> None:
    st.session_state.setdefault("question", "")
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_question", "")
    st.session_state.setdefault("uploaded_context", None)


def _metric_value(value: Any) -> str:
    if value is None:
        return "0"
    return str(value)


def render_hero() -> None:
    st.markdown(
        f"""
        <div class="ioo-hero">
          <h1>{APP_TITLE}</h1>
          <div class="ioo-subtitle">{APP_SUBTITLE}</div>
          <div class="ioo-chip-row">
            <span class="ioo-chip">Database-backed answers</span>
            <span class="ioo-chip">Multi-brand product search</span>
            <span class="ioo-chip">Evidence-first recommendations</span>
          </div>
          <p class="ioo-note">Ask about lighting selection, compare machine vision products, or upload inspection notes/images for structured review.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str | None, str, str]:
    stats = qa_engine.get_database_stats()
    brand_stats = qa_engine.get_database_stats_by_brand()
    knowledge_stats = knowledge_engine.get_knowledge_stats()
    knowledge_source_stats = knowledge_engine.get_knowledge_stats_by_source()
    counts = stats.get("counts", {})
    brands = brand_stats.get("brands", {})
    edmund_stats = knowledge_source_stats.get("Edmund Optics", {})

    st.sidebar.markdown("### Control Panel")
    brand_choice = st.sidebar.selectbox("Brand selector", BRAND_OPTIONS, index=0)
    mode_choice = st.sidebar.radio("Answer mode", MODE_OPTIONS, index=0, horizontal=True)
    focus_choice = st.sidebar.selectbox("Question focus", FOCUS_OPTIONS, index=0)
    brand_filter = None if brand_choice == "All Brands" else brand_choice
    engine_mode = "strict" if mode_choice == "Strict" else "exploratory"

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Data Scope")
    st.sidebar.metric("Brands", _metric_value(counts.get("brands", 0)))
    st.sidebar.metric("TMS Lite products", _metric_value(brands.get("TMS LITE", {}).get("products", 0)))
    st.sidebar.metric("Advanced Illumination products", _metric_value(brands.get("Advanced Illumination", {}).get("products", 0)))
    st.sidebar.metric("Total products", _metric_value(counts.get("products", 0)))
    st.sidebar.metric("Product specs", _metric_value(counts.get("product_specs", 0)))
    st.sidebar.metric("Product assets", _metric_value(counts.get("product_assets", 0)))
    knowledge_docs = knowledge_stats.get("knowledge_documents", 0)
    st.sidebar.metric("Knowledge documents", _metric_value(knowledge_docs) if knowledge_docs else "Coming soon")
    st.sidebar.metric("Knowledge sources", _metric_value(knowledge_stats.get("knowledge_sources", 0)))
    st.sidebar.metric("Edmund Optics documents", _metric_value(edmund_stats.get("documents", 0)))
    st.sidebar.metric("Edmund Optics cards", _metric_value(edmund_stats.get("cards", 0)))
    st.sidebar.metric("Pending review documents", _metric_value(knowledge_stats.get("pending_review_documents", 0)))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Trust / Limitations")
    st.sidebar.markdown(
        "- Answers are grounded in the current product database.\n"
        "- Missing values are shown as `not available`.\n"
        "- Product recommendations are preliminary and should be verified before customer use.\n"
        "- Uploaded image understanding is experimental unless a vision model is enabled."
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Demo Status")
    st.sidebar.markdown(
        "- Current stage: **Internal MVP**\n"
        "- Data scope: **TMS Lite + Advanced Illumination pilot**\n"
        "- Focus: machine vision lighting product search and selection support\n"
        "- Next: knowledge base review, image-assisted requirement intake, multi-brand expansion"
    )
    st.sidebar.caption(f"Data source: {stats.get('source_type')} | Run mode: {stats.get('mode')}")
    return brand_filter, engine_mode, focus_choice


def should_use_knowledge_flow(question: str, focus_choice: str) -> bool:
    if focus_choice in {"Lighting selection", "Knowledge explanation", "Uploaded material review"}:
        return True
    text = str(question or "").lower()
    return any(term.lower() in text for term in KNOWLEDGE_QUERY_TERMS)


def build_question_for_engine(question: str, uploaded_context: dict[str, Any] | None, focus_choice: str) -> str:
    question = question.strip()
    if not uploaded_context:
        return question
    text_context = uploaded_context.get("text")
    if not text_context:
        return question
    if focus_choice in {"Knowledge explanation", "Uploaded material review", "Lighting selection"}:
        context = str(text_context).strip()[:1800]
        return f"{question}\n\nUploaded text context:\n{context}" if question else f"Review this uploaded text context:\n{context}"
    return question


def process_upload(uploaded_file: Any) -> dict[str, Any] | None:
    if uploaded_file is None:
        if hasattr(st, "session_state"):
            st.session_state["uploaded_context"] = None
        return None
    filename = uploaded_file.name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    size = len(uploaded_file.getvalue())
    context: dict[str, Any] = {
        "filename": filename,
        "extension": extension,
        "size": size,
        "message": "File received.",
    }
    if extension in {"txt", "md"}:
        raw = uploaded_file.getvalue()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("utf-8", errors="ignore")
        context["text"] = text[:4000]
        context["message"] = "Uploaded text context detected."
    elif extension in {"png", "jpg", "jpeg"}:
        context["message"] = "Image uploaded. Visual interpretation is not enabled in this MVP unless a vision model is configured."
    elif extension == "pdf":
        context["message"] = "PDF received. Text extraction is not enabled in this MVP unless a document parser is configured."
    if hasattr(st, "session_state"):
        st.session_state["uploaded_context"] = context
    return context


def render_upload_context(context: dict[str, Any] | None, uploaded_file: Any) -> None:
    if not context:
        return
    size_kb = context.get("size", 0) / 1024
    st.markdown(
        f"""
        <div class="ioo-upload-context">
          <strong>{context.get('message')}</strong><br>
          File: {context.get('filename')} | Type: {context.get('extension') or 'unknown'} | Size: {size_kb:.1f} KB
        </div>
        """,
        unsafe_allow_html=True,
    )
    if context.get("extension") in {"png", "jpg", "jpeg"} and uploaded_file is not None:
        st.image(uploaded_file, caption=context.get("filename"), width=240)
    if context.get("text"):
        with st.expander("Uploaded text preview", expanded=False):
            st.text(context["text"][:1800])


def render_ask_card(brand_filter: str | None, engine_mode: str, focus_choice: str) -> None:
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">Ask IOO</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ioo-card-subtitle">Search products, compare vendors, or ask for lighting selection logic.</div>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Question",
        key="question",
        height=132,
        placeholder=(
            "Ask a product or machine vision lighting question...\n"
            "Examples:\n"
            "- Which products are suitable for metal scratch inspection?\n"
            "- Compare TMS Lite and Advanced Illumination ring lights.\n"
            "- Which products have datasheets?\n"
            "- What lighting type works for transparent edge detection?"
        ),
        label_visibility="collapsed",
    )

    uploaded_file = st.file_uploader(
        "Upload inspection material optional",
        type=["png", "jpg", "jpeg", "pdf", "txt", "md"],
        help="Upload a sample image, sketch, inspection note, or customer requirement.",
    )
    st.caption(
        "Upload a sample image, sketch, inspection note, or customer requirement. Current MVP stores and displays the file context; advanced image reasoning can be enabled later."
    )
    upload_context = process_upload(uploaded_file)
    render_upload_context(upload_context, uploaded_file)

    ask_col, clear_col = st.columns([1, 1])
    with ask_col:
        ask = st.button("Ask IOO", type="primary", use_container_width=True)
    with clear_col:
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["conversation"] = []
            st.session_state["last_result"] = None
            st.session_state["last_question"] = ""
            st.session_state["question"] = ""
            st.rerun()

    st.markdown("**Try a demo question**")
    chip_cols = st.columns(4)
    for idx, (label, prompt) in enumerate(EXAMPLE_QUESTIONS):
        with chip_cols[idx % 4]:
            if st.button(label, key=f"example_{idx}", use_container_width=True):
                st.session_state["question"] = prompt
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if ask:
        question = str(st.session_state.get("question") or "").strip()
        context = st.session_state.get("uploaded_context")
        if not question and not context:
            st.info("Ask a question or upload inspection material first.")
            return
        run_question(question, context, brand_filter, engine_mode, focus_choice)


def run_question(
    question: str,
    uploaded_context: dict[str, Any] | None,
    brand_filter: str | None,
    engine_mode: str,
    focus_choice: str,
) -> None:
    engine_question = build_question_for_engine(question, uploaded_context, focus_choice)
    use_knowledge = should_use_knowledge_flow(engine_question, focus_choice)
    with st.spinner("Retrieving grounded answer..."):
        if use_knowledge:
            result = answer_engine.answer_question(engine_question, brand_filter=brand_filter, mode=engine_mode)
        else:
            result = qa_engine.answer_question(engine_question, brand_filter=brand_filter, mode=engine_mode)
        if looks_like_cross_brand_family_comparison(engine_question) and not product_rows(result):
            result = cross_brand_family_comparison_result(engine_question, engine_mode)
        result = verifier.verify_answer(result)
    if uploaded_context:
        result["uploaded_context"] = uploaded_context
        result.setdefault("warnings", [])
        if uploaded_context.get("extension") in {"png", "jpg", "jpeg"}:
            result["warnings"].append("Image uploaded. Visual interpretation is not enabled in this MVP unless a vision model is configured.")
        if uploaded_context.get("extension") == "pdf":
            result["warnings"].append("PDF received. Text extraction is not enabled in this MVP unless a document parser is configured.")
    st.session_state["last_question"] = question or "Uploaded material review"
    st.session_state["last_result"] = result
    add_to_conversation(st.session_state["last_question"], result, uploaded_context)


def looks_like_cross_brand_family_comparison(question: str) -> bool:
    text = str(question or "").lower()
    return (
        "compare" in text
        and ("tms lite" in text or "tms" in text)
        and "advanced illumination" in text
        and any(term in text for term in ["ring", "backlight", "coaxial", "bar", "light"])
    )


def cross_brand_family_comparison_result(question: str, engine_mode: str) -> dict[str, Any]:
    text = str(question or "").lower()
    if "backlight" in text:
        query = "backlight"
        label = "backlight"
    elif "coaxial" in text:
        query = "coaxial light"
        label = "coaxial light"
    elif "bar" in text:
        query = "bar light"
        label = "bar light"
    else:
        query = "ring light"
        label = "ring light"
    hits = qa_engine.search_products(query, limit=24)
    tms_hits = [hit for hit in hits if hit.get("brand") == "TMS LITE"][:8]
    ai_hits = [hit for hit in hits if hit.get("brand") == "Advanced Illumination"][:8]
    selected = ai_hits + tms_hits
    sources: list[dict[str, Any]] = []
    for row in selected[:8]:
        sources.extend(qa_engine.get_product_sources(row.get("model", ""), brand_filter=row.get("brand"))[:2])
    answer = (
        f"Found database-backed {label} candidates from the current brand scope. "
        "This is a preliminary cross-brand comparison view, not a final equivalence recommendation. "
        "Review geometry, working distance, wavelength/color, electrical specs, datasheets, and sample images before selecting a substitute."
    )
    if not ai_hits or not tms_hits:
        answer += " One brand has limited matching records in the current database."
    warnings = [
        "Cross-brand equivalence requires human review of dimensions, optical geometry, wavelength/color, electrical parameters, and datasheets."
    ]
    return {
        "answer": answer,
        "knowledge_answer": "",
        "product_recommendations": selected,
        "matched_products": selected,
        "spec_table": [],
        "knowledge_sources": [],
        "product_sources": sources,
        "sources": sources,
        "missing_or_uncertain": warnings,
        "confidence": "medium",
        "mode": engine_mode,
        "evidence": [],
        "match_reason": [
            {
                "product_model": row.get("model"),
                "brand": row.get("brand"),
                "reason": f"Product matched cross-brand {label} comparison search.",
                "matched_fields": "model, family, light_type",
                "exact_match": True,
                "partial_match": False,
                "inferred_match": True,
            }
            for row in selected
        ],
        "query_interpretation": {
            "question_focus": "Product comparison",
            "comparison_type": f"cross-brand {label} family comparison",
            "exact_required": engine_mode == "strict",
        },
        "warnings": warnings,
    }


def add_to_conversation(question: str, result: dict[str, Any], uploaded_context: dict[str, Any] | None) -> None:
    item = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "answer": result.get("answer", ""),
        "confidence": result.get("confidence", ""),
        "mode": result.get("mode", ""),
        "matched_count": len(result.get("matched_products") or result.get("product_recommendations") or []),
        "uploaded_file": uploaded_context.get("filename") if uploaded_context else None,
    }
    history = [item] + list(st.session_state.get("conversation") or [])
    st.session_state["conversation"] = history[:5]


def next_step_for_result(result: dict[str, Any], focus_choice: str) -> str:
    if result.get("matched_products") or result.get("product_recommendations"):
        return "Review candidate products below, then verify datasheets and application fit before customer use."
    if focus_choice == "Uploaded material review":
        return "Provide working distance, field of view, material, defect type, and pass/fail examples for a stronger review."
    if result.get("knowledge_sources"):
        return "Use the source-linked selection logic below, then add product constraints such as voltage, color, size, and datasheet needs."
    return "Add product type, brand, model, voltage, material, defect type, or working distance to narrow the search."


def product_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return list(result.get("product_recommendations") or result.get("matched_products") or [])


def render_product_candidates(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("No database-backed product candidates returned for this question.")
        return
    table = []
    for row in rows[:30]:
        key_specs = []
        for label, field in [("Color", "color"), ("Voltage", "voltage"), ("Power", "power"), ("Current", "current")]:
            value = row.get(field)
            if value and value != "not available":
                key_specs.append(f"{label}: {value}")
        table.append(
            {
                "Brand": row.get("brand", "not available"),
                "Model": row.get("model", "not available"),
                "Product family / category": row.get("family") or row.get("product_family") or row.get("category") or "not available",
                "Light type": row.get("light_type", "not available"),
                "Key specs": "; ".join(key_specs) if key_specs else "not available",
                "Product URL": row.get("product_url", "not available"),
                "Datasheet URL": row.get("datasheet_url", "not available"),
            }
        )
    column_config = {}
    try:
        column_config = {
            "Product URL": st.column_config.LinkColumn("Product URL"),
            "Datasheet URL": st.column_config.LinkColumn("Datasheet URL"),
        }
    except Exception:
        column_config = {}
    st.dataframe(table, use_container_width=True, hide_index=True, column_config=column_config)


def render_sources(title: str, sources: list[dict[str, Any]]) -> None:
    st.markdown(f"**{title}**")
    if not sources:
        st.caption("No source URL available in the current database.")
        return
    for source in sources[:12]:
        url = source.get("url") or "not available"
        label = source.get("title") or source.get("source_name") or source.get("type") or "source"
        source_name = source.get("source_name") or source.get("publisher")
        source_type = source_name or source.get("type") or "source"
        if url != "not available":
            st.markdown(f"- **{source_type}**: [{label}]({url})")
        else:
            st.markdown(f"- **{source_type}**: not available")


def render_answer_card(result: dict[str, Any] | None, focus_choice: str) -> None:
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">IOO Answer</div>', unsafe_allow_html=True)
    if not result:
        st.markdown(
            '<div class="ioo-card-subtitle">Ask a question to see a grounded answer, candidate products, sources, and uncertainty notes.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    confidence = str(result.get("confidence", "low")).lower()
    mode = str(result.get("mode", "strict")).lower()
    pill_class = "ioo-pill-teal" if confidence == "high" else "ioo-pill-blue" if confidence == "medium" else "ioo-pill-amber"
    st.markdown(
        f"""
        <span class="ioo-pill {pill_class}">Confidence: {confidence.upper()}</span>
        <span class="ioo-pill ioo-pill-blue">Mode: {mode.upper()}</span>
        <span class="ioo-pill ioo-pill-teal">Database-backed</span>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Direct answer")
    st.write(result.get("answer", ""))

    st.markdown("### Recommended next step")
    st.info(next_step_for_result(result, focus_choice))

    uploaded_context = result.get("uploaded_context")
    if uploaded_context:
        st.markdown("### Uploaded context")
        st.caption(f"{uploaded_context.get('message')} File: {uploaded_context.get('filename')}")

    st.markdown("### Product candidates")
    render_product_candidates(product_rows(result))

    st.markdown("### Knowledge / selection logic")
    knowledge_answer = result.get("knowledge_answer")
    if knowledge_answer:
        knowledge_source_names = sorted(
            {
                str(source.get("source_name") or source.get("publisher"))
                for source in result.get("knowledge_sources", [])
                if source.get("source_name") or source.get("publisher")
            }
        )
        if "Edmund Optics" in knowledge_source_names:
            st.caption("Knowledge source: Edmund Optics")
        st.write(knowledge_answer)
    else:
        st.caption("Knowledge base module is under development for this question. This answer is currently based on product database and built-in selection rules.")

    st.markdown("### Confidence and warnings")
    missing = result.get("missing_or_uncertain") or []
    warnings = result.get("warnings") or []
    if not missing and not warnings:
        st.success("No additional uncertainty was flagged by the engine.")
    for item in missing[:6]:
        st.warning(item)
    for warning in warnings[:6]:
        if warning not in missing:
            st.warning(warning)

    st.markdown("### Sources")
    render_sources("Product sources", result.get("product_sources") or result.get("sources") or [])
    render_sources("Knowledge sources", result.get("knowledge_sources") or [])

    with st.expander("Technical details", expanded=False):
        st.markdown("**Query interpretation**")
        st.json(result.get("query_interpretation", {}))
        st.markdown("**Match reason**")
        match_reason = result.get("match_reason") or []
        if match_reason:
            st.dataframe(match_reason, use_container_width=True, hide_index=True)
        else:
            st.caption("No match reason returned.")
        st.markdown("**Evidence table**")
        evidence = result.get("evidence") or []
        if evidence:
            st.dataframe(evidence, use_container_width=True, hide_index=True)
        else:
            st.caption("No evidence rows returned.")
        st.markdown("**Raw sources**")
        st.code(json.dumps(result.get("sources") or [], ensure_ascii=False, indent=2), language="json")
        st.markdown("**Missing fields**")
        st.code(json.dumps(result.get("missing_or_uncertain") or [], ensure_ascii=False, indent=2), language="json")
        st.markdown("**Verification warnings**")
        st.code(json.dumps(result.get("warnings") or [], ensure_ascii=False, indent=2), language="json")

    render_feedback(result)
    st.markdown("</div>", unsafe_allow_html=True)


def render_feedback(result: dict[str, Any]) -> None:
    st.markdown("### Feedback")
    rating = st.radio("Was this answer useful?", ["Helpful", "Partially helpful", "Not helpful"], horizontal=True)
    issue_type = st.selectbox(
        "What should be improved?",
        ["Other", "Wrong product", "Missing product", "Bad source", "Too vague", "Bad recommendation"],
    )
    feedback = st.text_area("Free text feedback", height=84)
    if st.button("Save feedback"):
        if feedback.strip():
            save_feedback(st.session_state.get("last_question", ""), result, feedback.strip(), rating, issue_type)
            st.success(f"Feedback saved to {FEEDBACK_PATH}")
        else:
            st.info("Please write feedback before saving.")


def render_conversation_history() -> None:
    history = st.session_state.get("conversation") or []
    if not history:
        return
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">Recent conversation</div>', unsafe_allow_html=True)
    for item in history[:5]:
        st.markdown(
            f"""
            <div class="ioo-conversation">
              <div class="ioo-speaker">You</div>
              <div>{item.get('question')}</div>
              <div class="ioo-speaker" style="margin-top:8px;">IOO</div>
              <div class="ioo-small">Confidence: {item.get('confidence')} | Mode: {item.get('mode')} | Product candidates: {item.get('matched_count')}</div>
              <div class="ioo-small">{answer_summary(item.get('answer', ''), 320)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="IOO", layout="wide")
    inject_css()
    init_session_state()
    render_hero()
    if not check_password():
        st.stop()

    brand_filter, engine_mode, focus_choice = render_sidebar()
    render_ask_card(brand_filter, engine_mode, focus_choice)
    render_answer_card(st.session_state.get("last_result"), focus_choice)
    render_conversation_history()


if __name__ == "__main__":
    main()
