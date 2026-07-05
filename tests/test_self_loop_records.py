import tempfile
import unittest
from datetime import date
from pathlib import Path

from tradingagents.self_loop.records import (
    build_decision_record,
    find_latest_decision_record,
    load_decision_record,
    save_decision_record,
)


class TestSelfLoopRecords(unittest.TestCase):
    def test_save_load_and_find_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_record = {
                "ticker": "005930",
                "analysis_date": "2026-06-20",
                "decision": "hold",
            }
            new_record = {
                "ticker": "005930",
                "analysis_date": "2026-06-22",
                "decision": "buy_review",
            }
            old_path = save_decision_record(old_record, base_dir=tmp)
            new_path = save_decision_record(new_record, base_dir=tmp)

            self.assertEqual(load_decision_record(old_path)["decision"], "hold")
            latest = find_latest_decision_record("005930", base_dir=tmp, before_date="2026-06-23")
            self.assertIsNotNone(latest)
            latest_path, latest_record = latest
            self.assertEqual(Path(latest_path), new_path)
            self.assertEqual(latest_record["decision"], "buy_review")

            latest_before_new = find_latest_decision_record(
                "005930", base_dir=tmp, before_date="2026-06-21"
            )
            self.assertIsNotNone(latest_before_new)
            self.assertEqual(Path(latest_before_new[0]), old_path)

    def test_build_decision_record_uses_ai_extractor(self):
        def fake_extractor(_final_state):
            return {
                "decision": "buy_review",
                "confidence": "high",
                "thesis": "HBM demand drives upside.",
                "key_risk_triggers": ["HBM ASP drops"],
                "prediction_checklist": ["close return positive over horizon"],
            }

        record = build_decision_record(
            ticker="005930",
            analysis_date="2026-06-23",
            signal="buy",
            final_state={
                "investment_plan": "x",
                "final_trade_decision": "y",
                "market_report": "market data present",
                "news_report": "news present",
                "fundamentals_report": "",
            },
            report_path="reports/2026-06-23/005930.md",
            review_horizon_days=5,
            extractor=fake_extractor,
            trading_day_fn=lambda start, n: date(2026, 6, 30),
        )

        self.assertEqual(record["schema_version"], "self-loop-decision-v1")
        self.assertEqual(record["decision"], "buy_review")
        self.assertEqual(record["confidence"], "high")
        self.assertEqual(record["extraction_mode"], "ai")
        self.assertEqual(record["review_due"], "2026-06-30")
        self.assertEqual(record["key_risk_triggers"], ["HBM ASP drops"])
        # review window provenance (#3)
        self.assertEqual(record["review_due_basis"], "trading_day")
        self.assertEqual(record["review_horizon_trading_days"], 5)
        # data_sources/data_quality derived from produced sections, not hardcoded (#1/#4)
        self.assertEqual(record["data_quality"]["fundamentals"], "missing")
        self.assertEqual(record["data_quality"]["market"], "available")
        self.assertEqual(record["data_sources"], ["KIS", "Naver"])

    def test_review_due_basis_falls_back_to_weekday(self):
        def broken_trading_day(_start, _n):
            raise RuntimeError("calendar unavailable")

        record = build_decision_record(
            ticker="005930",
            analysis_date="2026-06-23",
            signal="hold",
            final_state={"final_trade_decision": "Hold."},
            report_path="reports/2026-06-23/005930.md",
            review_horizon_days=5,
            use_ai_extraction=False,
            trading_day_fn=broken_trading_day,
        )

        self.assertEqual(record["review_due_basis"], "weekday_fallback")
        self.assertEqual(record["data_sources"], [])

    def test_build_decision_record_falls_back_when_ai_disabled(self):
        record = build_decision_record(
            ticker="005930",
            analysis_date="2026-06-23",
            signal="hold",
            final_state={
                "investment_plan": "HBM thesis remains intact.",
                "trader_investment_plan": "",
                "final_trade_decision": "Hold with medium confidence.",
            },
            report_path="reports/2026-06-23/005930.md",
            review_horizon_days=5,
            use_ai_extraction=False,
            trading_day_fn=lambda start, n: date(2026, 6, 30),
        )

        self.assertEqual(record["decision"], "hold")
        self.assertEqual(record["extraction_mode"], "fallback")
        self.assertEqual(record["review_due"], "2026-06-30")
        self.assertTrue(record["prediction_checklist"])

    def test_build_decision_record_falls_back_when_extractor_raises(self):
        def boom(_final_state):
            raise RuntimeError("llm down")

        record = build_decision_record(
            ticker="005930",
            analysis_date="2026-06-23",
            signal="sell",
            final_state={"final_trade_decision": "매도 의견."},
            report_path="reports/2026-06-23/005930.md",
            review_horizon_days=5,
            extractor=boom,
            trading_day_fn=lambda start, n: date(2026, 6, 30),
        )

        self.assertEqual(record["extraction_mode"], "fallback")
        self.assertEqual(record["decision"], "sell_review")


if __name__ == "__main__":
    unittest.main()
