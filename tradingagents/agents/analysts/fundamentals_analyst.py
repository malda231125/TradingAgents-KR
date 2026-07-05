import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.dataflows.prefetch import prefetch_fundamentals_packet
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed, invoke_with_trace


def create_fundamentals_analyst(llm):
    node_name = "Fundamentals Analyst"

    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # Build the structured fundamentals feature packet (replaces the
        # legacy prefetch_fundamentals_data text blob — reduces analyst
        # prompt size from ~26k chars to ~2k while preserving essential
        # valuation/profitability/balance-sheet/momentum signals).
        emit_runtime_trace(
            "step.start",
            node=node_name,
            step="prefetch_fundamentals_packet",
            ticker=ticker,
            trade_date=current_date,
        )
        step_started = time.perf_counter()
        packet = prefetch_fundamentals_packet(ticker, current_date)
        packet_block = packet.to_prompt_block()
        emit_runtime_trace(
            "step.end",
            node=node_name,
            step="prefetch_fundamentals_packet",
            ticker=ticker,
            trade_date=current_date,
            elapsed=format_elapsed(time.perf_counter() - step_started),
            packet_chars=len(packet_block),
        )

        system_message = (
            "You are a Korea-market fundamentals analyst. Your task is to evaluate the company in a way that is useful "
            "for Korean equity trading and position sizing, not just to summarize accounting statements.\n\n"
            "Focus on these priorities:\n"
            "1. Financial quality and stability\n"
            "2. Earnings power and whether profitability is improving or deteriorating\n"
            "3. Balance-sheet pressure, leverage, and financing risk\n"
            "4. Whether current fundamentals support the market narrative\n"
            "5. Whether the stock looks driven by real earnings power or by short-term theme/speculation\n\n"
            "Instructions:\n"
            "- The financial data has been preprocessed into the structured feature packet below.\n"
            "- The `peer_context` block (when present) contains DART-sourced sector peer median values "
            "and ranks the target stock against its actual industry peers. THIS is the authoritative "
            "baseline — use it instead of any general 'good ROE / bad ROE' rules of thumb.\n"
            "- The `global_peer_context` block (when present) is SEC EDGAR-sourced overseas peer context. "
            "Use it only as a read-through signal for global demand, customer/supply-chain conditions, or sector risk. "
            "Do NOT treat it as a substitute for the target company's KIS/DART fundamentals.\n"
            "- When `peer_context` is null, the packet has NO industry baseline. In that case you must "
            "explicitly note that industry comparison is unavailable and apply your own knowledge of the "
            "industry the company operates in. Do NOT make up authoritative classifications you cannot back up.\n"
            "- The `data_quality_notes` block calls out limitations explicitly. Most importantly, the cashflow figures "
            "are an INFERRED proxy from KIS, not an official cashflow statement. Any conclusion that depends on cashflow "
            "must acknowledge that.\n"
            "- Distinguish between:\n"
            "  - strong underlying business quality\n"
            "  - acceptable but weakening fundamentals\n"
            "  - weak or fragile financial structure\n"
            "- Build your interpretation on top of the peer ranks and the raw YoY growth rates — do not "
            "merely restate them. Explain what each rank/diff means for an actual trading decision.\n"
            "- If the company may be tradable for momentum reasons despite mediocre fundamentals, separate that "
            "from a genuine quality thesis.\n\n"
            "At the end, append a concise Markdown table that summarizes:\n"
            "- category\n"
            "- evidence\n"
            "- interpretation\n"
            "- implication for trading/investing\n\n"
            f"For your reference, the current date is {current_date}. {instrument_context}\n\n"
            "--- FUNDAMENTALS FEATURE PACKET ---\n\n"
            f"{packet_block}"
            f"{lang_instruction}"
        )

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(
                content=f"Analyze the fundamentals for {ticker} as of {current_date} and produce your fundamentals analysis report."
            ),
        ]

        result = invoke_with_trace(node_name, llm, messages)

        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content), tool_calls=[])
        elif not hasattr(result, "tool_calls") or result.tool_calls is None:
            result.tool_calls = []

        return {
            "messages": [result],
            "fundamentals_report": result.content,
        }

    return fundamentals_analyst_node
