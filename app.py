
from flask import Flask, render_template, request
import re

app = Flask(__name__)

# Simple risk keywords (you can expand this or replace with ML model)
RISK_KEYWORDS = {
    "High Risk": ["penalty", "breach", "liability", "terminate immediately"],
    "Medium Risk": ["delay", "obligation", "indemnify"],
    "Low Risk": ["may", "should", "optional"]
}

def analyze_text(text):
    results = []
    for level, keywords in RISK_KEYWORDS.items():
        for word in keywords:
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                results.append((word, level))
    return results

def build_summary(analysis):
    counts = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    for _, level in analysis:
        counts[level] += 1

    if counts["High Risk"]:
        overall_risk = "High Risk"
    elif counts["Medium Risk"]:
        overall_risk = "Medium Risk"
    elif counts["Low Risk"]:
        overall_risk = "Low Risk"
    else:
        overall_risk = "No Immediate Risk"

    total_matches = sum(counts.values())
    return {
        "counts": counts,
        "overall_risk": overall_risk,
        "total_matches": total_matches,
    }

@app.route("/", methods=["GET", "POST"])
def index():
    analysis = []
    text = ""
    summary = build_summary(analysis)
    if request.method == "POST":
        text = request.form["contract"]
        analysis = analyze_text(text)
        summary = build_summary(analysis)
    return render_template("index.html", analysis=analysis, text=text, summary=summary)

if __name__ == "__main__":
    app.run(debug=True)
