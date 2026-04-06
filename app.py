import html
import io
import re
from collections import Counter
from difflib import SequenceMatcher

import altair as alt
import pandas as pd
import streamlit as st
from PyPDF2 import PdfReader
from docx import Document
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

st.set_page_config(
    page_title="Legal Contract Risk Analyzer",
    page_icon="⚖️",
    layout="wide",
)

RISK_LIBRARY = {
    "High Risk": {
        "weight": 24,
        "keywords": {
            "penalty": "Penalty language may impose immediate financial exposure.",
            "breach": "Breach terminology can trigger enforcement or damages.",
            "liability": "Liability wording may expand legal or financial responsibility.",
            "terminate immediately": "Immediate termination can create abrupt operational risk.",
            "unlimited liability": "Unlimited liability can expose a party to uncapped losses.",
            "damages": "Damages clauses can increase financial exposure after disputes.",
            "default": "Default wording can accelerate remedies against a party.",
            "exclusive jurisdiction": "Exclusive jurisdiction can reduce negotiation flexibility in disputes.",
        },
    },
    "Medium Risk": {
        "weight": 14,
        "keywords": {
            "delay": "Delay obligations can create service-level or delivery exposure.",
            "obligation": "Obligation wording may create enforceable performance duties.",
            "indemnify": "Indemnity language can shift third-party risk.",
            "notice period": "Notice periods affect termination flexibility and operational timing.",
            "warranty": "Warranty promises may create repair, refund, or compliance exposure.",
            "compliance": "Compliance obligations may require additional controls or audits.",
        },
    },
    "Low Risk": {
        "weight": 6,
        "keywords": {
            "may": "Optional wording may introduce ambiguity in responsibilities.",
            "should": "Soft language can weaken enforceability or expectations.",
            "optional": "Optional terms may reduce clarity around commitments.",
            "reasonable efforts": "Reasonable efforts language can be subjective in disputes.",
        },
    },
}

CLAUSE_LIBRARY = {
    "Payment Clause": [
        "pay",
        "payment",
        "invoice",
        "fee",
        "fees",
        "amount",
        "consideration",
    ],
    "Termination Clause": [
        "terminate",
        "termination",
        "notice period",
        "expire",
        "expiration",
    ],
    "Liability Clause": [
        "liability",
        "damages",
        "indemnify",
        "indemnity",
        "hold harmless",
    ],
    "Confidentiality Clause": [
        "confidential",
        "non-disclosure",
        "nda",
        "proprietary information",
        "trade secret",
    ],
    "Dispute Resolution Clause": [
        "arbitration",
        "dispute",
        "jurisdiction",
        "governing law",
        "court",
    ],
}

MISSING_CLAUSE_TARGETS = [
    "Termination Clause",
    "Dispute Resolution Clause",
]


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def split_sentences(text):
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]


def detect_clause_types(text):
    lowered = text.lower()
    detected = []
    for clause_name, patterns in CLAUSE_LIBRARY.items():
        matches = [pattern for pattern in patterns if pattern in lowered]
        if matches:
            detected.append(
                {
                    "clause": clause_name,
                    "matches": matches,
                    "explanation": f"Detected through terms like {', '.join(matches[:3])}.",
                }
            )
    return detected


