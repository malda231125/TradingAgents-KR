"""Pre-fetch all data needed by analysts before LLM calls.

Replaces the tool_calls loop pattern (bind_tools + iterative LLM calls)
with upfront data collection. Each analyst gets all its data in one pass,
then the LLM is called once with the full dataset in the prompt.

Includes file-based caching: same (ticker, date, data_type) won't re-call
the vendor API. Past-date data is cached permanently; today's data has a
1-hour TTL.

There are two output formats:

- The legacy `prefetch_*_data()` functions return a long human-readable
  text blob (15k–26k chars) that gets embedded in the analyst system
  prompt as-is. This format is preserved for backwards compatibility and
  for the human-readable report path.

- The newer `prefetch_*_packet()` functions return a small structured
  feature packet (typically 1–2k chars when serialized) that captures the
  same information in a form designed for LLM consumption. The first-stage
  analysts use the packet path; downstream nodes that already consume
  analyst output will switch over in a later phase.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta

from tradingagents.dataflows.interface import (
    get_multi_source_vendors,
    get_route_vendors,
    get_vendor_callable,
    route_to_vendor,
)
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.feature_packets import (
    FundamentalsPacket,
    MarketPacket,
    NewsPacket,
    build_fundamentals_packet,
    build_market_packet,
    build_news_packet_from_text,
)
from tradingagents.dataflows.korea_ticker import get_instrument_profile

logger = logging.getLogger(__name__)

MARKET_INDICATORS = [
    "rsi",
    "macd",
    "boll_ub",
    "boll_lb",
    "close_50_sma",
    "close_200_sma",
    "atr",
    "vwma",
]

# Cache TTL: 1 hour for today's data, permanent for past dates
_CACHE_TTL_SECONDS = 3600


def _get_cache_dir() -> str:
    """Get the cache directory path, creating it if needed."""
    config = get_config()
    cache_dir = os.path.join(config.get("data_cache_dir", "/tmp"), "prefetch_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _cache_key(func_name: str, *args, cache_identity=None) -> str:
    """Generate a deterministic cache key from function name and arguments."""
    raw = json.dumps(
        {
            "func_name": func_name,
            "args": [str(a) for a in args],
            "cache_identity": cache_identity,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_get(key: str, trade_date: str) -> str | None:
    """Read from cache. Returns None on miss or expired entry."""
    cache_dir = _get_cache_dir()
    path = os.path.join(cache_dir, f"{key}.json")

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Check TTL: today's data expires after 1 hour, past data is permanent
    today = datetime.now().strftime("%Y-%m-%d")
    if trade_date == today:
        age = time.time() - entry.get("ts", 0)
        if age > _CACHE_TTL_SECONDS:
            return None

    return entry.get("data")


def _cache_set(key: str, data: str) -> None:
    """Write to cache."""
    cache_dir = _get_cache_dir()
    path = os.path.join(cache_dir, f"{key}.json")

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except OSError as e:
        logger.warning("cache write failed for %s: %s", key, e)


def _safe_fetch(label: str, func, *args, cache_identity=None, **kwargs) -> str:
    """Call a vendor function with caching, or return an error note on failure."""
    # Extract trade_date from args for TTL logic
    # Convention: trade_date is always in the args passed to route_to_vendor
    trade_date = _extract_trade_date(args)
    cache_key = _cache_key(label, *args, cache_identity=cache_identity)

    cached = _cache_get(cache_key, trade_date)
    if cached is not None:
        logger.debug("cache hit for %s", label)
        return cached

    try:
        result = func(*args, **kwargs)
        formatted = f"## {label}\n{result}"
        _cache_set(cache_key, formatted)
        return formatted
    except Exception as e:
        logger.warning("prefetch failed for %s: %s", label, e)
        return f"## {label}\n[Data unavailable: {e}]"


def _extract_trade_date(args) -> str:
    """Best-effort extraction of trade_date from function args for cache TTL."""
    for arg in args:
        if isinstance(arg, str) and len(arg) == 10:
            try:
                datetime.strptime(arg, "%Y-%m-%d")
                return arg
            except ValueError:
                continue
    return datetime.now().strftime("%Y-%m-%d")


def clear_cache() -> int:
    """Clear all cached prefetch data. Returns number of files removed."""
    cache_dir = _get_cache_dir()
    count = 0
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(cache_dir, f))
                count += 1
    return count


def _route_cache_identity(method: str) -> dict:
    return {
        "method": method,
        "vendors": get_route_vendors(method),
    }


def _multi_source_cache_identity(method: str, vendor_name: str) -> dict:
    return {
        "method": method,
        "vendor": vendor_name,
        "vendors": get_multi_source_vendors(method),
    }


def prefetch_market_data(
    ticker: str, trade_date: str, lookback_days: int = 60
) -> str:
    """Pre-fetch stock price data and all technical indicators."""
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_date = (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    sections = []

    sections.append(
        _safe_fetch(
            "Stock Price Data (OHLCV)",
            route_to_vendor,
            "get_stock_data",
            ticker,
            start_date,
            trade_date,
            cache_identity=_route_cache_identity("get_stock_data"),
        )
    )

    for indicator in MARKET_INDICATORS:
        sections.append(
            _safe_fetch(
                f"Indicator: {indicator}",
                route_to_vendor,
                "get_indicators",
                ticker,
                indicator,
                trade_date,
                30,
                cache_identity=_route_cache_identity("get_indicators"),
            )
        )

    # Macro data (ECOS) — optional, only if ECOS key is available
    sections.append(
        _safe_fetch(
            "Korea Macro Summary (ECOS)",
            route_to_vendor,
            "get_macro_summary",
            trade_date,
            cache_identity=_route_cache_identity("get_macro_summary"),
        )
    )

    return "\n\n".join(sections)


def _adapt_vendor_args(method: str, vendor_name: str, args: tuple) -> tuple:
    """Convert canonical instrument input into vendor-specific arguments."""
    if method != "get_news" or not args:
        return args

    instrument = get_instrument_profile(args[0])
    if vendor_name == "naver":
        ticker_arg = instrument["news_query"]
    else:
        ticker_arg = instrument["yfinance_symbol"]

    return (ticker_arg, *args[1:])


def _fetch_from_selected_vendors(method: str, label_prefix: str, *args) -> list:
    """Call the configured multi-source vendors for a method and collect results."""
    vendors = get_multi_source_vendors(method)
    results = []

    for vendor_name in vendors:
        impl_func = get_vendor_callable(method, vendor_name)
        vendor_args = _adapt_vendor_args(method, vendor_name, args)
        label = f"{label_prefix} [{vendor_name}]"
        try:
            section = _safe_fetch(
                label,
                impl_func,
                *vendor_args,
                cache_identity=_multi_source_cache_identity(method, vendor_name),
            )
            if section and "[Data unavailable:" not in section:
                results.append(section)
                logger.debug("News vendor %s succeeded for %s", vendor_name, method)
        except Exception as e:
            logger.debug("News vendor %s failed for %s: %s", vendor_name, method, e)

    return results


def _deduplicate_news_sections(sections: list) -> str:
    """Merge news sections, apply noise filtering, and add dedup note.

    Applies spam/noise filtering to each section, then merges with
    a dedup instruction for the LLM.
    """
    from tradingagents.dataflows.news_filter import filter_news_text

    if not sections:
        return "## News\nNo news data available from any source."

    # Apply noise filter to each section
    filtered = [filter_news_text(s) for s in sections]
    combined = "\n\n".join(filtered)

    dedup_note = (
        "\n\n## Note on duplicate articles\n"
        "The above news was collected from multiple sources. "
        "Some articles may cover the same event. "
        "When analyzing, consolidate duplicate coverage into a single interpretation. "
        "Low-quality or spam articles have been pre-filtered."
    )
    return combined + dedup_note


def prefetch_news_data(
    ticker: str, trade_date: str, lookback_days: int = 7
) -> str:
    """Pre-fetch company news and global/macro news from configured multi-source vendors.

    By default this merges Naver and yfinance so the analyst sees both domestic
    coverage and an outside/global framing of the same Korean equity story.
    """
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_date = (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # Collect company news from configured news vendors
    company_news = _fetch_from_selected_vendors(
        "get_news", "Company News", ticker, start_date, trade_date
    )

    # Collect global news from configured news vendors
    global_news = _fetch_from_selected_vendors(
        "get_global_news", "Global/Macro News", trade_date, 7, 10
    )

    all_sections = company_news + global_news

    # If merged news fetch got nothing, fall back to the direct route order.
    if not all_sections:
        sections = []
        sections.append(
            _safe_fetch(
                "Company News",
                route_to_vendor,
                "get_news",
                ticker,
                start_date,
                trade_date,
                cache_identity=_route_cache_identity("get_news"),
            )
        )
        sections.append(
            _safe_fetch(
                "Global/Macro News",
                route_to_vendor,
                "get_global_news",
                trade_date,
                7,
                10,
                cache_identity=_route_cache_identity("get_global_news"),
            )
        )
        return "\n\n".join(sections)

    return _deduplicate_news_sections(all_sections)


def prefetch_fundamentals_data(ticker: str, trade_date: str) -> str:
    """Pre-fetch fundamentals, balance sheet, cashflow, and income statement."""
    sections = []

    sections.append(
        _safe_fetch(
            "Company Fundamentals",
            route_to_vendor,
            "get_fundamentals",
            ticker,
            trade_date,
            cache_identity=_route_cache_identity("get_fundamentals"),
        )
    )

    sections.append(
        _safe_fetch(
            "Balance Sheet (Quarterly)",
            route_to_vendor,
            "get_balance_sheet",
            ticker,
            "quarterly",
            trade_date,
            cache_identity=_route_cache_identity("get_balance_sheet"),
        )
    )

    sections.append(
        _safe_fetch(
            "Cash Flow (Quarterly)",
            route_to_vendor,
            "get_cashflow",
            ticker,
            "quarterly",
            trade_date,
            cache_identity=_route_cache_identity("get_cashflow"),
        )
    )

    sections.append(
        _safe_fetch(
            "Income Statement (Quarterly)",
            route_to_vendor,
            "get_income_statement",
            ticker,
            "quarterly",
            trade_date,
            cache_identity=_route_cache_identity("get_income_statement"),
        )
    )

    return "\n\n".join(sections)


def prefetch_market_packet(ticker: str, trade_date: str) -> MarketPacket:
    """Build the structured market feature packet for an instrument/date.

    This is the analyst-input replacement for `prefetch_market_data()`. It
    returns a `MarketPacket` rather than a giant text blob, so analyst
    prompts shrink from ~15k chars to ~1.5–2k chars while preserving the
    essential price/MA/volume/regime/macro information.

    The result is cached using the existing prefetch cache so the second
    invocation for the same (ticker, date) is free.
    """
    cache_key = _cache_key(
        "market_packet",
        ticker,
        trade_date,
        cache_identity={"format": "feature_packet_v2"},
    )
    cached = _cache_get(cache_key, trade_date)
    if cached is not None:
        try:
            return MarketPacket(**json.loads(cached))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("market_packet cache decode failed: %s", exc)

    packet = build_market_packet(ticker, trade_date)
    try:
        _cache_set(cache_key, json.dumps(packet.__dict__, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("market_packet cache write skipped: %s", exc)
    return packet


def prefetch_fundamentals_packet(ticker: str, trade_date: str) -> FundamentalsPacket:
    """Build the structured fundamentals feature packet for an instrument/date.

    Replaces the 26k-char text blob from `prefetch_fundamentals_data()` with
    a structured packet that already contains valuation, profitability,
    balance-sheet stress, and earnings-momentum interpretation.
    """
    cache_key = _cache_key(
        "fundamentals_packet",
        ticker,
        trade_date,
        cache_identity={"format": "feature_packet_v1"},
    )
    cached = _cache_get(cache_key, trade_date)
    if cached is not None:
        try:
            return FundamentalsPacket(**json.loads(cached))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("fundamentals_packet cache decode failed: %s", exc)

    packet = build_fundamentals_packet(ticker, trade_date)
    try:
        _cache_set(cache_key, json.dumps(packet.__dict__, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("fundamentals_packet cache write skipped: %s", exc)
    return packet


def prefetch_news_packet(ticker: str, trade_date: str, llm) -> NewsPacket:
    """Run the NLU news enricher and return a structured NewsPacket.

    Unlike the market and fundamentals packets, this one requires an LLM
    because the catalyst extraction is a real NLU task. The result is
    cached on disk keyed by (ticker, trade_date, hash(raw_news_text)) so
    re-runs of the same date with the same news set never re-call the
    enricher LLM.

    The cache key includes the raw news text hash so that if news changes
    intra-day (only relevant for today's date with TTL'd cache), the
    enricher is re-run.
    """
    from tradingagents.dataflows.feature_packets.news import build_news_packet_from_text
    from tradingagents.dataflows.korea_ticker import get_instrument_profile

    profile = get_instrument_profile(ticker)
    instrument = {
        "name": profile.get("name") or ticker,
        "stock_code": profile.get("stock_code") or ticker,
    }

    # Fetch the merged raw news text first (this path itself is cached at
    # the vendor level by _safe_fetch).
    try:
        raw_news = prefetch_news_data(ticker, trade_date)
    except Exception as exc:
        logger.warning("prefetch_news_data failed for %s: %s", ticker, exc)
        raw_news = ""

    raw_hash = hashlib.sha256(raw_news.encode("utf-8")).hexdigest()[:16]
    cache_key = _cache_key(
        "news_packet",
        ticker,
        trade_date,
        cache_identity={"format": "feature_packet_v1", "raw_hash": raw_hash},
    )
    cached = _cache_get(cache_key, trade_date)
    if cached is not None:
        try:
            return NewsPacket(**json.loads(cached))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("news_packet cache decode failed: %s", exc)

    packet = build_news_packet_from_text(
        instrument=instrument,
        as_of=trade_date,
        raw_news_text=raw_news,
        llm=llm,
        evidence_refs=[f"news:raw:{ticker}:{trade_date}"],
    )

    try:
        _cache_set(cache_key, json.dumps(packet.__dict__, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("news_packet cache write skipped: %s", exc)
    return packet


def prefetch_social_data(
    ticker: str, trade_date: str, lookback_days: int = 7
) -> str:
    """Pre-fetch company news/social context for the Social Media Analyst."""
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_date = (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    sections = _fetch_from_selected_vendors(
        "get_news",
        "Social/News Data",
        ticker,
        start_date,
        trade_date,
    )
    if sections:
        return _deduplicate_news_sections(sections)

    return _safe_fetch(
        "Social/News Data",
        route_to_vendor,
        "get_news",
        ticker,
        start_date,
        trade_date,
        cache_identity=_route_cache_identity("get_news"),
    )
