import functools

from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on the analyst outputs for {company_name}, produce a practical trading decision in a Korean equity context. {instrument_context}\n\nProposed Investment Plan: {investment_plan}\n\nMarket Report: {market_research_report}\n\nNews Report: {news_report}\n\nFundamentals Report: {fundamentals_report}\n\nSentiment Report (may be weak or incomplete): {sentiment_report}",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are a trading agent making a practical trading decision for a Korean stock. Your job is to convert the analysts' work into an actionable trading stance.

Rules:
- Prioritize Korean market structure: foreign/institutional flow, event risk, sector rotation, theme durability, and technical confirmation.
- Do not over-weight social sentiment unless it clearly adds value.
- Explicitly distinguish whether this is:
  - a short-term tactical trade
  - a medium-term position
  - or not a trade worth taking
- If the thesis depends on policy/theme momentum, say so explicitly.
- If the setup is weak or ambiguous, do not force conviction.
- End with a firm decision and always conclude with 'FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**'.

Apply lessons from past decisions to strengthen your judgment. Relevant past reflections: {past_memory_str}{get_language_instruction()}""",
            },
            context,
        ]

        result = invoke_with_trace(name, llm, messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
