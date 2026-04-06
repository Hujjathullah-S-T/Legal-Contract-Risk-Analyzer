import html
import io
import re
from collections import Counter
from datetime import datetime
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

st.set_page_config(page_title="Legal Contract Risk Analyzer", page_icon="⚖️", layout="wide")

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
    "Payment Clause": ["pay", "payment", "invoice", "fee", "fees", "amount", "consideration"],
    "Termination Clause": ["terminate", "termination", "notice period", "expire", "expiration"],
    "Liability Clause": ["liability", "damages", "indemnify", "indemnity", "hold harmless"],
    "Confidentiality Clause": ["confidential", "non-disclosure", "nda", "proprietary information", "trade secret"],
    "Dispute Resolution Clause": ["arbitration", "dispute", "jurisdiction", "governing law", "court"],
    "Data Privacy Clause": ["personal data", "gdpr", "privacy", "consent", "data processing"],
}

MISSING_CLAUSE_TARGETS = ["Termination Clause", "Dispute Resolution Clause"]

AMBIGUOUS_TERMS = {
    "reasonable": "Reasonable is open to interpretation and may create ambiguity.",
    "as soon as possible": "This phrase has no objective deadline.",
    "best effort": "Best effort is subjective and hard to enforce consistently.",
    "best efforts": "Best efforts is subjective and hard to enforce consistently.",
    "from time to time": "This phrase can make obligations unclear over time.",
    "promptly": "Promptly may be too vague without a measurable deadline.",
}

RISK_RECOMMENDATIONS = {
    "unlimited liability": "Replace with a capped liability clause tied to contract value.",
    "liability": "Consider limiting liability to direct damages with a monetary cap.",
    "indemnify": "Clarify indemnity scope, triggers, and exclusions.",
    "terminate immediately": "Add cure periods before immediate termination applies.",
    "penalty": "Use a proportionate liquidated damages clause instead of a broad penalty.",
    "exclusive jurisdiction": "Consider neutral jurisdiction or arbitration if flexibility is needed.",
}

COMPLIANCE_RULES = [
    {
        "name": "Privacy notice gap",
        "trigger": ["personal data", "customer data", "sensitive data"],
        "required_any": ["consent", "privacy", "gdpr", "security", "confidential"],
        "message": "Personal data is referenced without a strong privacy/compliance safeguard.",
    },
    {
        "name": "Security safeguard gap",
        "trigger": ["data", "system", "access"],
        "required_any": ["encryption", "security", "access control", "confidential"],
        "message": "The contract references data or system access but does not clearly mention security controls.",
    },
]

QUESTION_TOPICS = {
    "penalty": ["penalty", "liquidated damages"],
    "liability": ["liability", "damages", "indemnify", "indemnity"],
    "termination": ["terminate", "termination", "notice period"],
    "payment": ["pay", "payment", "invoice", "fee", "amount"],
    "confidentiality": ["confidential", "non-disclosure", "trade secret"],
    "privacy": ["privacy", "personal data", "gdpr", "consent"],
}

ROLE_DESCRIPTIONS = {
    "Lawyer": "Detailed legal signals, clause intelligence, and sentence-level reasoning.",
    "Client": "Plain-language explanation with practical concerns and missing safeguards.",
    "Manager": "Fast risk summary with score, top issues, and actions.",
}


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def split_sentences(text):
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", cleaned) if item.strip()]


def level_priority(level):
    return {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2}[level]


def level_class(level):
    return level.lower().split()[0]


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
        r"\b(?:Client|Company|Vendor|Supplier|Consultant|Employee|Contractor|Buyer|Seller|Lessor|Lessee|Service Provider|Customer)\b",
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
    for level, config in RISK_LIBRARY.items():
        for term, explanation in config["keywords"].items():
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
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


def detect_ambiguity(text):
    findings = []
    for sentence in split_sentences(text):
        for term, message in AMBIGUOUS_TERMS.items():
            if re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE):
                findings.append({"term": term, "sentence": sentence, "message": message})
    return findings


