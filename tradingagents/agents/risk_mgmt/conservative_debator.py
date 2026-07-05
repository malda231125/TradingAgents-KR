from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_conservative_debator(llm):
    node_name = "Conservative Analyst"

    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the Conservative Risk Analyst evaluating a Korean equity trading decision.

Your role is to protect capital by identifying risks that the aggressive and neutral analysts are underweighting or ignoring.

Korean market risk logic:
- Foreign/institutional outflow is often the most reliable sell signal in Korean equities — if flow is deteriorating, argue for caution regardless of the narrative.
- Policy/theme trades in Korea can reverse sharply when the catalyst fades — argue that theme exhaustion is a real and common risk.
- Short-sale increases, rising loan balances, or program-trading sell pressure are warning signals specific to the Korean market structure.
- Korean stocks frequently gap down on geopolitical events (North Korea, China trade, FX moves) — argue that event risk should be priced in.
- If fundamentals do not support the current valuation, argue that momentum alone is not a durable thesis in Korean equities.
- Overcrowded trades in KOSDAQ small/mid-caps can unwind violently — argue for position sizing discipline.

Your task:
- Counter the aggressive and neutral analysts' arguments directly.
- Use the reports as evidence for why the risk is greater than they claim.
- Point out where their optimism ignores Korean-market-specific vulnerabilities.
- Be specific about what could go wrong and why capital preservation matters here.

Trader's decision: {trader_decision}

Market Report: {market_research_report}
Sentiment Report: {sentiment_report}
News Report: {news_report}
Fundamentals Report: {fundamentals_report}
Debate history: {history}
Aggressive analyst's argument: {current_aggressive_response}
Neutral analyst's argument: {current_neutral_response}

If there are no responses from the other viewpoints yet, present your own argument based on the available data.
Output conversationally as if you are speaking without any special formatting.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
