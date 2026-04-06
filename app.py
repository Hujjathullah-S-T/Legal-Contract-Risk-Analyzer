import html
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from analyzer_core import (
    ROLE_DESCRIPTIONS,
    answer_question,
    compare_contracts,
    highlight_sentences_with_tooltips,
    read_uploaded_file,
    revise_contract_to_lower_risk,
    role_based_summary,
    run_full_analysis,
)

st.set_page_config(page_title="Legal Contract Risk Analyzer", page_icon="⚖️", layout="wide")
HISTORY_PATH = Path("analysis_history.json")
SAMPLE_CONTRACTS = {
    "Balanced Service Agreement": (
        "This agreement is made between Client and Vendor. The Vendor shall deliver monthly support reports. "
        "The Client shall pay INR 5000 within 15 days of invoice. Either party may terminate this agreement with 30 days notice. "
        "Confidential information must be protected and disputes shall be resolved by arbitration."
    ),
    "Risky Liability Clause": (
        "The Vendor shall be liable for all damages and unlimited liability shall apply. "
        "Either party may terminate immediately upon breach or payment failure. "
        "The Client shall indemnify the Company for any claim and penalty."
    ),
    "Ambiguous Draft": (
        "The Supplier should provide updates as soon as possible and use best efforts to maintain service levels. "
        "Reasonable changes may be made from time to time. Payment may be adjusted if needed."
    ),
}


def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history):
    try:
        HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except OSError:
        pass


def store_analysis(result):
    record = {
        "Date": result["created_at"],
        "File Name": result["source_name"],
        "Risk Score": result["summary"]["overall_score"],
        "Risk Level": result["summary"]["overall_risk"],
        "High Risk Count": result["summary"]["counts"]["High Risk"],
        "Medium Risk Count": result["summary"]["counts"]["Medium Risk"],
        "Low Risk Count": result["summary"]["counts"]["Low Risk"],
    }
    history = st.session_state.setdefault("analysis_history", [])
    history.insert(0, record)
    save_history(history)
    st.session_state["latest_result"] = result
    st.session_state["contract_chat_history"] = []
    st.session_state["revised_contract_package"] = None


st.session_state.setdefault("analysis_history", load_history())
st.session_state.setdefault("latest_result", None)
st.session_state.setdefault("contract_text", "")
st.session_state.setdefault("uploaded_contract_text", "")
st.session_state.setdefault("uploaded_contract_name", "Uploaded Contract")
st.session_state.setdefault("current_page", "🏠 Home")
st.session_state.setdefault("theme_mode", "Dark")
st.session_state.setdefault("reported_issues", [])
st.session_state.setdefault("issue_type", "UI issue")
st.session_state.setdefault("issue_details", "")
st.session_state.setdefault("contract_chat_history", [])
st.session_state.setdefault("revised_contract_package", None)

theme_mode = st.session_state.get("theme_mode", "Dark")
if theme_mode == "Light":
    theme = {
        "text": "#1d2430",
        "bg": "radial-gradient(circle at 8% 10%, rgba(168, 85, 24, 0.18), transparent 20%), radial-gradient(circle at 88% 14%, rgba(14, 116, 144, 0.12), transparent 22%), linear-gradient(135deg, #f7f1e4 0%, #efe2c7 42%, #fbf7ef 100%)",
        "sidebar_bg": "linear-gradient(180deg, #2c2118 0%, #443126 100%)",
        "sidebar_border": "rgba(124, 95, 67, 0.24)",
        "card_bg": "linear-gradient(180deg, rgba(255, 251, 242, 0.96) 0%, rgba(250, 242, 226, 0.94) 100%)",
        "card_border": "rgba(124, 95, 67, 0.18)",
        "card_shadow": "0 20px 38px rgba(101, 78, 57, 0.16)",
        "eyebrow_bg": "rgba(140, 89, 44, 0.12)",
        "eyebrow_text": "#8b5a2b",
        "title": "#1b2330",
        "muted": "#5f5649",
        "metric": "#0f6b73",
        "result": "#1b2330",
        "highlight_bg": "linear-gradient(180deg, rgba(255,248,236,0.98) 0%, rgba(255,252,246,0.98) 100%)",
        "highlight_border": "rgba(124, 95, 67, 0.18)",
        "highlight_text": "#1d2430",
        "nav_caption": "#eadfcb",
        "button_bg": "rgba(255, 247, 231, 0.08)",
        "button_text": "#f8efe0",
        "button_hover_bg": "linear-gradient(90deg, rgba(196, 144, 88, 0.22) 0%, rgba(230, 197, 156, 0.10) 100%)",
        "button_hover_text": "#fff8ef",
        "input_bg": "rgba(255, 255, 252, 0.96)",
        "input_text": "#1d2430",
        "input_border": "rgba(124, 95, 67, 0.24)",
        "file_bg": "rgba(255, 249, 239, 0.82)",
        "accent": "#9a6a3a",
        "accent_soft": "rgba(154, 106, 58, 0.12)",
        "surface_alt": "rgba(247, 236, 214, 0.92)",
        "divider": "rgba(154, 106, 58, 0.10)",
        "primary_label": "Dossier-inspired light mode",
    }
