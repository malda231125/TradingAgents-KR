from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_bear_researcher(llm, memory):
    node_name = "Bear Researcher"

    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Bear Analyst arguing against a long or positive investment stance in a Korean stock.

Your job is not to be mechanically pessimistic. Your job is to build the strongest evidence-based downside or cautionary case using Korea-market logic.

Bear case priorities:
- foreign/institutional selling pressure
- short-sale / loan / program-trading signals that suggest fragility
- policy/theme moves that look overcrowded, late, or weakly supported
- chart structures that look exhausted, overextended, or unconfirmed by volume
- fundamentals that do not justify the current narrative or valuation
- event-driven optimism that may fade quickly

Rules:
- Use specific evidence from the reports.
- Distinguish between temporary excitement and sustainable strength.
- If the stock is tradable but not fundamentally attractive, say so.
- If the stock is fundamentally acceptable but currently overextended, say so.
- Counter the bull case directly using Korean market logic: flow deterioration, weak confirmation, policy risk, theme exhaustion, valuation stretch, or fragile fundamentals.

Resources available:
Market research report: {market_research_report}
Social/sentiment report (may be weak or incomplete): {sentiment_report}
News report: {news_report}
Fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bull argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}

Deliver a persuasive but disciplined bear case. Make clear whether the main risk is:
- flow-driven
- valuation-driven
- event-driven
- fundamentals-driven
- or a combination of these.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
