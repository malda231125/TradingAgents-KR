"""Market feature packet — rule-based interpretation of OHLCV + macro for analysts.

The packet replaces the raw text blob produced by `prefetch_market_data()`.
It contains:

- typed price / MA / volume snapshots computed deterministically with pandas
- a `regime` classification derived from MA position and short-term momentum
- a list of natural-language `signals` bullets that capture the essential
  story (e.g. "5일선 위, 60일선 미회복")
- a small set of `macro_highlights` parsed from the ECOS macro summary text
- `evidence_refs` that point back to the raw vendor sources

Builders are split so that the pure-data path (`*_from_dataframes`) is fully
unit-testable without any network or API key.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import json
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------


@dataclass
class MarketPacket:
    instrument: dict
    as_of: str
    price: dict
    moving_averages: dict
    volume: dict
    volatility: dict
    technical_indicators: dict
    regime: dict
    signals: list[str]
    macro_highlights: list[str]
    sector_context: Optional[dict] = None
    investor_flow: Optional[dict] = None
    us_macro_context: Optional[dict] = None
    global_risk_context: Optional[dict] = None
    data_quality_notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Render the packet as a fenced JSON block suitable for a system prompt."""
        return (
            "```json\n"
            + json.dumps(asdict(self), ensure_ascii=False, indent=2)
            + "\n```"
        )


# ----------------------------------------------------------------------
# Numeric helpers
# ----------------------------------------------------------------------


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def _pct_change(later: Optional[float], earlier: Optional[float]) -> Optional[float]:
    if later is None or earlier is None or earlier == 0:
        return None
    return round((later / earlier - 1.0) * 100.0, 2)


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    if pd.isna(value):
        return None
    return round(float(value), digits)


# ----------------------------------------------------------------------
# Regime classification (rule-based, intentionally simple)
# ----------------------------------------------------------------------


def _classify_regime(
    *,
    above_ma20: Optional[bool],
    above_ma60: Optional[bool],
    change_5d_pct: Optional[float],
    change_20d_pct: Optional[float],
) -> dict:
    """Map MA position + momentum into one of a fixed set of regimes.

    The labels are intentionally limited so downstream prompts can rely on
    them as enums. The descriptions are short Korean sentences so the analyst
    LLM can use them directly without re-deriving the same observation.
    """
    if above_ma20 is None or above_ma60 is None:
        return {
            "label": "insufficient_history",
            "description": "이동평균을 산출할 충분한 거래일이 없습니다.",
        }

    if above_ma20 and above_ma60:
        if (change_20d_pct or 0) > 5:
            return {
                "label": "trending_up",
                "description": "20일선·60일선 모두 상회. 중기 추세 상승 진행 중.",
            }
        return {
            "label": "above_trend",
            "description": "20일선·60일선 모두 상회. 추세는 견고하나 강한 모멘텀은 아님.",
        }

    if above_ma20 and not above_ma60:
        if (change_5d_pct or 0) > 3:
            return {
                "label": "recovering_after_drawdown",
                "description": "20일선 위로 회복했으나 60일선 아래. 단기 반등 진행 중, 중기 추세 전환 미확정.",
            }
        return {
            "label": "rebounding_into_resistance",
            "description": "20일선 회복은 했으나 60일선 저항. 추세 전환 신호 약함.",
        }

    if not above_ma20 and above_ma60:
        return {
            "label": "pullback_in_uptrend",
            "description": "60일선은 유지하나 20일선 이탈. 상승 추세 내 단기 조정.",
        }

    # Both below
    if (change_5d_pct or 0) < -3:
        return {
            "label": "breaking_down",
            "description": "20일선·60일선 모두 이탈하며 단기 낙폭 확대. 추세 전환 위험.",
        }
    return {
        "label": "below_trend",
        "description": "20일선·60일선 모두 아래. 약세 추세 또는 횡보 하단.",
    }


# ----------------------------------------------------------------------
# Signal bullets (natural language interpretation)
# ----------------------------------------------------------------------


