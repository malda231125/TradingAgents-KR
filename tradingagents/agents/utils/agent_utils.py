from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)
from tradingagents.dataflows.korea_ticker import get_instrument_profile


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    profile = get_instrument_profile(ticker)
    if profile["resolved"]:
        return (
            f"The instrument to analyze is `{profile['display_name']}`. "
            f"For Korean structured market data use stock code `{profile['structured_symbol']}`. "
            f"For domestic news queries prefer company name `{profile['news_query']}`. "
            f"For yfinance-compatible lookups use `{profile['yfinance_symbol']}` unless an exchange-qualified symbol is already provided."
        )

    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )

def get_language_instruction(config: dict = None) -> str:
    """Return the prompt suffix that fixes the agent output language.

    Delegates to :mod:`tradingagents.i18n`, which maps ``report_language``
    (``ko``/``en``/``ja``/``zh``, default ``ko``) to a "write in X" instruction
    (empty for English). Unknown codes fall back to English.
    """
    from tradingagents.i18n import get_language_instruction as _resolve

    return _resolve(config)


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
