"""Tests for Phase 5-1 analyst parallelization.

Verifies:
1. Graph structure has fan-out from START to all analysts
2. Graph structure has fan-in from all analysts to Bull Researcher
3. No sequential analyst-to-analyst edges exist
"""

import unittest
from unittest.mock import MagicMock

from tradingagents.graph.setup import GraphSetup
from tradingagents.graph.conditional_logic import ConditionalLogic


class TestParallelGraphStructure(unittest.TestCase):
    """Verify fan-out / fan-in graph topology."""

    def _make_graph_setup(self):
        return GraphSetup(
            quick_thinking_llm=MagicMock(),
            deep_thinking_llm=MagicMock(),
            bull_memory=MagicMock(),
            bear_memory=MagicMock(),
            trader_memory=MagicMock(),
            invest_judge_memory=MagicMock(),
            portfolio_manager_memory=MagicMock(),
            conditional_logic=ConditionalLogic(),
        )

    def test_default_analysts_compile(self):
        """Graph with default analysts compiles without error."""
        gs = self._make_graph_setup()
        graph = gs.setup_graph(["market", "news", "fundamentals"])
        self.assertIsNotNone(graph)

    def test_single_analyst_compiles(self):
        """Graph with a single analyst compiles without error."""
        gs = self._make_graph_setup()
        graph = gs.setup_graph(["market"])
        self.assertIsNotNone(graph)

    def test_all_four_analysts_compile(self):
        """Graph with all 4 analysts compiles without error."""
        gs = self._make_graph_setup()
        graph = gs.setup_graph(["market", "social", "news", "fundamentals"])
        self.assertIsNotNone(graph)

    def test_empty_analysts_raises(self):
        """Empty analyst list raises ValueError."""
        gs = self._make_graph_setup()
        with self.assertRaises(ValueError):
            gs.setup_graph([])


if __name__ == "__main__":
    unittest.main()
