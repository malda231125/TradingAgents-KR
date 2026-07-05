"""Curated global peer universe for Korean equity read-through.

The mapping is intentionally small and explicit. It prevents overseas news and
filing collection from turning into broad-market search noise.
"""

from __future__ import annotations

from typing import Optional


GLOBAL_PEER_UNIVERSE: dict[str, dict] = {
    "KRX 반도체": {
        "peers": ["NVDA", "AMD", "MU", "INTC", "TSM", "ASML"],
        "etfs": ["SOXX", "SMH", "QQQ"],
        "sec_forms": ["10-K", "10-Q", "8-K", "20-F", "6-K"],
    },
    "K200 정보기술": {
        "peers": ["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
        "etfs": ["QQQ", "XLK"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
    "KRX 자동차": {
        "peers": ["TSLA", "GM", "F"],
        "etfs": ["CARZ", "XLY"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
    "KRX 은행": {
        "peers": ["JPM", "BAC", "C", "WFC"],
        "etfs": ["XLF", "KBE"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
    "KRX 헬스케어": {
        "peers": ["PFE", "MRK", "JNJ", "AMGN", "GILD"],
        "etfs": ["XLV", "IBB"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
    "KRX 에너지화학": {
        "peers": ["XOM", "CVX", "DOW", "ALB"],
        "etfs": ["XLE", "XLB"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
    "K200 산업재": {
        "peers": ["GE", "CAT", "HON"],
        "etfs": ["XLI"],
        "sec_forms": ["10-K", "10-Q", "8-K"],
    },
}


def get_global_peer_universe(stock_code: str) -> Optional[dict]:
    """Return global peer config for a Korean stock code, or None."""
    if not stock_code:
        return None

    from tradingagents.dataflows.sector_index import get_sector_for_stock

    sector = get_sector_for_stock(stock_code)
    if not sector:
        return None

    universe = GLOBAL_PEER_UNIVERSE.get(sector)
    if not universe:
        return None

    return {
        "sector": sector,
        "peers": list(universe.get("peers") or []),
        "etfs": list(universe.get("etfs") or []),
        "sec_forms": list(universe.get("sec_forms") or []),
    }
