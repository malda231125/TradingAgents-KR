import unittest

from tradingagents.self_loop.reviewer import (
    build_decision_extraction_prompt,
    build_review_prompt,
    parse_decision_extraction_response,
    parse_review_response,
)


class TestSelfLoopReviewer(unittest.TestCase):
    def test_build_prompt_contains_evidence_and_json_instruction(self):
        prompt = build_review_prompt(
            {"ticker": "005930", "decision": "hold"},
            {"overall": "hit", "price_result": {"return_pct": 2.1}},
        )

        self.assertIn("Return strict JSON", prompt)
        self.assertIn("005930", prompt)
        self.assertIn("preliminary_retrospective", prompt)

    def test_parse_review_response_from_fenced_json(self):
        parsed = parse_review_response(
            """```json
            {
              "overall": "miss",
              "reasoning": "The thesis failed.",
              "lesson": "Check foreign flow next time.",
              "confidence": "high"
            }
            ```"""
        )

        self.assertEqual(parsed["overall"], "miss")
        self.assertEqual(parsed["confidence"], "high")
        self.assertIn("foreign", parsed["lesson"])

    def test_parse_invalid_outcome_as_uncertain(self):
        parsed = parse_review_response(
            '{"overall": "maybe", "reasoning": "weak evidence", "lesson": null, "confidence": "weird"}'
        )

        self.assertEqual(parsed["overall"], "uncertain")
        self.assertEqual(parsed["confidence"], "medium")
        self.assertEqual(parsed["checklist_results"], [])

    def test_parse_review_response_parses_checklist_results(self):
        parsed = parse_review_response(
            """{
              "overall": "partial",
              "reasoning": "mixed",
              "checklist_results": [
                {"item": "price direction", "status": "HIT", "reason": "+2%"},
                {"item": "flow", "status": "bogus", "reason": "n/a"},
                {"item": "", "status": "hit", "reason": "dropped"}
              ],
              "lesson": null,
              "confidence": "medium"
            }"""
        )

        results = parsed["checklist_results"]
        # Empty-item row is dropped; invalid status normalizes to uncertain.
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "hit")
        self.assertEqual(results[1]["status"], "uncertain")

    def test_review_prompt_requests_per_item_checklist(self):
        prompt = build_review_prompt(
            {"ticker": "005930", "decision": "hold", "prediction_checklist": ["a", "b"]},
            {"missing_evidence": ["dart"], "evidence": {"flow": {"status": "available"}}},
        )
        self.assertIn("checklist_results", prompt)
        self.assertIn("missing_evidence", prompt)

    def test_decision_extraction_prompt_uses_plan_evidence(self):
        prompt = build_decision_extraction_prompt(
            {
                "investment_plan": "Accumulate on HBM strength",
                "trader_investment_plan": "Add on dips",
                "final_trade_decision": "Buy",
            }
        )

        self.assertIn("buy_review", prompt)
        self.assertIn("Do not rely on keyword matching", prompt)
        self.assertIn("HBM strength", prompt)

    def test_parse_decision_extraction_normalizes_fields(self):
        parsed = parse_decision_extraction_response(
            """```json
            {
              "decision": "BUY_REVIEW",
              "confidence": "weird",
              "thesis": "HBM upcycle intact.",
              "key_risk_triggers": ["ASP cut", ""],
              "prediction_checklist": ["close return positive"]
            }
            ```"""
        )

        self.assertEqual(parsed["decision"], "buy_review")
        self.assertEqual(parsed["confidence"], "medium")
        self.assertEqual(parsed["key_risk_triggers"], ["ASP cut"])
        self.assertEqual(parsed["prediction_checklist"], ["close return positive"])


if __name__ == "__main__":
    unittest.main()