else:
    theme = {
        "text": "#e7ecf4",
        "bg": "radial-gradient(circle at 10% 12%, rgba(192, 132, 47, 0.18), transparent 18%), radial-gradient(circle at 85% 14%, rgba(14, 165, 233, 0.10), transparent 18%), linear-gradient(135deg, #071018 0%, #101827 38%, #1a2133 100%)",
        "sidebar_bg": "linear-gradient(180deg, #0a0f17 0%, #151b26 100%)",
        "sidebar_border": "rgba(214, 176, 109, 0.14)",
        "card_bg": "linear-gradient(180deg, rgba(17, 24, 39, 0.86) 0%, rgba(24, 31, 47, 0.86) 100%)",
        "card_border": "rgba(214, 176, 109, 0.16)",
        "card_shadow": "0 24px 48px rgba(2, 6, 23, 0.34)",
        "eyebrow_bg": "rgba(214, 176, 109, 0.12)",
        "eyebrow_text": "#f1ca73",
        "title": "#f7f3eb",
        "muted": "#9ca7b7",
        "metric": "#f1ca73",
        "result": "#f7f3eb",
        "highlight_bg": "linear-gradient(180deg, rgba(12,19,31,0.96) 0%, rgba(19,28,43,0.96) 100%)",
        "highlight_border": "rgba(214, 176, 109, 0.14)",
        "highlight_text": "#e6edf7",
        "nav_caption": "#8f99aa",
        "button_bg": "rgba(255, 255, 255, 0.02)",
        "button_text": "#e8edf4",
        "button_hover_bg": "linear-gradient(90deg, rgba(214, 176, 109, 0.16) 0%, rgba(214, 176, 109, 0.06) 100%)",
        "button_hover_text": "#fffaf0",
        "input_bg": "rgba(11, 18, 29, 0.92)",
        "input_text": "#e8edf4",
        "input_border": "rgba(214, 176, 109, 0.18)",
        "file_bg": "rgba(11, 18, 29, 0.68)",
        "accent": "#d6b06d",
        "accent_soft": "rgba(214, 176, 109, 0.12)",
        "surface_alt": "rgba(31, 40, 58, 0.74)",
        "divider": "rgba(214, 176, 109, 0.08)",
        "primary_label": "Ink and brass dark mode",
    }

