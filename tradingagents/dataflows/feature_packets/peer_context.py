"""Peer financial context builder for FundamentalsPacket.

This module solves the "industry-blind anchoring" problem from the
context-compression discussion: rule-based labels like `roe_class: "average"`
are misleading because they classify against a single market-wide threshold,
ignoring that ROE expectations differ wildly by industry (banks: 7-9%
average is good, internet platforms: 15%+ is average).

The peer_context block answers the question "how does this stock's ROE
compare against its actual industry peers?" by fetching peer financials in
a single DART `fnlttMultiAcnt` call, computing the same set of metrics
(ROE / debt ratio / current ratio / operating margin / net margin / YoY
growth) for both target and peers, and reporting:

  - peer median for each metric
  - target's diff vs peer median
  - target's rank within peer group (top_third / middle_third / bottom_third)
  - a one-sentence Korean interpretation that reads like a sector analyst's
    quick-look note

Design notes:

- Pure-data path (`build_peer_context_from_metrics`) is fully unit-testable
  with no network access. The live path (`build_peer_context`) handles the
  DART call and corp_code resolution.
- Per the user's "no fallback" design directive, if the target's sector is
  not in the static mapping, or fewer than 2 peers can be resolved, this
  module returns None and the FundamentalsPacket builder simply omits the
  peer_context field entirely. There is no degenerate "vs broad market"
  fallback.
- The metric set is intentionally limited to what `fnlttMultiAcnt` returns
  (BS + IS line items only). Per-share valuation multiples like PER/PBR are
  NOT in peer_context — those stay in the existing `valuation` block which
  comes from the KIS stock_info endpoint.
"""

from __future__ import annotations

import logging
import statistics
from typing import Optional

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Account name lookup — handles slight variations in DART responses
# ----------------------------------------------------------------------


def _find_account(accounts: dict[str, dict], candidates: list[str]) -> Optional[dict]:
    """Return the first matching account dict by name, or None."""
    for name in candidates:
        if name in accounts:
            return accounts[name]
    # Substring fallback (DART 당기순이익 sometimes appears as "당기순이익(손실)")
    for name in candidates:
        for key in accounts:
            if name in key:
                return accounts[key]
    return None


def _value(accounts: dict[str, dict], candidates: list[str], period: str = "thstrm") -> Optional[float]:
    found = _find_account(accounts, candidates)
    if found is None:
        return None
    return found.get(period)


# ----------------------------------------------------------------------
# Metric computation — turn raw DART line items into ratios
# ----------------------------------------------------------------------


def _safe_div_pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return round(num / den * 100, 2)


def _yoy_pct(thstrm: Optional[float], frmtrm: Optional[float]) -> Optional[float]:
    if thstrm is None or frmtrm is None or frmtrm == 0:
        return None
    return round((thstrm - frmtrm) / abs(frmtrm) * 100, 2)


