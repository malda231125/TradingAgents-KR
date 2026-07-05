"""Tests for Korean data layer configuration.

Verifies:
1. Default config uses KIS for market data vendors
2. Default config uses CLI provider
3. Naver news module is registered in interface
4. Naver news functions handle missing credentials gracefully
5. Direct news vendor config remains stable while the main news prefetch path can merge sources
"""

import unittest
from unittest.mock import patch, MagicMock

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.interface import (
    VENDOR_METHODS,
    VENDOR_LIST,
    get_multi_source_vendors,
    get_route_vendors,
    route_to_vendor,
)


class TestDefaultConfigKoreanVendors(unittest.TestCase):
    """Verify default config points to Korean-market vendors."""

    def test_core_stock_default_is_kis(self):
        self.assertEqual(DEFAULT_CONFIG["data_vendors"]["core_stock_apis"], "kis")

    def test_indicators_default_is_kis(self):
        self.assertEqual(DEFAULT_CONFIG["data_vendors"]["technical_indicators"], "kis")

    def test_fundamental_default_is_kis(self):
        self.assertEqual(DEFAULT_CONFIG["data_vendors"]["fundamental_data"], "kis")

    def test_news_default_is_naver_then_yfinance(self):
        """Direct news routing prefers Naver first, then yfinance as a supplemental view."""
        self.assertEqual(DEFAULT_CONFIG["data_vendors"]["news_data"], "naver,yfinance")

    def test_multi_source_news_defaults(self):
        self.assertEqual(
            DEFAULT_CONFIG["multi_source_vendors"]["get_news"],
            "naver,yfinance",
        )
        self.assertEqual(
            DEFAULT_CONFIG["multi_source_vendors"]["get_global_news"],
            "naver,yfinance",
        )

    def test_insider_transactions_prefers_dart(self):
        self.assertEqual(
            DEFAULT_CONFIG["tool_vendors"]["get_insider_transactions"],
            "dart",
        )

    def test_llm_provider_is_cli(self):
        # Provider is CLI-first; the exact one is auto-detected (codex preferred).
        self.assertIn(DEFAULT_CONFIG["llm_provider"], ("claude-cli", "codex-cli"))

    def test_think_models_match_resolved_provider_defaults(self):
        # With model env vars unset, quick/deep follow the resolved provider's
        # defaults (auto-detected). This stays deterministic across machines.
        import os
        from tradingagents.default_config import get_cli_model_defaults

        expected = get_cli_model_defaults(DEFAULT_CONFIG["llm_provider"])
        if not os.getenv("TRADINGAGENTS_QUICK_MODEL"):
            self.assertEqual(DEFAULT_CONFIG["quick_think_llm"], expected["quick"])
        if not os.getenv("TRADINGAGENTS_DEEP_MODEL"):
            self.assertEqual(DEFAULT_CONFIG["deep_think_llm"], expected["deep"])


class TestNaverVendorRegistered(unittest.TestCase):
    """Verify Naver is registered as a vendor in interface.py."""

    def test_naver_in_vendor_list(self):
        self.assertIn("naver", VENDOR_LIST)

    def test_naver_in_get_news_vendors(self):
        self.assertIn("naver", VENDOR_METHODS["get_news"])

    def test_naver_in_get_global_news_vendors(self):
        self.assertIn("naver", VENDOR_METHODS["get_global_news"])


