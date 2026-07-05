"""Deterministic feature packets used as the structured input format for analysts.

These packets are the answer to the prompt-bloat problem: instead of feeding
analysts the raw 15k–26k char text dumps from `prefetch_*_data()`, we feed
them a small,
structured packet that already contains:

  - the latest values that matter (price, MA, volume, ROE, etc.)
  - rule-based interpretation (regime classification, trend direction)
  - natural-language signal bullets the analyst can build on
  - evidence references back to the raw data when needed

For news, see `news.py` (Phase 4-B) which uses a small NLU LLM call to
turn raw articles into a structured catalyst packet — that piece is not
purely rule-based because event semantics need real language understanding.

Builders are intentionally split into two layers:

  - `build_*_packet_from_dataframes(...)` takes already-loaded pandas
    DataFrames and is fully deterministic and unit-testable.
  - `build_*_packet(ticker, trade_date)` is a thin convenience wrapper
    that calls the live KIS vendor functions and delegates to the
    pure-data builder.
"""

from .market import MarketPacket, build_market_packet, build_market_packet_from_dataframes
from .fundamentals import (
    FundamentalsPacket,
    build_fundamentals_packet,
    build_fundamentals_packet_from_dataframes,
)
from .news import (
    NewsPacket,
    build_news_packet,
    build_news_packet_from_text,
)
from .us_macro import (
    build_global_risk_context_from_us_macro,
    build_us_macro_context,
    build_us_macro_context_from_dataframes,
)
from .global_peer import (
    build_global_peer_context,
    build_global_peer_context_from_sec_payloads,
)

__all__ = [
    "MarketPacket",
    "build_market_packet",
    "build_market_packet_from_dataframes",
    "FundamentalsPacket",
    "build_fundamentals_packet",
    "build_fundamentals_packet_from_dataframes",
    "NewsPacket",
    "build_news_packet",
    "build_news_packet_from_text",
    "build_us_macro_context",
    "build_us_macro_context_from_dataframes",
    "build_global_risk_context_from_us_macro",
    "build_global_peer_context",
    "build_global_peer_context_from_sec_payloads",
]
