import html

import altair as alt
import pandas as pd
import streamlit as st
from analyzer_core import (
    ROLE_DESCRIPTIONS,
    highlight_risk_terms,
    read_uploaded_file,
    role_based_summary,
    run_full_analysis,
)

st.set_page_config(page_title="Legal Contract Risk Analyzer", page_icon="⚖️", layout="wide")


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
    st.session_state["latest_result"] = result


st.session_state.setdefault("analysis_history", [])
st.session_state.setdefault("latest_result", None)
st.session_state.setdefault("contract_text", "")
st.session_state.setdefault("uploaded_contract_text", "")
st.session_state.setdefault("uploaded_contract_name", "Uploaded Contract")
st.session_state.setdefault("current_page", "🏠 Home")
st.session_state.setdefault("theme_mode", "Dark")

theme_mode = st.session_state.get("theme_mode", "Dark")
if theme_mode == "Light":
    theme = {
        "text": "#0f172a",
        "bg": "radial-gradient(circle at top left, rgba(14, 165, 233, 0.10), transparent 24%), radial-gradient(circle at top right, rgba(16, 185, 129, 0.10), transparent 24%), linear-gradient(135deg, #f7fbff 0%, #edf6ff 46%, #eefaf6 100%)",
        "sidebar_bg": "linear-gradient(180deg, #eef6fb 0%, #e2eef7 100%)",
        "sidebar_border": "rgba(148, 163, 184, 0.18)",
        "card_bg": "rgba(255, 255, 255, 0.88)",
        "card_border": "rgba(148, 163, 184, 0.18)",
        "card_shadow": "0 18px 40px rgba(148, 163, 184, 0.18)",
        "eyebrow_bg": "rgba(14, 165, 233, 0.12)",
        "eyebrow_text": "#0369a1",
        "title": "#0f172a",
        "muted": "#475569",
        "metric": "#0891b2",
        "result": "#0f172a",
        "highlight_bg": "rgba(255,255,255,0.96)",
        "highlight_border": "rgba(148,163,184,0.18)",
        "highlight_text": "#0f172a",
        "nav_caption": "#475569",
        "button_bg": "rgba(255,255,255,0.72)",
        "button_text": "#0f172a",
        "button_hover_bg": "rgba(14, 165, 233, 0.10)",
        "input_bg": "rgba(255,255,255,0.92)",
        "input_text": "#0f172a",
        "input_border": "rgba(148,163,184,0.20)",
        "file_bg": "rgba(255,255,255,0.72)",
        "primary_label": "Professional light workspace",
    }
else:
    theme = {
        "text": "#e5eef9",
        "bg": "radial-gradient(circle at top left, rgba(14, 165, 233, 0.10), transparent 24%), radial-gradient(circle at top right, rgba(16, 185, 129, 0.10), transparent 24%), linear-gradient(135deg, #071018 0%, #0b1722 46%, #101b27 100%)",
        "sidebar_bg": "linear-gradient(180deg, #08141c 0%, #0f1b27 100%)",
        "sidebar_border": "rgba(148, 163, 184, 0.10)",
        "card_bg": "rgba(15, 23, 42, 0.74)",
        "card_border": "rgba(148, 163, 184, 0.12)",
        "card_shadow": "0 18px 40px rgba(2, 6, 23, 0.24)",
        "eyebrow_bg": "rgba(14, 165, 233, 0.12)",
        "eyebrow_text": "#7dd3fc",
        "title": "#f8fafc",
        "muted": "#94a3b8",
        "metric": "#67e8f9",
        "result": "#f8fafc",
        "highlight_bg": "rgba(15,23,42,0.94)",
        "highlight_border": "rgba(148,163,184,0.12)",
        "highlight_text": "#e2e8f0",
        "nav_caption": "#94a3b8",
        "button_bg": "rgba(15, 23, 42, 0.54)",
        "button_text": "#e2e8f0",
        "button_hover_bg": "rgba(14, 165, 233, 0.14)",
        "input_bg": "rgba(15, 23, 42, 0.82)",
        "input_text": "#e2e8f0",
        "input_border": "rgba(148, 163, 184, 0.16)",
        "file_bg": "rgba(15, 23, 42, 0.54)",
        "primary_label": "Professional dark workspace",
    }

