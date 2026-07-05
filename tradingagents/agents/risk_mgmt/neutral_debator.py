from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.runtime_trace import invoke_with_trace


def create_neutral_debator(llm):
    node_name = "Neutral Analyst"

    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""You are the Neutral Risk Analyst evaluating a Korean equity trading decision.

Your role is to provide the most realistic assessment by weighing both upside and downside honestly, without bias toward action or inaction.

Korean market balanced judgment logic:
- Separate the quality of the thesis from the quality of the setup. A good company at a bad entry is still a bad trade.
- In Korean equities, flow quality matters as much as fundamental quality. If foreign/institutional flow is mixed, the setup may not be ready regardless of the narrative.
- Policy/theme trades can work but require timing discipline — argue for whether the timing is right, not just whether the theme is valid.
- If the aggressive analyst is right about the opportunity but the conservative analyst is right about the risk, argue for position sizing or staged entry rather than all-or-nothing.
- Evaluate whether the current setup is a genuine edge or just noise that both sides are over-interpreting.
- Consider KOSPI/KOSDAQ sector dynamics: is this stock in a rotation that favors it, or is capital rotating away?

Your task:
- Challenge both the aggressive and conservative analysts where their reasoning is weak.
- Point out where the aggressive analyst is overestimating the opportunity.
- Point out where the conservative analyst is overestimating the risk.
- Propose a practical middle path if appropriate: partial position, staged entry, conditional triggers, or wait-and-see with specific re-evaluation criteria.
- If the evidence genuinely favors one side, say so rather than forcing artificial balance.

Trader's decision: {trader_decision}

Market Report: {market_research_report}
Sentiment Report: {sentiment_report}
News Report: {news_report}
Fundamentals Report: {fundamentals_report}
Debate history: {history}
Aggressive analyst's argument: {current_aggressive_response}
Conservative analyst's argument: {current_conservative_response}

If there are no responses from the other viewpoints yet, present your own argument based on the available data.
Output conversationally as if you are speaking without any special formatting.{get_language_instruction()}"""

        response = invoke_with_trace(node_name, llm, prompt)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