st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Manrope', sans-serif; color: {theme["text"]}; }}
        .block-container {{ padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1320px; }}
        .stApp {{ background: {theme["bg"]}; }}
        [data-testid="stSidebar"] {{ background: {theme["sidebar_bg"]}; border-right: 1px solid {theme["sidebar_border"]}; }}
        [data-testid="stAppViewContainer"] {{
            background-image:
                linear-gradient(90deg, transparent 0%, transparent calc(100% - 1px), {theme["divider"]} calc(100% - 1px)),
                linear-gradient(0deg, transparent 0%, transparent calc(100% - 1px), {theme["divider"]} calc(100% - 1px));
            background-size: 32px 32px;
        }}
        .hero-card, .panel-card, .metric-card, .result-card, .empty-card, .sentence-card {{
            border-radius: 20px;
            background: {theme["card_bg"]};
            border: 1px solid {theme["card_border"]};
            box-shadow: {theme["card_shadow"]};
            backdrop-filter: blur(14px);
            padding: 1.15rem 1.2rem;
            margin-bottom: 0.85rem;
        }}
        .hero-card {{
            padding: 2.1rem 2.2rem;
            margin-bottom: 1.15rem;
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at 86% 16%, {theme["accent_soft"]}, transparent 28%),
                radial-gradient(circle at 18% 100%, rgba(14, 116, 144, 0.10), transparent 34%),
                linear-gradient(135deg, {theme["card_bg"]} 0%, {theme["surface_alt"]} 100%);
        }}
        .hero-card::after {{
            content: "§";
            position: absolute;
            right: 1.4rem;
            top: 0.45rem;
            font-size: 5rem;
            color: {theme["accent_soft"]};
            font-weight: 800;
            line-height: 1;
        }}
        .eyebrow {{ display: inline-block; padding: 0.5rem 0.9rem; border-radius: 999px; background: {theme["eyebrow_bg"]}; color: {theme["eyebrow_text"]}; font-size: 0.74rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; }}
        .hero-title {{ margin: 0.95rem 0 0.65rem; max-width: 820px; font-size: clamp(2.1rem, 3vw, 3.4rem); font-weight: 800; line-height: 1.05; color: {theme["title"]}; }}
        .hero-copy, .body-copy, .subtle-copy {{ color: {theme["muted"]}; line-height: 1.72; font-size: 0.98rem; }}
        .section-title {{ margin: 0; color: {theme["title"]}; font-size: 1.12rem; font-weight: 800; letter-spacing: 0.01em; }}
        .section-title::before {{
            content: "";
            display: inline-block;
            width: 22px;
            height: 2px;
            margin-right: 10px;
            vertical-align: middle;
            background: {theme["accent"]};
            border-radius: 999px;
        }}
        .metric-label {{ color: {theme["muted"]}; font-size: 0.9rem; margin-bottom: 0.5rem; }}
        .metric-value {{ font-size: 1.75rem; font-weight: 800; line-height: 1; color: {theme["metric"]}; }}
        .result-term {{ font-weight: 800; color: {theme["result"]}; }}
        .highlight-panel {{ padding: 1rem 1.1rem; border-radius: 16px; border: 1px solid {theme["highlight_border"]}; background: {theme["highlight_bg"]}; line-height: 1.78; color: {theme["highlight_text"]}; }}
        .sentence-highlight {{ padding: 0.08rem 0.18rem; border-radius: 0.35rem; border-bottom: 2px dotted currentColor; }}
        .high {{ color: #e11d48; background: rgba(225,29,72,0.12); }}
        .medium {{ color: #d97706; background: rgba(217,119,6,0.14); }}
        .low {{ color: #059669; background: rgba(5,150,105,0.14); }}
        .neutral {{ color: #0f766e; background: rgba(15,118,110,0.12); }}
        .badge {{
            display: inline-block;
            padding: 0.3rem 0.62rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 800;
            margin-bottom: 0.6rem;
        }}
        .score-list div {{ color: {theme["muted"]}; margin-bottom: 0.25rem; }}
        .status-banner {{ border-radius: 18px; padding: 1.15rem 1.2rem; color: white; margin-bottom: 0.9rem; }}
        .status-banner.high {{ background: linear-gradient(135deg, #9f1239, #e11d48, #fb7185); }}
        .status-banner.medium {{ background: linear-gradient(135deg, #a16207, #f59e0b, #fbbf24); }}
        .status-banner.low {{ background: linear-gradient(135deg, #047857, #10b981, #34d399); }}
        .status-banner.neutral {{ background: linear-gradient(135deg, #0f766e, #0891b2, #22d3ee); }}
        .status-label {{ font-size: 0.74rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.92; }}
        .status-title {{ margin: 0.45rem 0 0.25rem; font-size: 1.65rem; font-weight: 800; }}
        .nav-caption {{ color: {theme["nav_caption"]}; font-size: 0.92rem; }}
        .card-grid-title {{ color: {theme["title"]}; font-weight: 700; margin-bottom: 0.55rem; }}
        [data-testid="stSidebar"] .stButton > button {{
            width: 100%;
            justify-content: flex-start;
            border-radius: 14px;
            border: 1px solid {theme["card_border"]};
            background: {theme["button_bg"]};
            color: {theme["button_text"]};
            padding: 0.8rem 0.95rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            border-color: {theme["accent"]};
            background: {theme["button_hover_bg"]};
            color: {theme["button_hover_text"]};
            transform: translateX(4px);
        }}
        .stTextArea textarea, .stTextInput input {{
            background: {theme["input_bg"]} !important;
            color: {theme["input_text"]} !important;
            border: 1px solid {theme["input_border"]} !important;
            border-radius: 14px !important;
        }}
        .stSelectbox div[data-baseweb="select"] > div,
        .stSelectbox div[role="combobox"],
        .stMultiSelect div[data-baseweb="select"] > div,
        .stFileUploader small,
        .stCaption,
        .stAlert,
        .stAlert p,
        .stExpander summary,
        .stExpander details summary,
        .stExpander label,
        .stMarkdown,
        .stMarkdown strong,
        .highlight-panel strong,
        .result-card strong,
        .score-list strong,
        .stTextInput label,
        .stTextArea label,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stMarkdownContainer"] strong {{
            color: {theme["text"]} !important;
        }}
        .stExpander summary svg, .stExpander details summary svg {{ fill: {theme["text"]} !important; }}
        .stTextArea textarea:focus, .stTextInput input:focus {{ border-color: rgba(125, 211, 252, 0.4) !important; box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.22) !important; }}
        .stFileUploader {{ background: {theme["file_bg"]}; border-radius: 16px; border: 1px dashed rgba(148, 163, 184, 0.2); padding: 0.75rem 0.9rem; }}
        .stDownloadButton button, .stButton button[kind="primary"] {{ border-radius: 12px !important; }}
        .stSelectbox label, .stToggle label, .stFileUploader label {{ color: {theme["title"]} !important; }}
        .stDataFrame, .stTable {{ color: {theme["text"]}; }}
        .stForm {{
            padding: 1rem 1rem 0.2rem;
            border-radius: 18px;
            border: 1px solid {theme["card_border"]};
            background: {theme["surface_alt"]};
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🧭 Navigation Menu")
    nav_items = ["🏠 Home", "📊 Dashboard", "📝 Analyze Contract", "⚖️ Compare Contracts", "📈 Risk Report", "🕘 History", "⚙️ Settings / About"]
    for item in nav_items:
        label = f"• {item}" if st.session_state.get("current_page") == item else item
        if st.button(label, key=f"nav_{item}", use_container_width=True):
            st.session_state["current_page"] = item
    theme_choice = st.toggle("Light Mode", value=(theme_mode == "Light"))
    new_theme = "Light" if theme_choice else "Dark"
    if new_theme != st.session_state.get("theme_mode"):
        st.session_state["theme_mode"] = new_theme
        st.rerun()
    st.markdown(f"<div class='nav-caption'>{theme['primary_label']}</div>", unsafe_allow_html=True)
    selected_role = st.selectbox("View Mode", list(ROLE_DESCRIPTIONS.keys()), help="Switch between lawyer, client, and manager perspectives.")
    st.caption(ROLE_DESCRIPTIONS[selected_role])

current_page = st.session_state.get("current_page", "🏠 Home")
latest_result = st.session_state.get("latest_result")
history = st.session_state.get("analysis_history", [])


def render_home():
    st.markdown(
        """
        <div class="hero-card">
            <div class="eyebrow">Developed By Hujjathullah</div>
            <div class="hero-title">Legal Contract Risk Analyzer</div>
            <div class="hero-copy">A professional legal-NLP dashboard for contract review, file-based analysis, risk reporting, and presentation-ready summaries.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.markdown(
            """
            <div class='panel-card'>
                <div class='section-title'>Project Overview</div>
                <div class='body-copy'>This application helps review contract language through risk scoring, highlighted terms, clause checks, file upload support, reporting, and history tracking.</div>
            </div>
            <div class='panel-card'>
                <div class='section-title'>Chambers Overview</div>
                <div class='subtle-copy'>Risk score calculation, clause-focused analysis, side-by-side comparison, downloadable reports, and matter history inside a legal-themed review workspace.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class='panel-card'>
                <div class='section-title'>Developer</div>
                <div class='subtle-copy'>Hujjathullah</div>
            </div>
            <div class='panel-card'>
                <div class='section-title'>Case Flow</div>
                <div class='subtle-copy'>Use Analyze Contract for pasted text or uploaded files, Compare Contracts to review differences, and Risk Report to export the latest legal summary.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard():
    total_contracts = len(history)
    high_count = sum(1 for item in history if item["Risk Level"] == "High Risk")
    medium_count = sum(1 for item in history if item["Risk Level"] == "Medium Risk")
    low_count = sum(1 for item in history if item["Risk Level"] == "Low Risk")
    cols = st.columns(4)
    metrics = [("📄 Total Contracts Analyzed", total_contracts), ("🔴 High Risk Count", high_count), ("🟠 Medium Risk", medium_count), ("🟢 Low Risk", low_count)]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>", unsafe_allow_html=True)
    chart_col, recent_col = st.columns([1.1, 0.9], gap="large")
    with chart_col:
        distribution = pd.DataFrame([{"Risk Level": "High Risk", "Count": high_count}, {"Risk Level": "Medium Risk", "Count": medium_count}, {"Risk Level": "Low Risk", "Count": low_count}])
        chart = alt.Chart(distribution).mark_arc(innerRadius=55).encode(
            theta="Count:Q",
            color=alt.Color("Risk Level:N", scale=alt.Scale(domain=["High Risk", "Medium Risk", "Low Risk"], range=["#fb7185", "#fbbf24", "#34d399"])),
            tooltip=["Risk Level", "Count"],
        ).properties(height=320)
        st.markdown("<div class='panel-card'><div class='section-title'>Portfolio Risk Distribution</div></div>", unsafe_allow_html=True)
        st.altair_chart(chart, use_container_width=True)
    with recent_col:
        st.markdown("<div class='panel-card'><div class='section-title'>Recent Analyses</div></div>", unsafe_allow_html=True)
        if history:
            for item in history[:5]:
                st.markdown(f"<div class='result-card'><div class='result-term'>{html.escape(item['File Name'])}</div><div class='subtle-copy'>{item['Date']} · {item['Risk Level']} · Score {item['Risk Score']}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='empty-card'>No analyses yet. Use Analyze Contract to begin, then review outcomes here.</div>", unsafe_allow_html=True)


def render_clause_cards(summary):
    st.markdown("<div class='panel-card'><div class='section-title'>Clause Review</div></div>", unsafe_allow_html=True)
    cols = st.columns(2, gap="large")
    for index, item in enumerate(summary["clause_cards"]):
        badge_class = "neutral" if item["risk_level"] == "Needs Review" else item["risk_level"].lower().split()[0]
        matches = ", ".join(item["matches"][:3]) if item["matches"] else "No direct clause terms found"
        with cols[index % 2]:
            st.markdown(
                f"""
                <div class='result-card'>
                    <div class='badge {badge_class}'>{html.escape(item['risk_level'])}</div>
                    <div class='result-term'>{html.escape(item['clause'])}</div>
                    <div class='subtle-copy'>Score {item['score']} · Matches: {html.escape(matches)}</div>
                    <div class='subtle-copy'>{html.escape(item['explanation'])}</div>
                    <div class='subtle-copy'><strong>Recommendation:</strong> {html.escape(item['recommendation'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_score_breakdown(summary):
    breakdown = summary["score_breakdown"]
    st.markdown(
        f"""
        <div class='panel-card'>
            <div class='section-title'>Score Breakdown</div>
            <div class='score-list'>
                <div>Keywords: {breakdown['keywords']}</div>
                <div>Ambiguity: {breakdown['ambiguity']}</div>
                <div>Compliance: {breakdown['compliance']}</div>
                <div>Dependency: {breakdown['dependency']}</div>
                <div>Sentence Context: {breakdown['sentence_context']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_analyze_contract():
    st.markdown("<div class='panel-card'><div class='section-title'>Analyze Contract</div></div>", unsafe_allow_html=True)
    st.caption("Rule-based legal screening. Results are explainable and demo-friendly, but not a substitute for legal review.")
    sample_cols = st.columns(3)
    for col, (label, sample_text) in zip(sample_cols, SAMPLE_CONTRACTS.items()):
        with col:
            if st.button(label, use_container_width=True, key=f"sample_{label}"):
                st.session_state["contract_text"] = sample_text
                st.session_state["uploaded_contract_name"] = label
                st.rerun()
    uploaded_file = st.file_uploader("Upload Contract File", type=["pdf", "docx", "txt"], key="inline_upload")
    if uploaded_file is not None:
        extracted_text = read_uploaded_file(uploaded_file)
        st.session_state["uploaded_contract_text"] = extracted_text
        st.session_state["uploaded_contract_name"] = uploaded_file.name
        if extracted_text.strip():
            st.session_state["contract_text"] = extracted_text
            st.markdown("<div class='card-grid-title'>Extracted Text Preview</div>", unsafe_allow_html=True)
            st.text_area("Preview", extracted_text, height=180, key="inline_preview")
        else:
            st.warning("No readable text was extracted from the file.")
    contract_text = st.text_area("Paste Contract Text", value=st.session_state.get("contract_text", ""), height=300, placeholder="Paste the full contract text here...")
    st.session_state["contract_text"] = contract_text
    if st.button("Analyze Contract", type="primary", use_container_width=True):
        if not contract_text.strip():
            st.warning("Paste some contract text first.")
        else:
            with st.spinner("Analyzing contract..."):
                source_name = st.session_state.get("uploaded_contract_name") if uploaded_file is not None else "Pasted Contract"
                result = run_full_analysis(contract_text, source_name)
                store_analysis(result)
                st.success("Analysis completed successfully.")
                st.progress(min(result["summary"]["overall_score"], 100) / 100)
    result = st.session_state.get("latest_result")
    if result and result["text"]:
        summary = result["summary"]
        findings = result["findings"]
        st.markdown("<div class='panel-card'><div class='section-title'>Analysis Results</div></div>", unsafe_allow_html=True)
        left, right = st.columns([1.1, 0.9], gap="large")
        with left:
            st.markdown(f"<div class='highlight-panel'>{highlight_sentences_with_tooltips(result['text'], result['sentence_findings'])}</div>", unsafe_allow_html=True)
        with right:
            st.markdown(f"<div class='panel-card'><div class='status-banner {summary['overall_class']}'><div class='status-label'>Overall Risk Score</div><div class='status-title'>{summary['overall_score']}/100</div><p>{summary['overall_risk']}</p></div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Risk Categories</div><div class='subtle-copy'>🔴 {summary['counts']['High Risk']} high risk · 🟠 {summary['counts']['Medium Risk']} medium risk · 🟢 {summary['counts']['Low Risk']} low risk</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Executive Explanation</div><div class='subtle-copy'>{html.escape(role_based_summary(selected_role, summary, findings))}</div></div>", unsafe_allow_html=True)
            render_score_breakdown(summary)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Analysis Note</div><div class='subtle-copy'>{html.escape(summary['analysis_note'])}</div></div>", unsafe_allow_html=True)
            st.markdown("<div class='panel-card'><div class='section-title'>Download Report</div></div>", unsafe_allow_html=True)
            st.download_button(
                "📥 Download Report (PDF)",
                result["pdf_report"],
                file_name="contract_risk_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="analyze_download_pdf",
            )
            st.download_button(
                "📄 Download Report (DOCX)",
                result["docx_report"],
                file_name="contract_risk_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="analyze_download_docx",
            )
        with st.expander("Clause-by-Clause Review", expanded=True):
            render_clause_cards(summary)
        with st.expander("Risky Sentences and Reasons"):
            if result["sentence_findings"]:
                for item in result["sentence_findings"]:
                    st.markdown(
                        f"<div class='result-card'><div class='badge {item['level'].lower().split()[0]}'>{html.escape(item['level'])}</div><div class='subtle-copy'>{html.escape(item['sentence'])}</div><div class='subtle-copy'>{html.escape(item['reason'])}</div></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No risky sentences were identified by the current rule set.")
        with st.expander("AI Contract Chatbot", expanded=True):
            st.caption("Ask questions about the currently analyzed contract. Answers are grounded in the analyzed text and rule-based signals.")
            question = st.text_input(
                "Ask about the contract",
                placeholder="Example: Who is liable? What is the payment term? Is termination risky?",
                key="contract_question",
            )
            if st.button("Ask Contract Chatbot", use_container_width=True, key="ask_contract_chatbot"):
                if not question.strip():
                    st.warning("Enter a contract question first.")
                else:
                    response = answer_question(
                        question,
                        result["text"],
                        summary["entities"],
                        summary["obligations"],
                        findings,
                    )
                    st.session_state["contract_chat_history"].insert(
                        0,
                        {
                            "question": question.strip(),
                            "answer": response,
                        },
                    )
            if st.session_state["contract_chat_history"]:
                for item in st.session_state["contract_chat_history"][:4]:
                    st.markdown(
                        f"<div class='result-card'><div class='result-term'>Q: {html.escape(item['question'])}</div><div class='subtle-copy'>A: {html.escape(item['answer'])}</div></div>",
                        unsafe_allow_html=True,
                    )
        with st.expander("Reduce Risk With Safer Redraft", expanded=True):
            st.caption("Generate a lower-risk revised draft based on the current rule-based findings.")
            if st.button("Revise Contract to Lower Risk", use_container_width=True, key="revise_contract_button"):
                st.session_state["revised_contract_package"] = revise_contract_to_lower_risk(result["text"], summary, findings)
            revised_package = st.session_state.get("revised_contract_package")
            if revised_package:
                revised_result = revised_package["revised_result"]
                st.markdown(
                    f"<div class='result-card'><div class='result-term'>Risk Reduction</div><div class='subtle-copy'>Original: {summary['overall_risk']} ({summary['overall_score']}/100) · Revised: {revised_result['summary']['overall_risk']} ({revised_result['summary']['overall_score']}/100)</div></div>",
                    unsafe_allow_html=True,
                )
                if revised_package["changes"]:
                    for item in revised_package["changes"][:6]:
                        st.markdown(
                            f"<div class='result-card'><div class='result-term'>{html.escape(item['term'])}</div><div class='subtle-copy'>{html.escape(item['replacement'])}</div></div>",
                            unsafe_allow_html=True,
                        )
                st.text_area(
                    "Safer Revised Contract",
                    revised_package["revised_text"],
                    height=220,
                    key="safer_revised_contract_text",
                )


def render_compare_contracts():
    st.markdown("<div class='panel-card'><div class='section-title'>Compare Contracts</div></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        base_upload = st.file_uploader("Upload Base Contract", type=["pdf", "docx", "txt"], key="base_upload")
        if base_upload is not None:
            base_extracted = read_uploaded_file(base_upload)
            if base_extracted.strip():
                st.session_state["base_contract"] = base_extracted
        base_text = st.text_area("Base Contract", height=260, key="base_contract")
    with right:
        revised_upload = st.file_uploader("Upload Revised Contract", type=["pdf", "docx", "txt"], key="revised_upload")
        if revised_upload is not None:
            revised_extracted = read_uploaded_file(revised_upload)
            if revised_extracted.strip():
                st.session_state["revised_contract"] = revised_extracted
        revised_text = st.text_area("Revised Contract", height=260, key="revised_contract")

    if st.button("Compare Two Contracts", type="primary", use_container_width=True):
        if not base_text.strip() or not revised_text.strip():
            st.warning("Add both contracts before comparing them.")
            return
        comparison = compare_contracts(base_text, revised_text)
        st.markdown(
            f"""
            <div class='panel-card'>
                <div class='section-title'>Safety Verdict</div>
                <div class='result-term'>{html.escape(comparison['safer_contract'])}</div>
                <div class='subtle-copy'>{html.escape(comparison['safety_reason'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='metric-card'><div class='metric-label'>Similarity</div><div class='metric-value'>{comparison['similarity']}%</div></div>", unsafe_allow_html=True)
        c2.markdown(
            f"<div class='metric-card'><div class='metric-label'>Base Contract</div><div class='metric-value'>{comparison['base_score']}</div><div class='subtle-copy'>{html.escape(comparison['base_risk'])}</div></div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div class='metric-card'><div class='metric-label'>Revised Contract</div><div class='metric-value'>{comparison['compare_score']}</div><div class='subtle-copy'>{html.escape(comparison['compare_risk'])}</div></div>",
            unsafe_allow_html=True,
        )

        left_col, right_col = st.columns(2, gap="large")
        with left_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Added Risks</div></div>", unsafe_allow_html=True)
            for item in comparison["added_risks"] or ["No new risky terms"]:
                st.markdown(f"<div class='result-card'>{html.escape(item)}</div>", unsafe_allow_html=True)
        with right_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Removed Risks</div></div>", unsafe_allow_html=True)
            for item in comparison["removed_risks"] or ["No removed risky terms"]:
                st.markdown(f"<div class='result-card'>{html.escape(item)}</div>", unsafe_allow_html=True)
        with st.expander("Clause-Focused Changes", expanded=True):
            if comparison["clause_changes"]:
                for item in comparison["clause_changes"]:
                    badge_class = "low" if item["change"] == "Improved" else "high"
                    st.markdown(
                        f"<div class='result-card'><div class='badge {badge_class}'>{html.escape(item['change'])}</div><div class='result-term'>{html.escape(item['clause'])}</div><div class='subtle-copy'>{html.escape(item['summary'])}</div><div class='subtle-copy'>Base: {html.escape(item['base_risk'])} · Revised: {html.escape(item['revised_risk'])}</div></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No major clause-level changes were detected between the two contracts.")


def render_risk_report():
    st.markdown("<div class='panel-card'><div class='section-title'>Risk Report</div></div>", unsafe_allow_html=True)
    if not latest_result:
        st.info("Run an analysis first to generate a risk report.")
        return
    summary = latest_result["summary"]
    chart_col, side_col = st.columns([1.05, 0.95], gap="large")
    with chart_col:
        risk_df = pd.DataFrame([{"Risk Level": "High Risk", "Count": summary["counts"]["High Risk"]}, {"Risk Level": "Medium Risk", "Count": summary["counts"]["Medium Risk"]}, {"Risk Level": "Low Risk", "Count": summary["counts"]["Low Risk"]}])
        pie = alt.Chart(risk_df).mark_arc(innerRadius=55).encode(
            theta="Count:Q",
            color=alt.Color("Risk Level:N", scale=alt.Scale(domain=["High Risk", "Medium Risk", "Low Risk"], range=["#fb7185", "#fbbf24", "#34d399"])),
            tooltip=["Risk Level", "Count"],
        ).properties(height=280)
        st.altair_chart(pie, use_container_width=True)
        keyword_df = pd.DataFrame(summary["top_terms"], columns=["Keyword", "Hits"]) if summary["top_terms"] else pd.DataFrame([{"Keyword": "None", "Hits": 0}])
        bars = alt.Chart(keyword_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
            x=alt.X("Keyword:N", sort="-y"),
            y="Hits:Q",
            color=alt.value("#22d3ee"),
            tooltip=["Keyword", "Hits"],
        ).properties(height=280)
        st.altair_chart(bars, use_container_width=True)
    with side_col:
        st.markdown("<div class='panel-card'><div class='section-title'>Top Risky Clauses</div></div>", unsafe_allow_html=True)
        top_items = summary["clauses"] or [{"clause": "No clause classification available", "explanation": "Run or improve the analysis input."}]
        for item in top_items[:5]:
            st.markdown(f"<div class='result-card'><div class='result-term'>{html.escape(item['clause'])}</div><div class='subtle-copy'>{html.escape(item['explanation'])}</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='panel-card'><div class='section-title'>Analysis Note</div><div class='subtle-copy'>{html.escape(summary['analysis_note'])}</div></div>", unsafe_allow_html=True)


def render_history():
    st.markdown("<div class='panel-card'><div class='section-title'>History</div></div>", unsafe_allow_html=True)
    if not history:
        st.info("No analysis history yet.")
        return
    st.dataframe(pd.DataFrame(history), use_container_width=True)


def render_settings_about():
    st.markdown("<div class='panel-card'><div class='section-title'>Settings / About</div></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            """
            <div class='result-card'>
                <div class='result-term'>Project Info</div>
                <div class='subtle-copy'>Legal Contract Risk Analyzer with a refined interface, sidebar navigation, explainable legal-NLP analysis, reporting, and presentation-ready dashboards.</div>
            </div>
            <div class='result-card'>
                <div class='result-term'>Model Details</div>
                <div class='subtle-copy'>The current system uses heuristic NLP, regex extraction, rule-based scoring, and Streamlit analytics visualizations. Advanced outputs are presented as rule-based legal screening rather than generative legal advice.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='panel-card'><div class='section-title'>Report a Problem</div></div>", unsafe_allow_html=True)
        with st.form("problem_report_form", clear_on_submit=True):
            issue_type = st.selectbox(
                "Issue Type",
                ["UI issue", "Analysis problem", "Report download issue", "Performance issue", "Other"],
                key="issue_type",
            )
            issue_details = st.text_area(
                "Describe the problem",
                height=140,
                key="issue_details",
                placeholder="Describe what went wrong, where you saw it, and what you expected instead...",
            )
            submitted = st.form_submit_button("Submit Problem Report", use_container_width=True)
        if submitted:
            if not issue_details.strip():
                st.warning("Please describe the problem before submitting.")
            else:
                st.session_state["reported_issues"].insert(
                    0,
                    {
                        "type": issue_type,
                        "details": issue_details.strip(),
                    },
                )
                st.success("Problem report saved in this session.")
    with right:
        st.markdown(
            """
            <div class='result-card'>
                <div class='result-term'>Developer</div>
                <div class='subtle-copy'>Developed by Hujjathullah</div>
            </div>
            <div class='result-card'>
                <div class='result-term'>Theme</div>
                <div class='subtle-copy'>Light and dark interface modes are available from the sidebar.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state["reported_issues"]:
            st.markdown("<div class='panel-card'><div class='section-title'>Recent Problem Reports</div></div>", unsafe_allow_html=True)
            for issue in st.session_state["reported_issues"][:3]:
                st.markdown(
                    f"<div class='result-card'><div class='result-term'>{html.escape(issue['type'])}</div><div class='subtle-copy'>{html.escape(issue['details'])}</div></div>",
                    unsafe_allow_html=True,
                )


if current_page == "🏠 Home":
    render_home()
elif current_page == "📊 Dashboard":
    render_dashboard()
elif current_page == "📝 Analyze Contract":
    render_analyze_contract()
elif current_page == "⚖️ Compare Contracts":
    render_compare_contracts()
elif current_page == "📈 Risk Report":
    render_risk_report()
elif current_page == "🕘 History":
    render_history()
else:
    render_settings_about()
