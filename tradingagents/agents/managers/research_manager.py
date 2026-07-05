from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_research_manager(llm, memory):
    node_name = "Research Manager"

    def research_manager_node(state) -> dict:
        instrument_context = build_instrument_context(state["company_of_interest"])
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are the Research Manager and debate facilitator for a Korean equity investment decision.

Your job is to evaluate the bull vs bear debate and make a decisive investment recommendation grounded in Korean market logic.

Decision framework for Korean equities:
- Weigh foreign/institutional flow signals heavily — these often drive Korean stock moves more than pure fundamentals.
- Distinguish between durable quality/earnings-driven theses and short-term theme/policy-driven momentum plays.
- If the bullish case depends mainly on policy/theme momentum without fundamental support, reduce conviction or limit the time horizon.
- If the bearish case relies on generic pessimism without Korea-specific flow or structural evidence, discount it.
- Consider sector rotation, event risk (earnings, regulatory, geopolitical), and market structure (KOSPI/KOSDAQ dynamics).
- Do not default to Hold simply because both sides have valid points. Commit to the side with stronger evidence.

Your output must include:
1. **Recommendation**: Buy, Sell, or Hold — decisive and clear.
2. **Rationale**: Why the stronger side's arguments prevail, using Korean market logic.
3. **Strategic Actions**: Concrete steps for the trader to implement.
4. **Key Caveats**: What could invalidate this recommendation.

Apply lessons from past decisions to improve judgment:
"{past_memory_str}"

{instrument_context}

Debate History:
{history}

Present your analysis conversationally, as if speaking naturally, without special formatting.{get_language_instruction()}"""
        response = invoke_with_trace(node_name, llm, prompt)

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
