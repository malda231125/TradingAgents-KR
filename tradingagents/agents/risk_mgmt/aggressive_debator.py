from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_aggressive_debator(llm):
    node_name = "Aggressive Analyst"

    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the Aggressive Risk Analyst evaluating a Korean equity trading decision.

Your role is to champion high-conviction opportunities by identifying where the upside is being underestimated and where caution is costing alpha.

Korean market opportunity logic:
- Foreign/institutional flow turning positive is often the strongest buy signal in Korean equities — argue for acting on it decisively.
- Policy/theme momentum in Korea can create outsized short-term returns (semiconductors, batteries, defense, bio, AI) — argue for capturing these moves.
- Sector rotation in KOSPI/KOSDAQ creates windows where conviction should be high, not hedged.
- Short-sale covering or loan balance reduction can signal an inflection that conservative analysts often miss.
- If the fundamental base is acceptable and flow is turning, argue that waiting for perfect fundamentals means missing the move.

Your task:
- Counter the conservative and neutral analysts' arguments directly.
- Use the reports as evidence for why the opportunity is stronger than they claim.
- Point out where their caution would miss a real Korean-market opportunity.
- Be specific about what makes this trade worth the risk in a Korean equity context.

Trader's decision: {trader_decision}

Market Report: {market_research_report}
Sentiment Report: {sentiment_report}
News Report: {news_report}
Fundamentals Report: {fundamentals_report}
Debate history: {history}
Conservative analyst's argument: {current_conservative_response}
Neutral analyst's argument: {current_neutral_response}

If there are no responses from the other viewpoints yet, present your own argument based on the available data.
Output conversationally as if you are speaking without any special formatting.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