def extract_obligations(text):
    obligations = []
    pattern = re.compile(
        r"\b([A-Z][A-Za-z ]{1,40}|client|vendor|company|supplier|buyer|seller|employee|contractor|consultant)\b\s+"
        r"(shall|must|will|agrees to|is required to)\s+"
        r"([a-z]+)\s+([^.!?]+)",
        flags=re.IGNORECASE,
    )
    for sentence in split_sentences(text):
        match = pattern.search(sentence)
        if match:
            obligations.append(
                {
                    "subject": match.group(1).strip().title(),
                    "action": match.group(3).strip().capitalize(),
                    "object": match.group(4).strip(),
                    "sentence": sentence,
                }
            )
    return obligations


def detect_clause_dependencies(text):
    dependencies = []
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if ("terminate" in lowered or "termination" in lowered) and ("pay" in lowered or "payment" in lowered):
            if any(trigger in lowered for trigger in ["if", "unless", "upon", "only if", "fails", "failure"]):
                dependencies.append(
                    {
                        "source": "Termination Clause",
                        "depends_on": "Payment Clause",
                        "sentence": sentence,
                        "reason": "Termination appears conditional on payment behavior.",
                    }
                )
        if "liability" in lowered and ("confidential" in lowered or "data" in lowered):
            dependencies.append(
                {
                    "source": "Liability Clause",
                    "depends_on": "Confidentiality/Data Privacy Clause",
                    "sentence": sentence,
                    "reason": "Liability appears linked to confidentiality or data handling obligations.",
                }
            )
    return dependencies


def detect_sensitive_data(text):
    patterns = {
        "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "Phone": r"\b(?:\+91[- ]?)?[6-9]\d{9}\b",
        "Bank Account": r"\b\d{9,18}\b",
        "PAN": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    }
    findings = []
    for label, pattern in patterns.items():
        for match in re.findall(pattern, text):
            findings.append({"type": label, "value": match})
    return findings


def mask_sensitive_data(text):
    masked = text
    masks = {
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b": "[MASKED_EMAIL]",
        r"\b(?:\+91[- ]?)?[6-9]\d{9}\b": "[MASKED_PHONE]",
        r"\b[A-Z]{5}\d{4}[A-Z]\b": "[MASKED_PAN]",
        r"\b\d{9,18}\b": "[MASKED_ACCOUNT]",
    }
    for pattern, replacement in masks.items():
        masked = re.sub(pattern, replacement, masked)
    return masked


def detect_similar_clauses(text):
    sentences = split_sentences(text)
    similar_pairs = []
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            ratio = SequenceMatcher(None, sentences[i].lower(), sentences[j].lower()).ratio()
            if ratio >= 0.72 and sentences[i].lower() != sentences[j].lower():
                similar_pairs.append(
                    {
                        "sentence_a": sentences[i],
                        "sentence_b": sentences[j],
                        "similarity": round(ratio * 100, 2),
                    }
                )
    return similar_pairs[:8]


def summarize_contract(text, findings):
    sentences = split_sentences(text)
    if not sentences:
        return []
    clause_words = set()
    for patterns in CLAUSE_LIBRARY.values():
        clause_words.update(patterns)
    scored = []
    for sentence in sentences:
        lowered = sentence.lower()
        score = 0
        score += sum(1 for finding in findings if finding["term"] in lowered) * 3
        score += sum(1 for word in clause_words if word in lowered)
        score += 2 if any(token in lowered for token in ["shall", "must", "liable", "terminate", "payment"]) else 0
        scored.append((score, sentence))
    top_sentences = [sentence for score, sentence in sorted(scored, key=lambda item: item[0], reverse=True)[:5] if score > 0]
    if not top_sentences:
        top_sentences = sentences[:3]
    return top_sentences


def run_compliance_checks(text):
    lowered = text.lower()
    issues = []
    for rule in COMPLIANCE_RULES:
        if any(trigger in lowered for trigger in rule["trigger"]) and not any(req in lowered for req in rule["required_any"]):
            issues.append(rule["message"])
    return issues


