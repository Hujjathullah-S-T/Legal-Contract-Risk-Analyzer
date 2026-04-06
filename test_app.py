import unittest

from analyzer_core import (
    analyze_sentences,
    analyze_text,
    build_summary,
    compare_contracts,
    detect_clause_dependencies,
    detect_sensitive_data,
    mask_sensitive_data,
    run_full_analysis,
)


class ContractAnalyzerTests(unittest.TestCase):
    def test_high_risk_terms_are_detected(self):
        text = "The vendor will face a penalty for breach and unlimited liability for damages."
        findings = analyze_text(text)
        terms = {item["term"] for item in findings}
        self.assertIn("penalty", terms)
        self.assertIn("breach", terms)
        self.assertIn("unlimited liability", terms)

    def test_summary_marks_high_risk_for_strong_language(self):
        text = "Either party may terminate immediately upon breach and unlimited liability shall apply."
        findings = analyze_text(text)
        sentences = analyze_sentences(text)
        summary = build_summary(findings, text, sentences)
        self.assertEqual(summary["overall_risk"], "High Risk")
        self.assertGreaterEqual(summary["overall_score"], 80)

    def test_clause_dependency_detection_finds_payment_termination_link(self):
        text = "The agreement may terminate immediately if payment fails for more than 10 days."
        dependencies = detect_clause_dependencies(text)
        self.assertTrue(
            any(
                item["source"] == "Termination Clause"
                and item["depends_on"] == "Payment Clause"
                for item in dependencies
            )
        )

    def test_money_value_is_not_misclassified_as_bank_account(self):
        text = "Client shall pay INR 50000 before 10th Jan."
        sensitive_items = detect_sensitive_data(text)
        self.assertFalse(any(item["type"] == "Bank Account" for item in sensitive_items))

    def test_bank_account_is_detected_and_masked_when_labeled(self):
        text = "Bank account number 123456789012 must remain confidential."
        sensitive_items = detect_sensitive_data(text)
        self.assertTrue(any(item["type"] == "Bank Account" for item in sensitive_items))
        self.assertIn("[MASKED_ACCOUNT]", mask_sensitive_data(text))

    def test_clean_contract_returns_no_immediate_risk(self):
        text = (
            "This agreement is made between Client and Vendor. "
            "The parties agree to work together for software support from 1 January 2026."
        )
        result = run_full_analysis(text, "neutral")
        self.assertEqual(result["summary"]["overall_risk"], "No Immediate Risk")
        self.assertEqual(result["summary"]["overall_score"], 0)

    def test_compare_contracts_reports_which_contract_is_safer(self):
        base_text = "This agreement is made between Client and Vendor for support services."
        revised_text = "Either party may terminate immediately upon breach and unlimited liability shall apply."
        comparison = compare_contracts(base_text, revised_text)
        self.assertEqual(comparison["safer_contract"], "Base Contract")
        self.assertIn("lower overall risk score", comparison["safety_reason"])


if __name__ == "__main__":
    unittest.main()