class TestNaverNewsModule(unittest.TestCase):
    """Test Naver news module error handling."""

    def test_naver_available_returns_false_without_credentials(self):
        from tradingagents.dataflows.naver_news import _naver_available
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_naver_available())

    def test_naver_available_returns_true_with_credentials(self):
        from tradingagents.dataflows.naver_news import _naver_available
        with patch.dict("os.environ", {
            "NAVER_CLIENT_ID": "test_id",
            "NAVER_CLIENT_SECRET": "test_secret",
        }):
            self.assertTrue(_naver_available())

    def test_get_news_naver_raises_without_credentials(self):
        from tradingagents.dataflows.naver_news import get_news_naver
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                get_news_naver("삼성전자", "2026-03-20", "2026-03-27")

    def test_clean_html_removes_tags(self):
        from tradingagents.dataflows.naver_news import _clean_html
        self.assertEqual(_clean_html("<b>hello</b>"), "hello")
        self.assertEqual(_clean_html("a &amp; b"), "a & b")
        self.assertEqual(_clean_html("&quot;test&quot;"), '"test"')

    def test_format_news_items_empty(self):
        from tradingagents.dataflows.naver_news import _format_news_items
        self.assertEqual(_format_news_items([]), "No news articles found.")

    def test_format_news_items_basic(self):
        from tradingagents.dataflows.naver_news import _format_news_items
        items = [{
            "title": "<b>Test</b> News",
            "description": "Description here",
            "pubDate": "Thu, 27 Mar 2026 10:00:00 +0900",
            "originallink": "https://example.com/article",
        }]
        result = _format_news_items(items)
        self.assertIn("[1] Test News", result)
        self.assertIn("Description here", result)

    @patch("tradingagents.dataflows.naver_news.requests.get")
    def test_search_naver_news_success(self, mock_get):
        from tradingagents.dataflows.naver_news import _search_naver_news

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 1,
            "items": [{"title": "test", "description": "desc"}],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {
            "NAVER_CLIENT_ID": "id",
            "NAVER_CLIENT_SECRET": "secret",
        }):
            result = _search_naver_news("삼성전자")
            self.assertEqual(result["total"], 1)
            mock_get.assert_called_once()


class TestKisVendorInMethods(unittest.TestCase):
    """Verify KIS is registered for all expected data methods."""

    def test_kis_in_stock_data(self):
        self.assertIn("kis", VENDOR_METHODS["get_stock_data"])

    def test_kis_in_indicators(self):
        self.assertIn("kis", VENDOR_METHODS["get_indicators"])

    def test_kis_in_fundamentals(self):
        self.assertIn("kis", VENDOR_METHODS["get_fundamentals"])

    def test_kis_in_balance_sheet(self):
        self.assertIn("kis", VENDOR_METHODS["get_balance_sheet"])

    def test_kis_in_cashflow(self):
        self.assertIn("kis", VENDOR_METHODS["get_cashflow"])

    def test_kis_in_income_statement(self):
        self.assertIn("kis", VENDOR_METHODS["get_income_statement"])

    def test_kis_in_insider_transactions(self):
        self.assertIn("kis", VENDOR_METHODS["get_insider_transactions"])


class TestRoutingSemantics(unittest.TestCase):
    """Verify explicit routing vs merged multi-source selection semantics."""

    @patch(
        "tradingagents.dataflows.interface.get_config",
        return_value={"data_vendors": {"core_stock_apis": "kis"}, "tool_vendors": {}},
    )
    def test_structured_route_vendors_do_not_append_all_registered(self, _mock_config):
        self.assertEqual(get_route_vendors("get_stock_data"), ["kis"])

    @patch(
        "tradingagents.dataflows.interface.get_config",
        return_value={"data_vendors": {"news_data": "naver,yfinance"}, "tool_vendors": {}},
    )
    def test_direct_news_route_keeps_explicit_order(self, _mock_config):
        self.assertEqual(get_route_vendors("get_news"), ["naver", "yfinance"])

    @patch("tradingagents.dataflows.interface.get_config", return_value={})
    @patch(
        "tradingagents.dataflows.interface.VENDOR_METHODS",
        {
            "get_news": {
                "naver": lambda *a: "kr",
                "alpha_vantage": lambda *a: "legacy",
                "yfinance": lambda *a: "global",
            },
        },
    )
    def test_multi_source_news_defaults_exclude_legacy_vendor(self, _mock_config):
        self.assertEqual(get_multi_source_vendors("get_news"), ["naver", "yfinance"])

    @patch(
        "tradingagents.dataflows.interface.get_config",
        return_value={"data_vendors": {"news_data": "naver,yfinance"}, "tool_vendors": {}},
    )
    @patch(
        "tradingagents.dataflows.interface.VENDOR_METHODS",
        {
            "get_news": {
                "naver": lambda *a: (_ for _ in ()).throw(RuntimeError("naver down")),
                "yfinance": lambda *a: "global fallback",
            },
        },
    )
    def test_explicit_multi_vendor_route_can_fall_through(self, _mock_config):
        result = route_to_vendor("get_news", "005930", "2026-03-20", "2026-03-27")
        self.assertEqual(result, "global fallback")


if __name__ == "__main__":
    unittest.main()