def extract_entities(text):
    parties = set()
    dates = set()
    money = set()

    party_patterns = [
        r"\b(?:Client|Company|Vendor|Supplier|Consultant|Employee|Contractor|Buyer|Seller|Lessor|Lessee)\b",
        r"\b[A-Z][A-Za-z&., ]+(?:Ltd|Limited|LLP|LLC|Inc|Corp|Corporation|Private Limited|Pvt\. Ltd\.)\b",
    ]
    date_patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\b",
        r"\b(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+\d{1,2},?\s+\d{4}\b",
    ]
    money_patterns = [
        r"(?:₹|Rs\.?\s?|INR\s?)\d[\d,]*(?:\.\d+)?",
        r"(?:\$|USD\s?)\d[\d,]*(?:\.\d+)?",
        r"(?:€|EUR\s?)\d[\d,]*(?:\.\d+)?",
    ]

    for pattern in party_patterns:
        parties.update(re.findall(pattern, text))
    for pattern in date_patterns:
        dates.update(re.findall(pattern, text, flags=re.IGNORECASE))
    for pattern in money_patterns:
        money.update(re.findall(pattern, text, flags=re.IGNORECASE))

    return {
        "Parties": sorted({item.strip() for item in parties if item.strip()}),
        "Dates": sorted({item.strip() for item in dates if item.strip()}),
        "Money Values": sorted({item.strip() for item in money if item.strip()}),
    }


def analyze_text(text):
    findings = []
    matched_terms = []

    for level, config in RISK_LIBRARY.items():
        for term, explanation in config["keywords"].items():
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                matched_terms.append(term)
                findings.append(
                    {
                        "term": term,
                        "level": level,
                        "weight": config["weight"],
                        "explanation": explanation,
                    }
                )

    return findings


def analyze_sentences(text):
    sentence_findings = []
    for sentence in split_sentences(text):
        matches = []
        sentence_score = 0
        for level, config in RISK_LIBRARY.items():
            for term, explanation in config["keywords"].items():
                if re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE):
                    matches.append({"term": term, "level": level, "reason": explanation})
                    sentence_score += config["weight"]

        if matches:
            primary_level = sorted(matches, key=lambda item: level_priority(item["level"]))[0]["level"]
            sentence_findings.append(
                {
                    "sentence": sentence,
                    "matches": matches,
                    "score": min(sentence_score, 100),
                    "level": primary_level,
                    "reason": " ".join(match["reason"] for match in matches[:2]),
                }
            )
    return sentence_findings


def level_priority(level):
    order = {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2}
    return order[level]


def build_summary(findings, text, sentence_findings):
    counts = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    weights = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}

    for finding in findings:
        counts[finding["level"]] += 1
        weights[finding["level"]] += finding["weight"]

    raw_score = weights["High Risk"] + weights["Medium Risk"] + weights["Low Risk"]
    sentence_bonus = min(len(sentence_findings) * 4, 12)
    overall_score = min(raw_score + sentence_bonus, 100)

    if overall_score >= 80:
        overall_risk = "High Risk"
        overall_class = "high"
    elif overall_score >= 50:
        overall_risk = "Medium Risk"
        overall_class = "medium"
    elif overall_score > 0:
        overall_risk = "Low Risk"
        overall_class = "low"
    else:
        overall_risk = "No Immediate Risk"
        overall_class = "neutral"

    clauses = detect_clause_types(text)
    missing_clauses = [clause for clause in MISSING_CLAUSE_TARGETS if clause not in {item["clause"] for item in clauses}]
    entity_map = extract_entities(text)
    top_terms = Counter(finding["term"] for finding in findings).most_common(5)

    return {
        "counts": counts,
        "weights": weights,
        "overall_risk": overall_risk,
        "overall_class": overall_class,
        "overall_score": overall_score,
        "total_matches": sum(counts.values()),
        "total_sentences": len(split_sentences(text)),
        "risky_sentences": len(sentence_findings),
        "clauses": clauses,
        "missing_clauses": missing_clauses,
        "entities": entity_map,
        "top_terms": top_terms,
    }


def highlight_risk_terms(text):
    highlighted = html.escape(text)
    replacements = []
    for level, config in RISK_LIBRARY.items():
        level_class = level.lower().split()[0]
        for term in sorted(config["keywords"].keys(), key=len, reverse=True):
            replacements.append((term, level, level_class))

    for term, level, level_class in replacements:
        pattern = re.compile(rf"\b({re.escape(term)})\b", re.IGNORECASE)
        highlighted = pattern.sub(
            lambda match: (
                f"<span class='highlight {level_class}' title='{html.escape(level)}'>"
                f"{html.escape(match.group(0))}</span>"
            ),
            highlighted,
        )
    return highlighted.replace("\n", "<br>")


