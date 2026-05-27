from __future__ import annotations

import csv
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

import answer_engine
import brand_config
import sku_mapping


CONFIG = brand_config.load_config()
BRAND = CONFIG["brand"]
GAMIFICATION = CONFIG["gamification"]
APP_TITLE = BRAND["product_name"]
APP_SUBTITLE = BRAND["tagline"]
LOG_DIR = Path("logs")
CONVERSATION_LOG = LOG_DIR / "conversation_log.csv"
POINTS_LOG = LOG_DIR / "conversation_points.csv"
FEEDBACK_LOG = LOG_DIR / "feedback.csv"

EXAMPLE_PROMPTS = [
    ("Detect scratches on reflective metal", "Detect scratches on reflective metal."),
    ("Inspect transparent bottle edges", "Inspect transparent bottle edges."),
    ("Improve contrast on PCB defects", "Improve contrast on PCB defects."),
    ("Choose lighting for line scan", "I need lighting for line scan inspection."),
    ("Compare lighting approaches", "Compare dark-field, coaxial, and backlight approaches for my inspection."),
]


def get_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)  # type: ignore[attr-defined]
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name)


def configure_openai_secret() -> bool:
    env_var = str(CONFIG["openai"].get("env_var") or "OPENAI_API_KEY")
    secret = get_secret(env_var)
    if secret:
        os.environ[env_var] = secret
        return True
    return False


