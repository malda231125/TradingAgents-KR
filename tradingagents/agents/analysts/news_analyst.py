import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.dataflows.prefetch import prefetch_news_packet
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed, invoke_with_trace


def create_news_analyst(llm):
    node_name = "News Analyst"

    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # Build the structured news packet via the NLU enricher. The enricher
        # uses one small upstream LLM call to convert raw articles into
        # canonical catalysts; the result is cached on disk by (ticker, date,
        # raw_news_hash) so repeat runs are free. The news_analyst then
        # interprets the structured catalysts rather than re-reading the raw
        # articles itself, shrinking the analyst prompt from ~12k chars to
        # ~3k while preserving every meaningful catalyst.
        emit_runtime_trace(
            "step.start",
            node=node_name,
            step="prefetch_news_packet",
            ticker=ticker,
            trade_date=current_date,
        )
        step_started = time.perf_counter()
        packet = prefetch_news_packet(ticker, current_date, llm)
        packet_block = packet.to_prompt_block()
        emit_runtime_trace(
            "step.end",
            node=node_name,
            step="prefetch_news_packet",
            ticker=ticker,
            trade_date=current_date,
            elapsed=format_elapsed(time.perf_counter() - step_started),
            packet_chars=len(packet_block),
        )

        system_message = (
            "You are a Korea-market news analyst. Your role is to interpret the pre-extracted news catalysts below "
            "and explain what they imply for an actual trading decision in Korean equities.\n\n"
            "Focus on these priorities:\n"
            "1. Company-specific catalysts that can move the stock\n"
            "2. Disclosure-linked events, earnings, guidance, contracts, supply issues, regulatory issues\n"
            "3. Policy/theme/news flow that can affect sector rotation or short-term momentum in the Korean market\n"
            "4. Macro news only when it clearly matters for Korean equities, KRW, semiconductors, batteries, China exposure, rates, or foreign flow\n\n"
            "Important rules:\n"
            "- The `company_catalysts` and `macro_news` arrays below are the result of an upstream NLU pass that has "
            "already deduplicated articles and filtered noise. Do NOT re-derive them — interpret them.\n"
            "- For each catalyst, explain WHY it matters for the trade and WHAT condition would invalidate that view.\n"
            "- The `noise_count` tells you how many articles were filtered as noise. If it's high relative to the "
            "catalyst count, mention that the news flow is heavy on chatter relative to substance.\n"
            "- Trust the `expected_impact` and `confidence` labels but feel free to disagree explicitly when the "
            "catalyst summary suggests otherwise — explain your reasoning.\n"
            "- The `data_quality_notes` field calls out caveats (single source, vague wording). Reflect them in confidence statements.\n"
            "- Distinguish between fundamental, event-driven, policy/theme-driven, and sentiment-only catalysts.\n\n"
            "The final report should help a trader understand:\n"
            "- which catalysts actually matter\n"
            "- which look strong in headlines but weak in trading relevance\n"
            "- what may drive the stock in the short term versus medium term\n\n"
            "At the end, append a concise Markdown table that summarizes:\n"
            "- catalyst\n"
            "- why it matters\n"
            "- expected market impact\n"
            "- confidence\n\n"
            f"For your reference, the current date is {current_date}. {instrument_context}\n\n"
            "--- NEWS FEATURE PACKET ---\n\n"
            f"{packet_block}"
            f"{lang_instruction}"
        )

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(
                content=f"Analyze the news data for {ticker} as of {current_date} and produce your news analysis report."
            ),
        ]

        result = invoke_with_trace(node_name, llm, messages)

        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content), tool_calls=[])
        elif not hasattr(result, "tool_calls") or result.tool_calls is None:
            result.tool_calls = []

        return {
            "messages": [result],
            "news_report": result.content,
        }

    return news_analyst_node