def _build_signal_bullets(
    *,
    price: dict,
    ma: dict,
    volume: dict,
    volatility: dict,
    regime_label: str,
) -> list[str]:
    bullets: list[str] = []

    change_5d = price.get("change_5d_pct")
    change_20d = price.get("change_20d_pct")
    if change_5d is not None and abs(change_5d) >= 3:
        direction = "상승" if change_5d > 0 else "하락"
        bullets.append(f"최근 5거래일 {change_5d:+.2f}% {direction} — 단기 모멘텀 뚜렷")
    if change_20d is not None and abs(change_20d) >= 5:
        direction = "상승" if change_20d > 0 else "하락"
        bullets.append(f"최근 20거래일 {change_20d:+.2f}% {direction} — 중기 추세 영향력 있음")

    above5 = ma.get("above_ma5")
    above20 = ma.get("above_ma20")
    above60 = ma.get("above_ma60")

    if above20 is True and above60 is False:
        bullets.append("20일선 회복했으나 60일선 미회복 — 추세 전환 미확정")
    elif above20 is True and above60 is True:
        bullets.append("20일선·60일선 모두 상회 — 추세 견고")
    elif above20 is False and above60 is False:
        bullets.append("20일선·60일선 모두 이탈 — 약세 영역")
    elif above20 is False and above60 is True:
        bullets.append("60일선은 지지하나 20일선 이탈 — 상승 추세 내 조정 가능성")

    if above5 is True and above20 is False:
        bullets.append("5일선만 회복한 단기 반등 — 지속 가능성 약함")

    vol_ratio = volume.get("ratio_vs_20d_avg")
    if vol_ratio is not None:
        if vol_ratio >= 1.8:
            bullets.append(f"거래량이 20일 평균의 {vol_ratio:.2f}배 — 강한 참여 확증")
        elif vol_ratio >= 1.3:
            bullets.append(f"거래량이 20일 평균의 {vol_ratio:.2f}배 — 평균 이상 참여")
        elif vol_ratio <= 0.5:
            bullets.append(f"거래량이 20일 평균의 {vol_ratio:.2f}배 — 참여 매우 약함")
        elif vol_ratio < 0.8:
            bullets.append(f"거래량이 20일 평균의 {vol_ratio:.2f}배 — 모멘텀 확증 약함")

    std_pct = volatility.get("std_20d_pct")
    if std_pct is not None and std_pct >= 3.0:
        bullets.append(f"20일 표준편차 {std_pct:.2f}% — 변동성 높음, 손절폭 확장 필요")

    pct_from_high = volatility.get("pct_from_52w_high")
    if pct_from_high is not None and pct_from_high <= -25:
        bullets.append(f"52주 고점 대비 {pct_from_high:.1f}% — 깊은 조정 영역")
    elif pct_from_high is not None and pct_from_high >= -3:
        bullets.append(f"52주 고점 대비 {pct_from_high:.1f}% — 신고가 인접")

    if regime_label == "breaking_down":
        bullets.append("regime: breaking_down — 추세 전환 위험 감안한 진입 자제 권고")
    elif regime_label == "trending_up":
        bullets.append("regime: trending_up — 모멘텀 매매 환경 우호")
    elif regime_label == "recovering_after_drawdown":
        bullets.append("regime: recovering_after_drawdown — 거래량 확증 후 진입 검토")

    if not bullets:
        bullets.append("뚜렷한 단기/중기 신호 없음 — 관망 적정")

    return bullets


# ----------------------------------------------------------------------
# Sector context — stock vs sector index relative performance
# ----------------------------------------------------------------------