def compute_metrics_from_accounts(accounts: dict[str, dict[str, Optional[float]]]) -> dict:
    """Compute the standard ratio set from a single company's raw accounts.

    `accounts` is the inner dict from `get_dart_multi_company_financials`:

        {"매출액": {"thstrm": 333605938000000.0, "frmtrm": 300870903000000.0},
         "당기순이익": {...}, ...}

    Returns a dict with computed ratios (None for any metric that can't be
    computed because its inputs are missing).

    Note on banks/insurance/holding companies: DART returns these via the
    same `fnlttMultiAcnt` endpoint but with bank-specific accounts
    (이자수익, 순이자손익, 영업이익(손실), etc.) and no 매출액 line.
    The lookup candidates below cover both general companies and banks
    where reasonable; revenue-related metrics (revenue_yoy, operating_margin)
    will end up None for banks because there is no 매출액 to divide by.
    The peer comparison still works on ROE / debt_ratio which both come
    from BS items every filer reports.
    """
    revenue = _value(accounts, ["매출액"])
    revenue_prev = _value(accounts, ["매출액"], "frmtrm")
    # Banks use 영업이익(손실); general companies use 영업이익. Substring
    # match in _value handles both via the candidate list.
    operating_profit = _value(accounts, ["영업이익", "영업이익(손실)"])
    operating_profit_prev = _value(accounts, ["영업이익", "영업이익(손실)"], "frmtrm")
    net_income = _value(accounts, ["당기순이익", "당기순이익(손실)"])
    net_income_prev = _value(accounts, ["당기순이익", "당기순이익(손실)"], "frmtrm")

    total_assets = _value(accounts, ["자산총계"])
    total_liabilities = _value(accounts, ["부채총계"])
    total_equity = _value(accounts, ["자본총계"])
    current_assets = _value(accounts, ["유동자산"])
    current_liabilities = _value(accounts, ["유동부채"])

    return {
        "roe_pct": _safe_div_pct(net_income, total_equity),
        "debt_ratio_pct": _safe_div_pct(total_liabilities, total_equity),
        "current_ratio_pct": _safe_div_pct(current_assets, current_liabilities),
        "operating_margin_pct": _safe_div_pct(operating_profit, revenue),
        "net_margin_pct": _safe_div_pct(net_income, revenue),
        "revenue_yoy_pct": _yoy_pct(revenue, revenue_prev),
        "operating_profit_yoy_pct": _yoy_pct(operating_profit, operating_profit_prev),
        "net_income_yoy_pct": _yoy_pct(net_income, net_income_prev),
    }


# ----------------------------------------------------------------------
# Ranking and interpretation
# ----------------------------------------------------------------------


def _rank_in_peers(target: Optional[float], peer_values: list[float]) -> Optional[str]:
    """Return 'top_third' / 'middle_third' / 'bottom_third' / None."""
    if target is None or not peer_values:
        return None
    sorted_vals = sorted(peer_values)
    n = len(sorted_vals)
    # How many peers does the target beat?
    beats = sum(1 for v in sorted_vals if v < target)
    pct = beats / n
    if pct >= 2 / 3:
        return "top_third"
    if pct >= 1 / 3:
        return "middle_third"
    return "bottom_third"


def _peer_median(peer_metrics: list[dict], key: str) -> Optional[float]:
    values = [m[key] for m in peer_metrics if m.get(key) is not None]
    if not values:
        return None
    return round(statistics.median(values), 2)


def _diff(target: Optional[float], peer_med: Optional[float]) -> Optional[float]:
    if target is None or peer_med is None:
        return None
    return round(target - peer_med, 2)


def _interpret(
    *,
    roe_rank: Optional[str],
    debt_rank: Optional[str],
    op_margin_rank: Optional[str],
) -> str:
    """Build a one-sentence Korean interpretation from the rank tuple."""
    label = {
        "top_third": "상위",
        "middle_third": "중위",
        "bottom_third": "하위",
    }
    parts: list[str] = []
    if roe_rank:
        parts.append(f"수익성(ROE) 섹터 내 {label[roe_rank]}")
    if op_margin_rank:
        parts.append(f"영업이익률 {label[op_margin_rank]}")
    if debt_rank:
        # For debt ratio, LOWER is better, so flip the interpretation
        flipped = {
            "top_third": "보통보다 높음",
            "middle_third": "평균",
            "bottom_third": "낮은 편(안정)",
        }
        parts.append(f"재무 안정성 {flipped[debt_rank]}")

    if not parts:
        return "peer 비교 데이터 부족"
    return " / ".join(parts)


# ----------------------------------------------------------------------
# Pure-data builder
# ----------------------------------------------------------------------