def build_recommendations(findings, ambiguity_findings, missing_clauses):
    recommendations = []
    seen = set()
    for finding in findings:
        suggestion = RISK_RECOMMENDATIONS.get(finding["term"])
        if suggestion and suggestion not in seen:
            recommendations.append({"title": finding["term"], "suggestion": suggestion})
            seen.add(suggestion)
    for item in ambiguity_findings[:3]:
        suggestion = f"Replace '{item['term']}' with measurable language such as a fixed timeline, threshold, or duty."
        if suggestion not in seen:
            recommendations.append({"title": item["term"], "suggestion": suggestion})
            seen.add(suggestion)
    for clause in missing_clauses:
        suggestion = f"Add a clearly drafted {clause.lower()} to reduce negotiation and enforcement gaps."
        if suggestion not in seen:
            recommendations.append({"title": clause, "suggestion": suggestion})
            seen.add(suggestion)
    return recommendations[:8]


def answer_question(question, text, entities, obligations, findings):
    question_lower = question.lower().strip()
    if not question_lower:
        return "Ask a question about payment, liability, termination, confidentiality, dates, or parties."

    if "who" in question_lower and obligations:
        first = obligations[0]
        return f"{first['subject']} is obligated to {first['action'].lower()} {first['object']}."
    if "date" in question_lower or "when" in question_lower:
        if entities["Dates"]:
            return f"Detected date references: {', '.join(entities['Dates'][:3])}."
    if "party" in question_lower or "parties" in question_lower:
        if entities["Parties"]:
            return f"Detected parties: {', '.join(entities['Parties'][:5])}."
    if "money" in question_lower or "amount" in question_lower or "payment" in question_lower:
        if entities["Money Values"]:
            return f"Detected money values: {', '.join(entities['Money Values'][:3])}."

    for topic, keywords in QUESTION_TOPICS.items():
        if topic in question_lower or any(keyword in question_lower for keyword in keywords):
            for sentence in split_sentences(text):
                if any(keyword in sentence.lower() for keyword in keywords):
                    return sentence

    if findings:
        strongest = sorted(findings, key=lambda item: level_priority(item["level"]))[0]
        return f"The strongest detected risk is '{strongest['term']}' under {strongest['level']}. {strongest['explanation']}"
    return "I could not find a direct answer in the contract text. Try asking about payment, liability, termination, or dates."


def compare_contracts(base_text, compare_text):
    base_findings = analyze_text(base_text)
    compare_findings = analyze_text(compare_text)
    base_terms = {item["term"] for item in base_findings}
    compare_terms = {item["term"] for item in compare_findings}
    base_summary = build_summary(base_findings, base_text, analyze_sentences(base_text))
    compare_summary = build_summary(compare_findings, compare_text, analyze_sentences(compare_text))
    return {
        "similarity": round(SequenceMatcher(None, normalize_text(base_text).lower(), normalize_text(compare_text).lower()).ratio() * 100, 2),
        "base_score": base_summary["overall_score"],
        "compare_score": compare_summary["overall_score"],
        "added_risks": sorted(compare_terms - base_terms),
        "removed_risks": sorted(base_terms - compare_terms),
    }


def build_summary(findings, text, sentence_findings):
    counts = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    weights = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    for finding in findings:
        counts[finding["level"]] += 1
        weights[finding["level"]] += finding["weight"]

    ambiguity_findings = detect_ambiguity(text)
    obligations = extract_obligations(text)
    dependencies = detect_clause_dependencies(text)
    clauses = detect_clause_types(text)
    missing_clauses = [item for item in MISSING_CLAUSE_TARGETS if item not in {clause["clause"] for clause in clauses}]
    entity_map = extract_entities(text)
    sensitive_data = detect_sensitive_data(text)
    similar_clauses = detect_similar_clauses(text)
    compliance_issues = run_compliance_checks(text)

    raw_score = weights["High Risk"] + weights["Medium Risk"] + weights["Low Risk"]
    raw_score += min(len(ambiguity_findings) * 4, 12)
    raw_score += min(len(compliance_issues) * 8, 16)
    raw_score += min(len(dependencies) * 6, 12)
    overall_score = min(raw_score + min(len(sentence_findings) * 4, 12), 100)

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

    top_terms = Counter(item["term"] for item in findings).most_common(5)
    recommendations = build_recommendations(findings, ambiguity_findings, missing_clauses)

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
        "ambiguity": ambiguity_findings,
        "obligations": obligations,
        "dependencies": dependencies,
        "sensitive_data": sensitive_data,
        "similar_clauses": similar_clauses,
        "compliance_issues": compliance_issues,
        "recommendations": recommendations,
        "summary_points": summarize_contract(text, findings),
    }


