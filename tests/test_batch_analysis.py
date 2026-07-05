"""Tests for Phase 5-4 multi-ticker batch analysis.

Verifies:
1. batch_propagate method exists on TradingAgentsGraph
2. batch_propagate signature accepts tickers list and trade_date
3. Bot batch_command handler exists
4. _run_batch function signature
"""

import unittest
import inspect

from tradingagents.graph.trading_graph import TradingAgentsGraph
from cli.bot import batch_command, _run_batch


class TestBatchPropagateExists(unittest.TestCase):
    """Test batch_propagate method on TradingAgentsGraph."""

    def test_method_exists(self):
        self.assertTrue(hasattr(TradingAgentsGraph, "batch_propagate"))

    def test_method_signature(self):
        sig = inspect.signature(TradingAgentsGraph.batch_propagate)
        params = list(sig.parameters.keys())
        self.assertIn("tickers", params)
        self.assertIn("trade_date", params)


class TestBotBatchCommand(unittest.TestCase):
    """Test bot batch integration."""

    def test_batch_command_callable(self):
        self.assertTrue(callable(batch_command))

    def test_run_batch_signature(self):
        sig = inspect.signature(_run_batch)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["tickers", "trade_date"])


if __name__ == "__main__":
    unittest.main()