def build_peer_context_from_metrics(
    *,
    sector_name: str,
    target_corp_code: str,
    target_metrics: dict,
    peer_metrics_by_corp: dict[str, dict],
    bsns_year: str,
    reprt_code: str,
    min_peer_count: int = 2,
) -> Optional[dict]:
    """Build the peer_context block from already-computed metric dicts.

    This is the pure path — caller has already invoked
    `get_dart_multi_company_financials()` and run `compute_metrics_from_accounts`
    on each company. Returns None if there are fewer than `min_peer_count`
    peers with usable data.
    """
    # Drop the target itself in case the caller included it
    peer_metrics = [m for code, m in peer_metrics_by_corp.items() if code != target_corp_code]

    if len(peer_metrics) < min_peer_count:
        return None

    medians = {
        "roe_pct": _peer_median(peer_metrics, "roe_pct"),
        "debt_ratio_pct": _peer_median(peer_metrics, "debt_ratio_pct"),
        "current_ratio_pct": _peer_median(peer_metrics, "current_ratio_pct"),
        "operating_margin_pct": _peer_median(peer_metrics, "operating_margin_pct"),
        "net_margin_pct": _peer_median(peer_metrics, "net_margin_pct"),
        "revenue_yoy_pct": _peer_median(peer_metrics, "revenue_yoy_pct"),
        "net_income_yoy_pct": _peer_median(peer_metrics, "net_income_yoy_pct"),
    }

    def _values(key: str) -> list[float]:
        return [m[key] for m in peer_metrics if m.get(key) is not None]

    roe_rank = _rank_in_peers(target_metrics.get("roe_pct"), _values("roe_pct"))
    debt_rank = _rank_in_peers(target_metrics.get("debt_ratio_pct"), _values("debt_ratio_pct"))
    op_margin_rank = _rank_in_peers(
        target_metrics.get("operating_margin_pct"), _values("operating_margin_pct")
    )
    current_ratio_rank = _rank_in_peers(
        target_metrics.get("current_ratio_pct"), _values("current_ratio_pct")
    )

    target_vs_peer = {
        "roe": {
            "value_pct": target_metrics.get("roe_pct"),
            "diff_vs_peer_median_pp": _diff(target_metrics.get("roe_pct"), medians["roe_pct"]),
            "rank": roe_rank,
        },
        "debt_ratio": {
            "value_pct": target_metrics.get("debt_ratio_pct"),
            "diff_vs_peer_median_pp": _diff(
                target_metrics.get("debt_ratio_pct"), medians["debt_ratio_pct"]
            ),
            "rank": debt_rank,
        },
        "operating_margin": {
            "value_pct": target_metrics.get("operating_margin_pct"),
            "diff_vs_peer_median_pp": _diff(
                target_metrics.get("operating_margin_pct"),
                medians["operating_margin_pct"],
            ),
            "rank": op_margin_rank,
        },
        "current_ratio": {
            "value_pct": target_metrics.get("current_ratio_pct"),
            "diff_vs_peer_median_pp": _diff(
                target_metrics.get("current_ratio_pct"),
                medians["current_ratio_pct"],
            ),
            "rank": current_ratio_rank,
        },
        "net_income_yoy": {
            "value_pct": target_metrics.get("net_income_yoy_pct"),
            "diff_vs_peer_median_pp": _diff(
                target_metrics.get("net_income_yoy_pct"),
                medians["net_income_yoy_pct"],
            ),
        },
    }

    return {
        "sector": sector_name,
        "fiscal_period": {
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
        },
        "peer_count": len(peer_metrics),
        "peer_median": medians,
        "target_vs_peer": target_vs_peer,
        "interpretation": _interpret(
            roe_rank=roe_rank,
            debt_rank=debt_rank,
            op_margin_rank=op_margin_rank,
        ),
    }


# ----------------------------------------------------------------------
# Live builder
# ----------------------------------------------------------------------


# Default fiscal report — most recent annual filing. For trade dates in the
# first quarter when annual filings are not yet available, callers can
# override these.
DEFAULT_REPORT_CODE = "11011"  # 사업보고서 (Annual)


