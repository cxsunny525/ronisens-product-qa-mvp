from __future__ import annotations

import csv
import html
import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

import answer_engine
import brand_config
import product_search
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

UI_TEXT = {
    "en": {
        "ask_ioo": "Ask IOO",
        "continue": "Continue this IOO conversation",
        "question": "Question",
        "followup_placeholder": "Follow up with material, defect size, working distance, FOV, speed, or lighting constraints...",
        "first_placeholder": "Ask about a defect, material, field of view, working distance, or lighting challenge...",
        "add_material": "Add image, PDF, or requirement note",
        "upload_material": "Upload image, sketch, or requirement note",
        "upload_help": "Text notes are used immediately; image reasoning requires a vision model.",
        "clear": "Clear conversation",
        "direct": "Direct recommendation",
        "strategy": "Lighting strategy",
        "closest_products": "Closest IOO product options",
        "test_plan": "Practical test plan",
        "missing": "Missing information",
        "sources": "Sources / Basis",
        "product_results": "IOO product results",
        "product_shortlist": "Product shortlist",
        "confidence": "Confidence",
        "solution_profile": "Solution profile",
        "guest": "Guest Engineer",
        "apply_account": "Apply for an engineering account",
        "dialog_history": "Dialog history",
        "field_shortcuts": "Field shortcuts",
        "ask_by_defect": "Ask by defect",
        "upload_image": "Upload image",
        "compare_lights": "Compare lights",
        "earn_credits": "Earn credits",
        "sign_in": "Sign in / Apply",
        "details": "Details",
        "spec_sheet": "Spec sheet",
        "save": "Save",
        "compare": "Compare",
        "not_available": "not available",
        "general_candidate": "general IOO lighting candidate",
        "category": "category",
        "knowledge_basis": "Knowledge base basis",
        "product_basis": "IOO product database basis",
        "showing": "Showing first {shown} of {total} matching IOO products.",
        "no_match": "No exact IOO product match was found in the current product database.",
        "shortlist_sub": "Candidate public IOO models stay here quietly, without interrupting the conversation.",
        "empty_shortlist": "Ask about a defect, material, or setup. IOO will place candidate models, key specs, and sandbox detail links here after the first answer.",
        "try_preset": "Try a preset or type your own question and press Enter.",
        "new_conversation": "New conversation",
        "download_history": "Download history",
        "resume": "Resume",
        "no_history": "No saved session conversation yet",
        "active": "Active",
    },
    "zh": {
        "ask_ioo": "询问 IOO",
        "continue": "继续本次 IOO 对话",
        "question": "问题",
        "followup_placeholder": "继续补充材料、缺陷尺寸、工作距离、视野、速度或打光限制...",
        "first_placeholder": "描述缺陷、材料、视野、工作距离或打光问题...",
        "add_material": "添加图片、PDF 或需求说明",
        "upload_material": "上传图片、草图或需求说明",
        "upload_help": "文本说明会立即用于分析；图片理解需要视觉模型支持。",
        "clear": "清空对话",
        "direct": "直接建议",
        "strategy": "打光策略",
        "closest_products": "最接近的 IOO 产品选项",
        "test_plan": "建议测试步骤",
        "missing": "还需要补充的信息",
        "sources": "依据来源",
        "product_results": "IOO 产品结果",
        "product_shortlist": "产品候选",
        "confidence": "置信度",
        "solution_profile": "方案完整度",
        "guest": "访客工程师",
        "apply_account": "申请工程师账号",
        "dialog_history": "对话历史",
        "field_shortcuts": "快捷入口",
        "ask_by_defect": "按缺陷提问",
        "upload_image": "上传图片",
        "compare_lights": "对比光源",
        "earn_credits": "获取积分",
        "sign_in": "登录 / 申请",
        "details": "详情",
        "spec_sheet": "规格书",
        "save": "保存",
        "compare": "对比",
        "not_available": "暂无数据",
        "general_candidate": "IOO 通用光源候选",
        "category": "类别",
        "knowledge_basis": "知识库依据",
        "product_basis": "IOO 产品数据库依据",
        "showing": "显示前 {shown} 个，共 {total} 个匹配 IOO 产品。",
        "no_match": "当前 IOO 产品库中没有明确匹配的产品。",
        "shortlist_sub": "候选 IOO 型号会在这里保留，不打断对话。",
        "empty_shortlist": "请描述缺陷、材料或应用场景。IOO 回答后会在这里显示候选型号、关键参数和测试链接。",
        "try_preset": "可以点击示例，也可以直接输入问题并按 Enter。",
        "new_conversation": "新建对话",
        "download_history": "导出历史",
        "resume": "继续",
        "no_history": "当前浏览器会话还没有历史对话",
        "active": "当前",
    },
}

LIGHT_TYPE_LABELS = {
    "zh": {
        "bar_light": "条形光源",
        "ring_light": "环形光源",
        "backlight": "背光源",
        "coaxial_light": "同轴光源",
        "dome_light": "穹顶光 / 漫射光源",
        "dark_field": "暗场光源",
        "line_scan_light": "线扫光源",
        "spot_light": "点光源",
        "uv_light": "紫外光源",
        "ir_light": "红外光源",
        "machine_vision_light": "机器视觉光源",
    },
    "en": {},
}