def explain_contract(summary, findings):
    if not findings and not summary["ambiguity"] and not summary["compliance_issues"]:
        return "No tracked legal risk indicators were found in the submitted contract text."
    reasons = [item["explanation"] for item in sorted(findings, key=lambda item: level_priority(item["level"]))[:3]]
    if summary["ambiguity"]:
        reasons.append(f"Ambiguous wording like '{summary['ambiguity'][0]['term']}' reduces clarity.")
    if summary["compliance_issues"]:
        reasons.append(summary["compliance_issues"][0])
    joined = " ".join(reasons[:4])
    return f"This contract is marked as {summary['overall_risk']} with a score of {summary['overall_score']}/100. {joined}"


def highlight_risk_terms(text):
    highlighted = html.escape(text)
    replacements = []
    for level, config in RISK_LIBRARY.items():
        for term in sorted(config["keywords"], key=len, reverse=True):
            replacements.append((term, level_class(level), level))
    for term, css_class, label in replacements:
        pattern = re.compile(rf"\b({re.escape(term)})\b", re.IGNORECASE)
        highlighted = pattern.sub(
            lambda match: f"<span class='highlight {css_class}' title='{html.escape(label)}'>{html.escape(match.group(0))}</span>",
            highlighted,
        )
    for term in sorted(AMBIGUOUS_TERMS, key=len, reverse=True):
        pattern = re.compile(rf"\b({re.escape(term)})\b", re.IGNORECASE)
        highlighted = pattern.sub(
            lambda match: f"<span class='highlight ambiguous' title='Ambiguous'>{html.escape(match.group(0))}</span>",
            highlighted,
        )
    return highlighted.replace("\n", "<br>")


def build_redline_view(text):
    rendered = html.escape(text)
    for risky_term, suggestion in RISK_RECOMMENDATIONS.items():
        safe_phrase = html.escape(suggestion.split(".")[0])
        pattern = re.compile(rf"\b({re.escape(risky_term)})\b", re.IGNORECASE)
        rendered = pattern.sub(
            lambda match: f"<span class='strike'>{html.escape(match.group(0))}</span> <span class='insert'>{safe_phrase}</span>",
            rendered,
        )
    return rendered.replace("\n", "<br>")


def role_based_summary(role, summary, findings):
    if role == "Manager":
        top_issue = findings[0]["term"] if findings else "no major tracked issue"
        return f"Risk score {summary['overall_score']}/100. Overall status: {summary['overall_risk']}. Main concern: {top_issue}."
    if role == "Client":
        missing = ", ".join(summary["missing_clauses"]) if summary["missing_clauses"] else "no major missing clauses"
        return f"This contract may affect your obligations and costs. It is rated {summary['overall_risk']} and appears to have {missing}."
    return explain_contract(summary, findings)


