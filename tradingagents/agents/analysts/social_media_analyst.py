import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.dataflows.prefetch import prefetch_social_data
from tradingagents.runtime_trace import emit_runtime_trace, format_elapsed, invoke_with_trace


def create_social_media_analyst(llm):
    node_name = "Social Analyst"

    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # Pre-fetch all social/news data upfront (replaces tool_calls loop)
        emit_runtime_trace(
            "step.start",
            node=node_name,
            step="prefetch_social_data",
            ticker=ticker,
            trade_date=current_date,
        )
        step_started = time.perf_counter()
        social_data = prefetch_social_data(ticker, current_date)
        emit_runtime_trace(
            "step.end",
            node=node_name,
            step="prefetch_social_data",
            ticker=ticker,
            trade_date=current_date,
            elapsed=format_elapsed(time.perf_counter() - step_started),
            data_chars=len(social_data),
        )

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, "
            "recent company news, and public sentiment for a specific company over the past week. "
            "Your objective is to write a comprehensive long report detailing your analysis, insights, and implications "
            "for traders and investors on this company's current state after looking at social media and what people "
            "are saying about that company, analyzing sentiment data of what people feel each day about the company, "
            "and looking at recent company news.\n\n"
            "All relevant news and social data has been pre-fetched and is provided below. "
            "Provide specific, actionable insights with supporting evidence to help traders make informed decisions.\n\n"
            "Make sure to append a Markdown table at the end of the report to organize key points, organized and easy to read.\n\n"
            f"For your reference, the current date is {current_date}. {instrument_context}\n\n"
            "--- PRE-FETCHED SOCIAL/NEWS DATA ---\n\n"
            f"{social_data}"
            f"{lang_instruction}"
        )

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(
                content=f"Analyze the social media and news sentiment for {ticker} as of {current_date} and produce your report."
            ),
        ]

        result = invoke_with_trace(node_name, llm, messages)

        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content), tool_calls=[])
        elif not hasattr(result, "tool_calls") or result.tool_calls is None:
            result.tool_calls = []

        return {
            "messages": [result],
            "sentiment_report": result.content,
        }

    return social_media_analyst_node