def _compute_sector_context(
    *,
    sector_name: str,
    sector_ohlcv_df: pd.DataFrame,
    stock_change_5d_pct: Optional[float],
    stock_change_20d_pct: Optional[float],
) -> Optional[dict]:
    """Build the deterministic sector_context block from a sector index history.

    Returns None if the sector OHLCV is too short to compute meaningful
    deltas. The caller is responsible for omitting the field on None — we
    do NOT fall back to a "broad market" baseline because that would be
    misleading anchoring.
    """
    if sector_ohlcv_df is None or sector_ohlcv_df.empty:
        return None

    closes = pd.to_numeric(sector_ohlcv_df["Close"], errors="coerce").dropna()
    if len(closes) < 6:
        return None

    last = _safe_float(closes.iloc[-1])
    five_back = _safe_float(closes.iloc[-6]) if len(closes) >= 6 else None
    twenty_back = _safe_float(closes.iloc[-21]) if len(closes) >= 21 else None

    sector_change_5d = _pct_change(last, five_back)
    sector_change_20d = _pct_change(last, twenty_back)

    def _diff(stock_pct: Optional[float], sector_pct: Optional[float]) -> Optional[float]:
        if stock_pct is None or sector_pct is None:
            return None
        return round(stock_pct - sector_pct, 2)

    stock_relative_5d = _diff(stock_change_5d_pct, sector_change_5d)
    stock_relative_20d = _diff(stock_change_20d_pct, sector_change_20d)

    def _outperform(diff: Optional[float]) -> Optional[bool]:
        if diff is None:
            return None
        return diff > 0

    return {
        "sector_name": sector_name,
        "sector_change_5d_pct": sector_change_5d,
        "sector_change_20d_pct": sector_change_20d,
        "stock_relative_5d_pct": stock_relative_5d,
        "stock_relative_20d_pct": stock_relative_20d,
        "outperforming_sector_short_term": _outperform(stock_relative_5d),
        "outperforming_sector_medium_term": _outperform(stock_relative_20d),
    }


def _sector_context_signals(sector_context: Optional[dict]) -> list[str]:
    """Generate natural-language bullets describing sector relative performance."""
    if not sector_context:
        return []

    bullets: list[str] = []
    name = sector_context.get("sector_name", "섹터")

    sector_5d = sector_context.get("sector_change_5d_pct")
    rel_5d = sector_context.get("stock_relative_5d_pct")
    sector_20d = sector_context.get("sector_change_20d_pct")
    rel_20d = sector_context.get("stock_relative_20d_pct")

    if sector_5d is not None and rel_5d is not None:
        if abs(rel_5d) >= 1.0:
            verb = "outperform" if rel_5d > 0 else "underperform"
            bullets.append(
                f"{name} 섹터 5거래일 {sector_5d:+.2f}% 대비 종목 상대 {rel_5d:+.2f}%p — 단기 {verb}"
            )
        else:
            bullets.append(
                f"{name} 섹터 5거래일 {sector_5d:+.2f}%, 종목 상대 {rel_5d:+.2f}%p — 섹터와 동조"
            )

    if sector_20d is not None and rel_20d is not None and abs(rel_20d) >= 2.0:
        verb = "outperform" if rel_20d > 0 else "underperform"
        bullets.append(
            f"{name} 섹터 20거래일 {sector_20d:+.2f}% 대비 종목 상대 {rel_20d:+.2f}%p — 중기 {verb}"
        )

    return bullets


# ----------------------------------------------------------------------
# Investor flow context — foreign / institutional net buy pressure
# ----------------------------------------------------------------------