def check_password() -> bool:
    configured_password = get_secret("APP_PASSWORD")
    if not configured_password:
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
          --ioo-bg: #F4F7FA;
          --ioo-card: #FFFFFF;
          --ioo-text: #0B1220;
          --ioo-muted: #5D6B7A;
          --ioo-border: #D8E1EA;
          --ioo-navy: #0B1F33;
          --ioo-blue: #1D4ED8;
          --ioo-blue-soft: #EAF2FF;
          --ioo-teal: #0E7490;
          --ioo-cyan: #0891B2;
          --ioo-amber-bg: #FFFBEB;
          --ioo-amber-text: #B45309;
          --ioo-green-bg: #ECFDF5;
          --ioo-green-text: #047857;
          color-scheme: light;
        }
        .stApp,
        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at top left, rgba(29, 78, 216, 0.08), transparent 30rem),
            linear-gradient(180deg, #F8FBFF 0%, var(--ioo-bg) 42%, #F6F8FB 100%);
          color: var(--ioo-text);
        }
        [data-testid="stHeader"] { background: var(--ioo-navy); }
        .block-container {
          max-width: 1080px;
          padding-top: 6.4rem;
          padding-bottom: 4rem;
        }
        h1, h2, h3 { letter-spacing: 0; color: var(--ioo-text); }
        .ioo-topbar {
          display: flex; justify-content: space-between; align-items: center;
          gap: 20px; margin-bottom: 42px; padding: 22px 24px;
          background: rgba(255, 255, 255, 0.92);
          border: 1px solid var(--ioo-border);
          border-radius: 24px;
          box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
        }
        .ioo-brand-lockup {
          display: flex; align-items: center; gap: 18px;
        }
        .ioo-mark {
          min-width: 82px; height: 58px; display: flex; align-items: center; justify-content: center;
          border-radius: 18px;
          background: linear-gradient(135deg, #071527 0%, #123C69 54%, #0E7490 100%);
          color: #FFFFFF; font-size: 1.85rem; font-weight: 950; letter-spacing: 0.03em;
          box-shadow: 0 12px 28px rgba(14, 116, 144, 0.22);
        }
        .ioo-logo { font-size: 2rem; font-weight: 900; color: var(--ioo-text); line-height: 1.02; }
        .ioo-logo-sub { font-size: 0.95rem; color: var(--ioo-muted); margin-top: 6px; }
        .ioo-tag { font-size: 0.82rem; color: var(--ioo-muted); margin-top: 2px; }
        .ioo-status {
          display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end;
          gap: 8px; color: var(--ioo-muted); font-size: 0.84rem;
        }
        .ioo-status-pill {
          border: 1px solid #CBD5E1; background: #F8FAFC; border-radius: 999px;
          padding: 5px 10px;
        }
        .ioo-status-pill strong { color: var(--ioo-teal); }
        .ioo-hero { text-align: center; margin: 0 auto 24px auto; max-width: 880px; }
        .ioo-hero h1 { font-size: 2.72rem; line-height: 1.08; margin-bottom: 12px; color: #071527; }
        .ioo-hero p { color: var(--ioo-muted); font-size: 1.05rem; margin: 0 auto 10px auto; max-width: 720px; }
        .ioo-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .ioo-card {
          background: var(--ioo-card); border: 1px solid var(--ioo-border);
          border-radius: 18px; padding: 20px 22px; margin-bottom: 16px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .ioo-card-title { font-weight: 800; font-size: 1.1rem; margin-bottom: 8px; }
        .ioo-muted { color: var(--ioo-muted); }
        .ioo-pill {
          display: inline-flex; border-radius: 999px; padding: 4px 10px;
          font-weight: 700; font-size: 0.74rem; margin: 0 6px 6px 0;
          border: 1px solid var(--ioo-border); background: #F9FAFB;
        }
        .ioo-pill-blue { color: #1D4ED8; background: #EFF6FF; border-color: #BFDBFE; }
        .ioo-pill-teal { color: var(--ioo-teal); background: #ECFDF5; border-color: #A7F3D0; }
        .ioo-pill-amber { color: var(--ioo-amber-text); background: var(--ioo-amber-bg); border-color: #FDE68A; }
        .ioo-product-card {
          border: 1px solid var(--ioo-border); border-radius: 14px; padding: 14px;
          background: #FFFFFF; margin-bottom: 10px;
        }
        .ioo-product-title { font-weight: 800; font-size: 1rem; }
        .ioo-upload-note {
          border: 1px dashed #CBD5E1; background: #F8FAFC; border-radius: 14px;
          padding: 12px 14px; color: var(--ioo-muted); margin-top: 8px;
        }
        .ioo-how {
          display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
        }
        .ioo-how div {
          background: #FFFFFF; border: 1px solid var(--ioo-border);
          border-radius: 14px; padding: 14px; color: var(--ioo-muted);
        }
        .block-container label,
        .block-container p,
        .block-container span,
        .block-container div {
          color: inherit;
        }
        textarea,
        div[data-baseweb="textarea"] textarea,
        div[data-testid="stTextArea"] textarea {
          background: #FFFFFF !important;
          color: #111827 !important;
          border: 1px solid #C9D5E1 !important;
          border-radius: 14px !important;
          box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.03) !important;
        }
        textarea::placeholder {
          color: #6B7280 !important;
          opacity: 1 !important;
        }
        div[data-testid="stFileUploader"] section {
          background: #FFFFFF !important;
          border: 1px dashed #AFC0D1 !important;
          border-radius: 14px !important;
        }
        div[data-testid="stFileUploader"] button,
        div.stButton > button {
          background: #FFFFFF !important;
          color: #0F2742 !important;
          border: 1px solid #B8C6D6 !important;
          border-radius: 999px !important;
          font-weight: 650 !important;
        }
        div[data-testid="stFileUploader"] button:hover,
        div.stButton > button:hover {
          background: #F0F6FF !important;
          border-color: #7EA6E8 !important;
          color: #123C69 !important;
        }
        div.stButton > button[kind="primary"] {
          background: linear-gradient(135deg, #1D4ED8 0%, #0E7490 100%) !important;
          border-color: transparent !important;
          color: white !important;
          box-shadow: 0 10px 24px rgba(29, 78, 216, 0.18) !important;
        }
        div.stButton > button[kind="primary"]:hover {
          background: linear-gradient(135deg, #1E40AF 0%, #0F766E 100%) !important;
          color: white !important;
        }
        @media (max-width: 760px) {
          .ioo-topbar { align-items: flex-start; flex-direction: column; margin-bottom: 26px; }
          .ioo-brand-lockup { align-items: flex-start; }
          .ioo-mark { min-width: 70px; height: 52px; font-size: 1.55rem; }
          .ioo-logo { font-size: 1.6rem; }
          .ioo-status { justify-content: flex-start; }
          .ioo-hero h1 { font-size: 2rem; }
          .ioo-how { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("question", "")
    st.session_state.setdefault("pending_question", None)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_question", "")
    st.session_state.setdefault("uploaded_context", None)
    st.session_state.setdefault("last_upload_key", None)
    st.session_state.setdefault("points", 0)
    st.session_state.setdefault("points_events", [])


def award_points(amount: int, reason: str) -> None:
    if amount <= 0 or not GAMIFICATION.get("enabled", True):
        return
    st.session_state["points"] = int(st.session_state.get("points", 0)) + amount
    event = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": st.session_state["session_id"],
        "points_awarded": amount,
        "reason": reason,
        "total_points": st.session_state["points"],
    }
    st.session_state["points_events"].append(event)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    write_csv_row(POINTS_LOG, event)


def write_csv_row(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def render_topbar(openai_enabled: bool) -> None:
    points_name = GAMIFICATION.get("points_name", "IOO Insight Points")
    mode = "OpenAI ready" if openai_enabled else "Local fallback"
    st.markdown(
        f"""
        <div class="ioo-topbar">
          <div class="ioo-brand-lockup">
            <div class="ioo-mark">IOO</div>
            <div>
              <div class="ioo-logo">Lighting AI</div>
              <div class="ioo-logo-sub">Machine vision lighting selection assistant</div>
            </div>
          </div>
          <div class="ioo-status">
            <span class="ioo-status-pill">{mode}</span>
            <span class="ioo-status-pill">{points_name}: <strong>{st.session_state.get('points', 0)}</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="ioo-hero">
          <h1>Find the right machine vision lighting approach.</h1>
          <p>Describe your inspection challenge. IOO Lighting AI will suggest lighting strategies and matching IOO products.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def process_upload(uploaded_file: Any) -> dict[str, Any] | None:
    if uploaded_file is None:
        st.session_state["uploaded_context"] = None
        return None
    data = uploaded_file.getvalue()
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    upload_key = f"{uploaded_file.name}:{len(data)}"
    context: dict[str, Any] = {
        "filename": uploaded_file.name,
        "extension": extension,
        "size": len(data),
        "message": "File received.",
    }
    if extension in {"txt", "md"}:
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("utf-8", errors="ignore")
        context["text"] = text[:5000]
        context["message"] = "Text requirement note detected and added to the current context."
    elif extension in {"png", "jpg", "jpeg"}:
        context["message"] = "Image received. Visual reasoning can be enabled in a later version; for now, please describe the defect or inspection goal."
    elif extension == "pdf":
        context["message"] = "PDF received. Text extraction can be enabled in a later version; for now, key requirements can be pasted as text."
    st.session_state["uploaded_context"] = context
    if st.session_state.get("last_upload_key") != upload_key:
        st.session_state["last_upload_key"] = upload_key
        award_points(int(GAMIFICATION.get("upload_points", 10)), "uploaded_material")
    return context


def render_upload_context(context: dict[str, Any] | None, uploaded_file: Any) -> None:
    if not context:
        return
    size_kb = context.get("size", 0) / 1024
    st.markdown(
        f"""
        <div class="ioo-upload-note">
          <strong>{context.get('message')}</strong><br>
          File: {context.get('filename')} | Type: {context.get('extension') or 'unknown'} | Size: {size_kb:.1f} KB
        </div>
        """,
        unsafe_allow_html=True,
    )
    if context.get("extension") in {"png", "jpg", "jpeg"} and uploaded_file is not None:
        st.image(uploaded_file, caption=context.get("filename"), width=260)
    if context.get("text"):
        with st.expander("Uploaded text preview", expanded=False):
            st.text(context["text"][:1800])


def render_search_card() -> None:
    pending = st.session_state.get("pending_question")
    if pending is not None:
        st.session_state["question"] = pending
        st.session_state["pending_question"] = None
    st.markdown("### Ask IOO")
    st.caption("Describe an inspection problem, upload a requirement note, or start with one of the examples below.")
    st.text_area(
        "Describe your inspection problem",
        key="question",
        height=150,
        placeholder="Describe your inspection problem, material, defect, camera setup, or lighting challenge...",
        label_visibility="collapsed",
    )
    uploaded_file = st.file_uploader(
        "Upload image, sketch, or requirement note",
        type=["png", "jpg", "jpeg", "pdf", "txt", "md"],
        help="Upload a sample image, sketch, or requirement note. Text notes are used immediately.",
    )
    st.caption("Upload a sample image, sketch, or requirement note. Visual interpretation can be enabled with a vision model; text notes are used immediately.")
    upload_context = process_upload(uploaded_file)
    render_upload_context(upload_context, uploaded_file)
    ask_col, clear_col = st.columns([3, 1])
    with ask_col:
        ask_clicked = st.button("Ask IOO", type="primary", use_container_width=True)
    with clear_col:
        if st.button("Clear", use_container_width=True):
            st.session_state["conversation"] = []
            st.session_state["last_result"] = None
            st.session_state["last_question"] = ""
            st.session_state["pending_question"] = ""
            st.session_state["uploaded_context"] = None
            st.rerun()
    st.markdown('<div class="ioo-chip-row">', unsafe_allow_html=True)
    chip_cols = st.columns(5)
    for idx, (label, prompt) in enumerate(EXAMPLE_PROMPTS):
        with chip_cols[idx % 5]:
            if st.button(label, key=f"example_{idx}", use_container_width=True):
                st.session_state["pending_question"] = prompt
                st.rerun()
    if ask_clicked:
        run_question()


def run_question() -> None:
    question = str(st.session_state.get("question") or "").strip()
    uploaded_context = st.session_state.get("uploaded_context")
    if not question and not uploaded_context:
        st.info("Describe an inspection challenge or upload a requirement note first.")
        return
    points = int(GAMIFICATION.get("question_points", 5))
    if st.session_state.get("conversation"):
        points += int(GAMIFICATION.get("followup_points", 3))
    if has_parameter_details(question):
        points += int(GAMIFICATION.get("parameter_detail_points", 5))
    award_points(points, "asked_question")
    with st.spinner("IOO is searching lighting knowledge and product options..."):
        result = answer_engine.answer_question(
            question or "Review this uploaded material.",
            conversation_context=st.session_state.get("conversation", []),
            uploaded_context=uploaded_context,
        )
    st.session_state["last_result"] = result
    st.session_state["last_question"] = question or "Uploaded material review"
    add_conversation(question or "Uploaded material review", result, points)
    log_conversation(question or "Uploaded material review", result, points)


def has_parameter_details(question: str) -> bool:
    text = (question or "").lower()
    needles = ["mm", "cm", "fov", "field of view", "working distance", "wd", "speed", "metal", "glass", "plastic", "工作距离", "视野", "金属", "玻璃"]
    return sum(1 for needle in needles if needle in text) >= 2


def add_conversation(question: str, result: dict[str, Any], points_awarded: int) -> None:
    item = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "answer": result.get("answer", ""),
        "recommended_public_models": ", ".join(p.get("public_model", "") for p in result.get("closest_ioo_products", [])),
        "confidence": result.get("confidence", ""),
        "points_awarded": points_awarded,
        "used_openai": result.get("used_openai", False),
    }
    st.session_state["conversation"] = [item] + list(st.session_state.get("conversation") or [])[:7]


def log_conversation(question: str, result: dict[str, Any], points_awarded: int, feedback: str = "") -> None:
    interpretation = result.get("query_interpretation", {})
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": st.session_state["session_id"],
        "user_question": question,
        "detected_material": ",".join(tag for tag in interpretation.get("detected_tags", []) if tag in {"metal", "glass", "plastic", "reflective_surface"}),
        "detected_defect": ",".join(tag for tag in interpretation.get("detected_tags", []) if tag in {"scratch_detection", "transparent_edge", "pcb_inspection"}),
        "detected_application": ",".join(interpretation.get("detected_tags", [])[:8]),
        "recommended_public_models": ", ".join(p.get("public_model", "") for p in result.get("closest_ioo_products", [])),
        "confidence": result.get("confidence", ""),
        "points_awarded": points_awarded,
        "mode": result.get("mode", ""),
        "used_openai": result.get("used_openai", False),
        "feedback": feedback,
    }
    write_csv_row(CONVERSATION_LOG, row)


def render_answer(result: dict[str, Any] | None) -> None:
    if not result:
        render_how_it_works()
        return
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">IOO recommendation</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <span class="ioo-pill ioo-pill-blue">Confidence: {str(result.get('confidence', 'low')).upper()}</span>
        <span class="ioo-pill ioo-pill-teal">{result.get('fit_type', 'Close fit')}</span>
        <span class="ioo-pill ioo-pill-amber">Solution profile: {result.get('solution_profile_completeness', 'Low')}</span>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Direct recommendation")
    st.write(result.get("direct_recommendation", ""))
    st.subheader("Lighting strategy")
    st.write(result.get("lighting_strategy", ""))
    st.subheader("Closest IOO product options")
    render_product_options(result.get("closest_ioo_products", []))
    st.subheader("Practical test plan")
    for item in result.get("practical_test_plan", []):
        st.markdown(f"- {item}")
    st.subheader("Missing information")
    missing = result.get("missing_information", [])
    if missing:
        st.info("Great, one more detail will make the recommendation stronger: " + ", ".join(missing[:6]))
    else:
        st.success("The current information is enough for a first-pass recommendation.")
    st.subheader("Sources / Basis")
    render_sources(result)
    st.subheader("Continue the conversation")
    cols = st.columns(3)
    for idx, prompt in enumerate(result.get("follow_up_suggestions", [])[:3]):
        with cols[idx % 3]:
            if st.button(prompt, key=f"followup_{idx}", use_container_width=True):
                st.session_state["pending_question"] = prompt
                st.rerun()
    with st.expander("Advanced details", expanded=False):
        st.caption("Internal supplier details are hidden from this public demo.")
        st.json(
            {
                "query_interpretation": result.get("query_interpretation", {}),
                "match_reason": result.get("match_reason", []),
                "warnings": result.get("warnings", []),
                "knowledge_basis": result.get("knowledge_basis", []),
            }
        )
    render_feedback(result)
    st.markdown("</div>", unsafe_allow_html=True)


def render_product_options(products: list[dict[str, Any]]) -> None:
    if not products:
        st.info("This may be a custom lighting case. IOO can start with the closest standard geometry and adapt wavelength, mounting, or diffusion.")
        return
    for product in products[:5]:
        st.markdown(
            f"""
            <div class="ioo-product-card">
              <div class="ioo-product-title">{product.get('public_model')}</div>
              <div class="ioo-muted">{product.get('light_type', '').replace('_', ' ')} | {product.get('fit_type')}</div>
              <p>{product.get('why_it_may_fit')}</p>
              <div class="ioo-muted">Key specs: {product.get('key_specs') or 'not available'}</div>
              <div class="ioo-muted">Note: This may be a strong starting point; final selection should be verified with sample images.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sources(result: dict[str, Any]) -> None:
    sources = result.get("knowledge_sources", [])
    st.markdown("**Knowledge base basis**")
    if sources:
        for source in sources[:5]:
            title = source.get("title") or "Knowledge source"
            url = source.get("url")
            source_name = source.get("source_name") or "Knowledge source"
            st.markdown(f"- {source_name}: [{title}]({url})")
    else:
        st.caption("No public knowledge source URL is available for this question yet.")
    st.markdown("**IOO product database basis**")
    st.caption("IOO internal product database. Private supplier/source URLs are not shown in the public demo.")


def render_feedback(result: dict[str, Any]) -> None:
    st.markdown("### Was this useful?")
    rating = st.radio("Rate this answer", ["Helpful", "Partially helpful", "Not helpful"], horizontal=True, label_visibility="collapsed")
    issue = st.selectbox("What should be improved?", ["Other", "Wrong product", "Missing product", "Too vague", "Bad recommendation"])
    feedback = st.text_area("Feedback", height=82, placeholder="Tell IOO what would make this recommendation more useful.")
    if st.button("Save feedback"):
        award_points(int(GAMIFICATION.get("feedback_points", 5)), "feedback")
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": st.session_state["session_id"],
            "question": st.session_state.get("last_question", ""),
            "answer_summary": str(result.get("answer", ""))[:260],
            "rating": rating,
            "issue_type": issue,
            "feedback": feedback,
            "recommended_public_models": ", ".join(p.get("public_model", "") for p in result.get("closest_ioo_products", [])),
        }
        write_csv_row(FEEDBACK_LOG, row)
        log_conversation(st.session_state.get("last_question", ""), result, int(GAMIFICATION.get("feedback_points", 5)), feedback)
        st.success("Thanks. Your feedback helps improve IOO recommendations.")


def render_history() -> None:
    history = st.session_state.get("conversation") or []
    if not history:
        return
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">Recent conversation</div>', unsafe_allow_html=True)
    for item in history[:8]:
        st.markdown(f"**You:** {item.get('question')}")
        st.caption(
            f"IOO: {str(item.get('answer', '')).splitlines()[0][:260]} | Points +{item.get('points_awarded')} | Products: {item.get('recommended_public_models')}"
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_how_it_works() -> None:
    st.markdown('<div class="ioo-card">', unsafe_allow_html=True)
    st.markdown('<div class="ioo-card-title">How it works</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ioo-how">
          <div><strong>1. Understand</strong><br>Describe material, defect, geometry, and camera constraints.</div>
          <div><strong>2. Search knowledge</strong><br>IOO checks source-linked lighting and imaging notes.</div>
          <div><strong>3. Match products</strong><br>IOO recommends the closest available IOO configurations.</div>
          <div><strong>4. Refine</strong><br>Continue with working distance, field of view, or sample images.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="IOO", layout="wide")
    inject_css()
    init_state()
    openai_enabled = configure_openai_secret()
    if not check_password():
        st.stop()
    render_topbar(openai_enabled)
    render_hero()
    render_search_card()
    render_answer(st.session_state.get("last_result"))
    render_history()
    # Keep the public catalog fresh in case the CSVs were not uploaded.
    if not Path("public_products.csv").exists():
        sku_mapping.generate_files()


if __name__ == "__main__":
    main()
