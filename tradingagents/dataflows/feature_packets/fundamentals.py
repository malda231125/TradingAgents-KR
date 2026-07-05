"""Fundamentals feature packet — rule-based interpretation of KIS financial data.

The packet replaces the raw 26k-char text blob produced by
`prefetch_fundamentals_data()`. It captures:

- valuation multiples (PER/PBR/EPS/BPS) from the KIS stock-info endpoint
- profitability snapshot (ROE, operating margin) and YoY direction
- balance-sheet stress indicators (debt ratio, current ratio, stability label)
- earnings momentum direction
- a list of natural-language `signals` bullets
- explicit data quality notes — most importantly, the cashflow proxy warning,
  because KIS does not provide an official cashflow statement
- a `narrative_alignment` block that says whether fundamentals support a
  bullish market narrative or contradict it

Korean field names from KIS responses are matched fuzzily against multiple
candidate keys (the API uses different romanizations across endpoints).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import json
import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Dataclass
# ----------------------------------------------------------------------


@dataclass
class FundamentalsPacket:
    instrument: dict
    as_of: str
    valuation: dict
    profitability: dict
    balance_sheet: dict
    earnings_momentum: dict
    signals: list[str]
    peer_context: Optional[dict] = None
    global_peer_context: Optional[dict] = None
    data_quality_notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        return (
            "```json\n"
            + json.dumps(asdict(self), ensure_ascii=False, indent=2)
            + "\n```"
        )


# ----------------------------------------------------------------------
# Field extraction helpers
# ----------------------------------------------------------------------


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if value in ("", "-", "N/A"):
            return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _get_field(df: pd.DataFrame, candidate_keys: list[str]) -> Optional[str]:
    """Return the first non-null value across the candidate column names.

    KIS endpoints use Korean labels in some places and romanized keys in
    others. We accept either by case-insensitive substring match against the
    DataFrame columns.
    """
    if df is None or df.empty:
        return None

    column_lookup = {str(c).lower(): c for c in df.columns}
    for key in candidate_keys:
        # Exact (case-insensitive) match
        if key.lower() in column_lookup:
            col = column_lookup[key.lower()]
            val = df.iloc[0][col]
            if pd.notna(val) and str(val).strip() not in ("", "-"):
                return str(val).strip()
    # Substring match (column name contains the key)
    for key in candidate_keys:
        for col_lower, col_actual in column_lookup.items():
            if key.lower() in col_lower:
                val = df.iloc[0][col_actual]
                if pd.notna(val) and str(val).strip() not in ("", "-"):
                    return str(val).strip()
    return None


def _get_field_float(df: pd.DataFrame, candidate_keys: list[str]) -> Optional[float]:
    return _safe_float(_get_field(df, candidate_keys))


# ----------------------------------------------------------------------
# Interpretation helpers
# ----------------------------------------------------------------------
#
# NOTE — historical context (Phase 4-C-B):
#
# The previous version of this module exported `_classify_roe`,
# `_classify_debt_ratio`, and `_direction_from_yoy` which assigned
# market-wide threshold labels (e.g. ROE 10% → "average"). Those labels
# were removed because they were industry-blind: a 10% ROE is excellent
# for a bank but mediocre for an internet platform, and the labels
# anchored the downstream analyst LLM into the wrong baseline.
#
# Industry-aware classification is now provided by the `peer_context`
# block (see `feature_packets/peer_context.py`) which compares against
# the actual sector peer median. Tickers without a sector mapping get
# `peer_context=None` and the analyst is told to interpret raw numbers
# directly without an authoritative classification.


# ----------------------------------------------------------------------
# Pure-data builder
# ----------------------------------------------------------------------


def _build_signals_with_peer_context(
    *,
    roe: Optional[float],
    debt_ratio: Optional[float],
    current_ratio: Optional[float],
    revenue_yoy: Optional[float],
    net_income_yoy: Optional[float],
    per: Optional[float],
    peer_context: Optional[dict],
) -> list[str]:
    """Build natural-language signal bullets.

    When `peer_context` is provided, financial ratios are described relative
    to the sector peer median. Otherwise we report raw values without
    market-wide labels — analyst is told to apply industry context itself.
    """
    signals: list[str] = []

    rank_label = {
        "top_third": "섹터 내 상위 1/3",
        "middle_third": "섹터 내 중위",
        "bottom_third": "섹터 내 하위 1/3",
    }

    target_vs_peer = (peer_context or {}).get("target_vs_peer") or {}

    if roe is not None:
        info = target_vs_peer.get("roe") or {}
        rank = info.get("rank")
        diff = info.get("diff_vs_peer_median_pp")
        if rank and diff is not None:
            sign = "+" if diff >= 0 else ""
            signals.append(
                f"ROE {roe:.2f}% — {rank_label[rank]} (peer median 대비 {sign}{diff:.2f}pp)"
            )
        else:
            signals.append(f"ROE {roe:.2f}% — 산업 컨텍스트 비교 불가")

    if debt_ratio is not None:
        info = target_vs_peer.get("debt_ratio") or {}
        rank = info.get("rank")
        diff = info.get("diff_vs_peer_median_pp")
        if rank and diff is not None:
            # Lower debt ratio is better — flip the descriptive direction
            polarity = {
                "top_third": "보통보다 부채 비중 높음",
                "middle_third": "보통 수준",
                "bottom_third": "보통보다 부채 비중 낮음 (안정)",
            }
            sign = "+" if diff >= 0 else ""
            signals.append(
                f"부채비율 {debt_ratio:.2f}% — {polarity[rank]} (peer median 대비 {sign}{diff:.2f}pp)"
            )
        else:
            signals.append(f"부채비율 {debt_ratio:.2f}% — 산업 컨텍스트 비교 불가")

    if current_ratio is not None and current_ratio < 100:
        signals.append(f"유동비율 {current_ratio:.2f}% — 단기 유동성 부족 가능")

    if net_income_yoy is not None:
        if net_income_yoy >= 20:
            signals.append(f"순이익 +{net_income_yoy:.1f}% YoY — 실적 모멘텀 가속")
        elif net_income_yoy <= -20:
            signals.append(f"순이익 {net_income_yoy:.1f}% YoY — 실적 급격히 둔화")

    if revenue_yoy is not None:
        if revenue_yoy >= 10:
            signals.append(f"매출 +{revenue_yoy:.1f}% YoY — 외형 성장 견고")
        elif revenue_yoy <= -10:
            signals.append(f"매출 {revenue_yoy:.1f}% YoY — 외형 위축")

    if per is not None:
        # PER is a market valuation, not a per-industry rule. Keep it as a
        # raw observation only.
        if per > 0 and per < 10:
            signals.append(f"PER {per:.2f} — 저평가 영역(시장 전체 기준)")
        elif per > 30:
            signals.append(f"PER {per:.2f} — 고평가 영역(시장 전체 기준)")

    if not signals:
        signals.append("재무 데이터에서 뚜렷한 신호를 추출하지 못함")

    return signals


def build_fundamentals_packet_from_dataframes(
    *,
    instrument: dict,
    as_of: str,
    stock_info_df: Optional[pd.DataFrame] = None,
    financial_ratio_df: Optional[pd.DataFrame] = None,
    income_statement_df: Optional[pd.DataFrame] = None,
    balance_sheet_df: Optional[pd.DataFrame] = None,
    last_close_price: Optional[float] = None,
    peer_context: Optional[dict] = None,
    global_peer_context: Optional[dict] = None,
    evidence_refs: Optional[list[str]] = None,
) -> FundamentalsPacket:
    """Build a FundamentalsPacket from already-fetched KIS DataFrames.

    Field-source notes (verified against live KIS responses):

    - **EPS / BPS**: live in `financial_ratio_df` as `eps` / `bps`. They are
      NOT in `stock_info_df` despite the function accepting both — the
      stock-info endpoint only carries metadata (name, sector, listing).
    - **PER / PBR**: KIS does not return these directly. They are computed
      here from `last_close_price / EPS` and `last_close_price / BPS`.
      The live builder passes the most recent close from the OHLCV path.
    - **revenue_yoy**: KIS uses `grs` (Growth Rate of Sales), not the more
      common `sale_account_rate` naming.
    - **operating_margin / current_ratio**: NEITHER is exposed by KIS's
      financial-ratio endpoint. They are pulled from `peer_context` which
      computes them deterministically from DART line items
      (영업이익 / 매출액 and 유동자산 / 유동부채). When peer_context is
      absent, both fields stay None.

    The optional `peer_context` block (when provided) carries sector peer
    median comparisons computed via DART's fnlttMultiAcnt endpoint. When
    None, the packet contains raw financial ratios but NO authoritative
    classification labels — the analyst is expected to apply industry
    context itself.
    """
    notes: list[str] = [
        "현금흐름표는 KIS의 inferred proxy이며 official cashflow statement가 아님 — "
        "현금흐름 기반 결론은 제한적으로 해석할 것"
    ]

    # ---- valuation ----
    # EPS / BPS live in the financial_ratio endpoint, NOT stock_info.
    # PER / PBR are computed from the last close price + EPS / BPS because
    # KIS doesn't return them directly anywhere.
    eps = _get_field_float(financial_ratio_df, ["eps", "EPS", "주당순이익"])
    bps = _get_field_float(financial_ratio_df, ["bps", "BPS", "주당순자산"])

    per: Optional[float] = None
    pbr: Optional[float] = None
    if last_close_price is not None and eps is not None and eps != 0:
        per = round(last_close_price / eps, 2)
    if last_close_price is not None and bps is not None and bps != 0:
        pbr = round(last_close_price / bps, 2)

    valuation = {
        "per": per,
        "pbr": pbr,
        "eps": _round(eps),
        "bps": _round(bps),
    }
    if eps is None and bps is None:
        notes.append("KIS 재무비율 응답에 EPS/BPS가 없어 밸류에이션 미산출")
    elif last_close_price is None:
        notes.append("최근 종가가 제공되지 않아 PER/PBR 계산 불가 (EPS/BPS만 제공)")

    # ---- profitability ----
    roe = _get_field_float(financial_ratio_df, ["roe_val", "ROE", "자기자본이익률"])
    net_income_yoy = _get_field_float(
        financial_ratio_df, ["ntin_inrt", "순이익증가율", "net_income_growth"]
    )

    # operating_margin은 KIS financial-ratio에 없음 — peer_context에서 가져옴
    operating_margin: Optional[float] = None
    if peer_context:
        op_margin_block = (peer_context.get("target_vs_peer") or {}).get("operating_margin") or {}
        operating_margin = op_margin_block.get("value_pct")

    profitability = {
        "roe_pct": _round(roe),
        "operating_margin_pct": _round(operating_margin),
        "net_income_yoy_pct": _round(net_income_yoy),
    }

    # ---- balance sheet ----
    debt_ratio = _get_field_float(
        financial_ratio_df, ["lblt_rate", "부채비율", "debt_ratio"]
    )

    # current_ratio도 KIS financial-ratio에 없음 — peer_context에서 가져옴
    current_ratio: Optional[float] = None
    if peer_context:
        cr_block = (peer_context.get("target_vs_peer") or {}).get("current_ratio") or {}
        current_ratio = cr_block.get("value_pct")

    balance_sheet = {
        "debt_ratio_pct": _round(debt_ratio),
        "current_ratio_pct": _round(current_ratio),
    }
    if financial_ratio_df is None or financial_ratio_df.empty:
        notes.append("KIS 재무비율 응답이 비어 있음 — 수익성/안정성 미산출")

    # ---- earnings momentum ----
    # KIS 매출액증가율은 'grs' (Growth Rate of Sales) 컬럼에 있음.
    # bsop_prfi_inrt는 영업이익 증가율(GROWTH RATE)이지 영업이익률(MARGIN)이 아님.
    revenue_yoy = _get_field_float(
        financial_ratio_df, ["grs", "sale_account_rate", "매출액증가율", "revenue_growth"]
    )
    operating_profit_yoy = _get_field_float(
        financial_ratio_df, ["bsop_prfi_inrt", "영업이익증가율", "operating_profit_growth"]
    )

    earnings_momentum = {
        "revenue_yoy_pct": _round(revenue_yoy),
        "operating_profit_yoy_pct": _round(operating_profit_yoy),
        "net_income_yoy_pct": _round(net_income_yoy),
    }

    # ---- signals (peer-aware when peer_context is present) ----
    signals = _build_signals_with_peer_context(
        roe=roe,
        debt_ratio=debt_ratio,
        current_ratio=current_ratio,
        revenue_yoy=revenue_yoy,
        net_income_yoy=net_income_yoy,
        per=per,
        peer_context=peer_context,
    )

    # peer_context interpretation bullet (always last in the list when present)
    if peer_context:
        interpretation = peer_context.get("interpretation")
        if interpretation:
            signals.append(f"peer 비교: {interpretation}")
    else:
        notes.append(
            "peer_context 없음 — 산업/섹터 baseline 비교가 불가하므로 분류 라벨을 생성하지 않음. "
            "analyst는 raw 재무 수치를 산업 맥락에서 직접 해석할 것."
        )

    if global_peer_context:
        interpretation = global_peer_context.get("interpretation")
        if interpretation:
            signals.append(f"글로벌 peer 참고: {interpretation}")

    return FundamentalsPacket(
        instrument={
            "name": instrument.get("name", ""),
            "stock_code": instrument.get("stock_code", ""),
        },
        as_of=as_of,
        valuation=valuation,
        profitability=profitability,
        balance_sheet=balance_sheet,
        earnings_momentum=earnings_momentum,
        signals=signals,
        peer_context=peer_context,
        global_peer_context=global_peer_context,
        data_quality_notes=notes,
        evidence_refs=evidence_refs or [],
    )


# ----------------------------------------------------------------------
# Live builder
# ----------------------------------------------------------------------


def build_fundamentals_packet(ticker: str, trade_date: str) -> FundamentalsPacket:
    """Live convenience builder. Resolves the ticker, fetches the four KIS
    financial DataFrames, the most recent close price (for PER/PBR
    computation), builds the DART peer_context block when sector mapping
    is available, and delegates to the pure-data builder.

    The peer_context block is omitted (None) when:
      - the ticker is not in STOCK_TO_SECTOR
      - DART corp_code resolution fails for the target
      - fewer than 2 sector peers can be resolved to corp_codes
      - DART fnlttMultiAcnt returns no data
    """
    from datetime import datetime, timedelta

    from tradingagents.dataflows.feature_packets.peer_context import build_peer_context
    from tradingagents.dataflows.korea_ticker import get_instrument_profile
    from tradingagents.dataflows.kis_vendor import (
        get_kis_balance_sheet_dataframe,
        get_kis_financial_ratio_dataframe,
        get_kis_income_statement_dataframe,
        get_kis_ohlcv_dataframe,
        get_kis_stock_info_dataframe,
    )

    profile = get_instrument_profile(ticker)
    instrument = {
        "name": profile.get("name") or ticker,
        "stock_code": profile.get("stock_code") or ticker,
    }
    symbol = instrument["stock_code"]

    def _safe_call(label: str, fn, *args, **kwargs) -> Optional[pd.DataFrame]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("KIS %s fetch failed for %s: %s", label, symbol, exc)
            return None

    stock_info = _safe_call("stock_info", get_kis_stock_info_dataframe, symbol)
    ratio = _safe_call("financial_ratio", get_kis_financial_ratio_dataframe, symbol)
    income = _safe_call("income_statement", get_kis_income_statement_dataframe, symbol)
    balance = _safe_call("balance_sheet", get_kis_balance_sheet_dataframe, symbol)

    # Most recent close — needed to compute PER/PBR from EPS/BPS. Use a
    # short 10-day OHLCV fetch since we only need the latest non-empty close.
    last_close: Optional[float] = None
    try:
        end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        start_dt = (end_dt - timedelta(days=10)).strftime("%Y-%m-%d")
        ohlcv = get_kis_ohlcv_dataframe(symbol, start_dt, trade_date)
        if ohlcv is not None and not ohlcv.empty and "Close" in ohlcv.columns:
            closes = pd.to_numeric(ohlcv["Close"], errors="coerce").dropna()
            if not closes.empty:
                last_close = float(closes.iloc[-1])
    except Exception as exc:
        logger.warning("last close fetch failed for %s: %s", symbol, exc)

    # Peer context — degrades gracefully to None on any failure
    try:
        peer_ctx = build_peer_context(symbol, trade_date)
    except Exception as exc:
        logger.warning("peer_context build failed for %s: %s", symbol, exc)
        peer_ctx = None

    global_peer_ctx = _try_build_global_peer_context(symbol, trade_date)

    evidence_refs = [
        f"kis:stock_info:{symbol}",
        f"kis:financial_ratio:{symbol}",
        f"kis:income_statement:{symbol}",
        f"kis:balance_sheet:{symbol}",
    ]
    if last_close is not None:
        evidence_refs.append(f"kis:last_close:{symbol}:{trade_date}")
    if peer_ctx:
        peer_year = (peer_ctx.get("fiscal_period") or {}).get("bsns_year", "")
        peer_report = (peer_ctx.get("fiscal_period") or {}).get("reprt_code", "")
        evidence_refs.append(f"dart:multi_acnt:{peer_year}:{peer_report}")
    if global_peer_ctx:
        evidence_refs.append(f"sec:global_peer:{symbol}:{trade_date}")

    return build_fundamentals_packet_from_dataframes(
        instrument=instrument,
        as_of=trade_date,
        stock_info_df=stock_info,
        financial_ratio_df=ratio,
        income_statement_df=income,
        balance_sheet_df=balance,
        last_close_price=last_close,
        peer_context=peer_ctx,
        global_peer_context=global_peer_ctx,
        evidence_refs=evidence_refs,
    )


def _try_build_global_peer_context(stock_code: str, trade_date: str) -> Optional[dict]:
    """Best-effort SEC EDGAR global peer context."""
    try:
        import os

        from tradingagents.dataflows.config import get_config

        config = get_config()
        if not (config.get("global_data") or {}).get("enable_sec_edgar", True):
            return None
        if not os.environ.get("SEC_USER_AGENT"):
            return None

        from tradingagents.dataflows.feature_packets.global_peer import (
            build_global_peer_context,
        )

        return build_global_peer_context(stock_code, trade_date)
    except Exception as exc:
        logger.warning("global_peer_context build failed for %s: %s", stock_code, exc)
        return None
