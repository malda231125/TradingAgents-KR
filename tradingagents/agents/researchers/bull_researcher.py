from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_bull_researcher(llm, memory):
    node_name = "Bull Researcher"

    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

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

        prompt = f"""You are a Bull Analyst arguing for a long or positive investment stance in a Korean stock.

Your job is not to produce generic optimism. Your job is to make the strongest evidence-based bullish case possible using Korea-market logic.

Bull case priorities:
- foreign/institutional flow improvement or persistence
- strong or improving earnings/fundamental support
- policy/theme momentum that is credible rather than purely speculative
- sector rotation or market structure that favors the stock
- technical setup that supports continuation rather than exhaustion
- evidence that bearish concerns are overstated, temporary, or already priced in

Rules:
- Use the reports as evidence, not as decoration.
- If the bullish case depends on momentum or policy/theme conditions rather than deep fundamentals, say so explicitly.
- If the thesis is short-term rather than structural, say so explicitly.
- Do not rely on vague sentiment arguments.
- Counter the bear case directly using Korean market logic: flow, policy, sector context, market structure, and evidence from current reports.

Resources available:
Market research report: {market_research_report}
Social/sentiment report (may be weak or incomplete): {sentiment_report}
News report: {news_report}
Fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}

Deliver a persuasive but disciplined bull case. Make clear whether the opportunity is:
- quality-driven
- earnings-driven
- flow-driven
- policy/theme-driven
- or a hybrid of these.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
