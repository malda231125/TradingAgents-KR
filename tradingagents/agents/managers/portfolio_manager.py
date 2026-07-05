from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_portfolio_manager(llm, memory):
    node_name = "Portfolio Manager"

    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision for a Korean equity context.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Trader's proposed plan: **{trader_plan}**
- Lessons from past decisions: **{past_memory_str}**

**Required Output Structure:**
1. **Rating**: State one of Buy / Overweight / Hold / Underweight / Sell.
2. **Executive Summary**: A concise action plan covering entry logic, sizing logic, invalidation/risk points, and time horizon.
3. **Investment Thesis**: Detailed reasoning anchored in Korean market structure.
4. **Key Risk Triggers**: What would invalidate the decision.

---

Decision principles for Korean equities:
- Separate quality/fundamental conviction from short-term theme or flow-driven opportunity.
- Explicitly weigh foreign/institutional flow, short-sale pressure, and event-driven volatility.
- Do not over-rely on weak social sentiment evidence.
- If the stock is only attractive as a tactical trade and not a durable investment, say so.
- If the best decision is Hold because the setup is ambiguous, explain why ambiguity itself is the decision.

**Risk Analysts Debate History:**
{history}

---

Be decisive, evidence-based, and practical.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return portfolio_manager_node