def _default_bsns_year(trade_date: str) -> str:
    """Pick the most recent annual report year for a given trade date.

    For dates in 2026-04-10, we use 2025 because Samsung et al filed their
    2025 annual reports in March 2026. For dates earlier than late March in
    a given year, the previous-previous year is safer (2025 → 2024).

    Heuristic: if the trade month is April or later, use year-1. Otherwise
    use year-2 to be safe.
    """
    try:
        year, month, _day = trade_date.split("-")
        year_int = int(year)
        month_int = int(month)
    except (ValueError, AttributeError):
        return "2024"

    if month_int >= 4:
        return str(year_int - 1)
    return str(year_int - 2)


def build_peer_context(
    stock_code: str,
    trade_date: str,
    *,
    bsns_year: Optional[str] = None,
    reprt_code: str = DEFAULT_REPORT_CODE,
    min_peer_count: int = 2,
) -> Optional[dict]:
    """Live convenience builder.

    Resolves the target stock's sector, gathers peer corp_codes, calls
    DART's multi-company endpoint, computes metrics, and delegates to
    `build_peer_context_from_metrics`. Returns None on any failure path:

    - target stock is not in STOCK_TO_SECTOR
    - target stock's corp_code can't be resolved
    - DART API call fails
    - fewer than `min_peer_count` peers have usable data

    No fallback — by design.
    """
    from tradingagents.dataflows.dart_api import get_dart_multi_company_financials
    from tradingagents.dataflows.korea_ticker import get_corp_code
    from tradingagents.dataflows.sector_index import (
        get_peer_stocks_in_sector,
        get_sector_for_stock,
    )

    sector_name = get_sector_for_stock(stock_code)
    if not sector_name:
        return None

    target_corp_code = get_corp_code(stock_code)
    if not target_corp_code:
        logger.debug("peer_context: target %s has no DART corp_code", stock_code)
        return None

    peer_stock_codes = get_peer_stocks_in_sector(sector_name, exclude=stock_code)
    if not peer_stock_codes:
        return None

    # Resolve peer stock codes to corp_codes; skip ones that don't resolve
    peer_corp_codes: list[str] = []
    for ps in peer_stock_codes:
        cc = get_corp_code(ps)
        if cc:
            peer_corp_codes.append(cc)

    if len(peer_corp_codes) < min_peer_count:
        logger.debug(
            "peer_context: insufficient resolvable peer corp_codes for %s in %s (%d < %d)",
            stock_code,
            sector_name,
            len(peer_corp_codes),
            min_peer_count,
        )
        return None

    fiscal_year = bsns_year or _default_bsns_year(trade_date)

    all_corp_codes = [target_corp_code] + peer_corp_codes
    raw_data = get_dart_multi_company_financials(
        all_corp_codes,
        bsns_year=fiscal_year,
        reprt_code=reprt_code,
    )

    if not raw_data:
        logger.debug(
            "peer_context: DART multi-acnt returned no data for %s/%s",
            fiscal_year,
            reprt_code,
        )
        return None

    target_accounts = raw_data.get(target_corp_code)
    if not target_accounts:
        logger.debug(
            "peer_context: target %s (%s) absent from DART response — perhaps not yet filed",
            stock_code,
            target_corp_code,
        )
        return None

    target_metrics = compute_metrics_from_accounts(target_accounts)

    peer_metrics_by_corp = {}
    for corp_code, accounts in raw_data.items():
        if corp_code == target_corp_code:
            continue
        peer_metrics_by_corp[corp_code] = compute_metrics_from_accounts(accounts)

    return build_peer_context_from_metrics(
        sector_name=sector_name,
        target_corp_code=target_corp_code,
        target_metrics=target_metrics,
        peer_metrics_by_corp=peer_metrics_by_corp,
        bsns_year=fiscal_year,
        reprt_code=reprt_code,
        min_peer_count=min_peer_count,
    )