def build_report_text(text, findings, sentence_findings, summary):
    lines = [
        "Legal Contract Risk Analyzer Report",
        "",
        f"Overall Risk: {summary['overall_risk']}",
        f"Overall Risk Score: {summary['overall_score']}/100",
        f"Total Sentences: {summary['total_sentences']}",
        f"Risky Sentences: {summary['risky_sentences']}",
        f"Total Risk Matches: {summary['total_matches']}",
        "",
        "Key Summary Points:",
    ]
    lines.extend(f"- {point}" for point in summary["summary_points"] or ["No summary points available"])
    lines.extend(
        [
            "",
            "Clause Dependencies:",
        ]
    )
    if summary["dependencies"]:
        lines.extend(f"- {item['source']} depends on {item['depends_on']}: {item['sentence']}" for item in summary["dependencies"])
    else:
        lines.append("- No clause dependencies detected")
    lines.extend(["", "Ambiguity Findings:"])
    if summary["ambiguity"]:
        lines.extend(f"- {item['term']}: {item['message']}" for item in summary["ambiguity"])
    else:
        lines.append("- No major ambiguous terms detected")
    lines.extend(["", "Obligations:"])
    if summary["obligations"]:
        lines.extend(f"- {item['subject']} must {item['action'].lower()} {item['object']}" for item in summary["obligations"])
    else:
        lines.append("- No obligations extracted")
    lines.extend(["", "Compliance Issues:"])
    if summary["compliance_issues"]:
        lines.extend(f"- {issue}" for issue in summary["compliance_issues"])
    else:
        lines.append("- No compliance gaps detected by the rule set")
    lines.extend(["", "Sensitive Data:"])
    if summary["sensitive_data"]:
        lines.extend(f"- {item['type']}: {item['value']}" for item in summary["sensitive_data"])
    else:
        lines.append("- No sensitive data patterns detected")
    lines.extend(["", "Recommendations:"])
    if summary["recommendations"]:
        lines.extend(f"- {item['title']}: {item['suggestion']}" for item in summary["recommendations"])
    else:
        lines.append("- No recommendations generated")
    lines.extend(["", "Explainable Summary:", explain_contract(summary, findings), "", "Original Contract Text:", text or "No text submitted"])
    return "\n".join(lines)