st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Manrope', sans-serif; color: {theme["text"]}; }}
        .block-container {{ padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1320px; }}
        .stApp {{ background: {theme["bg"]}; }}
        [data-testid="stSidebar"] {{ background: {theme["sidebar_bg"]}; border-right: 1px solid {theme["sidebar_border"]}; }}
        .hero-card, .panel-card, .metric-card, .result-card, .empty-card, .sentence-card {{
            border-radius: 20px;
            background: {theme["card_bg"]};
            border: 1px solid {theme["card_border"]};
            box-shadow: {theme["card_shadow"]};
            backdrop-filter: blur(12px);
            padding: 1.15rem 1.2rem;
            margin-bottom: 0.85rem;
        }}
        .hero-card {{ padding: 2.1rem 2.2rem; margin-bottom: 1.15rem; }}
        .eyebrow {{ display: inline-block; padding: 0.5rem 0.9rem; border-radius: 999px; background: {theme["eyebrow_bg"]}; color: {theme["eyebrow_text"]}; font-size: 0.74rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; }}
        .hero-title {{ margin: 0.95rem 0 0.65rem; max-width: 820px; font-size: clamp(2.1rem, 3vw, 3.4rem); font-weight: 800; line-height: 1.05; color: {theme["title"]}; }}
        .hero-copy, .body-copy, .subtle-copy {{ color: {theme["muted"]}; line-height: 1.72; font-size: 0.98rem; }}
        .section-title {{ margin: 0; color: {theme["title"]}; font-size: 1.12rem; font-weight: 800; letter-spacing: 0.01em; }}
        .metric-label {{ color: {theme["muted"]}; font-size: 0.9rem; margin-bottom: 0.5rem; }}
        .metric-value {{ font-size: 1.75rem; font-weight: 800; line-height: 1; color: {theme["metric"]}; }}
        .result-term {{ font-weight: 800; color: {theme["result"]}; }}
        .highlight-panel {{ padding: 1rem 1.1rem; border-radius: 16px; border: 1px solid {theme["highlight_border"]}; background: {theme["highlight_bg"]}; line-height: 1.78; color: {theme["highlight_text"]}; }}
        .high {{ color: #fb7185; background: rgba(251,113,133,0.14); }}
        .medium {{ color: #fbbf24; background: rgba(251,191,36,0.16); }}
        .low {{ color: #34d399; background: rgba(52,211,153,0.15); }}
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
            border-radius: 12px;
            border: 1px solid {theme["card_border"]};
            background: {theme["button_bg"]};
            color: {theme["button_text"]};
            padding: 0.72rem 0.9rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
            box-shadow: none;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{ border-color: rgba(125, 211, 252, 0.28); background: {theme["button_hover_bg"]}; color: #ffffff; }}
        .stTextArea textarea, .stTextInput input {{
            background: {theme["input_bg"]} !important;
            color: {theme["input_text"]} !important;
            border: 1px solid {theme["input_border"]} !important;
            border-radius: 14px !important;
        }}
        .stTextArea textarea:focus, .stTextInput input:focus {{ border-color: rgba(125, 211, 252, 0.4) !important; box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.22) !important; }}
        .stFileUploader {{ background: {theme["file_bg"]}; border-radius: 16px; border: 1px dashed rgba(148, 163, 184, 0.2); padding: 0.75rem 0.9rem; }}
        .stDownloadButton button, .stButton button[kind="primary"] {{ border-radius: 12px !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🧭 Navigation Menu")
    nav_items = ["🏠 Home", "📊 Dashboard", "📝 Analyze Contract", "📁 Upload File", "📈 Risk Report", "🕘 History", "⚙️ Settings / About"]
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
                <div class='section-title'>Key Features</div>
                <div class='subtle-copy'>Risk score calculation, contract upload, highlighted analysis, downloadable reports, dashboard charts, and session history.</div>
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
                <div class='section-title'>Use This App</div>
                <div class='subtle-copy'>Go to Analyze Contract to paste text, Upload File to process documents, and Risk Report to export the latest result.</div>
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
            st.markdown("<div class='empty-card'>No analyses yet. Use Analyze Contract or Upload File to begin.</div>", unsafe_allow_html=True)


def render_analyze_contract():
    st.markdown("<div class='panel-card'><div class='section-title'>Analyze Contract</div></div>", unsafe_allow_html=True)
    contract_text = st.text_area("Paste Contract Text", value=st.session_state.get("contract_text", ""), height=300, placeholder="Paste the full contract text here...")
    st.session_state["contract_text"] = contract_text
    if st.button("Analyze Contract", type="primary", use_container_width=True):
        if not contract_text.strip():
            st.warning("Paste some contract text first.")
        else:
            with st.spinner("Analyzing contract..."):
                result = run_full_analysis(contract_text, "Pasted Contract")
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
            st.markdown(f"<div class='highlight-panel'>{highlight_risk_terms(result['text'])}</div>", unsafe_allow_html=True)
        with right:
            st.markdown(f"<div class='panel-card'><div class='status-banner {summary['overall_class']}'><div class='status-label'>Overall Risk Score</div><div class='status-title'>{summary['overall_score']}/100</div><p>{summary['overall_risk']}</p></div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Risk Categories</div><div class='subtle-copy'>🔴 {summary['counts']['High Risk']} high risk · 🟠 {summary['counts']['Medium Risk']} medium risk · 🟢 {summary['counts']['Low Risk']} low risk</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Executive Explanation</div><div class='subtle-copy'>{html.escape(role_based_summary(selected_role, summary, findings))}</div></div>", unsafe_allow_html=True)


def render_upload_file():
    st.markdown("<div class='panel-card'><div class='section-title'>Upload File</div></div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf", "docx", "txt"], key="page_upload")
    if uploaded_file is not None:
        extracted_text = read_uploaded_file(uploaded_file)
        st.session_state["uploaded_contract_text"] = extracted_text
        st.session_state["uploaded_contract_name"] = uploaded_file.name
        st.markdown("<div class='card-grid-title'>Extracted Text Preview</div>", unsafe_allow_html=True)
        st.text_area("Preview", extracted_text, height=260)
        if st.button("Analyze Uploaded Contract", use_container_width=True, type="primary"):
            if extracted_text.strip():
                with st.spinner("Analyzing contract..."):
                    result = run_full_analysis(extracted_text, uploaded_file.name)
                    store_analysis(result)
                    st.success(f"Analysis saved for {uploaded_file.name}.")
            else:
                st.warning("No readable text was extracted from the file.")


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
        st.download_button("📥 Download Report (PDF)", latest_result["pdf_report"], file_name="contract_risk_report.pdf", mime="application/pdf", use_container_width=True)


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
                <div class='subtle-copy'>The current system uses heuristic NLP, regex extraction, rule-based scoring, and Streamlit analytics visualizations for fast demo-ready results.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
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


if current_page == "🏠 Home":
    render_home()
elif current_page == "📊 Dashboard":
    render_dashboard()
elif current_page == "📝 Analyze Contract":
    render_analyze_contract()
elif current_page == "📁 Upload File":
    render_upload_file()
elif current_page == "📈 Risk Report":
    render_risk_report()
elif current_page == "🕘 History":
    render_history()
else:
    render_settings_about()
