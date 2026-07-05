"""Tests for the prefetch module and refactored analyst nodes.

These tests verify:
1. prefetch functions produce structured output with correct sections
2. prefetch handles vendor errors gracefully
3. analyst nodes work with prefetched data (no bind_tools dependency)
4. analyst nodes return correct state keys
"""

import tempfile
import unittest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

from tradingagents.dataflows.prefetch import (
    prefetch_market_data,
    prefetch_news_data,
    prefetch_fundamentals_data,
    prefetch_social_data,
    MARKET_INDICATORS,
    _safe_fetch,
)

# Use a fresh temp cache dir for each test class to avoid cross-test contamination
_CACHE_MOCK = patch(
    "tradingagents.dataflows.prefetch.get_config",
    return_value={"data_cache_dir": tempfile.mkdtemp()},
)
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst


class TestSafeFetch(unittest.TestCase):
    """Test the _safe_fetch error-handling wrapper."""

    def test_successful_fetch(self):
        result = _safe_fetch("Test Label", lambda: "data here")
        self.assertIn("## Test Label", result)
        self.assertIn("data here", result)

    def test_failed_fetch_returns_error_note(self):
        def failing_func():
            raise ConnectionError("network down")

        result = _safe_fetch("Broken Source", failing_func)
        self.assertIn("## Broken Source", result)
        self.assertIn("[Data unavailable:", result)
        self.assertIn("network down", result)


class TestPrefetchMarketData(unittest.TestCase):
    """Test prefetch_market_data assembles all expected sections."""

    def setUp(self):
        self._cache_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": tempfile.mkdtemp()},
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()

    @patch("tradingagents.dataflows.prefetch.route_to_vendor")
    def test_returns_stock_data_and_all_indicators(self, mock_route):
        mock_route.return_value = "mock data"

        result = prefetch_market_data("005930", "2026-03-27")

        self.assertIn("## Stock Price Data (OHLCV)", result)
        for indicator in MARKET_INDICATORS:
            self.assertIn(f"## Indicator: {indicator}", result)

        # 1 stock data + 8 indicators + 1 macro summary = 10 total
        self.assertEqual(mock_route.call_count, 1 + len(MARKET_INDICATORS) + 1)

    @patch("tradingagents.dataflows.prefetch.route_to_vendor")
    def test_handles_partial_failures(self, mock_route):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                raise RuntimeError("indicator failed")
            return "ok"

        mock_route.side_effect = side_effect
        result = prefetch_market_data("005930", "2026-03-27")

        self.assertIn("[Data unavailable:", result)
        self.assertIn("ok", result)

    @patch("tradingagents.dataflows.prefetch.route_to_vendor")
    def test_date_calculation(self, mock_route):
        mock_route.return_value = "data"
        prefetch_market_data("005930", "2026-03-27", lookback_days=60)

        first_call_args = mock_route.call_args_list[0]
        # get_stock_data call: route_to_vendor("get_stock_data", ticker, start_date, end_date)
        self.assertEqual(first_call_args[0][0], "get_stock_data")
        self.assertEqual(first_call_args[0][1], "005930")
        self.assertEqual(first_call_args[0][2], "2026-01-26")  # 60 days before 03-27
        self.assertEqual(first_call_args[0][3], "2026-03-27")