def build_pdf_report(report_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.6 * inch, leftMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], textColor=HexColor("#1f2937"), fontSize=18, leading=22, spaceAfter=12)
    body_style = ParagraphStyle("BodyStyle", parent=styles["BodyText"], fontSize=10, leading=14, textColor=HexColor("#334155"))
    story = []
    lines = report_text.split("\n")
    if lines:
        story.append(Paragraph(html.escape(lines[0]), title_style))
        story.append(Spacer(1, 0.15 * inch))
    for line in lines[1:]:
        story.append(Paragraph(html.escape(line) if line.strip() else "&nbsp;", body_style))
        story.append(Spacer(1, 0.06 * inch))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def run_full_analysis(text, source_name="Pasted Contract"):
    findings = analyze_text(text) if text else []
    sentence_findings = analyze_sentences(text) if text else []
    summary = build_summary(findings, text, sentence_findings)
    report_text = build_report_text(text, findings, sentence_findings, summary)
    pdf_report = build_pdf_report(report_text) if text else b""
    return {
        "source_name": source_name,
        "text": text,
        "findings": findings,
        "sentence_findings": sentence_findings,
        "summary": summary,
        "report_text": report_text,
        "pdf_report": pdf_report,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


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

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Manrope', sans-serif; color: #e5eef9; }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, 0.24), transparent 25%),
                radial-gradient(circle at top right, rgba(217, 72, 95, 0.18), transparent 22%),
                linear-gradient(135deg, #081120 0%, #0f172a 50%, #111827 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.12);
        }
        .hero-card, .panel-card, .metric-card, .result-card, .empty-card, .sentence-card {
            border-radius: 24px;
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.14);
            box-shadow: 0 22px 60px rgba(2, 6, 23, 0.34);
            backdrop-filter: blur(14px);
            padding: 1.2rem 1.3rem;
            margin-bottom: 0.9rem;
        }
        .hero-card { padding: 2rem 2.2rem; }
        .eyebrow { display: inline-block; padding: 0.55rem 0.95rem; border-radius: 999px; background: rgba(30, 41, 59, 0.9); color: #93c5fd; font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }
        .hero-title { margin: 1rem 0 0.65rem; font-size: clamp(2rem, 3vw, 4rem); font-weight: 800; line-height: 1; color: #f8fafc; }
        .hero-copy, .body-copy, .subtle-copy { color: #94a3b8; line-height: 1.7; font-size: 1rem; }
        .section-title { margin: 0; color: #f8fafc; font-size: 1.25rem; font-weight: 800; }
        .helper-row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 1rem 0 1.1rem; }
        .pill, .chip { display: inline-block; padding: 0.45rem 0.75rem; border-radius: 999px; font-size: 0.8rem; font-weight: 800; }
        .high { color: #d9485f; background: rgba(217,72,95,0.14); }
        .medium { color: #f08c2b; background: rgba(240,140,43,0.16); }
        .low { color: #2f9e44; background: rgba(47,158,68,0.15); }
        .ambiguous { color: #7c3aed; background: rgba(124,58,237,0.14); }
        .status-banner { border-radius: 22px; padding: 1.35rem; color: white; margin-bottom: 1rem; }
        .status-banner.high { background: linear-gradient(135deg, #b4233d, #d9485f, #ef476f); }
        .status-banner.medium { background: linear-gradient(135deg, #c76a09, #f08c2b, #f7b267); }
        .status-banner.low { background: linear-gradient(135deg, #1f7a39, #2f9e44, #57cc99); }
        .status-banner.neutral { background: linear-gradient(135deg, #285fcb, #3b82f6, #60a5fa); }
        .status-label { font-size: 0.8rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }
        .status-title { margin: 0.5rem 0 0.35rem; font-size: 1.8rem; font-weight: 800; }
        .metric-label { color: #94a3b8; font-size: 0.9rem; margin-bottom: 0.5rem; }
        .metric-value { font-size: 1.9rem; font-weight: 800; line-height: 1; color: #60a5fa; }
        .result-row, .sentence-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
        .result-term { font-weight: 800; color: #f8fafc; }
        .highlight-panel { padding: 1rem 1.2rem; border-radius: 20px; border: 1px solid rgba(148,163,184,0.12); background: rgba(15,23,42,0.94); line-height: 1.8; color: #e2e8f0; }
        .highlight { padding: 0.1rem 0.3rem; border-radius: 0.35rem; font-weight: 700; }
        .strike { text-decoration: line-through; color: #b4233d; font-weight: 700; }
        .insert { color: #1f7a39; font-weight: 700; background: rgba(47,158,68,0.12); padding: 0.1rem 0.25rem; border-radius: 0.3rem; }
        .missing { color: #b4233d; font-weight: 700; }
        .ok { color: #1f7a39; font-weight: 700; }
        .nav-caption { color: #94a3b8; font-size: 0.92rem; }
        .card-grid-title { color: #cbd5e1; font-weight: 700; margin-bottom: 0.55rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
        <div class="eyebrow">AI Legal Intelligence Demo</div>
        <div class="hero-title">Analyze contracts with explainable legal-NLP features.</div>
        <div class="hero-copy">
            This version adds clause dependencies, ambiguity detection, obligation extraction, summarization,
            Q&A, semantic similarity, compliance checks, auto-redlining, role-based views, multi-contract analysis,
            and sensitive-data masking.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🧭 Navigation Menu")
    current_page = st.radio(
        "Go to",
        [
            "📊 Dashboard",
            "📝 Analyze Contract",
            "📁 Upload File",
            "📈 Risk Report",
            "🕘 History",
            "⚙️ Settings / About",
        ],
        label_visibility="collapsed",
    )
    st.markdown("<div class='nav-caption'>Dark presentation theme enabled</div>", unsafe_allow_html=True)
    selected_role = st.selectbox("View Mode", list(ROLE_DESCRIPTIONS.keys()), help="Switch between lawyer, client, and manager perspectives.")
    st.caption(ROLE_DESCRIPTIONS[selected_role])


latest_result = st.session_state.get("latest_result")
history = st.session_state.get("analysis_history", [])


def render_dashboard():
    total_contracts = len(history)
    high_count = sum(1 for item in history if item["Risk Level"] == "High Risk")
    medium_count = sum(1 for item in history if item["Risk Level"] == "Medium Risk")
    low_count = sum(1 for item in history if item["Risk Level"] == "Low Risk")

    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("📄 Total Contracts Analyzed", total_contracts),
        ("🔴 High Risk Count", high_count),
        ("🟠 Medium Risk", medium_count),
        ("🟢 Low Risk", low_count),
    ]
    for col, (label, value) in zip([col1, col2, col3, col4], metrics):
        with col:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>", unsafe_allow_html=True)

    chart_col, recent_col = st.columns([1.1, 0.9], gap="large")
    with chart_col:
        distribution = pd.DataFrame(
            [
                {"Risk Level": "High Risk", "Count": high_count},
                {"Risk Level": "Medium Risk", "Count": medium_count},
                {"Risk Level": "Low Risk", "Count": low_count},
            ]
        )
        chart = alt.Chart(distribution).mark_arc(innerRadius=55).encode(
            theta="Count:Q",
            color=alt.Color("Risk Level:N", scale=alt.Scale(domain=["High Risk", "Medium Risk", "Low Risk"], range=["#d9485f", "#f08c2b", "#2f9e44"])),
            tooltip=["Risk Level", "Count"],
        ).properties(height=320)
        st.markdown("<div class='panel-card'><div class='section-title'>Risk Distribution</div></div>", unsafe_allow_html=True)
        st.altair_chart(chart, use_container_width=True)
    with recent_col:
        st.markdown("<div class='panel-card'><div class='section-title'>Recent Analyses</div></div>", unsafe_allow_html=True)
        if history:
            for item in history[:5]:
                st.markdown(
                    f"<div class='result-card'><div class='result-term'>{html.escape(item['File Name'])}</div><div class='subtle-copy'>{item['Date']} · {item['Risk Level']} · Score {item['Risk Score']}</div></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div class='empty-card'>No analyses yet. Use Analyze Contract or Upload File to begin.</div>", unsafe_allow_html=True)


def render_analyze_contract():
    st.markdown("<div class='panel-card'><div class='section-title'>Analyze Contract</div><div class='body-copy'>Paste contract text, run analysis, and review highlighted risks with explanations.</div></div>", unsafe_allow_html=True)
    contract_text = st.text_area(
        "Paste Contract Text",
        value=st.session_state.get("contract_text", ""),
        height=300,
        placeholder="Paste the full contract text here...",
    )
    st.session_state["contract_text"] = contract_text
    if st.button("Analyze Button", type="primary", use_container_width=True):
        if not contract_text.strip():
            st.warning("Paste some contract text first.")
        else:
            with st.spinner("Analyzing contract..."):
                result = run_full_analysis(contract_text, "Pasted Contract")
                store_analysis(result)
                latest = result["summary"]
                st.success("Analysis complete.")
                st.progress(min(latest["overall_score"], 100) / 100)

    result = st.session_state.get("latest_result")
    if result and result["text"]:
        summary = result["summary"]
        findings = result["findings"]
        st.markdown("<div class='panel-card'><div class='section-title'>Results Section</div></div>", unsafe_allow_html=True)
        left, right = st.columns([1.1, 0.9], gap="large")
        with left:
            st.markdown(f"<div class='highlight-panel'>{highlight_risk_terms(result['text'])}</div>", unsafe_allow_html=True)
        with right:
            st.markdown(
                f"""
                <div class="panel-card">
                    <div class="status-banner {summary['overall_class']}">
                        <div class="status-label">Risk Score Meter</div>
                        <div class="status-title">{summary['overall_score']}/100</div>
                        <p>{summary['overall_risk']}</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(f"<div class='panel-card'><div class='section-title'>Risk Categories</div><div class='subtle-copy'>🔴 {summary['counts']['High Risk']} high · 🟠 {summary['counts']['Medium Risk']} medium · 🟢 {summary['counts']['Low Risk']} low</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='panel-card'><div class='section-title'>Explanation</div><div class='subtle-copy'>{html.escape(role_based_summary(selected_role, summary, findings))}</div></div>", unsafe_allow_html=True)


def render_upload_file():
    st.markdown("<div class='panel-card'><div class='section-title'>Upload File</div><div class='body-copy'>Upload a PDF or DOCX file, preview the extracted text, and analyze it directly.</div></div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf", "docx", "txt"], key="page_upload")
    if uploaded_file is not None:
        extracted_text = read_uploaded_file(uploaded_file)
        st.session_state["uploaded_contract_text"] = extracted_text
        st.session_state["uploaded_contract_name"] = uploaded_file.name
        st.markdown("<div class='card-grid-title'>Extracted Text Preview</div>", unsafe_allow_html=True)
        st.text_area("Preview", extracted_text, height=260, disabled=False)
        if st.button("Analyze Uploaded File", use_container_width=True, type="primary"):
            if extracted_text.strip():
                with st.spinner("Analyzing contract..."):
                    result = run_full_analysis(extracted_text, uploaded_file.name)
                    store_analysis(result)
                    st.success(f"Analysis saved for {uploaded_file.name}")
            else:
                st.warning("No readable text was extracted from the file.")


def render_risk_report():
    st.markdown("<div class='panel-card'><div class='section-title'>Risk Report</div><div class='body-copy'>Charts, top risky clauses, and downloadable analysis output.</div></div>", unsafe_allow_html=True)
    if not latest_result:
        st.info("Run an analysis first to generate a risk report.")
        return
    summary = latest_result["summary"]
    findings = latest_result["findings"]
    chart_col, side_col = st.columns([1.05, 0.95], gap="large")
    with chart_col:
        risk_df = pd.DataFrame(
            [
                {"Risk Level": "High Risk", "Count": summary["counts"]["High Risk"]},
                {"Risk Level": "Medium Risk", "Count": summary["counts"]["Medium Risk"]},
                {"Risk Level": "Low Risk", "Count": summary["counts"]["Low Risk"]},
            ]
        )
        pie = alt.Chart(risk_df).mark_arc(innerRadius=55).encode(
            theta="Count:Q",
            color=alt.Color("Risk Level:N", scale=alt.Scale(domain=["High Risk", "Medium Risk", "Low Risk"], range=["#d9485f", "#f08c2b", "#2f9e44"])),
            tooltip=["Risk Level", "Count"],
        ).properties(height=280)
        st.altair_chart(pie, use_container_width=True)

        keyword_df = pd.DataFrame(summary["top_terms"], columns=["Keyword", "Hits"]) if summary["top_terms"] else pd.DataFrame([{"Keyword": "None", "Hits": 0}])
        bars = alt.Chart(keyword_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
            x=alt.X("Keyword:N", sort="-y"),
            y="Hits:Q",
            color=alt.value("#60a5fa"),
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
    st.markdown("<div class='panel-card'><div class='section-title'>History</div><div class='body-copy'>Past analyses from this app session.</div></div>", unsafe_allow_html=True)
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
                <div class='subtle-copy'>Legal Contract Risk Analyzer with dark-theme sidebar UI, rule-based legal NLP, charts, history, file upload, and report generation.</div>
            </div>
            <div class='result-card'>
                <div class='result-term'>Model Details</div>
                <div class='subtle-copy'>Current system uses heuristic NLP, regex extraction, rule-based scoring, and Streamlit analytics visualizations.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class='result-card'>
                <div class='result-term'>Team Members</div>
                <div class='subtle-copy'>Update these names before your college demo:</div>
                <div class='subtle-copy'>1. Team Member 1</div>
                <div class='subtle-copy'>2. Team Member 2</div>
                <div class='subtle-copy'>3. Team Member 3</div>
            </div>
            <div class='result-card'>
                <div class='result-term'>Theme</div>
                <div class='subtle-copy'>Dark theme is enabled for a modern presentation-friendly look.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if current_page == "📊 Dashboard":
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
