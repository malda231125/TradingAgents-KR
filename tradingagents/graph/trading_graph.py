# TradingAgents/graph/trading_graph.py

import os
import time
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from tradingagents.llm_clients import create_llm_client

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        self.selected_analysts = list(selected_analysts)

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()

        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.portfolio_manager_memory = FinancialSituationMemory("portfolio_manager_memory", self.config)

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.portfolio_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        elif provider in ("claude-cli", "codex-cli"):
            timeout = self.config.get("cli_timeout")
            if timeout:
                kwargs["timeout"] = timeout
            max_retries = self.config.get("cli_max_retries")
            if max_retries:
                kwargs["max_retries"] = max_retries
            # Reasoning effort is Claude-CLI only (--effort flag).
            if provider == "claude-cli":
                effort = self.config.get("cli_effort") or self.config.get("anthropic_effort")
                if effort:
                    kwargs["effort"] = effort

        return kwargs

    def propagate(self, company_name, trade_date, self_loop_context: str | None = None):
        """Run the trading agents graph for a company on a specific date."""

        self.ticker = company_name
        started = time.perf_counter()
        emit_runtime_trace(
            "graph.start",
            ticker=company_name,
            trade_date=trade_date,
            analysts=",".join(self.selected_analysts),
            provider=self.config.get("llm_provider"),
            quick_model=self.config.get("quick_think_llm"),
            deep_model=self.config.get("deep_think_llm"),
        )

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, self_loop_context=self_loop_context
        )
        args = self.propagator.get_graph_args()

        try:
            if self.debug:
                # Debug mode with tracing
                trace = []
                for chunk in self.graph.stream(init_agent_state, **args):
                    if len(chunk["messages"]) == 0:
                        pass
                    else:
                        chunk["messages"][-1].pretty_print()
                        trace.append(chunk)

                final_state = trace[-1]
            else:
                # Standard mode without tracing
                final_state = self.graph.invoke(init_agent_state, **args)
        except Exception as exc:
            emit_runtime_trace(
                "graph.fail",
                ticker=company_name,
                trade_date=trade_date,
                elapsed=format_elapsed(time.perf_counter() - started),
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

        # Store current state for reflection
        if self_loop_context:
            final_state["self_loop_context"] = self_loop_context
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        signal = self.process_signal(final_state["final_trade_decision"])
        emit_runtime_trace(
            "graph.end",
            ticker=company_name,
            trade_date=trade_date,
            elapsed=format_elapsed(time.perf_counter() - started),
            signal=signal,
        )
        return final_state, signal

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
            "self_loop_context": final_state.get("self_loop_context") or "",
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_portfolio_manager(
            self.curr_state, returns_losses, self.portfolio_manager_memory
        )

    def batch_propagate(self, tickers: list, trade_date: str) -> dict:
        """Run analysis for multiple tickers sequentially.

        Args:
            tickers: List of ticker symbols (e.g. ["005930", "000660"])
            trade_date: Trading date in yyyy-mm-dd format

        Returns:
            Dict of {ticker: {"final_state": state, "signal": signal, "decision": str, "error": None}}
            On failure for a ticker: {"error": str, ...}
        """
        results = {}
        for ticker in tickers:
            try:
                final_state, signal = self.propagate(ticker, trade_date)
                results[ticker] = {
                    "final_state": final_state,
                    "signal": signal,
                    "decision": final_state.get("final_trade_decision", ""),
                    "error": None,
                }
            except Exception as e:
                results[ticker] = {
                    "final_state": None,
                    "signal": None,
                    "decision": None,
                    "error": str(e),
                }
        return results

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