class TestPrefetchNewsData(unittest.TestCase):
    """Test prefetch_news_data multi-source aggregation."""

    def setUp(self):
        self._cache_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": tempfile.mkdtemp()},
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()

    @patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
        "get_news": {
            "naver": lambda *a: "네이버 뉴스 결과",
            "alpha_vantage": lambda *a: "legacy alpha news",
            "yfinance": lambda *a: "yfinance news results",
        },
        "get_global_news": {
            "naver": lambda *a: "네이버 글로벌 뉴스",
            "alpha_vantage": lambda *a: "legacy alpha global",
            "yfinance": lambda *a: "yfinance global news",
        },
    })
    def test_returns_multi_source_news(self):
        result = prefetch_news_data("005930", "2026-03-27")

        self.assertIn("네이버 뉴스", result)
        self.assertIn("yfinance news", result)
        self.assertIn("네이버 글로벌", result)
        self.assertIn("yfinance global", result)
        self.assertIn("[naver]", result)
        self.assertIn("[yfinance]", result)
        self.assertNotIn("legacy alpha", result)

    @patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
        "get_news": {
            "naver": lambda *a: "네이버 뉴스",
            "yfinance": lambda *a: "yfinance news",
        },
        "get_global_news": {
            "naver": lambda *a: "global kr",
            "yfinance": lambda *a: "global en",
        },
    })
    def test_includes_dedup_note(self):
        result = prefetch_news_data("005930", "2026-03-27")
        self.assertIn("duplicate", result.lower())

    @patch(
        "tradingagents.dataflows.prefetch.get_multi_source_vendors",
        return_value=["naver", "yfinance"],
    )
    @patch("tradingagents.dataflows.prefetch.get_vendor_callable")
    def test_company_name_adapts_to_vendor_specific_news_identifiers(
        self,
        mock_get_vendor_callable,
        _mock_vendors,
    ):
        seen_args = {}

        def side_effect(method, vendor_name):
            def impl(*args):
                seen_args[(method, vendor_name)] = args
                return f"{vendor_name}:{method}"
            return impl

        mock_get_vendor_callable.side_effect = side_effect

        result = prefetch_news_data("삼성전자", "2026-03-27")

        self.assertEqual(seen_args[("get_news", "naver")][0], "삼성전자")
        self.assertEqual(seen_args[("get_news", "yfinance")][0], "005930")
        self.assertIn("[naver]", result)
        self.assertIn("[yfinance]", result)

    @patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
        "get_news": {
            "naver": lambda *a: (_ for _ in ()).throw(RuntimeError("naver down")),
            "yfinance": lambda *a: (_ for _ in ()).throw(RuntimeError("yf down")),
        },
        "get_global_news": {
            "naver": lambda *a: (_ for _ in ()).throw(RuntimeError("naver global down")),
            "yfinance": lambda *a: (_ for _ in ()).throw(RuntimeError("yf global down")),
        },
    })
    @patch("tradingagents.dataflows.prefetch.route_to_vendor")
    def test_fallback_when_all_vendors_fail(self, mock_route):
        mock_route.return_value = "fallback news"
        result = prefetch_news_data("005930", "2026-03-27")
        self.assertIn("fallback news", result)


class TestPrefetchFundamentalsData(unittest.TestCase):
    """Test prefetch_fundamentals_data assembles all financial sections."""

    def setUp(self):
        self._cache_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": tempfile.mkdtemp()},
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()

    @patch("tradingagents.dataflows.prefetch.route_to_vendor")
    def test_returns_all_sections(self, mock_route):
        mock_route.return_value = "financial data"

        result = prefetch_fundamentals_data("005930", "2026-03-27")

        self.assertIn("## Company Fundamentals", result)
        self.assertIn("## Balance Sheet (Quarterly)", result)
        self.assertIn("## Cash Flow (Quarterly)", result)
        self.assertIn("## Income Statement (Quarterly)", result)
        self.assertEqual(mock_route.call_count, 4)


class TestPrefetchSocialData(unittest.TestCase):
    """Test prefetch_social_data assembles social/news section."""

    def setUp(self):
        self._cache_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": tempfile.mkdtemp()},
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()

    @patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
        "get_news": {
            "naver": lambda *a: "국내 뉴스",
            "yfinance": lambda *a: "global lens",
        },
    })
    def test_returns_social_section(self):
        result = prefetch_social_data("005930", "2026-03-27")

        self.assertIn("## Social/News Data [naver]", result)
        self.assertIn("## Social/News Data [yfinance]", result)