def _compute_investor_flow_context(
    investor_flow_df: Optional[pd.DataFrame],
    *,
    max_days: int = 5,
) -> Optional[dict]:
    """Build a compact foreign/institutional flow block.

    Korean large caps are often driven by foreign net buying and whether
    institutions absorb or amplify that pressure. This block is deterministic
    evidence for the analyst; it does not make the buy/sell decision itself.
    """
    if investor_flow_df is None or investor_flow_df.empty:
        return None

    required = {"Date", "ForeignNetBuyShares", "InstitutionNetBuyShares"}
    if not required.issubset(set(investor_flow_df.columns)):
        return None

    df = investor_flow_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["ForeignNetBuyShares"] = pd.to_numeric(
        df["ForeignNetBuyShares"], errors="coerce"
    )
    df["InstitutionNetBuyShares"] = pd.to_numeric(
        df["InstitutionNetBuyShares"], errors="coerce"
    )
    if "Close" in df.columns:
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    else:
        df["Close"] = None
    df = df.dropna(subset=["Date"]).sort_values("Date").tail(max_days)
    if df.empty:
        return None

    recent = df.iloc[-1]
    foreign_series = df["ForeignNetBuyShares"].dropna()
    institution_series = df["InstitutionNetBuyShares"].dropna()

    def _streak(values: list[float], predicate) -> int:
        streak = 0
        for value in reversed(values):
            if predicate(value):
                streak += 1
            else:
                break
        return streak

    foreign_values = [float(v) for v in foreign_series.tolist()]
    institution_values = [float(v) for v in institution_series.tolist()]
    foreign_sell_streak = _streak(foreign_values, lambda v: v < 0)
    foreign_buy_streak = _streak(foreign_values, lambda v: v > 0)

    recent_foreign = _safe_float(recent.get("ForeignNetBuyShares"))
    recent_institution = _safe_float(recent.get("InstitutionNetBuyShares"))
    net_combined = None
    if recent_foreign is not None or recent_institution is not None:
        net_combined = (recent_foreign or 0.0) + (recent_institution or 0.0)

    absorption = "unknown"
    if recent_foreign is not None and recent_institution is not None:
        if recent_foreign < 0 and recent_institution > 0:
            absorption = "institution_absorbing_foreign_selling"
        elif recent_foreign < 0 and recent_institution < 0:
            absorption = "both_selling"
        elif recent_foreign > 0 and recent_institution > 0:
            absorption = "both_buying"
        elif recent_foreign > 0 and recent_institution < 0:
            absorption = "foreign_buying_institution_selling"
        else:
            absorption = "mixed_or_flat"

    recent_rows = []
    for _, row in df.iterrows():
        recent_rows.append(
            {
                "date": row["Date"].strftime("%Y-%m-%d"),
                "close": _round(_safe_float(row.get("Close"))),
                "foreign_net_buy_shares": int(row["ForeignNetBuyShares"])
                if pd.notna(row.get("ForeignNetBuyShares"))
                else None,
                "institution_net_buy_shares": int(row["InstitutionNetBuyShares"])
                if pd.notna(row.get("InstitutionNetBuyShares"))
                else None,
            }
        )

    return {
        "lookback_days": len(recent_rows),
        "latest_date": recent["Date"].strftime("%Y-%m-%d"),
        "latest": {
            "foreign_net_buy_shares": int(recent_foreign)
            if recent_foreign is not None
            else None,
            "institution_net_buy_shares": int(recent_institution)
            if recent_institution is not None
            else None,
            "combined_foreign_institution_net_buy_shares": int(net_combined)
            if net_combined is not None
            else None,
            "absorption": absorption,
        },
        "streaks": {
            "foreign_net_sell_days": foreign_sell_streak,
            "foreign_net_buy_days": foreign_buy_streak,
        },
        "window_totals": {
            "foreign_net_buy_shares": int(foreign_series.sum())
            if not foreign_series.empty
            else None,
            "institution_net_buy_shares": int(institution_series.sum())
            if not institution_series.empty
            else None,
        },
        "recent_rows": recent_rows,
    }


def _investor_flow_signals(investor_flow: Optional[dict]) -> list[str]:
    if not investor_flow:
        return []

    latest = investor_flow.get("latest") or {}
    streaks = investor_flow.get("streaks") or {}
    foreign = latest.get("foreign_net_buy_shares")
    institution = latest.get("institution_net_buy_shares")
    absorption = latest.get("absorption")
    sell_streak = streaks.get("foreign_net_sell_days") or 0
    buy_streak = streaks.get("foreign_net_buy_days") or 0

    bullets: list[str] = []
    if foreign is not None and institution is not None:
        bullets.append(
            f"최근 투자자 수급: 외국인 {foreign:+,}주, 기관 {institution:+,}주"
        )
    if sell_streak >= 3:
        bullets.append(f"외국인 {sell_streak}거래일 연속 순매도 — 대형주 수급 부담")
    elif buy_streak >= 3:
        bullets.append(f"외국인 {buy_streak}거래일 연속 순매수 — 수급 모멘텀 우호")

    if absorption == "institution_absorbing_foreign_selling":
        bullets.append("외국인 매도를 기관이 흡수 중 — 하락 압력 완충 여부 확인")
    elif absorption == "both_selling":
        bullets.append("외국인·기관 동반 순매도 — 수급 악화 신호")
    elif absorption == "both_buying":
        bullets.append("외국인·기관 동반 순매수 — 수급 확증 신호")
    elif absorption == "foreign_buying_institution_selling":
        bullets.append("외국인 매수 우위이나 기관 매도 출회 — 주도 수급 지속성 확인")

    return bullets


