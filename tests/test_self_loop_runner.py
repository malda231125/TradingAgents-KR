import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.run_self_loop import run_self_loop
from tradingagents.self_loop.records import save_decision_record


def fake_decision_extractor(_final_state):
    # Offline stand-in for the AI decision extractor; keeps tests network-free.
    return {
        "decision": "hold",
        "confidence": "medium",
        "thesis": "Stay put.",
        "key_risk_triggers": ["macro shock"],
        "prediction_checklist": ["close return aligns with hold over horizon"],
    }


def fake_trading_day_fn(start, n):
    # Deterministic calendar (weekends skipped) so review_due needs no network.
    cursor = start if isinstance(start, date) else date.fromisoformat(str(start))
    remaining = int(n)
    while remaining > 0:
        cursor = cursor + timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def _offline_kwargs():
    return {
        "decision_extractor": fake_decision_extractor,
        "trading_day_fn": fake_trading_day_fn,
    }


def fake_graph_runner(ticker, analysis_date, prior_context):
    final_state = {
        "market_report": f"Market report for {ticker}",
        "news_report": "News report",
        "fundamentals_report": "Fundamentals report",
        "investment_plan": "Investment plan with risk trigger.",
        "trader_investment_plan": "Trader plan.",
        "final_trade_decision": "Hold with medium confidence.",
        "investment_debate_state": {},
        "risk_debate_state": {},
    }
    if prior_context:
        final_state["market_report"] += f"\n\nPrior context:\n{prior_context}"
    return final_state, "hold"


class TestSelfLoopRunner(unittest.TestCase):
    def test_run_without_prior_record_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_self_loop(
                ticker="005930",
                analysis_date="2026-06-23",
                base_dir=tmp,
                graph_runner=fake_graph_runner,
                **_offline_kwargs(),
            )

            self.assertTrue(Path(result["report_path"]).exists())
            self.assertTrue(Path(result["decision_path"]).exists())
            self.assertTrue(Path(result["digest_path"]).exists())
            self.assertIsNone(result["retrospective_path"])

    def test_run_with_prior_record_writes_retrospective_and_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_decision_record(
                {
                    "schema_version": "self-loop-decision-v1",
                    "ticker": "005930",
                    "analysis_date": "2026-06-20",
                    "review_due": "2026-06-22",
                    "decision": "buy_review",
                    "prediction_checklist": ["price direction"],
                },
                base_dir=tmp,
            )
            retrospective = {
                "schema_version": "self-loop-retrospective-v1",
                "ticker": "005930",
                "analysis_date": "2026-06-20",
                "check_date": "2026-06-23",
                "review_due": "2026-06-22",
                "decision": "buy_review",
                "overall": "miss",
                "price_result": {"status": "available", "return_pct": -3.0, "message": "mocked"},
                "checklist_results": [{"item": "price direction", "status": "miss", "reason": "mocked"}],
                "lesson": "Mock lesson",
            }
            with patch("scripts.run_self_loop.run_retrospective", return_value=retrospective):
                result = run_self_loop(
                    ticker="005930",
                    analysis_date="2026-06-23",
                    base_dir=tmp,
                    graph_runner=fake_graph_runner,
                    **_offline_kwargs(),
                )

            self.assertTrue(Path(result["retrospective_path"]).exists())
            lessons_path = Path(tmp) / "lessons" / "005930.jsonl"
            self.assertTrue(lessons_path.exists())
            report_text = Path(result["report_path"]).read_text(encoding="utf-8")
            # Section headers are localized to the active report language; assert
            # against the same i18n strings the renderer uses.
            from tradingagents.i18n import get_report_strings

            s = get_report_strings()
            self.assertIn(s["sl_context"], report_text)
            self.assertIn(s["sl_result"], report_text)
            self.assertIn("Mock lesson", report_text)

    def test_lesson_summary_is_created_when_threshold_is_reached(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_decision_record(
                {
                    "schema_version": "self-loop-decision-v1",
                    "ticker": "005930",
                    "analysis_date": "2026-06-20",
                    "review_due": "2026-06-22",
                    "decision": "buy_review",
                    "prediction_checklist": ["price direction"],
                },
                base_dir=tmp,
            )
            retrospective = {
                "schema_version": "self-loop-retrospective-v1",
                "ticker": "005930",
                "analysis_date": "2026-06-20",
                "check_date": "2026-06-23",
                "review_due": "2026-06-22",
                "decision": "buy_review",
                "overall": "miss",
                "price_result": {"status": "available", "return_pct": -3.0, "message": "mocked"},
                "checklist_results": [{"item": "price direction", "status": "miss", "reason": "mocked"}],
                "lesson": "Mock lesson",
            }
            with patch("scripts.run_self_loop.run_retrospective", return_value=retrospective):
                with patch(
                    "scripts.run_self_loop.summarize_lessons_with_subscription_ai",
                    return_value="# Self-loop lesson summary\n\nSummarized.",
                ):
                    run_self_loop(
                        ticker="005930",
                        analysis_date="2026-06-23",
                        base_dir=tmp,
                        graph_runner=fake_graph_runner,
                        lesson_summary_threshold=1,
                        **_offline_kwargs(),
                    )

            summary_path = Path(tmp) / "lessons" / "005930.summary.md"
            self.assertTrue(summary_path.exists())
            self.assertIn("Summarized", summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
