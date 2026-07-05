import os
import shutil

CLI_PROVIDER_MODEL_DEFAULTS = {
    "claude-cli": {
        "quick": "sonnet",
        "deep": "opus",
    },
    "codex-cli": {
        "quick": "gpt-5.5",
        "deep": "gpt-5.5",
    },
}

# Order in which an installed CLI runtime is auto-detected when the provider is
# left unset. Codex is the documented public default, so it is preferred; Claude
# Code is the fallback. Each entry maps a provider key to its executable name.
_CLI_PROVIDER_COMMANDS = (
    ("codex-cli", "codex"),
    ("claude-cli", "claude"),
)


def detect_cli_provider() -> str | None:
    """Return the first CLI provider whose executable is on PATH, else None."""
    for provider, command in _CLI_PROVIDER_COMMANDS:
        if shutil.which(command):
            return provider
    return None


def normalize_llm_provider(provider: str | None) -> str:
    """Normalize provider names and fall back to the supported default."""
    normalized = (provider or "claude-cli").strip().lower()
    if normalized in CLI_PROVIDER_MODEL_DEFAULTS:
        return normalized
    return "claude-cli"


def resolve_default_provider(env_provider: str | None) -> str:
    """Resolve the default CLI provider.

    An explicit, non-empty ``TRADINGAGENTS_LLM_PROVIDER`` is honored (normalized).
    When it is unset/blank, auto-detect an installed CLI runtime (codex preferred,
    then claude); if neither is installed, fall back to the documented default
    (``codex-cli``).
    """
    if env_provider and env_provider.strip():
        return normalize_llm_provider(env_provider)
    return detect_cli_provider() or "codex-cli"


def get_cli_model_defaults(provider: str | None) -> dict[str, str]:
    """Return the default quick/deep model pair for the selected CLI provider."""
    normalized = normalize_llm_provider(provider)
    return CLI_PROVIDER_MODEL_DEFAULTS[normalized].copy()


_DEFAULT_PROVIDER = resolve_default_provider(
    os.getenv("TRADINGAGENTS_LLM_PROVIDER")
)
_DEFAULT_MODELS = get_cli_model_defaults(_DEFAULT_PROVIDER)

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": _DEFAULT_PROVIDER,
    "deep_think_llm": os.getenv(
        "TRADINGAGENTS_DEEP_MODEL",
        _DEFAULT_MODELS["deep"],
    ),
    "quick_think_llm": os.getenv(
        "TRADINGAGENTS_QUICK_MODEL",
        _DEFAULT_MODELS["quick"],
    ),
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # CLI backend configuration (for supported *-cli providers)
    "cli_timeout": int(os.getenv("TRADINGAGENTS_CLI_TIMEOUT", "300")),
    "cli_max_retries": int(os.getenv("TRADINGAGENTS_CLI_MAX_RETRIES", "2")),
    # Claude CLI reasoning effort (low|medium|high|xhigh|max).
    "cli_effort": os.getenv("TRADINGAGENTS_CLI_EFFORT"),
    # Report/output language for agents and the final report.
    # ko (default) | en | ja | zh — unknown codes fall back to en. See tradingagents/i18n.py.
    "report_language": os.getenv("TRADINGAGENTS_REPORT_LANGUAGE", "ko"),
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data source configuration
    # Structured market data uses one primary source per category.
    # News is different: the main analyst path intentionally merges multiple
    # sources so it can combine domestic and overseas perspectives.
    "data_vendors": {
        "core_stock_apis": "kis",              # Primary source for OHLCV
        "technical_indicators": "kis",         # Primary source for indicators
        "fundamental_data": "kis",             # Primary source for fundamentals/statements
        "news_data": "naver,yfinance",         # Direct-route order for company/global news
        "macro_data": "ecos",                  # Primary source for Korea macro summary
    },
    # Multi-source news collection used by prefetch_news_data()/prefetch_social_data()
    "multi_source_vendors": {
        "get_news": "naver,yfinance",
        "get_global_news": "naver,yfinance",
    },
    # Overseas context is optional enrichment. It should not replace KIS/DART/ECOS.
    "global_data": {
        "enable_fred": True,
        "enable_sec_edgar": True,
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        "get_insider_transactions": "dart",   # Disclosure/event-style data should prefer DART
        # Example: "get_stock_data": "yfinance",  # Override category default
    },
}