# ----------------------------------------------------------------------
# Macro highlights — parse the ECOS macro summary text
# ----------------------------------------------------------------------


_MACRO_KEYWORDS = (
    "기준금리",
    "원/달러",
    "원달러",
    "KOSPI",
    "코스피",
    "M2",
    "소비자물가",
    "CPI",
    "환율",
)


def _parse_macro_highlights(macro_text: str | None, max_items: int = 6) -> list[str]:
    """Pull a few key indicator lines out of the long ECOS macro text.

    The ECOS summary returns up to ~100 KeyStatisticList rows. Most of them are
    not directly useful for an equity trading decision. We keep only the lines
    that mention a known set of indicators.
    """
    if not macro_text:
        return []

    out: list[str] = []
    for raw_line in macro_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(kw in line for kw in _MACRO_KEYWORDS):
            cleaned = line.lstrip("[]- ")
            if cleaned and cleaned not in out:
                out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


# ----------------------------------------------------------------------
# Pure-data builder
# ----------------------------------------------------------------------


def build_market_packet_from_dataframes(
    *,
    instrument: dict,
    as_of: str,
    ohlcv_df: pd.DataFrame,
    indicators: Optional[dict] = None,
    macro_text: Optional[str] = None,
    sector_name: Optional[str] = None,
    sector_ohlcv_df: Optional[pd.DataFrame] = None,
    investor_flow_df: Optional[pd.DataFrame] = None,
    us_macro_context: Optional[dict] = None,
    global_risk_context: Optional[dict] = None,
    evidence_refs: Optional[list[str]] = None,
) -> MarketPacket:
    """Build a MarketPacket from already-fetched DataFrames.

    Parameters
    ----------
    instrument : dict
        Resolved instrument profile (must contain at least `name` and `stock_code`).
    as_of : str
        Trade date in yyyy-mm-dd format. Used in the packet header.
    ohlcv_df : pd.DataFrame
        DataFrame with columns Date, Open, High, Low, Close, Volume sorted ascending.
    indicators : dict, optional
        Optional dict of additional indicator values such as
        {"rsi_14": 58.2, "macd": 1240.5, "macd_signal": 980.3}.
        Caller is responsible for computation; passing None is allowed.
    macro_text : str, optional
        The raw ECOS macro summary text. We extract a few key bullets from it.
    sector_name : str, optional
        Sector name (KIS index name) for the stock. When None, the
        sector_context block is omitted entirely.
    sector_ohlcv_df : pd.DataFrame, optional
        Sector index daily history matching the same columns as ohlcv_df.
        Combined with sector_name to compute the sector_context block.
        When either sector_name or sector_ohlcv_df is missing or empty, the
        sector_context block is omitted (no fallback to a generic baseline).
    evidence_refs : list[str], optional
        Lookup IDs that downstream nodes can use to fetch raw fallback data.
    """
    notes: list[str] = []
    investor_flow = _compute_investor_flow_context(investor_flow_df)

    if ohlcv_df is None or ohlcv_df.empty:
        return MarketPacket(
            instrument={
                "name": instrument.get("name", ""),
                "stock_code": instrument.get("stock_code", ""),
            },
            as_of=as_of,
            price={},
            moving_averages={},
            volume={},
            volatility={},
            technical_indicators=indicators or {},
            regime={
                "label": "no_data",
                "description": "OHLCV 데이터가 없어 분석 불가.",
            },
            signals=["가격 데이터를 가져오지 못했습니다."],
            macro_highlights=_parse_macro_highlights(macro_text),
            sector_context=None,
            investor_flow=investor_flow,
            us_macro_context=us_macro_context,
            global_risk_context=global_risk_context,
            data_quality_notes=["KIS OHLCV 응답이 비어 있음"],
            evidence_refs=evidence_refs or [],
        )

    df = ohlcv_df.copy()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    closes = df["Close"].dropna()
    if closes.empty:
        notes.append("유효한 종가 데이터가 없습니다.")

    last_close = _safe_float(closes.iloc[-1]) if not closes.empty else None
    prev_close = _safe_float(closes.iloc[-2]) if len(closes) >= 2 else None
    close_5d_ago = _safe_float(closes.iloc[-6]) if len(closes) >= 6 else None
    close_20d_ago = _safe_float(closes.iloc[-21]) if len(closes) >= 21 else None

    price = {
        "close": _round(last_close),
        "previous_close": _round(prev_close),
        "change_1d_pct": _pct_change(last_close, prev_close),
        "change_5d_pct": _pct_change(last_close, close_5d_ago),
        "change_20d_pct": _pct_change(last_close, close_20d_ago),
    }

    ma5 = _safe_float(closes.tail(5).mean()) if len(closes) >= 5 else None
    ma20 = _safe_float(closes.tail(20).mean()) if len(closes) >= 20 else None
    ma60 = _safe_float(closes.tail(60).mean()) if len(closes) >= 60 else None

    def _above(value: Optional[float], reference: Optional[float]) -> Optional[bool]:
        if value is None or reference is None:
            return None
        return value >= reference

    moving_averages = {
        "ma5": _round(ma5),
        "ma20": _round(ma20),
        "ma60": _round(ma60),
        "above_ma5": _above(last_close, ma5),
        "above_ma20": _above(last_close, ma20),
        "above_ma60": _above(last_close, ma60),
        "ma20_distance_pct": _pct_change(last_close, ma20),
        "ma60_distance_pct": _pct_change(last_close, ma60),
    }

    volumes = df["Volume"].dropna()
    latest_volume = _safe_float(volumes.iloc[-1]) if not volumes.empty else None
    avg_20d_volume = _safe_float(volumes.tail(20).mean()) if len(volumes) >= 20 else None
    vol_ratio = None
    if latest_volume is not None and avg_20d_volume not in (None, 0):
        vol_ratio = round(latest_volume / avg_20d_volume, 2)

    volume_block = {
        "latest": int(latest_volume) if latest_volume is not None else None,
        "avg_20d": int(avg_20d_volume) if avg_20d_volume is not None else None,
        "ratio_vs_20d_avg": vol_ratio,
        "is_abnormal_high": (vol_ratio is not None and vol_ratio >= 1.8),
        "is_abnormal_low": (vol_ratio is not None and vol_ratio <= 0.5),
    }

    # Volatility: 20-day daily-return standard deviation in percent
    std_20d_pct: Optional[float] = None
    if len(closes) >= 21:
        returns = closes.pct_change().dropna().tail(20)
        if not returns.empty:
            std_20d_pct = round(float(returns.std() * 100), 2)

    # 52-week high/low (use whatever history we have, capped at 252 trading days)
    window = closes.tail(252)
    high_52w = _safe_float(window.max()) if not window.empty else None
    low_52w = _safe_float(window.min()) if not window.empty else None

    volatility = {
        "std_20d_pct": std_20d_pct,
        "high_52w": _round(high_52w),
        "low_52w": _round(low_52w),
        "pct_from_52w_high": _pct_change(last_close, high_52w),
        "pct_from_52w_low": _pct_change(last_close, low_52w),
    }

    regime = _classify_regime(
        above_ma20=moving_averages["above_ma20"],
        above_ma60=moving_averages["above_ma60"],
        change_5d_pct=price["change_5d_pct"],
        change_20d_pct=price["change_20d_pct"],
    )

    signals = _build_signal_bullets(
        price=price,
        ma=moving_averages,
        volume=volume_block,
        volatility=volatility,
        regime_label=regime["label"],
    )

    # Sector context — only built when both name and OHLCV are provided.
    # Omitted entirely otherwise to avoid misleading anchoring.
    sector_context = None
    if sector_name and sector_ohlcv_df is not None and not sector_ohlcv_df.empty:
        sector_context = _compute_sector_context(
            sector_name=sector_name,
            sector_ohlcv_df=sector_ohlcv_df,
            stock_change_5d_pct=price.get("change_5d_pct"),
            stock_change_20d_pct=price.get("change_20d_pct"),
        )
        signals.extend(_sector_context_signals(sector_context))

    if investor_flow is not None:
        signals.extend(_investor_flow_signals(investor_flow))

    if len(closes) < 60:
        notes.append(f"60일 미만의 거래일 데이터({len(closes)}일)로 일부 지표가 누락될 수 있음")

    return MarketPacket(
        instrument={
            "name": instrument.get("name", ""),
            "stock_code": instrument.get("stock_code", ""),
        },
        as_of=as_of,
        price=price,
        moving_averages=moving_averages,
        volume=volume_block,
        volatility=volatility,
        technical_indicators=indicators or {},
        regime=regime,
        signals=signals,
        macro_highlights=_parse_macro_highlights(macro_text),
        sector_context=sector_context,
        investor_flow=investor_flow,
        us_macro_context=us_macro_context,
        global_risk_context=global_risk_context,
        data_quality_notes=notes,
        evidence_refs=evidence_refs or [],
    )