def explain_contract(summary, findings):
    if not findings:
        return "No tracked risk indicators were found in the submitted contract text."

    highest = summary["overall_risk"]
    reasons = [finding["explanation"] for finding in sorted(findings, key=lambda item: level_priority(item["level"]))[:3]]
    return f"This contract is marked as {highest} because it contains language that may increase legal or financial exposure. " + " ".join(reasons)


def read_uploaded_file(uploaded_file):
    file_name = uploaded_file.name.lower()
    if file_name.endswith(".txt"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")
    if file_name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if file_name.endswith(".docx"):
        document = Document(io.BytesIO(uploaded_file.getvalue()))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    return ""


def build_report_text(text, findings, sentence_findings, summary):
    lines = [
        "Legal Contract Risk Analyzer Report",
        "",
        f"Overall Risk: {summary['overall_risk']}",
        f"Overall Risk Score: {summary['overall_score']}/100",
        f"Total Clauses / Sentences: {summary['total_sentences']}",
        f"Risky Sentences: {summary['risky_sentences']}",
        f"Total Risk Matches: {summary['total_matches']}",
        "",
        "Risk Distribution:",
        f"- High Risk: {summary['counts']['High Risk']}",
        f"- Medium Risk: {summary['counts']['Medium Risk']}",
        f"- Low Risk: {summary['counts']['Low Risk']}",
        "",
        "Detected Clauses:",
    ]
    if summary["clauses"]:
        lines.extend(f"- {item['clause']}: {item['explanation']}" for item in summary["clauses"])
    else:
        lines.append("- No known clause types detected")

    lines.append("")
    lines.append("Missing Clauses:")
    if summary["missing_clauses"]:
        lines.extend(f"- {clause}" for clause in summary["missing_clauses"])
    else:
        lines.append("- No key missing clauses detected")

    lines.append("")
    lines.append("Named Entities:")
    for label, values in summary["entities"].items():
        lines.append(f"- {label}: {', '.join(values) if values else 'None detected'}")

    lines.append("")
    lines.append("Sentence-Level Risk Analysis:")
    if sentence_findings:
        for item in sentence_findings:
            lines.append(f"- [{item['level']}] {item['sentence']}")
            lines.append(f"  Reason: {item['reason']}")
    else:
        lines.append("- No risky sentences detected")

    lines.append("")
    lines.append("Matched Risk Terms:")
    if findings:
        for finding in findings:
            lines.append(f"- {finding['term']} ({finding['level']}): {finding['explanation']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Contract Explanation:")
    lines.append(explain_contract(summary, findings))
    lines.append("")
    lines.append("Original Contract Text:")
    lines.append(text or "No text submitted")
    return "\n".join(lines)


def build_pdf_report(report_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.6 * inch, leftMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        textColor=HexColor("#1f2937"),
        fontSize=18,
        leading=22,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=HexColor("#334155"),
    )

    story = []
    lines = report_text.split("\n")
    if lines:
        story.append(Paragraph(html.escape(lines[0]), title_style))
        story.append(Spacer(1, 0.15 * inch))
    for line in lines[1:]:
        safe_line = html.escape(line) if line.strip() else "&nbsp;"
        story.append(Paragraph(safe_line, body_style))
        story.append(Spacer(1, 0.06 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def compare_contracts(base_text, compare_text):
    base_findings = analyze_text(base_text)
    compare_findings = analyze_text(compare_text)
    base_terms = {item["term"] for item in base_findings}
    compare_terms = {item["term"] for item in compare_findings}

    return {
        "similarity": round(SequenceMatcher(None, normalize_text(base_text).lower(), normalize_text(compare_text).lower()).ratio() * 100, 2),
        "base_score": build_summary(base_findings, base_text, analyze_sentences(base_text))["overall_score"],
        "compare_score": build_summary(compare_findings, compare_text, analyze_sentences(compare_text))["overall_score"],
        "added_risks": sorted(compare_terms - base_terms),
        "removed_risks": sorted(base_terms - compare_terms),
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
        .empty-card,
        .sentence-card,
        .entity-card {
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.80);
            border: 1px solid rgba(255, 255, 255, 0.72);
            box-shadow: 0 20px 60px rgba(150, 107, 59, 0.14);
            backdrop-filter: blur(14px);
        }

        .hero-card {
            padding: 2rem 2.2rem;
            margin-bottom: 1rem;
        }

        .panel-card,
        .metric-card,
        .result-card,
        .empty-card,
        .sentence-card,
        .entity-card {
            padding: 1.2rem 1.3rem;
            margin-bottom: 0.9rem;
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
        .body-copy,
        .subtle-copy {
            color: #5b6472;
            line-height: 1.7;
            font-size: 1rem;
        }

        .section-title {
            margin: 0;
            color: #1f2937;
            font-size: 1.25rem;
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
            padding: 0.55rem 0.9rem;
            border-radius: 999px;
            font-size: 0.84rem;
            font-weight: 700;
        }

        .pill.high,
        .chip.high,
        .highlight.high {
            color: #d9485f;
            background: rgba(217, 72, 95, 0.14);
        }

        .pill.medium,
        .chip.medium,
        .highlight.medium {
            color: #f08c2b;
            background: rgba(240, 140, 43, 0.16);
        }

        .pill.low,
        .chip.low,
        .highlight.low {
            color: #2f9e44;
            background: rgba(47, 158, 68, 0.15);
        }

        .chip {
            display: inline-block;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
        }

        .status-banner {
            border-radius: 22px;
            padding: 1.35rem;
            color: white;
            margin-bottom: 1rem;
        }

        .status-banner.high { background: linear-gradient(135deg, #b4233d, #d9485f, #ef476f); }
        .status-banner.medium { background: linear-gradient(135deg, #c76a09, #f08c2b, #f7b267); }
        .status-banner.low { background: linear-gradient(135deg, #1f7a39, #2f9e44, #57cc99); }
        .status-banner.neutral { background: linear-gradient(135deg, #285fcb, #3b82f6, #60a5fa); }

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

        .result-row,
        .sentence-row {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }

        .result-term,
        .entity-title {
            font-weight: 800;
            color: #1f2937;
        }

        .highlight-panel {
            padding: 1rem 1.2rem;
            border-radius: 20px;
            border: 1px solid rgba(115, 122, 140, 0.12);
            background: rgba(255, 255, 255, 0.9);
            line-height: 1.8;
            color: #1f2937;
        }

        .highlight {
            padding: 0.1rem 0.3rem;
            border-radius: 0.35rem;
            font-weight: 700;
        }

        .missing {
            color: #b4233d;
            font-weight: 700;
        }

        .ok {
            color: #1f7a39;
            font-weight: 700;
        }

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
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
        <div class="eyebrow">AI Legal Intelligence Demo</div>
        <div class="hero-title">Analyze contracts with smarter scoring, clause checks, and explainable risk insights.</div>
        <div class="hero-copy">
            Upload or paste a contract to detect risky language, score legal exposure from 0 to 100,
            classify clause types, extract entities, compare versions, and export a polished report.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

main_tab, compare_tab = st.tabs(["Contract Analyzer", "Compare Contracts"])

with main_tab:
    left_col, right_col = st.columns([1.2, 0.95], gap="large")

    with left_col:
        st.markdown(
            """
            <div class="panel-card">
                <div class="section-title">Input Contract</div>
                <div class="body-copy">
                    Use pasted text or upload a PDF, DOCX, or TXT file. The analyzer will score risk, inspect sentences,
                    extract key legal entities, classify clauses, and explain why risky language was detected.
                </div>
                <div class="helper-row">
                    <span class="pill high">High: liability, breach, terminate immediately</span>
                    <span class="pill medium">Medium: indemnify, warranty, compliance</span>
                    <span class="pill low">Low: may, should, optional</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader("Upload contract", type=["pdf", "docx", "txt"])
        if uploaded_file is not None:
            extracted_text = read_uploaded_file(uploaded_file)
            if extracted_text.strip():
                st.session_state["contract_text"] = extracted_text
                st.success(f"Loaded text from {uploaded_file.name}")
            else:
                st.warning("The uploaded file did not contain readable text.")

        contract_text = st.text_area(
            "Paste contract text",
            value=st.session_state.get("contract_text", ""),
            placeholder="Paste contract text here. Example: Client shall pay ₹50,000 before 10th Jan. Either party may terminate immediately upon breach, and liability for damages shall survive termination.",
            height=320,
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

    text_to_analyze = st.session_state.get("contract_text", "").strip()
    findings = analyze_text(text_to_analyze) if text_to_analyze else []
    sentence_findings = analyze_sentences(text_to_analyze) if text_to_analyze else []
    summary = build_summary(findings, text_to_analyze, sentence_findings)
    report_text = build_report_text(text_to_analyze, findings, sentence_findings, summary)
    pdf_report = build_pdf_report(report_text) if text_to_analyze else b""

    with right_col:
        st.markdown(
            f"""
            <div class="panel-card">
                <div class="status-banner {summary['overall_class']}">
                    <div class="status-label">Overall Risk Assessment</div>
                    <div class="status-title">{summary['overall_risk']}</div>
                    <p class="status-copy">
                        Risk score: <strong>{summary['overall_score']}/100</strong><br>
                        {summary['total_matches']} matched indicators across {summary['risky_sentences']} risky sentence(s).
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        metric_col1, metric_col2 = st.columns(2, gap="small")
        with metric_col1:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>High Risk Terms</div><div class='metric-value high'>{summary['counts']['High Risk']}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-card'><div class='metric-label'>Clause Count</div><div class='metric-value neutral'>{len(summary['clauses'])}</div></div>", unsafe_allow_html=True)
        with metric_col2:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>Medium + Low Terms</div><div class='metric-value medium'>{summary['counts']['Medium Risk'] + summary['counts']['Low Risk']}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Sentences</div><div class='metric-value neutral'>{summary['total_sentences']}</div></div>", unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="panel-card">
                <div class="section-title">Explainable Summary</div>
                <div class="subtle-copy">{html.escape(explain_contract(summary, findings))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        download_col1, download_col2 = st.columns(2, gap="small")
        with download_col1:
            st.download_button(
                "Download TXT Report",
                data=report_text.encode("utf-8"),
                file_name="contract_risk_report.txt",
                mime="text/plain",
                use_container_width=True,
                disabled=not text_to_analyze,
            )
        with download_col2:
            st.download_button(
                "Download PDF Report",
                data=pdf_report,
                file_name="contract_risk_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=not text_to_analyze,
            )

    if analyze_clicked and not text_to_analyze:
        st.warning("Paste some contract text or upload a file first.")

    dashboard_tab, sentence_tab, entity_tab, clause_tab = st.tabs(
        ["Dashboard", "Sentence Analysis", "Entities & Highlighting", "Clause Intelligence"]
    )

    with dashboard_tab:
        chart_col, side_col = st.columns([1.1, 0.9], gap="large")
        with chart_col:
            risk_df = pd.DataFrame(
                [
                    {"Risk Level": "High Risk", "Count": summary["counts"]["High Risk"]},
                    {"Risk Level": "Medium Risk", "Count": summary["counts"]["Medium Risk"]},
                    {"Risk Level": "Low Risk", "Count": summary["counts"]["Low Risk"]},
                ]
            )
            pie_chart = (
                alt.Chart(risk_df)
                .mark_arc(innerRadius=55)
                .encode(
                    theta="Count:Q",
                    color=alt.Color(
                        "Risk Level:N",
                        scale=alt.Scale(
                            domain=["High Risk", "Medium Risk", "Low Risk"],
                            range=["#d9485f", "#f08c2b", "#2f9e44"],
                        ),
                    ),
                    tooltip=["Risk Level", "Count"],
                )
                .properties(height=320)
            )
            st.markdown("<div class='panel-card'><div class='section-title'>Risk Distribution</div></div>", unsafe_allow_html=True)
            st.altair_chart(pie_chart, use_container_width=True)

            bar_df = pd.DataFrame(
                [
                    {"Metric": "Overall Score", "Value": summary["overall_score"]},
                    {"Metric": "Risky Sentences", "Value": summary["risky_sentences"]},
                    {"Metric": "Clauses Found", "Value": len(summary["clauses"])},
                    {"Metric": "Entities Found", "Value": sum(len(values) for values in summary["entities"].values())},
                ]
            )
            bar_chart = (
                alt.Chart(bar_df)
                .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
                .encode(
                    x=alt.X("Metric:N", sort=None),
                    y="Value:Q",
                    color=alt.value("#3b82f6"),
                    tooltip=["Metric", "Value"],
                )
                .properties(height=300)
            )
            st.markdown("<div class='panel-card'><div class='section-title'>Analysis Metrics</div></div>", unsafe_allow_html=True)
            st.altair_chart(bar_chart, use_container_width=True)

        with side_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Top Risky Terms</div></div>", unsafe_allow_html=True)
            if summary["top_terms"]:
                for term, count in summary["top_terms"]:
                    st.markdown(
                        f"<div class='result-card'><div class='result-row'><div class='result-term'>{html.escape(term)}</div><div class='chip medium'>{count} hit(s)</div></div></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("<div class='empty-card'><div class='subtle-copy'>No risky terms detected yet.</div></div>", unsafe_allow_html=True)

            st.markdown("<div class='panel-card'><div class='section-title'>Quick Flags</div></div>", unsafe_allow_html=True)
            if summary["missing_clauses"]:
                for clause in summary["missing_clauses"]:
                    st.markdown(
                        f"<div class='result-card'><span class='missing'>Missing:</span> {html.escape(clause)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("<div class='result-card'><span class='ok'>All tracked critical clauses were detected.</span></div>", unsafe_allow_html=True)

    with sentence_tab:
        st.markdown("<div class='panel-card'><div class='section-title'>Sentence-Level Risk Analysis</div><div class='subtle-copy'>Each risky sentence includes its severity, score, and explanation.</div></div>", unsafe_allow_html=True)
        if sentence_findings:
            for item in sentence_findings:
                level_class = item["level"].lower().split()[0]
                terms = ", ".join(match["term"] for match in item["matches"])
                st.markdown(
                    f"""
                    <div class="sentence-card">
                        <div class="sentence-row">
                            <div>
                                <div class="result-term">{html.escape(item['sentence'])}</div>
                                <div class="subtle-copy">Why risky: {html.escape(item['reason'])}</div>
                                <div class="subtle-copy">Matched terms: {html.escape(terms)}</div>
                            </div>
                            <div class="chip {level_class}">{item['level']} · {item['score']}/100</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div class='empty-card'><div class='subtle-copy'>No risky sentences detected yet.</div></div>", unsafe_allow_html=True)

    with entity_tab:
        entity_col, highlight_col = st.columns([0.9, 1.1], gap="large")
        with entity_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Named Entities</div><div class='subtle-copy'>Regex-based extraction for parties, dates, and money values.</div></div>", unsafe_allow_html=True)
            for label, values in summary["entities"].items():
                st.markdown(f"<div class='entity-card'><div class='entity-title'>{html.escape(label)}</div></div>", unsafe_allow_html=True)
                if values:
                    for value in values:
                        st.markdown(f"<div class='result-card'>{html.escape(value)}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='empty-card'><div class='subtle-copy'>None detected</div></div>", unsafe_allow_html=True)
        with highlight_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Highlighted Contract Text</div><div class='subtle-copy'>Risky words are color-coded directly in the contract.</div></div>", unsafe_allow_html=True)
            if text_to_analyze:
                st.markdown(f"<div class='highlight-panel'>{highlight_risk_terms(text_to_analyze)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='empty-card'><div class='subtle-copy'>Add text to see highlighted risk terms.</div></div>", unsafe_allow_html=True)

    with clause_tab:
        clause_col, missing_col = st.columns(2, gap="large")
        with clause_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Clause Classification</div></div>", unsafe_allow_html=True)
            if summary["clauses"]:
                for clause in summary["clauses"]:
                    st.markdown(
                        f"<div class='result-card'><div class='result-term'>{html.escape(clause['clause'])}</div><div class='subtle-copy'>{html.escape(clause['explanation'])}</div></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("<div class='empty-card'><div class='subtle-copy'>No known clause types detected.</div></div>", unsafe_allow_html=True)
        with missing_col:
            st.markdown("<div class='panel-card'><div class='section-title'>Missing Clause Detection</div></div>", unsafe_allow_html=True)
            if summary["missing_clauses"]:
                for clause in summary["missing_clauses"]:
                    st.markdown(f"<div class='result-card'><span class='missing'>{html.escape(clause)}</span> was not detected in the submitted contract.</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='result-card'><span class='ok'>Termination and dispute resolution clauses were both detected.</span></div>", unsafe_allow_html=True)

with compare_tab:
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">Contract Comparison Tool</div>
            <div class="body-copy">
                Compare a base contract against a revised version to spot similarity, score change, and newly introduced risky terms.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    base_col, revised_col = st.columns(2, gap="large")
    with base_col:
        base_text = st.text_area("Base contract", height=240, key="base_contract")
    with revised_col:
        revised_text = st.text_area("Revised contract", height=240, key="revised_contract")

    if base_text.strip() and revised_text.strip():
        comparison = compare_contracts(base_text, revised_text)
        comp_col1, comp_col2, comp_col3 = st.columns(3, gap="small")
        with comp_col1:
            st.metric("Similarity", f"{comparison['similarity']}%")
        with comp_col2:
            st.metric("Base Score", f"{comparison['base_score']}/100")
        with comp_col3:
            st.metric("Revised Score", f"{comparison['compare_score']}/100", delta=comparison["compare_score"] - comparison["base_score"])

        compare_left, compare_right = st.columns(2, gap="large")
        with compare_left:
            st.markdown("<div class='panel-card'><div class='section-title'>Added Risks in Revised Contract</div></div>", unsafe_allow_html=True)
            if comparison["added_risks"]:
                for term in comparison["added_risks"]:
                    st.markdown(f"<div class='result-card'><span class='missing'>New Risk:</span> {html.escape(term)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='empty-card'><div class='subtle-copy'>No new risky terms detected.</div></div>", unsafe_allow_html=True)
        with compare_right:
            st.markdown("<div class='panel-card'><div class='section-title'>Removed Risks from Revised Contract</div></div>", unsafe_allow_html=True)
            if comparison["removed_risks"]:
                for term in comparison["removed_risks"]:
                    st.markdown(f"<div class='result-card'><span class='ok'>Removed:</span> {html.escape(term)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='empty-card'><div class='subtle-copy'>No risky terms were removed.</div></div>", unsafe_allow_html=True)
    else:
        st.info("Add both a base contract and a revised contract to compare them.")
