import re

import streamlit as st

st.set_page_config(
    page_title="Legal Contract Risk Analyzer",
    page_icon="⚖️",
    layout="wide",
)

RISK_KEYWORDS = {
    "High Risk": ["penalty", "breach", "liability", "terminate immediately"],
    "Medium Risk": ["delay", "obligation", "indemnify"],
    "Low Risk": ["may", "should", "optional"],
}


def analyze_text(text):
    results = []
    for level, keywords in RISK_KEYWORDS.items():
        for word in keywords:
            if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
                results.append((word, level))
    return results


def build_summary(analysis):
    counts = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    for _, level in analysis:
        counts[level] += 1

    if counts["High Risk"]:
        overall_risk = "High Risk"
        overall_class = "high"
    elif counts["Medium Risk"]:
        overall_risk = "Medium Risk"
        overall_class = "medium"
    elif counts["Low Risk"]:
        overall_risk = "Low Risk"
        overall_class = "low"
    else:
        overall_risk = "No Immediate Risk"
        overall_class = "neutral"

    total_matches = sum(counts.values())
    return {
        "counts": counts,
        "overall_risk": overall_risk,
        "overall_class": overall_class,
        "total_matches": total_matches,
    }


st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Manrope', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 160, 122, 0.30), transparent 28%),
                radial-gradient(circle at top right, rgba(80, 200, 180, 0.22), transparent 24%),
                linear-gradient(135deg, #f4efe5 0%, #fff8ef 48%, #fde7d7 100%);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .hero-card,
        .panel-card,
        .metric-card,
        .result-card,
        .empty-card {
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(255, 255, 255, 0.7);
            box-shadow: 0 20px 60px rgba(150, 107, 59, 0.14);
            backdrop-filter: blur(14px);
        }

        .hero-card {
            padding: 2rem 2.2rem;
            margin-bottom: 1rem;
        }

        .eyebrow {
            display: inline-block;
            padding: 0.55rem 0.95rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.9);
            color: #9a5f11;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .hero-title {
            margin: 1rem 0 0.65rem;
            font-size: clamp(2rem, 3vw, 4rem);
            font-weight: 800;
            line-height: 1;
            color: #1f2937;
        }

        .hero-copy,
        .body-copy {
            color: #5b6472;
            line-height: 1.7;
            font-size: 1rem;
        }

        .panel-card {
            padding: 1.5rem;
            height: 100%;
        }

        .section-title {
            margin: 0;
            color: #1f2937;
            font-size: 1.35rem;
            font-weight: 800;
        }

        .helper-row {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin: 1rem 0 1.1rem;
        }

        .pill {
            display: inline-block;
            padding: 0.6rem 0.9rem;
            border-radius: 999px;
            font-size: 0.84rem;
            font-weight: 700;
        }

        .pill.high {
            color: #d9485f;
            background: rgba(217, 72, 95, 0.12);
        }

        .pill.medium {
            color: #f08c2b;
            background: rgba(240, 140, 43, 0.14);
        }

        .pill.low {
            color: #2f9e44;
            background: rgba(47, 158, 68, 0.14);
        }

        .status-banner {
            border-radius: 22px;
            padding: 1.35rem;
            color: white;
            margin-bottom: 1rem;
        }

        .status-banner.high {
            background: linear-gradient(135deg, #b4233d, #d9485f, #ef476f);
        }

        .status-banner.medium {
            background: linear-gradient(135deg, #c76a09, #f08c2b, #f7b267);
        }

        .status-banner.low {
            background: linear-gradient(135deg, #1f7a39, #2f9e44, #57cc99);
        }

        .status-banner.neutral {
            background: linear-gradient(135deg, #285fcb, #3b82f6, #60a5fa);
        }

        .status-label {
            font-size: 0.8rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0.95;
        }

        .status-title {
            margin: 0.5rem 0 0.35rem;
            font-size: 1.8rem;
            font-weight: 800;
        }

        .status-copy {
            margin: 0;
            line-height: 1.6;
        }

        .metric-card {
            padding: 1rem 1.1rem;
            margin-bottom: 0.9rem;
        }

        .metric-label {
            color: #5b6472;
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            font-size: 1.9rem;
            font-weight: 800;
            line-height: 1;
        }

        .metric-value.high { color: #d9485f; }
        .metric-value.medium { color: #f08c2b; }
        .metric-value.low { color: #2f9e44; }
        .metric-value.neutral { color: #3b82f6; }

        .result-card,
        .empty-card {
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
        }

        .result-card.high {
            background: rgba(217, 72, 95, 0.12);
        }

        .result-card.medium {
            background: rgba(240, 140, 43, 0.14);
        }

        .result-card.low {
            background: rgba(47, 158, 68, 0.14);
        }

        .result-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .result-term {
            font-weight: 800;
            color: #1f2937;
            text-transform: capitalize;
        }

        .risk-chip {
            display: inline-block;
            padding: 0.45rem 0.75rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.85);
            font-size: 0.8rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .risk-chip.high { color: #d9485f; }
        .risk-chip.medium { color: #f08c2b; }
        .risk-chip.low { color: #2f9e44; }

        div[data-testid="stTextArea"] textarea {
            border-radius: 20px;
            border: 1px solid rgba(115, 122, 140, 0.16);
            background: rgba(255, 255, 255, 0.92);
            color: #1f2937;
            line-height: 1.65;
        }

        div[data-testid="stButton"] button {
            border-radius: 16px;
            font-weight: 800;
            border: 0;
            padding: 0.75rem 1.2rem;
        }

        .footer-note {
            color: #5b6472;
            font-size: 0.92rem;
            margin-top: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
        <div class="eyebrow">Contract Intelligence Workspace</div>
        <div class="hero-title">Spot risky legal language faster, with clearer signals.</div>
        <div class="hero-copy">
            Paste a clause, agreement, or full contract below to surface risky terms, get an instant severity snapshot,
            and review results in a clean Streamlit dashboard.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1.25, 0.9], gap="large")

with left_col:
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">Analyze contract text</div>
            <div class="body-copy">
                This analyzer scans for high, medium, and low risk indicators so you can quickly focus on clauses that may need closer review.
            </div>
            <div class="helper-row">
                <span class="pill high">High: penalty, breach, liability</span>
                <span class="pill medium">Medium: delay, obligation, indemnify</span>
                <span class="pill low">Low: may, should, optional</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_text = st.session_state.get(
        "contract_text",
        "",
    )
    contract_text = st.text_area(
        "Paste contract text",
        value=default_text,
        placeholder="Paste contract text here... For example: If either party commits a breach, the agreement may terminate immediately and liability may apply.",
        height=340,
        label_visibility="collapsed",
    )
    st.session_state["contract_text"] = contract_text

    action_col, clear_col = st.columns([1, 1], gap="small")
    with action_col:
        analyze_clicked = st.button("Analyze Contract", use_container_width=True, type="primary")
    with clear_col:
        clear_clicked = st.button("Clear", use_container_width=True)

    if clear_clicked:
        st.session_state["contract_text"] = ""
        st.rerun()

    st.markdown(
        '<div class="footer-note">Better readability, faster scanning, and a friendlier workflow for quick legal triage.</div>',
        unsafe_allow_html=True,
    )

analysis = []
if st.session_state.get("contract_text"):
    analysis = analyze_text(st.session_state["contract_text"])
summary = build_summary(analysis)

with right_col:
    st.markdown(
        f"""
        <div class="panel-card">
            <div class="status-banner {summary['overall_class']}">
                <div class="status-label">Overall Assessment</div>
                <div class="status-title">{summary['overall_risk']}</div>
                <p class="status-copy">
                    {"No tracked risk keywords were found in the current submission." if summary['total_matches'] == 0 else f"{summary['total_matches']} risk indicator{'s' if summary['total_matches'] != 1 else ''} found in the submitted text."}
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_col1, metric_col2 = st.columns(2, gap="small")
    with metric_col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">High Risk</div>
                <div class="metric-value high">{summary['counts']['High Risk']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Low Risk</div>
                <div class="metric-value low">{summary['counts']['Low Risk']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with metric_col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Medium Risk</div>
                <div class="metric-value medium">{summary['counts']['Medium Risk']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Total Matches</div>
                <div class="metric-value neutral">{summary['total_matches']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">Detected Terms</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if analysis:
        for word, level in analysis:
            level_class = level.lower().split()[0]
            st.markdown(
                f"""
                <div class="result-card {level_class}">
                    <div class="result-row">
                        <div class="result-term">{word}</div>
                        <div class="risk-chip {level_class}">{level}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div class="empty-card">
                <div class="section-title">Ready for analysis</div>
                <div class="body-copy">
                    Submit contract text to see a colorful risk overview, keyword matches, and a quick severity breakdown.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

if analyze_clicked and not st.session_state.get("contract_text", "").strip():
    st.warning("Paste some contract text first so the analyzer has something to review.")