class TestAnalystNodes(unittest.TestCase):
    """Test that refactored analyst nodes work without bind_tools."""

    def _make_mock_llm(self, response_text="Mock analyst report"):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content=response_text, tool_calls=[]
        )
        return mock_llm

    def _make_state(self, ticker="005930", date="2026-03-27"):
        return {
            "trade_date": date,
            "company_of_interest": ticker,
            "messages": [],
        }

    @patch("tradingagents.agents.analysts.market_analyst.prefetch_market_packet")
    def test_market_analyst_returns_report(self, mock_prefetch):
        from tradingagents.dataflows.feature_packets import MarketPacket

        mock_prefetch.return_value = MarketPacket(
            instrument={"name": "삼성전자", "stock_code": "005930"},
            as_of="2026-03-27",
            price={}, moving_averages={}, volume={}, volatility={},
            technical_indicators={},
            regime={"label": "above_trend", "description": "test"},
            signals=["test signal"],
            macro_highlights=[],
        )
        llm = self._make_mock_llm("Market analysis complete.")

        node = create_market_analyst(llm)
        result = node(self._make_state())

        self.assertEqual(result["market_report"], "Market analysis complete.")
        self.assertEqual(len(result["messages"]), 1)
        self.assertIsInstance(result["messages"][0], AIMessage)
        self.assertEqual(result["messages"][0].tool_calls, [])
        mock_prefetch.assert_called_once_with("005930", "2026-03-27")
        llm.invoke.assert_called_once()

    @patch("tradingagents.agents.analysts.news_analyst.prefetch_news_packet")
    def test_news_analyst_returns_report(self, mock_prefetch):
        from tradingagents.dataflows.feature_packets import NewsPacket

        mock_prefetch.return_value = NewsPacket(
            instrument={"name": "삼성전자", "stock_code": "005930"},
            as_of="2026-03-27",
            company_catalysts=[],
            macro_news=[],
            noise_count=0,
        )
        llm = self._make_mock_llm("News analysis complete.")

        node = create_news_analyst(llm)
        result = node(self._make_state())

        self.assertEqual(result["news_report"], "News analysis complete.")
        self.assertEqual(len(result["messages"]), 1)
        self.assertIsInstance(result["messages"][0], AIMessage)
        mock_prefetch.assert_called_once()

    @patch("tradingagents.agents.analysts.fundamentals_analyst.prefetch_fundamentals_packet")
    def test_fundamentals_analyst_returns_report(self, mock_prefetch):
        from tradingagents.dataflows.feature_packets import FundamentalsPacket

        mock_prefetch.return_value = FundamentalsPacket(
            instrument={"name": "삼성전자", "stock_code": "005930"},
            as_of="2026-03-27",
            valuation={}, profitability={}, balance_sheet={}, earnings_momentum={},
            signals=["test signal"],
            peer_context=None,
        )
        llm = self._make_mock_llm("Fundamentals analysis complete.")

        node = create_fundamentals_analyst(llm)
        result = node(self._make_state())

        self.assertEqual(result["fundamentals_report"], "Fundamentals analysis complete.")
        self.assertEqual(len(result["messages"]), 1)
        mock_prefetch.assert_called_once()

    @patch("tradingagents.agents.analysts.social_media_analyst.prefetch_social_data")
    def test_social_analyst_returns_report(self, mock_prefetch):
        mock_prefetch.return_value = "## Social\nmock social"
        llm = self._make_mock_llm("Sentiment analysis complete.")

        node = create_social_media_analyst(llm)
        result = node(self._make_state())

        self.assertEqual(result["sentiment_report"], "Sentiment analysis complete.")
        self.assertEqual(len(result["messages"]), 1)
        mock_prefetch.assert_called_once()

    @patch("tradingagents.agents.analysts.market_analyst.prefetch_market_packet")
    def test_analyst_handles_non_aimessage_response(self, mock_prefetch):
        """Ensure analyst wraps non-AIMessage responses properly."""
        from tradingagents.dataflows.feature_packets import MarketPacket

        mock_prefetch.return_value = MarketPacket(
            instrument={"name": "삼성전자", "stock_code": "005930"},
            as_of="2026-03-27",
            price={}, moving_averages={}, volume={}, volatility={},
            technical_indicators={},
            regime={"label": "above_trend", "description": "test"},
            signals=["test signal"],
            macro_highlights=[],
        )
        llm = MagicMock()
        # Simulate an LLM that returns something with .content but not AIMessage
        mock_response = MagicMock()
        mock_response.content = "wrapped response"
        mock_response.tool_calls = None
        # Make isinstance check fail for AIMessage
        type(mock_response).__name__ = "SomeOtherMessage"
        llm.invoke.return_value = AIMessage(content="wrapped response", tool_calls=[])

        node = create_market_analyst(llm)
        result = node(self._make_state())

        self.assertEqual(result["market_report"], "wrapped response")
        self.assertEqual(result["messages"][0].tool_calls, [])


class TestAnalystGraphCompatibility(unittest.TestCase):
    """Test that analyst nodes remain compatible with the existing graph structure.

    The graph's conditional_logic checks `messages[-1].tool_calls` to decide
    whether to route to the tool node or to Msg Clear. With prefetch, analysts
    should always produce messages with empty tool_calls, causing the graph to
    skip the tool node and go straight to Msg Clear.
    """

    @patch("tradingagents.agents.analysts.market_analyst.prefetch_market_packet")
    def test_market_analyst_tool_calls_empty(self, mock_prefetch):
        from tradingagents.dataflows.feature_packets import MarketPacket

        mock_prefetch.return_value = MarketPacket(
            instrument={"name": "삼성전자", "stock_code": "005930"},
            as_of="2026-03-27",
            price={}, moving_averages={}, volume={}, volatility={},
            technical_indicators={},
            regime={"label": "above_trend", "description": "test"},
            signals=["test signal"],
            macro_highlights=[],
        )
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="report", tool_calls=[])

        node = create_market_analyst(llm)
        result = node({
            "trade_date": "2026-03-27",
            "company_of_interest": "005930",
            "messages": [],
        })

        last_message = result["messages"][-1]
        self.assertEqual(last_message.tool_calls, [])


if __name__ == "__main__":
    unittest.main()
