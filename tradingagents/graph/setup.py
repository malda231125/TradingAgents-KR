# TradingAgents/graph/setup.py

import time
from typing import Dict, Any, List
from langgraph.graph import END, StateGraph, START

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed

from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm,
        deep_thinking_llm,
        bull_memory,
        bear_memory,
        trader_memory,
        invest_judge_memory,
        portfolio_manager_memory,
        conditional_logic: ConditionalLogic,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.portfolio_manager_memory = portfolio_manager_memory
        self.conditional_logic = conditional_logic

    def _instrument_node(self, node_name: str, node):
        def wrapped(state):
            company_name = state.get("company_of_interest", "")
            trade_date = state.get("trade_date", "")
            started = time.perf_counter()
            emit_runtime_trace(
                "node.start",
                node=node_name,
                ticker=company_name,
                trade_date=trade_date,
            )
            try:
                result = node(state)
            except Exception as exc:
                emit_runtime_trace(
                    "node.fail",
                    node=node_name,
                    ticker=company_name,
                    trade_date=trade_date,
                    elapsed=format_elapsed(time.perf_counter() - started),
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise

            output_keys = ",".join(sorted(result.keys())) if isinstance(result, dict) else None
            emit_runtime_trace(
                "node.end",
                node=node_name,
                ticker=company_name,
                trade_date=trade_date,
                elapsed=format_elapsed(time.perf_counter() - started),
                output_keys=output_keys,
            )
            return result

        return wrapped

    def setup_graph(
        self, selected_analysts: List[str] = ["market", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        With the prefetch pattern, analysts no longer use tool_calls loops.
        The graph is simplified: analysts connect directly in sequence,
        without ToolNode or Msg Clear intermediaries.

        Args:
            selected_analysts: List of analyst types to include.
                Options: "market", "social", "news", "fundamentals"
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes
        analyst_nodes = {}

        if "market" in selected_analysts:
            analyst_nodes["market"] = create_market_analyst(self.quick_thinking_llm)

        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(self.quick_thinking_llm)

        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(self.quick_thinking_llm)

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(self.quick_thinking_llm)

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm, self.bull_memory
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm, self.bear_memory
        )
        research_manager_node = create_research_manager(
            self.deep_thinking_llm, self.invest_judge_memory
        )
        trader_node = create_trader(self.quick_thinking_llm, self.trader_memory)

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(
            self.deep_thinking_llm, self.portfolio_manager_memory
        )

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes directly (no ToolNode or Msg Clear intermediaries)
        for analyst_type, node in analyst_nodes.items():
            node_name = f"{analyst_type.capitalize()} Analyst"
            workflow.add_node(node_name, self._instrument_node(node_name, node))

        # Add other nodes
        workflow.add_node(
            "Bull Researcher",
            self._instrument_node("Bull Researcher", bull_researcher_node),
        )
        workflow.add_node(
            "Bear Researcher",
            self._instrument_node("Bear Researcher", bear_researcher_node),
        )
        workflow.add_node(
            "Research Manager",
            self._instrument_node("Research Manager", research_manager_node),
        )
        workflow.add_node("Trader", self._instrument_node("Trader", trader_node))
        workflow.add_node(
            "Aggressive Analyst",
            self._instrument_node("Aggressive Analyst", aggressive_analyst),
        )
        workflow.add_node(
            "Neutral Analyst",
            self._instrument_node("Neutral Analyst", neutral_analyst),
        )
        workflow.add_node(
            "Conservative Analyst",
            self._instrument_node("Conservative Analyst", conservative_analyst),
        )
        workflow.add_node(
            "Portfolio Manager",
            self._instrument_node("Portfolio Manager", portfolio_manager_node),
        )

        # Fan-out: START connects to ALL analysts (parallel execution)
        # Fan-in: ALL analysts connect to Bull Researcher
        # langgraph runs all START-connected nodes concurrently and waits
        # for all to complete before proceeding to Bull Researcher.
        # Each analyst writes to a separate state key (market_report,
        # news_report, etc.) so there are no merge conflicts.
        for analyst_type in selected_analysts:
            analyst_name = f"{analyst_type.capitalize()} Analyst"
            workflow.add_edge(START, analyst_name)
            workflow.add_edge(analyst_name, "Bull Researcher")

        # Debate edges (unchanged)
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )

        workflow.add_edge("Portfolio Manager", END)

        return workflow.compile()
