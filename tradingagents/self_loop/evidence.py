"""Build the retrospective evidence packet.

The retrospective is only as good as the evidence it can see. The previous
implementation handed the AI reviewer a price-only view, so it could not judge
the non-price parts of a thesis (flow, disclosures, news, macro). This module
collects an evidence packet across the Korea data stack so the reviewer can
score every checklist item, and so missing data is explicit rather than
silently treated as ``uncertain``.

Deterministic layer only: this module gathers raw evidence and records what is
missing. It does not classify hit/miss — that judgment belongs to the AI
reviewer (see ``reviewer.review_with_subscription_ai``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .records import parse_date


# Each fetcher takes (ticker, start_date, end_date) and returns a text summary.
EvidenceFetcher = Callable[[str, str, str], str]

# Non-price evidence categories collected from the Korea data stack.
EVIDENCE_CATEGORIES = ("price", "flow", "dart", "news", "macro")

# Keep each evidence summary bounded so the reviewer prompt stays small.
_MAX_SUMMARY_CHARS = 2000


def build_evidence_packet(
    decision_record: dict[str, Any],
    *,
    check_date: str | date,
    price_result: dict[str, Any] | None = None,
    flow_fetcher: EvidenceFetcher | None = None,
    dart_fetcher: EvidenceFetcher | None = None,
    news_fetcher: EvidenceFetcher | None = None,
    macro_fetcher: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Collect evidence for the review window of a prior decision record.

    Fetchers are injectable so tests stay network-free. When a fetcher is
    ``None`` the corresponding Korea vendor callable is used. Any fetcher that
    raises or returns empty text is recorded in ``missing_evidence`` and marked
    ``missing`` in ``data_quality`` instead of failing the whole packet.
    """
    ticker = str(decision_record["ticker"])
    analysis_date = parse_date(decision_record["analysis_date"]).isoformat()
    check_date_s = parse_date(check_date).isoformat()

    flow_fetcher = flow_fetcher or _default_flow_fetcher
    dart_fetcher = dart_fetcher or _default_dart_fetcher
    news_fetcher = news_fetcher or _default_news_fetcher
    macro_fetcher = macro_fetcher or _default_macro_fetcher

    price_evidence = _price_evidence(price_result)
    flow_evidence = _collect(flow_fetcher, ticker, analysis_date, check_date_s)
    dart_evidence = _collect(dart_fetcher, ticker, analysis_date, check_date_s)
    news_evidence = _collect(news_fetcher, ticker, analysis_date, check_date_s)
    macro_evidence = _collect_macro(macro_fetcher, check_date_s)

    evidence = {
        "price": price_evidence,
        "flow": flow_evidence,
        "dart": dart_evidence,
        "news": news_evidence,
        "macro": macro_evidence,
    }
    data_quality = {category: item["status"] for category, item in evidence.items()}
    missing_evidence = [category for category, status in data_quality.items() if status != "available"]

    return {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "check_date": check_date_s,
        "evidence": evidence,
        "data_quality": data_quality,
        "missing_evidence": missing_evidence,
    }


def _price_evidence(price_result: dict[str, Any] | None) -> dict[str, Any]:
    if not price_result:
        return {"status": "missing", "summary": None, "detail": None}
    status = "available" if price_result.get("status") == "available" else "missing"
    return {
        "status": status,
        "summary": price_result.get("message"),
        "detail": {
            "start_close": price_result.get("start_close"),
            "end_close": price_result.get("end_close"),
            "return_pct": price_result.get("return_pct"),
        },
    }


def _collect(fetcher: EvidenceFetcher, ticker: str, start_date: str, end_date: str) -> dict[str, Any]:
    try:
        raw = fetcher(ticker, start_date, end_date)
    except Exception as exc:  # noqa: BLE001 - record failure, never abort the packet
        return {"status": "missing", "summary": None, "error": f"{type(exc).__name__}: {exc}"}
    return _normalize_text_evidence(raw)


def _collect_macro(fetcher: Callable[[str], str], check_date: str) -> dict[str, Any]:
    try:
        raw = fetcher(check_date)
    except Exception as exc:  # noqa: BLE001
        return {"status": "missing", "summary": None, "error": f"{type(exc).__name__}: {exc}"}
    return _normalize_text_evidence(raw)


def _normalize_text_evidence(raw: Any) -> dict[str, Any]:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return {"status": "missing", "summary": None}
    truncated = text[:_MAX_SUMMARY_CHARS]
    return {
        "status": "available",
        "summary": truncated,
        "truncated": len(text) > _MAX_SUMMARY_CHARS,
    }


def _window_lookback_days(start_date: str, end_date: str, *, padding: int = 7) -> int:
    start = parse_date(start_date)
    end = parse_date(end_date)
    return max((end - start).days + padding, padding)


def _default_flow_fetcher(ticker: str, start_date: str, end_date: str) -> str:
    from tradingagents.dataflows.kis_vendor import get_kis_market_signals

    return get_kis_market_signals(ticker, end_date, _window_lookback_days(start_date, end_date))


def _default_dart_fetcher(ticker: str, start_date: str, end_date: str) -> str:
    from tradingagents.dataflows.dart_api import get_dart_events

    return get_dart_events(ticker, start_date, end_date)


def _default_news_fetcher(ticker: str, start_date: str, end_date: str) -> str:
    from tradingagents.dataflows.naver_news import get_news_naver

    return get_news_naver(ticker, start_date, end_date)


def _default_macro_fetcher(check_date: str) -> str:
    from tradingagents.dataflows.ecos_api import get_korea_macro_summary

    return get_korea_macro_summary(check_date)
