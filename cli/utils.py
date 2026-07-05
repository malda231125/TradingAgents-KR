import questionary
from typing import List

from rich.console import Console

from cli.models import AnalystType
from tradingagents.default_config import (
    DEFAULT_CONFIG,
    get_cli_model_defaults,
    normalize_llm_provider,
)

console = Console()

TICKER_INPUT_EXAMPLES = "Examples: 005930, 삼성전자, 000660, SK하이닉스, 7203.T"

ANALYST_ORDER = [
    ("Market Analyst", AnalystType.MARKET),
    ("News Analyst", AnalystType.NEWS),
    ("Fundamentals Analyst", AnalystType.FUNDAMENTALS),
    ("Social Media Analyst (optional / low priority)", AnalystType.SOCIAL),
]

CLI_PROVIDER_OPTIONS = [
    ("Claude CLI (local login required)", "claude-cli"),
    ("Codex CLI (local login required)", "codex-cli"),
]

MODEL_OPTIONS = {
    "claude-cli": {
        "quick": [
            ("Claude Sonnet - Recommended default", "sonnet"),
            ("Claude Haiku - Fastest option", "haiku"),
            ("Claude Opus - Highest capability", "opus"),
        ],
        "deep": [
            ("Claude Opus - Highest capability", "opus"),
            ("Claude Sonnet - Recommended default", "sonnet"),
            ("Claude Haiku - Fastest option", "haiku"),
        ],
    },
    "codex-cli": {
        "quick": [
            ("GPT-5.4 - Recommended default", "gpt-5.4"),
            ("GPT-5.4 mini - Lower quota / lighter runs", "gpt-5.4-mini"),
        ],
        "deep": [
            ("GPT-5.4 - Recommended default", "gpt-5.4"),
            ("GPT-5.4 mini - Lower quota / lighter runs", "gpt-5.4-mini"),
        ],
    },
}


def _reorder_choices(
    options: list[tuple[str, str]],
    preferred_value: str | None,
) -> list[tuple[str, str]]:
    if not preferred_value:
        return options

    preferred = [item for item in options if item[1] == preferred_value]
    remaining = [item for item in options if item[1] != preferred_value]
    return preferred + remaining if preferred else options


def _preferred_model(provider: str, kind: str) -> str:
    provider_lower = normalize_llm_provider(provider)
    configured_provider = normalize_llm_provider(DEFAULT_CONFIG.get("llm_provider"))
    provider_defaults = get_cli_model_defaults(provider_lower)

    if provider_lower == configured_provider:
        if kind == "quick":
            return DEFAULT_CONFIG.get("quick_think_llm", provider_defaults["quick"])
        return DEFAULT_CONFIG.get("deep_think_llm", provider_defaults["deep"])

    return provider_defaults[kind]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        f"Enter the exact ticker symbol to analyze ({TICKER_INPUT_EXAMPLES}):",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        console.print("\n[red]No ticker symbol provided. Exiting...[/red]")
        exit(1)

    return normalize_ticker_symbol(ticker)


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return ticker.strip().upper()


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""
    import re
    from datetime import datetime

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    date = questionary.text(
        "Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "Please enter a valid date in YYYY-MM-DD format.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        console.print("\n[red]No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts() -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""
    choices = questionary.checkbox(
        "Select Your [Analysts Team]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in ANALYST_ORDER
        ],
        instruction="\n- Press Space to select/unselect analysts\n- Press 'a' to select/unselect all\n- Press Enter when done",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        console.print("\n[red]No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    # Define research depth options with their corresponding values
    DEPTH_OPTIONS = [
        ("Shallow - Quick research, few debate and strategy discussion rounds", 1),
        ("Medium - Middle ground, moderate debate rounds and strategy discussion", 3),
        ("Deep - Comprehensive research, in depth debate and strategy discussion", 5),
    ]

    choice = questionary.select(
        "Select Your [Research Depth]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in DEPTH_OPTIONS
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No research depth selected. Exiting...[/red]")
        exit(1)

    return choice


def select_shallow_thinking_agent(provider) -> str:
    """Select shallow thinking llm engine using an interactive selection."""
    provider_lower = (provider or "").strip().lower()
    if provider_lower not in MODEL_OPTIONS:
        raise ValueError(
            "Interactive CLI only supports the claude-cli and codex-cli providers."
        )
    provider_lower = normalize_llm_provider(provider_lower)
    shallow_agent_options = MODEL_OPTIONS.get(provider_lower, {}).get("quick")
    shallow_agent_options = _reorder_choices(
        shallow_agent_options,
        _preferred_model(provider_lower, "quick"),
    )

    choice = questionary.select(
        "Select Your [Quick-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in shallow_agent_options
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print(
            "\n[red]No shallow thinking llm engine selected. Exiting...[/red]"
        )
        exit(1)

    return choice


def select_deep_thinking_agent(provider) -> str:
    """Select deep thinking llm engine using an interactive selection."""
    provider_lower = (provider or "").strip().lower()
    if provider_lower not in MODEL_OPTIONS:
        raise ValueError(
            "Interactive CLI only supports the claude-cli and codex-cli providers."
        )
    provider_lower = normalize_llm_provider(provider_lower)
    deep_agent_options = MODEL_OPTIONS.get(provider_lower, {}).get("deep")
    deep_agent_options = _reorder_choices(
        deep_agent_options,
        _preferred_model(provider_lower, "deep"),
    )

    choice = questionary.select(
        "Select Your [Deep-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in deep_agent_options
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No deep thinking llm engine selected. Exiting...[/red]")
        exit(1)

    return choice

def select_llm_provider() -> tuple[str, str | None]:
    """Select the LLM backend for the CLI workflow."""
    configured_provider = normalize_llm_provider(DEFAULT_CONFIG.get("llm_provider"))
    provider_options = _reorder_choices(CLI_PROVIDER_OPTIONS, configured_provider)
    
    choice = questionary.select(
        "Select your LLM Provider:",
        choices=[
            questionary.Choice(display, value=provider)
            for display, provider in provider_options
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()
    
    if choice is None:
        console.print("\n[red]No CLI backend selected. Exiting...[/red]")
        exit(1)

    display_name = next(
        display for display, provider in CLI_PROVIDER_OPTIONS if provider == choice
    )
    print(f"You selected: {display_name}")

    return choice, None
