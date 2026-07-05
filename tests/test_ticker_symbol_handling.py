import unittest

from cli.utils import normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context


class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_build_instrument_context_mentions_korean_stock_code(self):
        context = build_instrument_context("삼성전자")
        self.assertIn("005930", context)
        self.assertIn("삼성전자", context)


if __name__ == "__main__":
    unittest.main()
