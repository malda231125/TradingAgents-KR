# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .naver_news import get_news_naver, get_global_news_naver
from .dart_api import get_dart_events
from .ecos_api import get_korea_macro_summary
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .kis_vendor import (
    get_kis_stock_data,
    get_kis_indicators,
    get_kis_fundamentals,
    get_kis_balance_sheet,
    get_kis_cashflow,
    get_kis_income_statement,
    get_kis_market_signals,
)

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and corporate-event data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macro economic indicators",
        "tools": [
            "get_macro_summary",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "kis",
    "naver",
    "dart",
    "ecos",
]

DEFAULT_MULTI_SOURCE_VENDORS = {
    "get_news": ["naver", "yfinance"],
    "get_global_news": ["naver", "yfinance"],
}

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "kis": get_kis_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "kis": get_kis_indicators,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "kis": get_kis_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "kis": get_kis_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "kis": get_kis_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "kis": get_kis_income_statement,
    },
    # news_data
    "get_news": {
        "naver": get_news_naver,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "naver": get_global_news_naver,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "dart": get_dart_events,
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "kis": get_kis_market_signals,
    },
    # Macro data (Korean market)
    "get_macro_summary": {
        "ecos": get_korea_macro_summary,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def _parse_vendor_names(vendor_config) -> list[str]:
    """Parse a comma-separated or list-based vendor config into ordered names."""
    if vendor_config is None:
        return []

    if isinstance(vendor_config, str):
        if vendor_config.strip() in ("", "default"):
            return []
        return [v.strip() for v in vendor_config.split(",") if v.strip()]

    if isinstance(vendor_config, (list, tuple)):
        names = []
        for vendor in vendor_config:
            name = str(vendor).strip()
            if name:
                names.append(name)
        return names

    raise TypeError(f"Unsupported vendor config type: {type(vendor_config)!r}")

def _filter_supported_vendors(method: str, vendors: list[str]) -> list[str]:
    """Keep only vendors supported by the target method."""
    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    supported = []
    for vendor in vendors:
        if vendor in VENDOR_METHODS[method] and vendor not in supported:
            supported.append(vendor)
    return supported

def get_route_vendors(method: str) -> list[str]:
    """Return the explicit vendor order for direct route_to_vendor() calls.

    Structured categories are expected to specify a single primary source.
    If a caller configures multiple vendors explicitly, they are treated as an
    opt-in fallback chain in the listed order.
    """
    category = get_category_for_method(method)
    configured_vendors = _parse_vendor_names(get_vendor(category, method))
    supported = _filter_supported_vendors(method, configured_vendors)

    if configured_vendors and not supported:
        configured = ", ".join(configured_vendors)
        raise ValueError(
            f"No supported vendors configured for '{method}': {configured}"
        )

    if supported:
        return supported

    available = list(VENDOR_METHODS[method].keys())
    if not available:
        raise RuntimeError(f"No registered vendors for '{method}'")
    return [available[0]]

def get_multi_source_vendors(method: str) -> list[str]:
    """Return the configured vendor set for merged multi-source collection."""
    config = get_config()
    merge_config = config.get("multi_source_vendors", {}).get(method)
    configured_vendors = _parse_vendor_names(merge_config)
    if not configured_vendors:
        configured_vendors = DEFAULT_MULTI_SOURCE_VENDORS.get(method, [])

    supported = _filter_supported_vendors(method, configured_vendors)
    if configured_vendors and not supported:
        configured = ", ".join(configured_vendors)
        raise ValueError(
            f"No supported multi-source vendors configured for '{method}': {configured}"
        )

    if supported:
        return supported

    return get_route_vendors(method)

def get_vendor_callable(method: str, vendor: str):
    """Return the concrete implementation for a method/vendor pair."""
    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")
    if vendor not in VENDOR_METHODS[method]:
        raise ValueError(f"Vendor '{vendor}' is not registered for '{method}'")

    vendor_impl = VENDOR_METHODS[method][vendor]
    return vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

def route_to_vendor(method: str, *args, **kwargs):
    """Route a method to its configured primary vendor order.

    Unlike the older implicit fallback behavior, this only tries vendors that
    are explicitly configured for the method/category. A single configured
    vendor behaves as a strict primary source. Multiple configured vendors are
    treated as an opt-in fallback chain.
    """
    route_vendors = get_route_vendors(method)
    errors = []

    for index, vendor in enumerate(route_vendors):
        impl_func = get_vendor_callable(method, vendor)

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError as e:
            if len(route_vendors) == 1:
                raise
            errors.append(f"{vendor}: {e}")
            continue
        except Exception as e:
            if len(route_vendors) == 1:
                raise
            errors.append(f"{vendor}: {e}")
            if index < len(route_vendors) - 1:
                continue
            break

    configured = ", ".join(route_vendors)
    detail = "; ".join(errors) if errors else "no vendor returned a result"
    raise RuntimeError(
        f"All configured vendors failed for '{method}' "
        f"(configured: {configured}): {detail}"
    )
