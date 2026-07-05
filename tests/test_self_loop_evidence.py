import unittest

from tradingagents.self_loop.evidence import build_evidence_packet


DECISION = {"ticker": "005930", "analysis_date": "2026-06-23"}
PRICE_OK = {
    "status": "available",
    "message": "price move evaluated",
    "start_close": 100.0,
    "end_close": 105.0,
    "return_pct": 5.0,
}


class TestSelfLoopEvidence(unittest.TestCase):
    def test_collects_available_and_missing_evidence(self):
        packet = build_evidence_packet(
            DECISION,
            check_date="2026-06-28",
            price_result=PRICE_OK,
            flow_fetcher=lambda *_: "외국인 순매도 지속",
            dart_fetcher=lambda *_: "",  # empty -> missing
            news_fetcher=lambda *_: "HBM 수요 견조 기사",
            macro_fetcher=lambda _date: "원/달러 환율 상승",
        )

        self.assertEqual(packet["data_quality"]["price"], "available")
        self.assertEqual(packet["data_quality"]["flow"], "available")
        self.assertEqual(packet["data_quality"]["dart"], "missing")
        self.assertEqual(packet["data_quality"]["macro"], "available")
        self.assertIn("dart", packet["missing_evidence"])
        self.assertEqual(packet["evidence"]["price"]["detail"]["return_pct"], 5.0)
        self.assertEqual(packet["evidence"]["flow"]["summary"], "외국인 순매도 지속")

    def test_fetcher_failure_is_recorded_not_raised(self):
        def boom(*_):
            raise RuntimeError("vendor down")

        packet = build_evidence_packet(
            DECISION,
            check_date="2026-06-28",
            price_result=PRICE_OK,
            flow_fetcher=boom,
            dart_fetcher=lambda *_: "disclosure",
            news_fetcher=lambda *_: "news",
            macro_fetcher=lambda _date: "macro",
        )

        self.assertEqual(packet["evidence"]["flow"]["status"], "missing")
        self.assertIn("vendor down", packet["evidence"]["flow"]["error"])
        self.assertIn("flow", packet["missing_evidence"])

    def test_missing_price_result_marks_price_missing(self):
        packet = build_evidence_packet(
            DECISION,
            check_date="2026-06-28",
            price_result=None,
            flow_fetcher=lambda *_: "flow",
            dart_fetcher=lambda *_: "dart",
            news_fetcher=lambda *_: "news",
            macro_fetcher=lambda _date: "macro",
        )

        self.assertEqual(packet["evidence"]["price"]["status"], "missing")
        self.assertIn("price", packet["missing_evidence"])

    def test_long_summary_is_truncated(self):
        packet = build_evidence_packet(
            DECISION,
            check_date="2026-06-28",
            price_result=PRICE_OK,
            flow_fetcher=lambda *_: "x" * 5000,
            dart_fetcher=lambda *_: "d",
            news_fetcher=lambda *_: "n",
            macro_fetcher=lambda _date: "m",
        )

        self.assertTrue(packet["evidence"]["flow"]["truncated"])
        self.assertLessEqual(len(packet["evidence"]["flow"]["summary"]), 2000)


if __name__ == "__main__":
    unittest.main()