FIT_TYPE_LABELS = {
    "zh": {
        "Exact fit": "精确匹配",
        "Close fit": "接近匹配",
        "Workaround fit": "替代方案匹配",
        "Needs custom / manual review": "需要定制或人工确认",
        "Database sample": "数据库样例",
        "Sandbox candidate": "沙盒候选",
    },
    "en": {},
}


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
          --ioo-ink-950: #22333B;
          --ioo-ink-900: #30464F;
          --ioo-panel-850: #FFFFFF;
          --ioo-panel-800: #F8FCFB;
          --ioo-panel-760: #EEF6F4;
          --ioo-line-600: #D5E5E2;
          --ioo-line-500: #BFD4D0;
          --ioo-text-100: #22333B;
          --ioo-text-300: #465E66;
          --ioo-text-500: #6F838A;
          --ioo-text-650: #91A2A7;
          --ioo-optic-cyan: #2BA7A5;
          --ioo-optic-cyan-soft: #DDF6F2;
          --ioo-lamp-amber: #C8842C;
          --ioo-lamp-amber-soft: #FFF1D6;
          --ioo-signal-green: #6EA47D;
          --ioo-soft-lavender: #E8E7FF;
          --ioo-danger-soft: #C86C61;
          --ioo-shadow-blue: #DDEBEA;
          --ioo-gradient-rest-field: linear-gradient(135deg, #F8FBF9 0%, #EEF6F4 48%, #EAF3F7 100%);
          --ioo-gradient-focus-glow: radial-gradient(circle at 50% 12%, rgba(43,167,165,0.15), rgba(248,251,249,0) 46%);
          --ioo-gradient-credit-glow: linear-gradient(135deg, rgba(255,241,214,0.95), rgba(221,246,242,0.88));
          --ioo-font-ui: Inter, IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif;
          --ioo-font-mono: JetBrains Mono, SFMono-Regular, Consolas, monospace;
          --ioo-radius-md: 14px;
          --ioo-radius-lg: 22px;
          --ioo-radius-xl: 30px;
          --ioo-shadow-panel: 0 24px 70px rgba(70,94,102,0.14);
          color-scheme: light;
        }
        .stApp,
        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at 22% 8%, rgba(43,167,165,0.13), transparent 34%),
            radial-gradient(circle at 86% 16%, rgba(200,132,44,0.10), transparent 31%),
            var(--ioo-gradient-rest-field) !important;
          color: var(--ioo-text-100) !important;
          font-family: var(--ioo-font-ui) !important;
        }
        [data-testid="stHeader"] { background: rgba(248,251,249,0.86) !important; backdrop-filter: blur(16px); }
        [data-testid="stToolbar"] { color: var(--ioo-text-300) !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        .block-container {
          max-width: 1480px;
          padding-top: 5.6rem;
          padding-bottom: 3rem;
        }
        h1, h2, h3 { letter-spacing: -0.025em; color: var(--ioo-text-100) !important; }
        p, span, label, div { color: inherit; }
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stMarkdownContainer"] h4,
        [data-testid="stMarkdownContainer"] strong {
          color: var(--ioo-text-100) !important;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stMarkdownContainer"] em {
          color: var(--ioo-text-300) !important;
        }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] * {
          color: #506A72 !important;
          opacity: 1 !important;
        }
        div[data-testid="stExpander"] {
          border-radius: 16px !important;
          background: rgba(255,255,255,0.92) !important;
          border: 1px solid var(--ioo-line-600) !important;
          overflow: hidden !important;
        }
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary * {
          color: var(--ioo-text-100) !important;
          font-weight: 760 !important;
          background: rgba(255,255,255,0.92) !important;
        }
        div[data-testid="stExpander"] details,
        div[data-testid="stExpander"] div[role="button"] {
          background: rgba(255,255,255,0.92) !important;
          color: var(--ioo-text-100) !important;
        }
        div[data-testid="stAlert"],
        div[data-testid="stAlert"] * {
          color: var(--ioo-text-100) !important;
        }
        .ioo-topbar {
          display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: center;
          margin-bottom: 18px;
        }
        .ioo-brand-lockup { display: flex; align-items: center; gap: 12px; }
        .ioo-mark {
          width: 46px; height: 46px; border-radius: 15px; display: grid; place-items: center;
          background: #FFFFFF; border: 1px solid var(--ioo-line-600);
          box-shadow: 0 10px 30px rgba(70,94,102,0.10);
        }
        .ioo-mark-ring {
          width: 29px; height: 29px; border-radius: 50%; display: grid; place-items: center;
          border: 4px solid var(--ioo-optic-cyan);
        }
        .ioo-mark-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ioo-lamp-amber); }
        .ioo-logo { font-size: 1.06rem; font-weight: 820; color: var(--ioo-text-100); letter-spacing: 0.01em; }
        .ioo-logo-sub { color: var(--ioo-text-500); font-size: 0.78rem; margin-top: 1px; }
        .ioo-status { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 10px; }
        .ioo-credit-pill,
        .ioo-streak-pill,
        .ioo-auth-button {
          min-height: 40px; border-radius: 999px; padding: 0 15px;
          display: inline-flex; align-items: center; gap: 8px; font-weight: 760;
          border: 1px solid var(--ioo-line-600); background: rgba(255,255,255,0.74);
          color: var(--ioo-text-300);
        }
        .ioo-credit-pill { background: var(--ioo-gradient-credit-glow); border-color: rgba(200,132,44,0.30); }
        .ioo-credit-pill strong { color: var(--ioo-lamp-amber); font-family: var(--ioo-font-mono); }
        .ioo-auth-button { color: #FFFFFF; background: linear-gradient(135deg, #2BA7A5, #4F8EA3); border: 0; box-shadow: 0 12px 28px rgba(43,167,165,0.18); }
        .soft-panel {
          background: rgba(255,255,255,0.78); border: 1px solid rgba(213,229,226,0.96);
          box-shadow: var(--ioo-shadow-panel); border-radius: var(--ioo-radius-xl);
          overflow: hidden; backdrop-filter: blur(22px);
        }
        .left-rail-soft, .product-rail-soft { padding: 16px; }
        .product-rail-soft { min-height: calc(100vh - 128px); }
        .left-rail-soft {
          display: flex; flex-direction: column; gap: 14px;
          min-height: 0; height: auto; position: sticky; top: 88px;
        }
        .profile-card-soft {
          padding: 16px; border-radius: 24px; border: 1px solid rgba(43,167,165,0.18);
          background: linear-gradient(180deg, rgba(221,246,242,0.72), rgba(255,255,255,0.76));
        }
        .avatar-row { display: flex; align-items: center; gap: 12px; }
        .avatar-soft {
          width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center;
          background: rgba(221,246,242,0.86); border: 1px solid rgba(43,167,165,0.30);
          color: var(--ioo-optic-cyan); font-weight: 800;
        }
        .profile-name { font-weight: 760; color: var(--ioo-text-100); }
        .profile-meta { color: var(--ioo-text-500); font-size: 12px; margin-top: 3px; display: block; }
        .points-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; }
        .mini-metric {
          padding: 10px; border-radius: 16px; background: rgba(255,255,255,0.74);
          border: 1px solid rgba(213,229,226,0.9);
        }
        .mini-metric strong { display: block; font-family: var(--ioo-font-mono); color: var(--ioo-lamp-amber); font-size: 17px; }
        .mini-metric span { color: var(--ioo-text-500); font-size: 11px; }
        .section-title-soft {
          display: flex; justify-content: space-between; align-items: center; color: var(--ioo-text-500);
          font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; margin: 2px 2px 0;
        }
        .history-list-soft { display: flex; flex-direction: column; gap: 8px; }
        .history-item-soft {
          padding: 11px 12px; border-radius: 16px; border: 1px solid transparent;
          background: rgba(248,252,251,0.76); color: var(--ioo-text-300);
        }
        .history-item-soft.active { border-color: rgba(43,167,165,0.25); background: rgba(221,246,242,0.82); }
        .history-item-soft small { display: block; margin-top: 4px; color: var(--ioo-text-650); }
        .shortcut-grid-soft { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .shortcut-soft {
          padding: 12px 10px; min-height: 72px; border-radius: 18px;
          background: rgba(248,252,251,0.78); border: 1px solid var(--ioo-line-600);
          color: var(--ioo-text-300); font-size: 12px;
        }
        .shortcut-soft b { display: block; color: var(--ioo-text-100); margin-bottom: 7px; }
        .chat-panel-soft { min-height: auto; }
        .compact-intro {
          margin: 0 0 16px;
          padding: 18px 20px;
          border-radius: 24px;
          border: 1px solid rgba(213,229,226,0.92);
          background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(248,252,251,0.82));
          box-shadow: 0 14px 42px rgba(70,94,102,0.08);
        }
        .compact-intro .intro-kicker {
          display: block;
          color: var(--ioo-optic-cyan);
          font-size: 0.72rem;
          font-weight: 820;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          margin-bottom: 8px;
        }
        .compact-intro h1 {
          font-size: clamp(25px, 3vw, 38px);
          line-height: 1.12;
          margin: 0 0 8px;
          letter-spacing: -0.035em;
          max-width: 720px;
        }
        .compact-intro p {
          color: var(--ioo-text-500);
          margin: 0;
          font-size: 0.98rem;
          line-height: 1.55;
          max-width: 720px;
        }
        .ioo-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 18px; }
        .ioo-card {
          background: rgba(255,255,255,0.80); border: 1px solid var(--ioo-line-600);
          border-radius: 22px; padding: 18px 20px; margin: 14px 0;
        }
        .ioo-card-title { font-weight: 800; font-size: 1.1rem; margin-bottom: 8px; }
        .ioo-muted { color: var(--ioo-text-500); }
        .ioo-pill {
          display: inline-flex; border-radius: 999px; padding: 4px 10px;
          font-weight: 700; font-size: 0.74rem; margin: 0 6px 6px 0;
          border: 1px solid var(--ioo-line-600); background: #F9FAFB;
        }
        .ioo-pill-blue { color: var(--ioo-text-300); background: #F8FCFB; border-color: var(--ioo-line-600); }
        .ioo-pill-teal { color: var(--ioo-optic-cyan); background: var(--ioo-optic-cyan-soft); border-color: #B8E7E2; }
        .ioo-pill-amber { color: var(--ioo-lamp-amber); background: var(--ioo-lamp-amber-soft); border-color: #F1D6A8; }
        .ioo-product-card {
          border: 1px solid var(--ioo-line-600); border-radius: 18px; padding: 13px;
          background: rgba(255,255,255,0.82); margin-bottom: 10px;
        }
        .ioo-product-title { font-weight: 800; font-size: 1rem; }
        .ioo-upload-note {
          border: 1px dashed var(--ioo-line-500); background: #F8FCFB; border-radius: 14px;
          padding: 12px 14px; color: var(--ioo-text-500); margin-top: 8px;
        }
        .ioo-how {
          display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
        }
        .ioo-how div {
          background: #FFFFFF; border: 1px solid var(--ioo-line-600);
          border-radius: 14px; padding: 14px; color: var(--ioo-text-500);
        }
        textarea,
        input,
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea,
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {
          background: rgba(255,255,255,0.94) !important;
          color: var(--ioo-text-100) !important;
          border: 1px solid rgba(43,167,165,0.24) !important;
          border-radius: 20px !important;
          box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.03) !important;
          caret-color: #111827 !important;
          user-select: text !important;
          -webkit-user-select: text !important;
          pointer-events: auto !important;
          opacity: 1 !important;
          position: relative !important;
          z-index: 2 !important;
        }
        div[data-testid="stTextInput"],
        div[data-testid="stTextInput"] *,
        div[data-testid="stTextArea"],
        div[data-testid="stTextArea"] * {
          pointer-events: auto !important;
          user-select: text !important;
          -webkit-user-select: text !important;
        }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {
          outline: 2px solid rgba(43,167,165,0.42) !important;
          outline-offset: 2px !important;
          border-color: var(--ioo-optic-cyan) !important;
          box-shadow: 0 0 0 3px rgba(43,167,165,0.12) !important;
        }
        textarea::selection,
        input::selection {
          background: rgba(43,167,165,0.22) !important;
          color: #111827 !important;
        }
        textarea::placeholder,
        input::placeholder {
          color: var(--ioo-text-650) !important;
          opacity: 1 !important;
        }
        div[data-testid="stFileUploader"] section {
          background: rgba(255,255,255,0.96) !important;
          border: 1px dashed var(--ioo-line-500) !important;
          border-radius: 20px !important;
        }
        div[data-testid="stFileUploader"] *,
        div[data-testid="stFileUploader"] small,
        div[data-testid="stFileUploader"] span,
        div[data-testid="stFileUploader"] p {
          color: var(--ioo-text-300) !important;
          opacity: 1 !important;
        }
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
          background: rgba(255,255,255,0.96) !important;
          border: 1px solid var(--ioo-line-600) !important;
          color: var(--ioo-text-100) !important;
        }
        div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] * {
          color: var(--ioo-text-100) !important;
        }
        div[data-testid="stFileUploader"] button,
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] button {
          background: rgba(255,255,255,0.96) !important;
          color: var(--ioo-ink-900) !important;
          border: 1px solid var(--ioo-line-600) !important;
          border-radius: 999px !important;
          font-weight: 650 !important;
          min-height: 40px !important;
        }
        div[data-testid="stFileUploader"] button:hover,
        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {
          background: var(--ioo-optic-cyan-soft) !important;
          border-color: var(--ioo-optic-cyan) !important;
          color: var(--ioo-ink-900) !important;
        }
        div.stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] {
          background: linear-gradient(135deg, #2BA7A5, #4F8EA3) !important;
          border-color: transparent !important;
          color: white !important;
          box-shadow: 0 12px 26px rgba(43,167,165,0.20) !important;
        }
        div.stButton > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
          background: linear-gradient(135deg, #268F8E, #477F93) !important;
          color: white !important;
        }
        .product-rail-title { font-size: 0.98rem; font-weight: 820; color: var(--ioo-text-100); margin: 0 0 4px; }
        .product-rail-kicker {
          color: var(--ioo-optic-cyan); font-size: 0.68rem; font-weight: 820;
          letter-spacing: 0.13em; text-transform: uppercase; margin-bottom: 6px;
        }
        .product-rail-sub { color: var(--ioo-text-500); font-size: 0.78rem; line-height: 1.45; margin-bottom: 12px; }
        .product-empty-soft {
          padding: 14px; border-radius: 18px; border: 1px dashed var(--ioo-line-500);
          background: rgba(255,255,255,0.66); color: var(--ioo-text-500);
          font-size: 0.82rem; line-height: 1.48;
        }
        .soft-product-card {
          border-radius: 22px; border: 1px solid var(--ioo-line-600); background: rgba(255,255,255,0.80);
          padding: 12px; display: grid; grid-template-columns: 82px 1fr; gap: 12px; margin-bottom: 12px;
        }
        .soft-product-image {
          min-height: 82px; border-radius: 18px; background: rgba(238,246,244,0.90);
          border: 1px solid var(--ioo-line-600); display: grid; place-items: center; overflow: hidden;
        }
        .soft-product-image svg { width: 78px; height: auto; }
        .soft-product-info h3 {
          margin: 0; font-size: 0.95rem; font-family: var(--ioo-font-mono); color: var(--ioo-text-100);
        }
        .soft-product-info p { margin: 6px 0 8px; color: var(--ioo-text-500); font-size: 0.78rem; line-height: 1.38; }
        .spec-tags { display: flex; flex-wrap: wrap; gap: 6px; }
        .spec-tags span {
          font-size: 0.68rem; color: var(--ioo-text-300); padding: 5px 7px; border-radius: 999px;
          background: rgba(238,246,244,0.92); border: 1px solid rgba(213,229,226,0.8);
        }
        .card-links { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
        .card-links a, .card-links span {
          color: var(--ioo-optic-cyan); font-size: 0.74rem; font-weight: 760;
        }
        .reward-card-soft {
          margin-top: 16px; padding: 16px; border-radius: 24px; background: var(--ioo-gradient-credit-glow);
          border: 1px solid rgba(200,132,44,0.22);
        }
        .reward-card-soft h3 { margin: 0 0 6px; color: var(--ioo-text-100); font-size: 1rem; }
        .reward-card-soft p { margin: 0; color: var(--ioo-text-500); line-height: 1.45; font-size: 0.82rem; }
        .reward-meter { margin-top: 12px; height: 9px; border-radius: 999px; background: rgba(191,212,208,0.88); overflow: hidden; }
        .reward-meter span { display: block; height: 100%; width: 68%; background: linear-gradient(90deg, var(--ioo-lamp-amber), var(--ioo-optic-cyan)); border-radius: inherit; }
        .mobile-product-tab { display: none; }
        .mobile-product-drawer { display: none; }
        @media (max-width: 1160px) {
          .left-rail-soft, .product-rail-soft, .chat-panel-soft { min-height: auto; }
        }
        @media (max-width: 820px) {
          .block-container {
            padding-top: 4.25rem;
            padding-left: 0.82rem;
            padding-right: 0.82rem;
            padding-bottom: 7.4rem;
          }
          .ioo-topbar {
            grid-template-columns: 1fr;
            gap: 10px;
            margin-bottom: 12px;
            padding: 10px 0 4px;
          }
          .ioo-mark { width: 42px; height: 42px; border-radius: 14px; }
          .ioo-logo { font-size: 1.28rem; }
          .ioo-logo-sub { display: none; }
          .ioo-status {
            justify-content: flex-start;
            flex-wrap: nowrap;
            overflow-x: auto;
            padding-bottom: 2px;
          }
          .ioo-credit-pill, .ioo-streak-pill, .ioo-auth-button {
            min-height: 42px;
            white-space: nowrap;
            padding: 0 13px;
            font-size: 0.82rem;
          }
          .left-rail-soft,
          .product-rail-soft {
            display: none !important;
          }
          .soft-panel {
            border-radius: 24px;
            box-shadow: 0 16px 42px rgba(70,94,102,0.13);
          }
          .compact-intro {
            margin-bottom: 10px;
            padding: 15px 15px;
            border-radius: 20px;
          }
          .compact-intro h1 { font-size: 1.52rem; }
          .compact-intro p { font-size: 0.88rem; }
          div[data-testid="stTextArea"] textarea {
            min-height: 116px !important;
            font-size: 0.96rem !important;
          }
          div[data-testid="stFileUploader"] section {
            min-height: 74px !important;
          }
          div.stButton > button,
          div[data-testid="stFileUploader"] button,
          div[data-testid="stFormSubmitButton"] button {
            min-height: 44px !important;
          }
          .ioo-how { grid-template-columns: 1fr; }
          .shortcut-grid-soft { grid-template-columns: repeat(4, minmax(128px, 1fr)); overflow-x: auto; }
          .history-mobile-row { display: flex; overflow-x: auto; gap: 8px; padding-bottom: 2px; }
          .history-mobile-row .history-item-soft { min-width: 184px; }
          .ioo-card {
            padding: 15px 15px;
            border-radius: 20px;
          }
          .ioo-card h3,
          .ioo-card h2,
          .ioo-card h1 {
            font-size: 1.05rem !important;
          }
          .soft-product-card { grid-template-columns: 74px 1fr; }
          .soft-product-image { min-height: 74px; }
          .mobile-product-drawer {
            display: block;
            margin-top: 14px;
            margin-bottom: 16px;
            padding: 14px;
          }
          .mobile-product-drawer .soft-product-card {
            background: rgba(255,255,255,0.88);
          }
          .mobile-product-tab {
            position: fixed; left: 12px; right: 12px; bottom: 12px; display: grid;
            grid-template-columns: 1fr auto; gap: 10px; align-items: center; min-height: 58px;
            padding: 10px 12px; border-radius: 22px; background: rgba(255,255,255,0.94);
            border: 1px solid rgba(43,167,165,0.26); box-shadow: 0 18px 48px rgba(70,94,102,0.20);
            backdrop-filter: blur(20px); z-index: 10;
          }
          .mobile-product-tab b { font-size: 13px; color: var(--ioo-text-100); }
          .mobile-product-tab span { color: var(--ioo-text-500); font-size: 12px; }
          .mobile-product-tab .open-pill {
            min-height: 42px; border-radius: 15px; background: linear-gradient(135deg, #2BA7A5, #4F8EA3);
            color: #FFFFFF; font-weight: 800; padding: 10px 13px; text-align: center;
            text-decoration: none;
          }
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
    st.session_state.setdefault("language", "en")
    st.session_state.setdefault("threads", [])
    st.session_state.setdefault("active_thread_id", None)
    ensure_active_thread()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_thread(title: str | None = None) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "id": str(uuid.uuid4()),
        "title": title or ("新对话" if current_language() == "zh" else "New conversation"),
        "created_at": timestamp,
        "updated_at": timestamp,
        "language": current_language(),
        "messages": [],
        "last_result": None,
        "last_question": "",
    }


def ensure_active_thread() -> dict[str, Any]:
    threads = st.session_state.setdefault("threads", [])
    active_id = st.session_state.get("active_thread_id")
    for thread in threads:
        if thread.get("id") == active_id:
            return thread
    thread = make_thread()
    threads.insert(0, thread)
    st.session_state["active_thread_id"] = thread["id"]
    return thread


def active_thread() -> dict[str, Any]:
    return ensure_active_thread()


def thread_title_from_question(question: str) -> str:
    cleaned = " ".join(str(question or "").split())
    if not cleaned:
        return "Uploaded material review"
    return cleaned[:42] + ("..." if len(cleaned) > 42 else "")


def load_thread(thread_id: str) -> None:
    for thread in st.session_state.get("threads", []):
        if thread.get("id") == thread_id:
            st.session_state["active_thread_id"] = thread_id
            st.session_state["conversation"] = list(thread.get("messages") or [])
            st.session_state["last_result"] = thread.get("last_result")
            st.session_state["last_question"] = thread.get("last_question", "")
            st.session_state["language"] = thread.get("language", st.session_state.get("language", "en"))
            st.session_state["question"] = ""
            return


def start_new_thread() -> None:
    current = active_thread()
    if not current.get("messages") and not current.get("last_result"):
        st.session_state["conversation"] = []
        st.session_state["last_result"] = None
        st.session_state["last_question"] = ""
        st.session_state["question"] = ""
        st.session_state["uploaded_context"] = None
        return
    thread = make_thread()
    st.session_state["threads"].insert(0, thread)
    st.session_state["active_thread_id"] = thread["id"]
    st.session_state["conversation"] = []
    st.session_state["last_result"] = None
    st.session_state["last_question"] = ""
    st.session_state["question"] = ""
    st.session_state["uploaded_context"] = None


def update_active_thread(question: str, result: dict[str, Any], item: dict[str, Any]) -> None:
    thread = active_thread()
    if not thread.get("messages"):
        thread["title"] = thread_title_from_question(question)
    thread["messages"] = [item] + list(thread.get("messages") or [])[:19]
    thread["last_result"] = result
    thread["last_question"] = question
    thread["language"] = result.get("language") or st.session_state.get("language") or "en"
    thread["updated_at"] = now_iso()
    # Keep recently used threads at the top, like common LLM chat sidebars.
    threads = [t for t in st.session_state.get("threads", []) if t.get("id") != thread.get("id")]
    st.session_state["threads"] = [thread] + threads[:39]


def export_thread_payload(thread: dict[str, Any]) -> str:
    payload = {
        "title": thread.get("title"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
        "language": thread.get("language"),
        "messages": thread.get("messages") or [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def detect_user_language(text: str | None) -> str:
    return answer_engine.detect_user_language(text or "")


def current_language() -> str:
    result = st.session_state.get("last_result") or {}
    language = result.get("language") or st.session_state.get("language") or "en"
    return "zh" if language == "zh" else "en"


def ui_text(key: str, **kwargs: Any) -> str:
    language = current_language()
    value = UI_TEXT.get(language, UI_TEXT["en"]).get(key, UI_TEXT["en"].get(key, key))
    return value.format(**kwargs) if kwargs else value


def localize_value(value: Any, key: str | None = None) -> str:
    language = current_language()
    text = str(value or "").strip()
    if not text or text.lower() == "not available":
        return ui_text("not_available")
    normalized = text.replace("-", "_").lower()
    if key == "light_type" or normalized in LIGHT_TYPE_LABELS["zh"]:
        if language == "zh":
            return LIGHT_TYPE_LABELS["zh"].get(normalized, text.replace("_", " "))
        return text.replace("_", " ")
    if key == "fit_type" or text in FIT_TYPE_LABELS["zh"]:
        if language == "zh":
            return FIT_TYPE_LABELS["zh"].get(text, text)
        return text
    if language == "zh" and text == "general IOO lighting candidate":
        return ui_text("general_candidate")
    return text.replace("_", " ")


def localize_reason(value: Any) -> str:
    text = str(value or "").strip()
    if current_language() != "zh" or not text:
        return text
    replacements = {
        "matches red light": "匹配红光",
        "red light evidence": "有红光证据",
        "matches green light": "匹配绿光",
        "matches blue light": "匹配蓝光",
        "24V evidence": "有 24V 参数",
        "ring light geometry": "环形光几何结构匹配",
        "backlight geometry": "背光几何结构匹配",
        "coaxial geometry": "同轴光几何结构匹配",
        "surface defect lighting approach": "适合表面缺陷打光思路",
        "edge/silhouette lighting approach": "适合边缘 / 轮廓打光思路",
        "reflective surface lighting approach": "适合反光表面打光思路",
        "general IOO lighting candidate": "IOO 通用光源候选",
        "closest searchable IOO product; more inspection details are needed": "当前可检索到的接近 IOO 产品；需要更多检测参数",
        "model exactly matched in the IOO product database": "型号在 IOO 产品库中精确匹配",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


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


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def points_today() -> int:
    return sum(int(event.get("points_awarded", 0)) for event in st.session_state.get("points_events", []))


def reward_target() -> int:
    # TODO: Replace this local placeholder with account-backed reward thresholds.
    return 1850


def reward_progress_percent() -> int:
    target = reward_target()
    if target <= 0:
        return 0
    return max(4, min(100, int(int(st.session_state.get("points", 0)) / target * 100)))


def product_asset_svg(light_type: str) -> str:
    asset_dir = Path("docs/design/ioo-softlight/ioo_redesign_package_softlight/assets")
    normalized = (light_type or "").lower()
    if any(token in normalized for token in ["bar", "line", "dark"]):
        name = "product-light-bar.svg"
    elif any(token in normalized for token in ["coaxial", "coax"]):
        name = "product-coaxial.svg"
    else:
        name = "product-dome.svg"
    path = asset_dir / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return '<svg width="160" height="120" viewBox="0 0 160 120" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="160" height="120" rx="24" fill="#F8FCFB"/><rect x="24" y="24" width="112" height="72" rx="22" fill="#DDF6F2" stroke="#BFD4D0"/><circle cx="80" cy="60" r="18" fill="#2BA7A5" opacity="0.55"/></svg>'


def product_asset_path(light_type: str) -> Path | None:
    asset_dir = Path("docs/design/ioo-softlight/ioo_redesign_package_softlight/assets")
    normalized = (light_type or "").lower()
    if any(token in normalized for token in ["bar", "line", "dark"]):
        name = "product-light-bar.svg"
    elif any(token in normalized for token in ["coaxial", "coax"]):
        name = "product-coaxial.svg"
    else:
        name = "product-dome.svg"
    path = asset_dir / name
    return path if path.exists() else None


def product_links(model: str) -> tuple[str, str]:
    slug = (model or "ioo-product").lower()
    return (f"https://ioo.pro/products/{slug}", f"https://ioo.pro/specs/{slug}.pdf")


def placeholder_products() -> list[dict[str, Any]]:
    try:
        rows = product_search.search_products("", limit=3)["products"]
    except Exception:
        rows = []
    for row in rows:
        row.setdefault("fit_type", "Database sample")
        row.setdefault("why_it_may_fit", "Public IOO product database sample.")
    return rows


def render_topbar(openai_enabled: bool) -> None:
    if current_language() == "zh":
        mode = "AI 已就绪" if openai_enabled else "本地模式"
        streak = "8 天工程师连续使用"
        credits = "积分"
    else:
        mode = "AI ready" if openai_enabled else "Local mode"
        streak = "8-day engineer streak"
        credits = "Credits"
    st.markdown(
        f"""
        <div class="ioo-topbar">
          <div class="ioo-brand-lockup">
            <div class="ioo-mark"><div class="ioo-mark-ring"><div class="ioo-mark-dot"></div></div></div>
            <div>
              <div class="ioo-logo">IOO</div>
              <div class="ioo-logo-sub">Industrial Optics Online</div>
            </div>
          </div>
          <div class="ioo-status">
            <span class="ioo-credit-pill"><span>{credits}</span><strong>{st.session_state.get('points', 0):,}</strong></span>
            <span class="ioo-streak-pill">{streak}</span>
            <span class="ioo-auth-button">{ui_text("sign_in")}</span>
            <span class="ioo-streak-pill">{mode}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="compact-intro">
          <span class="intro-kicker">IOO Lighting AI</span>
          <h1>Turn an inspection problem into a lighting test plan.</h1>
          <p>Describe the material, defect, field of view, working distance, or image context. IOO returns a practical lighting approach and candidate IOO configurations to try first.</p>
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
    in_conversation = bool(st.session_state.get("last_result"))
    heading = ui_text("continue") if in_conversation else ui_text("ask_ioo")
    placeholder = (
        ui_text("followup_placeholder")
        if in_conversation
        else ui_text("first_placeholder")
    )
    st.markdown(f"### {heading}")
    with st.form("ask_ioo_form", clear_on_submit=False):
        question_col, send_col = st.columns([0.82, 0.18], vertical_alignment="bottom")
        with question_col:
            st.text_input(
                ui_text("question"),
                key="question",
                placeholder=placeholder,
                label_visibility="collapsed",
            )
        with send_col:
            submitted = st.form_submit_button(ui_text("ask_ioo"), type="primary", use_container_width=True)
    if submitted:
        run_question()
        st.rerun()
    if in_conversation:
        with st.expander(ui_text("add_material"), expanded=False):
            uploaded_file = st.file_uploader(
                ui_text("upload_material"),
                type=["png", "jpg", "jpeg", "pdf", "txt", "md"],
                help=ui_text("upload_help"),
            )
            upload_context = process_upload(uploaded_file)
            render_upload_context(upload_context, uploaded_file)
        if st.button(ui_text("new_conversation"), use_container_width=True):
            start_new_thread()
            st.rerun()
    else:
        with st.expander(ui_text("add_material"), expanded=False):
            uploaded_file = st.file_uploader(
                ui_text("upload_material"),
                type=["png", "jpg", "jpeg", "pdf", "txt", "md"],
                help=ui_text("upload_help"),
            )
            upload_context = process_upload(uploaded_file)
            render_upload_context(upload_context, uploaded_file)
        st.caption(ui_text("try_preset"))
        chip_cols = st.columns(2)
        for idx, (label, prompt) in enumerate(EXAMPLE_PROMPTS):
            with chip_cols[idx % 2]:
                if st.button(label, key=f"example_{idx}", use_container_width=True):
                    st.session_state["pending_question"] = prompt
                    run_question(prompt)
                    st.rerun()


def run_question(question_override: str | None = None) -> None:
    question = str(question_override if question_override is not None else st.session_state.get("question") or "").strip()
    if question:
        st.session_state["language"] = detect_user_language(question)
    uploaded_context = st.session_state.get("uploaded_context")
    if not question and not uploaded_context:
        st.info("请先描述检测问题，或上传需求说明。" if current_language() == "zh" else "Describe an inspection challenge or upload a requirement note first.")
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
    st.session_state["conversation"] = [item] + list(st.session_state.get("conversation") or [])[:19]
    update_active_thread(question, result, item)


def _render_left_rail_legacy() -> None:
    history = st.session_state.get("conversation") or []
    today = points_today()
    remaining = max(0, reward_target() - int(st.session_state.get("points", 0)))
    if history:
        history_html = "".join(
            f'<div class="history-item-soft{" active" if idx == 0 else ""}">'
            f'{e(str(item.get("question") or "Lighting case"))[:72]}'
            f'<small>{e(str(item.get("recommended_public_models") or "IOO recommendation"))[:96]}</small>'
            f'</div>'
            for idx, item in enumerate(history[:4])
        )
    else:
        history_html = (
            '<div class="history-item-soft active">'
            + ("开始一个打光问题" if current_language() == "zh" else "Start a lighting case")
            + '<small>'
            + ("按缺陷、材料或应用场景提问" if current_language() == "zh" else "Ask by defect, material, or setup")
            + '</small>'
            '</div>'
        )
    left_html = (
        '<aside class="soft-panel left-rail-soft">'
        '<section class="profile-card-soft">'
        '<div class="avatar-row">'
        '<span class="avatar-soft">IOO</span>'
        f'<span><span class="profile-name">{ui_text("guest")}</span>'
        f'<span class="profile-meta">{ui_text("apply_account")}</span></span>'
        '</div>'
        '<div class="points-row">'
        f'<span class="mini-metric"><strong>+{today}</strong><span>today</span></span>'
        f'<span class="mini-metric"><strong>{remaining}</strong><span>to next reward</span></span>'
        '</div>'
        '</section>'
        f'<div class="section-title-soft"><span>{ui_text("dialog_history")}</span><span>{len(history)}</span></div>'
        f'<div class="history-list-soft">{history_html}</div>'
        f'<div class="section-title-soft"><span>{ui_text("field_shortcuts")}</span><span>tap</span></div>'
        '<div class="shortcut-grid-soft">'
        f'<div class="shortcut-soft"><b>{ui_text("ask_by_defect")}</b>{"划痕、凹痕、污渍、毛刺" if current_language() == "zh" else "Scratch, dent, stain, burr"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("upload_image")}</b>{"附上样品图或草图" if current_language() == "zh" else "Attach sample or sketch"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("compare_lights")}</b>{"条形、同轴、穹顶" if current_language() == "zh" else "Bar, coaxial, dome"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("earn_credits")}</b>{"提问和追问" if current_language() == "zh" else "Questions and follow-ups"}</div>'
        '</div>'
        '</aside>'
    )
    st.markdown(left_html, unsafe_allow_html=True)


def render_left_rail() -> None:
    threads = [
        thread
        for thread in st.session_state.get("threads", [])
        if thread.get("messages") or thread.get("last_result")
    ]
    today = points_today()
    remaining = max(0, reward_target() - int(st.session_state.get("points", 0)))
    profile_html = (
        '<div class="soft-panel left-rail-soft">'
        '<section class="profile-card-soft">'
        '<div class="avatar-row">'
        '<span class="avatar-soft">IOO</span>'
        f'<span><span class="profile-name">{ui_text("guest")}</span>'
        f'<span class="profile-meta">{ui_text("apply_account")}</span></span>'
        '</div>'
        '<div class="points-row">'
        f'<span class="mini-metric"><strong>+{today}</strong><span>today</span></span>'
        f'<span class="mini-metric"><strong>{remaining}</strong><span>to next reward</span></span>'
        '</div>'
        '</section>'
        f'<div class="section-title-soft"><span>{ui_text("dialog_history")}</span><span>{len(threads)}</span></div>'
        '</div>'
    )
    st.markdown(profile_html, unsafe_allow_html=True)

    if st.button(ui_text("new_conversation"), key="left_new_conversation", use_container_width=True):
        start_new_thread()
        st.rerun()

    if threads:
        active_id = st.session_state.get("active_thread_id")
        for idx, thread in enumerate(threads[:10]):
            title = str(thread.get("title") or thread.get("last_question") or "Lighting case")
            title = title[:54] + ("..." if len(title) > 54 else "")
            prefix = "● " if thread.get("id") == active_id else ""
            if st.button(prefix + title, key=f"history_thread_{thread.get('id', idx)}", use_container_width=True):
                load_thread(str(thread.get("id")))
                st.rerun()
        current = active_thread()
        if current.get("messages") or current.get("last_result"):
            st.download_button(
                ui_text("download_history"),
                data=export_thread_payload(current).encode("utf-8-sig"),
                file_name=f"ioo-conversation-{current.get('id', 'history')}.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.caption(ui_text("no_history"))

    shortcuts_html = (
        '<div class="soft-panel left-rail-soft shortcuts-only">'
        f'<div class="section-title-soft"><span>{ui_text("field_shortcuts")}</span><span>tap</span></div>'
        '<div class="shortcut-grid-soft">'
        f'<div class="shortcut-soft"><b>{ui_text("ask_by_defect")}</b>{"Scratch, dent, stain, burr" if current_language() != "zh" else "缺陷、材料、应用"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("upload_image")}</b>{"Attach sample or sketch" if current_language() != "zh" else "上传样品图或草图"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("compare_lights")}</b>{"Bar, coaxial, dome" if current_language() != "zh" else "条形、同轴、穹顶"}</div>'
        f'<div class="shortcut-soft"><b>{ui_text("earn_credits")}</b>{"Questions and follow-ups" if current_language() != "zh" else "提问和追问"}</div>'
        '</div>'
        '</div>'
    )
    st.markdown(shortcuts_html, unsafe_allow_html=True)


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
    st.markdown(f'<div class="ioo-card-title">{"IOO 建议" if current_language() == "zh" else "IOO recommendation"}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <span class="ioo-pill ioo-pill-blue">{ui_text("confidence")}: {str(result.get('confidence', 'low')).upper()}</span>
        <span class="ioo-pill ioo-pill-teal">{localize_value(result.get('fit_type', 'Close fit'), 'fit_type')}</span>
        <span class="ioo-pill ioo-pill-amber">{ui_text("solution_profile")}: {result.get('solution_profile_completeness', 'Low')}</span>
        """,
        unsafe_allow_html=True,
    )
    st.subheader(ui_text("direct"))
    st.write(result.get("direct_recommendation", ""))
    if result.get("lighting_strategy"):
        st.subheader(ui_text("strategy"))
        st.write(result.get("lighting_strategy", ""))
    if result.get("intent") in {"list_search", "attribute_search", "model_lookup", "comparison"}:
        render_product_results(result)
    else:
        st.subheader(ui_text("closest_products"))
        render_product_options(result.get("closest_ioo_products", []))
    test_plan = result.get("practical_test_plan", []) or []
    if test_plan:
        st.subheader(ui_text("test_plan"))
        for item in test_plan:
            st.markdown(f"- {item}")
    missing = result.get("missing_information", []) or []
    if missing and result.get("intent") == "recommendation":
        st.subheader(ui_text("missing"))
        prefix = "为了让建议更准确，请补充：" if current_language() == "zh" else "To make this recommendation stronger: "
        st.info(prefix + ", ".join(missing[:6]))
    if should_show_sources(result):
        st.subheader(ui_text("sources"))
        render_sources(result)
    st.subheader("Continue the conversation")
    cols = st.columns(3)
    for idx, prompt in enumerate(result.get("follow_up_suggestions", [])[:3]):
        with cols[idx % 3]:
            if st.button(prompt, key=f"followup_{idx}", use_container_width=True):
                st.session_state["pending_question"] = prompt
                st.rerun()
    with st.expander("Advanced details", expanded=False):
        st.caption("Private traceability fields are hidden from this public demo.")
        st.json(
            {
                "query_interpretation": result.get("query_interpretation", {}),
                "match_reason": result.get("match_reason", []),
                "warnings": result.get("warnings", []),
                "knowledge_basis": result.get("knowledge_basis", []),
            }
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_product_results(result: dict[str, Any]) -> None:
    products = result.get("product_results", []) or []
    total = int(result.get("total_matched") or len(products))
    showing = len(products)
    st.subheader(ui_text("product_results"))
    if total:
        st.caption(ui_text("showing", shown=showing, total=total))
    else:
        st.info(ui_text("no_match"))
        return
    rows = localize_product_rows(product_search.product_table_rows(products, limit=20))
    st.dataframe(rows, use_container_width=True, hide_index=True)
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        st.download_button(
            "下载当前结果 CSV" if current_language() == "zh" else "Download shown results CSV",
            data=buffer.getvalue().encode("utf-8-sig"),
            file_name="ioo_product_results.csv",
            mime="text/csv",
            use_container_width=True,
        )


def localize_product_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if current_language() != "zh":
        return rows
    column_labels = {
        "public_model": "型号",
        "light_type": "光源类型",
        "product_category": "产品类别",
        "product_family": "产品系列",
        "color": "颜色",
        "wavelength_nm": "波长",
        "voltage_v": "电压",
        "power_w": "功率",
        "current_a": "电流",
        "dimensions": "尺寸",
        "fit_type": "匹配类型",
        "why_it_may_fit": "匹配原因",
    }
    localized = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            label = column_labels.get(key, key)
            if key == "light_type":
                new_row[label] = localize_value(value, "light_type")
            elif key == "fit_type":
                new_row[label] = localize_value(value, "fit_type")
            elif key == "why_it_may_fit":
                new_row[label] = localize_reason(value)
            else:
                new_row[label] = localize_value(value)
        localized.append(new_row)
    return localized


def render_product_options(products: list[dict[str, Any]]) -> None:
    if not products:
        st.info("这可能是定制打光场景。IOO 可以先从最接近的标准几何结构开始，再调整波长、安装或扩散方式。" if current_language() == "zh" else "This may be a custom lighting case. IOO can start with the closest standard geometry and adapt wavelength, mounting, or diffusion.")
        return
    for product in products[:5]:
        light_type = localize_value(product.get("light_type", ""), "light_type")
        fit_type = localize_value(product.get("fit_type"), "fit_type")
        key_specs = localize_value(product.get("key_specs"))
        note = "这可以作为初步测试起点；最终选型需要用样品图验证。" if current_language() == "zh" else "This may be a strong starting point; final selection should be verified with sample images."
        st.markdown(
            f"""
            <div class="ioo-product-card">
              <div class="ioo-product-title">{product.get('public_model')}</div>
              <div class="ioo-muted">{light_type} | {fit_type}</div>
              <p>{localize_reason(product.get('why_it_may_fit'))}</p>
              <div class="ioo-muted">{"关键参数" if current_language() == "zh" else "Key specs"}: {key_specs}</div>
              <div class="ioo-muted">{"备注" if current_language() == "zh" else "Note"}: {note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_product_card_native(product: dict[str, Any], key_prefix: str) -> None:
    model = str(product.get("public_model") or "IOO-SANDBOX")
    light_type = localize_value(product.get("light_type", "") or "lighting", "light_type")
    reason = localize_reason(product.get("why_it_may_fit") or product.get("public_description") or ui_text("general_candidate"))
    key_specs = localize_value(product.get("key_specs") or "not available")
    fit_type = localize_value(product.get("fit_type") or "Sandbox candidate", "fit_type")
    details_url, spec_url = product_links(model)
    with st.container(border=True):
        img_col, text_col = st.columns([0.34, 0.66], vertical_alignment="center")
        with img_col:
            asset = product_asset_path(str(product.get("light_type", "")))
            if asset:
                st.image(str(asset), use_container_width=True)
            else:
                st.caption("IOO")
        with text_col:
            st.markdown(f"**{model}**")
            st.caption(str(reason))
        st.caption(f"{light_type} | {fit_type} | {key_specs}")
        details = []
        for label, field in [
            (ui_text("category"), "product_category"),
            ("颜色" if current_language() == "zh" else "color", "color"),
            ("波长" if current_language() == "zh" else "wavelength", "wavelength_nm"),
            ("电压" if current_language() == "zh" else "voltage", "voltage_v"),
            ("功率" if current_language() == "zh" else "power", "power_w"),
        ]:
            value = product.get(field)
            if value and str(value).lower() != "not available":
                details.append(f"{label}: {localize_value(value, field)}")
        if details:
            st.caption(" | ".join(details[:5]))
        st.markdown(f"[{ui_text('details')}]({details_url}) &nbsp; [{ui_text('spec_sheet')}]({spec_url})", unsafe_allow_html=True)
        save_col, compare_col = st.columns(2)
        with save_col:
            st.button(ui_text("save"), key=f"{key_prefix}_save_{model}", use_container_width=True)
        with compare_col:
            st.button(ui_text("compare"), key=f"{key_prefix}_compare_{model}", use_container_width=True)


def current_recommended_products() -> list[dict[str, Any]]:
    result = st.session_state.get("last_result") or {}
    products = result.get("closest_ioo_products") or []
    if products:
        return products
    products = result.get("product_results") or []
    if products:
        return products[:5]
    return []


def render_product_rail() -> None:
    products = current_recommended_products()
    display_products = products
    st.markdown(
        f"""
        <div class="product-rail-kicker">{"IOO 回答后" if current_language() == "zh" else "After IOO answers"}</div>
        <div class="product-rail-title">{ui_text("product_shortlist")}</div>
        <div class="product-rail-sub">{ui_text("shortlist_sub")}</div>
        """,
        unsafe_allow_html=True,
    )
    if not display_products:
        st.markdown(
            f"""
            <div class="product-empty-soft">
              {ui_text("empty_shortlist")}
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    for idx, product in enumerate(display_products[:4]):
        render_product_card_native(product, f"rail_{idx}")


def render_mobile_product_tab() -> None:
    products = current_recommended_products()
    count = len(products)
    label = f"{count} 个产品候选" if current_language() == "zh" and count else f"{count} products recommended" if count else ("产品会显示在这里" if current_language() == "zh" else "Products will appear here")
    st.markdown(
        f"""
        <div class="mobile-product-tab">
          <span><b>{e(label)}</b><br><span>Models, images, spec links, save and compare actions</span></span>
          <a class="open-pill" href="#ioo-mobile-products">{"打开" if current_language() == "zh" else "Open"}</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mobile_product_drawer() -> None:
    products = current_recommended_products()
    count = len(products)
    title = f"{count} 个产品候选" if current_language() == "zh" and count else f"{count} product candidates" if count else ui_text("product_shortlist")
    st.markdown('<div id="ioo-mobile-products"></div>', unsafe_allow_html=True)
    st.markdown(f"### {title}")
    st.caption("移动端产品候选区，仅显示公开 IOO 型号。" if current_language() == "zh" else "Mobile product drawer for quick field review. Public IOO models only.")
    for idx, product in enumerate(products[:4]):
        render_product_card_native(product, f"mobile_{idx}")


def render_sources(result: dict[str, Any]) -> None:
    sources = result.get("knowledge_sources", [])
    if sources:
        st.markdown(f"**{ui_text('knowledge_basis')}**")
        for source in sources[:5]:
            title = source.get("title") or "Knowledge source"
            url = source.get("url")
            source_name = source.get("source_name") or "Knowledge source"
            if url:
                st.markdown(f"- {source_name}: [{title}]({url})")
            else:
                st.markdown(f"- {source_name}: {title}")
    if result.get("product_results") or result.get("closest_ioo_products"):
        st.markdown(f"**{ui_text('product_basis')}**")
        st.caption("产品匹配来自 IOO 公开产品数据库；私有追溯链接不会在公开页面显示。" if current_language() == "zh" else "Product matches are from the IOO public product database. Private traceability URLs are not shown.")


def should_show_sources(result: dict[str, Any]) -> bool:
    if result.get("knowledge_sources"):
        return True
    return bool(result.get("product_results") or result.get("closest_ioo_products"))


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
    has_saved_threads = any(
        thread.get("messages") or thread.get("last_result")
        for thread in st.session_state.get("threads", [])
    )
    in_conversation = bool(st.session_state.get("last_result")) or has_saved_threads
    if in_conversation:
        left_col, center_col, right_col = st.columns([0.20, 0.58, 0.22], gap="large")
        with left_col:
            render_left_rail()
        with center_col:
            if not st.session_state.get("last_result"):
                render_hero()
            render_search_card()
            if st.session_state.get("last_result"):
                render_answer(st.session_state.get("last_result"))
            else:
                render_how_it_works()
            render_mobile_product_drawer()
        with right_col:
            render_product_rail()
    else:
        spacer_col, center_col, right_col = st.columns([0.08, 0.68, 0.24], gap="large")
        with center_col:
            render_hero()
            render_search_card()
        with right_col:
            render_product_rail()
    render_mobile_product_tab()
    # Keep the public catalog fresh in case generated product files were not uploaded.
    if not Path("public_products.csv").exists() or not Path("data/ioo_products.db").exists():
        sku_mapping.generate_files()


if __name__ == "__main__":
    main()