# ----------------------------------------------------------------------
# Live builder — calls the KIS / ECOS vendors
# ----------------------------------------------------------------------


_INDICATOR_LOOKBACK_DAYS = 90


def build_market_packet(
    ticker: str,
    trade_date: str,
    *,
    lookback_days: int = 120,
) -> MarketPacket:
    """Live convenience builder. Resolves the ticker, fetches OHLCV via KIS,
    optionally enriches with stockstats indicators, an ECOS macro snippet,
    and the matching sector index history, then delegates to
    `build_market_packet_from_dataframes`.

    Failures in optional layers (indicators, macro, sector) are caught and
    logged so that the packet still degrades gracefully — the analyst will
    see the deterministic price/MA/volume part even if any enrichment layer
    is unavailable. Sector context is omitted (set to None) when the stock
    is not in the curated sector mapping or the KIS sector index call
    fails; it does NOT fall back to a generic broad-market baseline.
    """
    from tradingagents.dataflows.korea_ticker import get_instrument_profile
    from tradingagents.dataflows.kis_vendor import (
        get_kis_investor_flow_dataframe,
        get_kis_ohlcv_dataframe,
        get_kis_sector_index_dataframe,
    )
    from tradingagents.dataflows.sector_index import get_sector_index_code_for_stock

    profile = get_instrument_profile(ticker)
    instrument = {
        "name": profile.get("name") or ticker,
        "stock_code": profile.get("stock_code") or ticker,
    }
    symbol = instrument["stock_code"]

    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=lookback_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    try:
        ohlcv = get_kis_ohlcv_dataframe(symbol, start_date, trade_date)
    except Exception as exc:
        logger.warning("KIS OHLCV fetch failed for %s: %s", symbol, exc)
        ohlcv = pd.DataFrame()

    try:
        investor_flow_df = get_kis_investor_flow_dataframe(symbol)
    except Exception as exc:
        logger.warning("KIS investor flow fetch failed for %s: %s", symbol, exc)
        investor_flow_df = pd.DataFrame()

    indicators = _try_compute_indicators(ohlcv)
    macro_text = _try_fetch_macro_text(trade_date)
    us_macro_context = _try_build_us_macro_context(trade_date)
    global_risk_context = None
    if us_macro_context:
        try:
            from tradingagents.dataflows.feature_packets.us_macro import (
                build_global_risk_context_from_us_macro,
            )

            global_risk_context = build_global_risk_context_from_us_macro(us_macro_context)
        except Exception as exc:
            logger.debug("global risk context derivation skipped: %s", exc)

    sector_name: Optional[str] = None
    sector_ohlcv: Optional[pd.DataFrame] = None
    sector_lookup = get_sector_index_code_for_stock(symbol)
    if sector_lookup is not None:
        sector_name, sector_code = sector_lookup
        try:
            sector_ohlcv = get_kis_sector_index_dataframe(
                sector_code, start_date, trade_date
            )
        except Exception as exc:
            logger.warning(
                "KIS sector index fetch failed for %s (%s/%s): %s",
                symbol,
                sector_name,
                sector_code,
                exc,
            )
            sector_ohlcv = None

    evidence_refs = [
        f"kis:ohlcv:{symbol}:{start_date}:{trade_date}",
    ]
    if investor_flow_df is not None and not investor_flow_df.empty:
        evidence_refs.append(f"kis:investor_flow:{symbol}:recent")
    if indicators:
        evidence_refs.append(f"stockstats:indicators:{symbol}")
    if macro_text:
        evidence_refs.append(f"ecos:macro_summary:{trade_date}")
    if us_macro_context:
        evidence_refs.append(f"fred:us_macro:{trade_date}")
    if sector_lookup is not None:
        evidence_refs.append(f"kis:sector_index:{sector_lookup[1]}:{start_date}:{trade_date}")

    return build_market_packet_from_dataframes(
        instrument=instrument,
        as_of=trade_date,
        ohlcv_df=ohlcv,
        indicators=indicators,
        macro_text=macro_text,
        sector_name=sector_name,
        sector_ohlcv_df=sector_ohlcv,
        investor_flow_df=investor_flow_df,
        us_macro_context=us_macro_context,
        global_risk_context=global_risk_context,
        evidence_refs=evidence_refs,
    )


