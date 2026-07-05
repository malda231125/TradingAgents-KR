import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.dataflows.prefetch import prefetch_market_packet
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed, invoke_with_trace


def create_market_analyst(llm):
    node_name = "Market Analyst"

    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # Build the structured market feature packet (replaces the legacy
        # prefetch_market_data text blob — reduces analyst prompt size from
        # ~15k chars to ~2k while preserving essential signals).
        emit_runtime_trace(
            "step.start",
            node=node_name,
            step="prefetch_market_packet",
            ticker=ticker,
            trade_date=current_date,
        )
        step_started = time.perf_counter()
        packet = prefetch_market_packet(ticker, current_date)
        packet_block = packet.to_prompt_block()
        emit_runtime_trace(
            "step.end",
            node=node_name,
            step="prefetch_market_packet",
            ticker=ticker,
            trade_date=current_date,
            elapsed=format_elapsed(time.perf_counter() - step_started),
            packet_chars=len(packet_block),
        )

        system_message = (
            "You are a Korea-market trading analyst. Your job is not to produce a generic US-style macro note. "
            "Your job is to interpret market structure for Korean equities in a way that is useful for actual trading decisions.\n\n"
            "Focus on the following priorities:\n"
            "1. Price structure and trend persistence\n"
            "2. Volume confirmation and abnormal participation\n"
            "3. Volatility regime and whether the stock is trending, exhausted, or range-bound\n"
            "4. Korean market context such as KOSPI/KOSDAQ behavior, sector rotation, and event-driven moves\n"
            "5. Whether the current chart behavior is compatible with a momentum trade, mean-reversion trade, or no-trade stance\n\n"
            "Instructions:\n"
            "- The market data has been preprocessed into the structured feature packet below.\n"
            "- Treat the `signals` and `regime` fields as deterministic observations — do NOT recompute them.\n"
            "- Build your analysis ON TOP of those signals: explain *why* they matter, how they fit together, and what they imply for an actual trading decision.\n"
            "- The `sector_context` block (when present) tells you the stock's relative performance versus its KIS sector index. Use this to distinguish 'this stock is moving with its sector' (low conviction trade) from 'this stock is moving against its sector' (high conviction trade).\n"
            "- If `sector_context` is missing (set to null or absent), this stock has no curated sector mapping — explicitly note that sector relative performance is unknown and avoid implying sector context that you do not have.\n"
            "- The `investor_flow` block is KIS foreign/institutional net-buy evidence. For Korean large caps, treat it as a core setup-quality input alongside price and volume: foreign accumulation/distribution, institutional absorption, and combined selling/buying pressure can confirm or invalidate the chart setup.\n"
            "- The `us_macro_context` and `global_risk_context` blocks, when present, are FRED-based overseas risk filters. Use them only when the connection to Korean equities is direct: rates, USD/KRW pressure, foreign flow, risk-off moves, semiconductors, batteries, autos, banks, or high-beta growth stocks.\n"
            "- The `evidence_refs` list points to the underlying raw data sources if you need to caveat anything.\n"
            "- Do not force a bullish or bearish conclusion if the regime is ambiguous.\n"
            "- Explicitly distinguish between trend continuation, short-term noise, overextension, and invalid setups.\n"
            "- If volume does not confirm the move, say so clearly.\n"
            "- If the setup looks like a policy/theme spike rather than a durable trend, say so clearly.\n"
            "- Do not let US macro override the KIS price/volume setup by itself. Treat it as a risk/regime filter, not a standalone buy/sell signal.\n\n"
            "The report should be detailed, evidence-based, and directly useful for a trader who needs to judge setup quality "
            "rather than read a generic commentary.\n\n"
            "At the end, append a concise Markdown table that summarizes:\n"
            "- signal\n"
            "- evidence\n"
            "- implication for trade\n\n"
            f"For your reference, the current date is {current_date}. {instrument_context}\n\n"
            "--- MARKET FEATURE PACKET ---\n\n"
            f"{packet_block}"
            f"{lang_instruction}"
        )

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(
                content=f"Analyze the market data for {ticker} as of {current_date} and produce your trading analysis report."
            ),
        ]

        result = invoke_with_trace(node_name, llm, messages)

        # Ensure result is AIMessage with empty tool_calls for graph compatibility
        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content), tool_calls=[])
        elif not hasattr(result, "tool_calls") or result.tool_calls is None:
            result.tool_calls = []

        return {
            "messages": [result],
            "market_report": result.content,
        }

    return market_analyst_node
