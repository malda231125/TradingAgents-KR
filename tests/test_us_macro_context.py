import pandas as pd

from tradingagents.dataflows.feature_packets.market import build_market_packet_from_dataframes
from tradingagents.dataflows.feature_packets.us_macro import (
    build_global_risk_context_from_us_macro,
    build_us_macro_context_from_dataframes,
)


def _frame(values: list[float], start: str = "2026-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(values), freq="D")
    return pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "value": values})


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        }
    )


def test_us_macro_context_computes_rate_bp_and_regimes():
    frames = {
        "DGS2": _frame([4.0] * 25 + [4.2, 4.25, 4.3, 4.35, 4.4, 4.5]),
        "DGS10": _frame([4.1] * 25 + [4.2, 4.25, 4.3, 4.32, 4.35, 4.4]),
        "T10Y2Y": _frame([-0.2] * 31),
        "VIXCLS": _frame([18.0] * 25 + [21.0, 22.0, 23.0, 24.0, 25.0, 26.0]),
        "DTWEXBGS": _frame([100 + i * 0.2 for i in range(31)]),
        "DFF": _frame([4.3] * 31),
        "BAMLH0A0HYM2": _frame([3.5] * 31),
        "CPIAUCSL": _frame([320.0] * 31),
        "UNRATE": _frame([4.0] * 31),
    }

    ctx = build_us_macro_context_from_dataframes(frames, as_of="2026-01-31")

    assert ctx is not None
    assert ctx["rates"]["us_2y"]["latest"] == 4.5
    assert ctx["rates"]["us_2y"]["change_5d_bp"] == 30.0
    assert ctx["rates"]["curve_10y_2y"]["latest"] == -0.2
    assert ctx["risk"]["vix"]["regime"] == "elevated"
    assert ctx["risk"]["credit_spread"]["regime"] == "normal"
    assert ctx["dollar"]["broad_index"]["trend"] == "stronger"
    assert "미국 금리" in ctx["interpretation"]


def test_us_macro_context_handles_missing_series():
    ctx = build_us_macro_context_from_dataframes(
        {"DGS10": _frame([4.0, 4.1, 4.2, 4.3, 4.4, 4.5])},
        as_of="2026-01-06",
    )

    assert ctx is not None
    assert ctx["rates"]["us_10y"]["latest"] == 4.5
    assert any("FRED DGS2" in note for note in ctx["data_quality_notes"])


def test_global_risk_context_derives_from_us_macro():
    ctx = build_us_macro_context_from_dataframes(
        {
            "VIXCLS": _frame([19, 20, 21, 22, 23, 24]),
            "BAMLH0A0HYM2": _frame([3.5] * 6),
            "DTWEXBGS": _frame([100, 101, 102, 103, 104, 105]),
        },
        as_of="2026-01-06",
    )

    risk = build_global_risk_context_from_us_macro(ctx)
    assert risk is not None
    assert risk["source"] == "fred"
    assert risk["vix"]["regime"] == "elevated"


def test_market_packet_serializes_us_macro_context():
    us_macro = {"as_of": "2026-01-31", "interpretation": "test macro"}
    packet = build_market_packet_from_dataframes(
        instrument={"name": "삼성전자", "stock_code": "005930"},
        as_of="2026-01-31",
        ohlcv_df=_ohlcv([100 + i for i in range(70)]),
        us_macro_context=us_macro,
        global_risk_context={"source": "fred"},
    )

    assert packet.us_macro_context == us_macro
    assert packet.global_risk_context == {"source": "fred"}
    block = packet.to_prompt_block()
    assert "us_macro_context" in block
    assert "global_risk_context" in block