def _try_compute_indicators(ohlcv: pd.DataFrame) -> dict:
    """Best-effort RSI/MACD extraction. Returns {} on failure or sparse data."""
    if ohlcv is None or ohlcv.empty or len(ohlcv) < 30:
        return {}
    try:
        from tradingagents.dataflows.stockstats_utils import _clean_dataframe, wrap

        df = ohlcv.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = _clean_dataframe(df)
        wrapped = wrap(df)
        # Touching the attribute triggers stockstats to compute and cache it.
        rsi_series = wrapped["rsi_14"]
        macd_series = wrapped["macd"]
        macd_signal_series = wrapped["macds"]

        return {
            "rsi_14": _round(_safe_float(rsi_series.dropna().iloc[-1])) if not rsi_series.dropna().empty else None,
            "macd": _round(_safe_float(macd_series.dropna().iloc[-1])) if not macd_series.dropna().empty else None,
            "macd_signal": _round(_safe_float(macd_signal_series.dropna().iloc[-1])) if not macd_signal_series.dropna().empty else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("indicator computation skipped: %s", exc)
        return {}


def _try_fetch_macro_text(trade_date: str) -> Optional[str]:
    """Best-effort ECOS macro summary fetch. Returns None on failure."""
    try:
        from tradingagents.dataflows.ecos_api import get_korea_macro_summary

        return get_korea_macro_summary(trade_date)
    except Exception as exc:
        logger.debug("ECOS macro summary skipped: %s", exc)
        return None


def _try_build_us_macro_context(trade_date: str) -> Optional[dict]:
    """Best-effort FRED US macro context. Returns None when disabled/unavailable."""
    try:
        import os

        from tradingagents.dataflows.config import get_config

        config = get_config()
        if not (config.get("global_data") or {}).get("enable_fred", True):
            return None
        if not os.environ.get("FRED_API_KEY"):
            return None

        from tradingagents.dataflows.feature_packets.us_macro import build_us_macro_context

        return build_us_macro_context(trade_date)
    except Exception as exc:
        logger.warning("FRED US macro context skipped: %s", exc)
        return None
