"""US macro context builder backed by FRED.

The output is a compact context card for Korean equity analysis. It keeps
latest values and short-window deltas, not raw time series.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd


FRED_SERIES = {
    "DGS2": "us_2y",
    "DGS10": "us_10y",
    "T10Y2Y": "curve_10y_2y",
    "VIXCLS": "vix",
    "DTWEXBGS": "broad_dollar_index",
    "DFF": "fed_funds_effective",
    "BAMLH0A0HYM2": "high_yield_spread",
    "CPIAUCSL": "cpi",
    "UNRATE": "unemployment_rate",
}


def _normalize_frame(df: pd.DataFrame | None, as_of: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "value"])
    out = df.copy()
    if "date" in out.columns and "Date" not in out.columns:
        out = out.rename(columns={"date": "Date"})
    if "VALUE" in out.columns and "value" not in out.columns:
        out = out.rename(columns={"VALUE": "value"})
    if "Date" not in out.columns or "value" not in out.columns:
        return pd.DataFrame(columns=["Date", "value"])
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    as_of_ts = pd.Timestamp(as_of)
    out = out.dropna(subset=["Date", "value"])
    out = out[out["Date"] <= as_of_ts].sort_values("Date").reset_index(drop=True)
    return out


def _latest(df: pd.DataFrame) -> Optional[float]:
    if df.empty:
        return None
    return round(float(df["value"].iloc[-1]), 4)


def _prev_value(df: pd.DataFrame, periods_back: int) -> Optional[float]:
    if len(df) <= periods_back:
        return None
    return float(df["value"].iloc[-1 - periods_back])


def _bp_change(df: pd.DataFrame, periods_back: int) -> Optional[float]:
    latest = _latest(df)
    previous = _prev_value(df, periods_back)
    if latest is None or previous is None:
        return None
    return round((latest - previous) * 100, 1)


def _pct_change(df: pd.DataFrame, periods_back: int) -> Optional[float]:
    latest = _latest(df)
    previous = _prev_value(df, periods_back)
    if latest is None or previous in (None, 0):
        return None
    return round((latest / previous - 1) * 100, 2)


def _rate_block(df: pd.DataFrame) -> dict:
    return {
        "latest": _latest(df),
        "change_5d_bp": _bp_change(df, 5),
        "change_20d_bp": _bp_change(df, 20),
    }


def _vix_regime(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value < 15:
        return "calm"
    if value < 20:
        return "normal"
    if value < 30:
        return "elevated"
    return "stressed"


def _credit_regime(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value < 4:
        return "normal"
    if value < 6:
        return "elevated"
    return "stressed"


def _dollar_trend(change_20d_pct: Optional[float]) -> Optional[str]:
    if change_20d_pct is None:
        return None
    if change_20d_pct >= 0.75:
        return "stronger"
    if change_20d_pct <= -0.75:
        return "weaker"
    return "flat"


def _field_count(block: dict) -> int:
    count = 0
    for value in block.values():
        if isinstance(value, dict):
            count += _field_count(value)
        elif value is not None:
            count += 1
    return count


def _build_interpretation(context: dict) -> str:
    parts: list[str] = []

    us_2y = (context.get("rates") or {}).get("us_2y") or {}
    us_10y = (context.get("rates") or {}).get("us_10y") or {}
    curve = (context.get("rates") or {}).get("curve_10y_2y") or {}
    vix = (context.get("risk") or {}).get("vix") or {}
    credit = (context.get("risk") or {}).get("credit_spread") or {}
    dollar = (context.get("dollar") or {}).get("broad_index") or {}

    if (us_2y.get("change_5d_bp") or 0) >= 10 or (us_10y.get("change_5d_bp") or 0) >= 10:
        parts.append("미국 금리 상승은 성장주와 고PER 종목에 할인율 부담")
    elif (us_2y.get("change_5d_bp") or 0) <= -10 or (us_10y.get("change_5d_bp") or 0) <= -10:
        parts.append("미국 금리 하락은 성장주 밸류에이션 부담 완화 요인")

    if curve.get("latest") is not None and curve["latest"] < 0:
        parts.append("장단기 금리차 역전은 경기 둔화 리스크를 동반")

    if vix.get("regime") in ("elevated", "stressed"):
        parts.append("VIX 상승 구간이라 한국 증시 외국인 수급과 갭 리스크 점검 필요")

    if credit.get("regime") in ("elevated", "stressed"):
        parts.append("신용 스프레드가 높아 위험자산 선호 약화 가능성")

    if dollar.get("trend") == "stronger":
        parts.append("달러 강세는 원화 약세와 외국인 수급 부담, 수출주 환율 효과가 혼재")
    elif dollar.get("trend") == "weaker":
        parts.append("달러 약세는 원화와 신흥국 위험자산에는 우호적")

    if not parts:
        return "미국 거시 환경은 뚜렷한 방향성보다 중립적 리스크 점검 요인으로 해석."
    return " / ".join(parts) + "."


def build_global_risk_context_from_us_macro(us_macro_context: Optional[dict]) -> Optional[dict]:
    """Derive a small risk-regime block from the broader US macro context."""
    if not us_macro_context:
        return None
    risk = us_macro_context.get("risk") or {}
    dollar = us_macro_context.get("dollar") or {}
    if not risk and not dollar:
        return None
    return {
        "source": "fred",
        "as_of": us_macro_context.get("as_of"),
        "vix": risk.get("vix"),
        "credit_spread": risk.get("credit_spread"),
        "dollar_trend": (dollar.get("broad_index") or {}).get("trend"),
        "interpretation": us_macro_context.get("interpretation"),
    }


def build_us_macro_context_from_dataframes(
    series_frames: dict[str, pd.DataFrame],
    *,
    as_of: str,
) -> Optional[dict]:
    """Build compact US macro context from already-fetched FRED frames."""
    normalized = {
        series_id: _normalize_frame(frame, as_of)
        for series_id, frame in (series_frames or {}).items()
    }

    notes = []
    for series_id in FRED_SERIES:
        if normalized.get(series_id, pd.DataFrame()).empty:
            notes.append(f"FRED {series_id} 데이터 없음")

    rates = {
        "us_2y": _rate_block(normalized.get("DGS2", pd.DataFrame())),
        "us_10y": _rate_block(normalized.get("DGS10", pd.DataFrame())),
        "curve_10y_2y": _rate_block(normalized.get("T10Y2Y", pd.DataFrame())),
        "fed_funds_effective": {
            "latest": _latest(normalized.get("DFF", pd.DataFrame())),
            "change_20d_bp": _bp_change(normalized.get("DFF", pd.DataFrame()), 20),
        },
    }

    vix_df = normalized.get("VIXCLS", pd.DataFrame())
    vix_latest = _latest(vix_df)
    credit_df = normalized.get("BAMLH0A0HYM2", pd.DataFrame())
    credit_latest = _latest(credit_df)
    risk = {
        "vix": {
            "latest": vix_latest,
            "change_5d_pct": _pct_change(vix_df, 5),
            "regime": _vix_regime(vix_latest),
        },
        "credit_spread": {
            "latest": credit_latest,
            "change_20d_bp": _bp_change(credit_df, 20),
            "regime": _credit_regime(credit_latest),
        },
    }

    dollar_df = normalized.get("DTWEXBGS", pd.DataFrame())
    dollar_change = _pct_change(dollar_df, 20)
    dollar = {
        "broad_index": {
            "latest": _latest(dollar_df),
            "change_20d_pct": dollar_change,
            "trend": _dollar_trend(dollar_change),
        }
    }

    macro = {
        "cpi": {"latest": _latest(normalized.get("CPIAUCSL", pd.DataFrame()))},
        "unemployment_rate": {"latest": _latest(normalized.get("UNRATE", pd.DataFrame()))},
    }

    context = {
        "as_of": as_of,
        "rates": rates,
        "risk": risk,
        "dollar": dollar,
        "macro": macro,
        "interpretation": "",
        "confidence": "low",
        "data_quality_notes": notes,
    }
    available = _field_count(
        {
            "rates": rates,
            "risk": risk,
            "dollar": dollar,
            "macro": macro,
        }
    )
    if available == 0:
        return None
    if available >= 12:
        context["confidence"] = "high"
    elif available >= 6:
        context["confidence"] = "medium"
    context["interpretation"] = _build_interpretation(context)
    return context


def build_us_macro_context(trade_date: str) -> Optional[dict]:
    """Live builder that fetches FRED data and returns the context card."""
    from tradingagents.dataflows.fred_api import get_fred_latest_window

    frames = get_fred_latest_window(FRED_SERIES.keys(), trade_date, lookback_days=180)
    return build_us_macro_context_from_dataframes(frames, as_of=trade_date)
