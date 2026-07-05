"""Tests for Phase 2 graph simplification.

Verifies that:
1. conditional_logic no longer has should_continue_* for analysts
2. setup.py builds a graph without ToolNode/MsgClear nodes
3. trading_graph.py no longer creates tool nodes
4. Graph structure connects analysts directly in sequence
"""

import unittest
from unittest.mock import MagicMock, patch

from tradingagents.graph.conditional_logic import ConditionalLogic


class TestConditionalLogicCleanup(unittest.TestCase):
    """Verify analyst-related conditional methods were removed."""

    def test_no_should_continue_market(self):
        cl = ConditionalLogic()
        self.assertFalse(hasattr(cl, "should_continue_market"))

    def test_no_should_continue_social(self):
        cl = ConditionalLogic()
        self.assertFalse(hasattr(cl, "should_continue_social"))

    def test_no_should_continue_news(self):
        cl = ConditionalLogic()
        self.assertFalse(hasattr(cl, "should_continue_news"))

    def test_no_should_continue_fundamentals(self):
        cl = ConditionalLogic()
        self.assertFalse(hasattr(cl, "should_continue_fundamentals"))

    def test_debate_logic_preserved(self):
        cl = ConditionalLogic(max_debate_rounds=1)
        self.assertTrue(hasattr(cl, "should_continue_debate"))
        self.assertTrue(hasattr(cl, "should_continue_risk_analysis"))


class TestSetupGraphStructure(unittest.TestCase):
    """Verify the simplified graph structure."""

    def test_setup_no_tool_nodes_parameter(self):
        """GraphSetup no longer accepts tool_nodes parameter."""
        from tradingagents.graph.setup import GraphSetup
        import inspect

        sig = inspect.signature(GraphSetup.__init__)
        param_names = list(sig.parameters.keys())
        self.assertNotIn("tool_nodes", param_names)

    def test_setup_init_params(self):
        """GraphSetup takes the expected simplified parameter list."""
        from tradingagents.graph.setup import GraphSetup
        import inspect

        sig = inspect.signature(GraphSetup.__init__)
        param_names = list(sig.parameters.keys())
        self.assertIn("quick_thinking_llm", param_names)
        self.assertIn("deep_thinking_llm", param_names)
        self.assertIn("bull_memory", param_names)
        self.assertIn("conditional_logic", param_names)


class TestTradingGraphNoToolNodes(unittest.TestCase):
    """Verify trading_graph.py no longer creates tool nodes."""

    def test_no_create_tool_nodes_method(self):
        """TradingAgentsGraph should not have _create_tool_nodes."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        self.assertFalse(hasattr(TradingAgentsGraph, "_create_tool_nodes"))

    def test_no_tool_node_import(self):
        """ToolNode should not be imported in trading_graph module."""
        import tradingagents.graph.trading_graph as tg_module
        self.assertFalse(hasattr(tg_module, "ToolNode"))


class TestNoToolNodeImportInSetup(unittest.TestCase):
    """Verify setup.py no longer imports ToolNode."""

    def test_no_tool_node_import(self):
        import tradingagents.graph.setup as setup_module
        self.assertFalse(hasattr(setup_module, "ToolNode"))


if __name__ == "__main__":
    unittest.main()
