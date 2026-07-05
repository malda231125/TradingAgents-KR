"""Tests for DART disclosure event classifier."""

import unittest

from tradingagents.dataflows.dart_classifier import (
    classify_disclosure,
    format_classified_disclosures,
    IMPACT_MARKERS,
)


class TestClassifyDisclosure(unittest.TestCase):

    # Positive events
    def test_treasury_stock_purchase(self):
        event_type, impact = classify_disclosure("자기주식 취득 결정")
        self.assertEqual(impact, "positive")
        self.assertIn("자사주", event_type)

    def test_dividend(self):
        event_type, impact = classify_disclosure("현금배당 결정")
        self.assertEqual(impact, "positive")

    def test_large_order(self):
        event_type, impact = classify_disclosure("대규모 수주 공시")
        self.assertEqual(impact, "positive")

    def test_bonus_issue(self):
        event_type, impact = classify_disclosure("무상증자 결정")
        self.assertEqual(impact, "positive")

    # Negative events
    def test_rights_offering(self):
        event_type, impact = classify_disclosure("유상증자결정")
        self.assertEqual(impact, "negative")

    def test_capital_reduction(self):
        event_type, impact = classify_disclosure("감자 결정")
        self.assertEqual(impact, "negative")

    def test_embezzlement(self):
        event_type, impact = classify_disclosure("횡령 발생 사실 확인")
        self.assertEqual(impact, "negative")

    def test_delisting(self):
        event_type, impact = classify_disclosure("상장폐지 심사 대상 지정")
        self.assertEqual(impact, "negative")

    def test_cb_issuance(self):
        event_type, impact = classify_disclosure("전환사채 발행 결정")
        self.assertEqual(impact, "negative")

    def test_conversion_exercise(self):
        event_type, impact = classify_disclosure("전환권 행사")
        self.assertEqual(impact, "negative")

    # Neutral events
    def test_quarterly_report(self):
        event_type, impact = classify_disclosure("분기보고서 (2026.03)")
        self.assertEqual(impact, "neutral")

    def test_annual_report(self):
        event_type, impact = classify_disclosure("사업보고서 (2025.12)")
        self.assertEqual(impact, "neutral")

    def test_correction(self):
        event_type, impact = classify_disclosure("[기재정정]사업보고서")
        self.assertEqual(impact, "neutral")

    # Needs review events
    def test_major_shareholder_change(self):
        event_type, impact = classify_disclosure("최대주주 변경")
        self.assertEqual(impact, "needs_review")

    def test_merger(self):
        event_type, impact = classify_disclosure("합병 결정")
        self.assertEqual(impact, "needs_review")

    def test_executive_change(self):
        event_type, impact = classify_disclosure("대표이사 변경")
        self.assertEqual(impact, "needs_review")

    def test_earnings(self):
        event_type, impact = classify_disclosure("영업이익 등의 전망")
        self.assertEqual(impact, "needs_review")

    # Unknown
    def test_unknown_disclosure(self):
        event_type, impact = classify_disclosure("기타 비정형 공시 제목")
        self.assertEqual(impact, "unknown")
        self.assertEqual(event_type, "기타 공시")


class TestFormatClassifiedDisclosures(unittest.TestCase):

    def test_formats_mixed_disclosures(self):
        disclosures = [
            {"report_nm": "유상증자결정", "rcept_dt": "20260315", "flr_nm": "테스트기업"},
            {"report_nm": "자기주식 취득 결정", "rcept_dt": "20260310", "flr_nm": "삼성전자"},
            {"report_nm": "분기보고서 (2026.03)", "rcept_dt": "20260320", "flr_nm": "삼성전자"},
            {"report_nm": "최대주주 변경", "rcept_dt": "20260312", "flr_nm": "XYZ기업"},
        ]

        result = format_classified_disclosures(disclosures)

        # Negative should appear first
        self.assertIn("주의 필요", result)
        self.assertIn("유상증자", result)
        self.assertIn("[-]", result)

        # Positive
        self.assertIn("긍정적 신호", result)
        self.assertIn("자사주", result)
        self.assertIn("[+]", result)

        # Neutral
        self.assertIn("일반/중립", result)
        self.assertIn("분기보고서", result)

        # Needs review
        self.assertIn("확인 필요", result)
        self.assertIn("최대주주", result)
        self.assertIn("[?]", result)

        # Summary
        self.assertIn("Summary", result)
        self.assertIn("4 disclosures", result)

    def test_empty_list(self):
        result = format_classified_disclosures([])
        self.assertIn("No disclosures", result)

    def test_all_negative(self):
        disclosures = [
            {"report_nm": "유상증자결정", "rcept_dt": "20260315", "flr_nm": "A기업"},
            {"report_nm": "횡령 발생", "rcept_dt": "20260310", "flr_nm": "B기업"},
        ]
        result = format_classified_disclosures(disclosures)
        self.assertIn("2 negative", result)

    def test_impact_markers_exist(self):
        self.assertEqual(IMPACT_MARKERS["positive"], "[+]")
        self.assertEqual(IMPACT_MARKERS["negative"], "[-]")
        self.assertEqual(IMPACT_MARKERS["neutral"], "[=]")
        self.assertEqual(IMPACT_MARKERS["needs_review"], "[?]")


if __name__ == "__main__":
    unittest.main()
