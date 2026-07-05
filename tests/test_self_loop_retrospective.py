import tempfile
import unittest

import pandas as pd

from tradingagents.self_loop.retrospective import (
    render_retrospective_markdown,
    run_retrospective,
    save_retrospective_markdown,
)


def fake_prices(_ticker, _start, _end):
    return pd.DataFrame(
        [
            {"Date": "2026-06-20", "Close": 100},
            {"Date": "2026-06-23", "Close": 105},
            {"Date": "2026-06-28", "Close": 108},
        ]
    )


class TestSelfLoopRetrospective(unittest.TestCase):
    def test_buy_review_hits_positive_price_move(self):
        result = run_retrospective(
            {
                "ticker": "005930",
                "analysis_date": "2026-06-23",
                "review_due": "2026-06-28",
                "decision": "buy_review",
                "prediction_checklist": ["review horizon 내 종가 수익률이 decision 방향과 일치하는가?"],
            },
            as_of_date="2026-06-28",
            price_fetcher=fake_prices,
        )

        self.assertEqual(result["overall"], "hit")
        self.assertEqual(result["price_result"]["return_pct"], 2.8571)
        self.assertIsNone(result["lesson"])

    def test_uncertain_when_price_fetch_fails(self):
        def failing_fetcher(_ticker, _start, _end):
            raise RuntimeError("boom")

        result = run_retrospective(
            {
                "ticker": "005930",
                "analysis_date": "2026-06-23",
                "review_due": "2026-06-28",
                "decision": "hold",
                "prediction_checklist": ["price direction"],
            },
            as_of_date="2026-06-28",
            price_fetcher=failing_fetcher,
        )

        self.assertEqual(result["overall"], "uncertain")
        self.assertIn("price fetch failed", result["price_result"]["message"])
        self.assertIsNotNone(result["lesson"])

    def test_render_and_save_markdown(self):
        result = run_retrospective(
            {
                "ticker": "005930",
                "analysis_date": "2026-06-23",
                "review_due": "2026-06-28",
                "decision": "sell_review",
                "prediction_checklist": ["price direction"],
            },
            as_of_date="2026-06-28",
            price_fetcher=fake_prices,
        )
        markdown = render_retrospective_markdown(result)
        self.assertIn("Self-loop retrospective", markdown)
        with tempfile.TemporaryDirectory() as tmp:
            path = save_retrospective_markdown(result, base_dir=tmp)
            self.assertTrue(path.exists())

    def test_ai_reviewer_overrides_preliminary_result(self):
        captured = {}

        def reviewer(_record, preliminary):
            captured["preliminary"] = preliminary
            return {
                "overall": "partial",
                "reasoning": "Price was positive but original checklist lacked non-price evidence.",
                "checklist_results": [
                    {"item": "price direction", "status": "hit", "reason": "+2.8%"},
                    {"item": "foreign flow improved", "status": "miss", "reason": "net selling"},
                ],
                "lesson": "Add explicit non-price evidence checks next time.",
                "confidence": "medium",
            }

        def fake_evidence_builder(_record, *, check_date, price_result):
            return {
                "evidence": {"flow": {"status": "available", "summary": "net selling"}},
                "data_quality": {"price": "available", "flow": "available", "dart": "missing"},
                "missing_evidence": ["dart"],
            }

        result = run_retrospective(
            {
                "ticker": "005930",
                "analysis_date": "2026-06-23",
                "review_due": "2026-06-28",
                "decision": "buy_review",
                "prediction_checklist": ["price direction", "foreign flow improved"],
            },
            as_of_date="2026-06-28",
            price_fetcher=fake_prices,
            ai_reviewer=reviewer,
            evidence_builder=fake_evidence_builder,
        )

        self.assertEqual(result["overall"], "partial")
        self.assertEqual(result["ai_review"]["status"], "completed")
        self.assertIn("non-price", result["lesson"])
        # Evidence packet is collected and exposed for the reviewer + report.
        self.assertEqual(result["missing_evidence"], ["dart"])
        self.assertEqual(result["data_quality"]["flow"], "available")
        # AI per-item checklist results replace the preliminary all-uncertain rows.
        statuses = {row["item"]: row["status"] for row in result["checklist_results"]}
        self.assertEqual(statuses["foreign flow improved"], "miss")
        # The reviewer actually saw the evidence packet.
        self.assertIn("flow", captured["preliminary"]["evidence"])


if __name__ == "__main__":
    unittest.main()
