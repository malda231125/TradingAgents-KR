"""Tests for the deterministic feature packet builders.

These tests stay on the pure-data path (`*_from_dataframes`) so they need
no network access and no KIS / ECOS keys.
"""

import json

import pandas as pd
import pytest

from tradingagents.dataflows.feature_packets.market import (
    MarketPacket,
    _classify_regime,
    _compute_investor_flow_context,
    _compute_sector_context,
    _investor_flow_signals,
    _parse_macro_highlights,
    _sector_context_signals,
    build_market_packet_from_dataframes,
)
from tradingagents.dataflows.feature_packets.fundamentals import (
    FundamentalsPacket,
    build_fundamentals_packet_from_dataframes,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _make_ohlcv(closes: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame ending on a known date."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n

    base_date = pd.Timestamp("2026-04-10")
    dates = [(base_date - pd.Timedelta(days=(n - 1 - i))).strftime("%Y-%m-%d") for i in range(n)]

    return pd.DataFrame(
        {
            "Date": dates,
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": volumes,
        }
    )


SAMSUNG_INSTRUMENT = {"name": "삼성전자", "stock_code": "005930"}


# ----------------------------------------------------------------------
# Market packet — happy path
# ----------------------------------------------------------------------


class TestMarketPacketHappyPath:
    def test_basic_packet_for_uptrend_history(self):
        # Steady uptrend over 70 days: from 100 to 170
        closes = [100 + i for i in range(70)]
        df = _make_ohlcv(closes)

        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
        )

        assert isinstance(packet, MarketPacket)
        assert packet.instrument == SAMSUNG_INSTRUMENT
        assert packet.as_of == "2026-04-10"

        # Last close is 169
        assert packet.price["close"] == 169.0
        assert packet.price["change_1d_pct"] is not None
        assert packet.price["change_5d_pct"] is not None
        assert packet.price["change_20d_pct"] is not None

        # In a steady uptrend, latest close should be above MA20 and MA60
        assert packet.moving_averages["above_ma20"] is True
        assert packet.moving_averages["above_ma60"] is True
        assert packet.regime["label"] in ("trending_up", "above_trend")

        # We should have at least one signal bullet
        assert len(packet.signals) >= 1

    def test_recovery_after_drawdown_regime(self):
        # 60 days flat at 100, then a sharp 10-day rally to 115
        closes = [100.0] * 60 + [100 + i * 1.5 for i in range(10)]
        df = _make_ohlcv(closes)

        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
        )

        # 20-day MA gets dragged up by the rally → above_ma20 True.
        # 60-day MA mostly reflects the flat period → above_ma60 True too
        # in this synthetic case. The regime should still be a bullish label,
        # not a bearish one.
        assert packet.regime["label"] in (
            "trending_up",
            "above_trend",
            "recovering_after_drawdown",
            "rebounding_into_resistance",
        )
        # 5-day change is strongly positive
        assert packet.price["change_5d_pct"] > 5

    def test_breaking_down_regime(self):
        # Long uptrend then a sharp drop in last 10 days
        closes = [100 + i for i in range(60)] + [160 - i * 4 for i in range(10)]
        df = _make_ohlcv(closes)

        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
        )

        # Latest close (~124) should be below the 20-day MA after the drop
        assert packet.moving_averages["above_ma20"] is False
        # Recent 5-day change must be negative
        assert packet.price["change_5d_pct"] < 0
        assert packet.regime["label"] in ("breaking_down", "below_trend")

    def test_packet_serializes_to_prompt_block(self):
        df = _make_ohlcv([100 + i for i in range(70)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT, as_of="2026-04-10", ohlcv_df=df
        )
        block = packet.to_prompt_block()

        assert block.startswith("```json")
        assert block.endswith("```")

        # Strip fence and verify it's valid JSON
        body = block.strip("`").lstrip("json").strip()
        parsed = json.loads(body)
        assert parsed["instrument"]["stock_code"] == "005930"
        assert "regime" in parsed
        assert "signals" in parsed


# ----------------------------------------------------------------------
# Market packet — degenerate / edge cases
# ----------------------------------------------------------------------


class TestMarketPacketEdgeCases:
    def test_empty_ohlcv_returns_no_data_packet(self):
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=pd.DataFrame(),
        )
        assert packet.regime["label"] == "no_data"
        assert packet.signals  # has at least one bullet
        assert packet.data_quality_notes  # warning recorded

    def test_short_history_omits_long_horizon_metrics(self):
        # Only 10 trading days — not enough for 20d/60d MA
        df = _make_ohlcv([100 + i for i in range(10)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT, as_of="2026-04-10", ohlcv_df=df
        )

        assert packet.moving_averages["ma20"] is None
        assert packet.moving_averages["ma60"] is None
        assert packet.moving_averages["above_ma20"] is None
        assert packet.regime["label"] == "insufficient_history"
        # data_quality_notes should mention the short window
        assert any("거래일" in note for note in packet.data_quality_notes)

    def test_volume_ratio_flags_abnormal_high(self):
        closes = [100 + i for i in range(40)]
        # Last day has 5x average volume
        volumes = [1_000_000] * 39 + [5_000_000]
        df = _make_ohlcv(closes, volumes=volumes)
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT, as_of="2026-04-10", ohlcv_df=df
        )

        assert packet.volume["ratio_vs_20d_avg"] is not None
        assert packet.volume["ratio_vs_20d_avg"] >= 1.8
        assert packet.volume["is_abnormal_high"] is True

    def test_sector_context_omitted_when_no_sector_data(self):
        df = _make_ohlcv([100 + i for i in range(40)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
        )
        # No sector data passed → omitted (None)
        assert packet.sector_context is None

    def test_sector_context_omitted_when_only_name_no_ohlcv(self):
        df = _make_ohlcv([100 + i for i in range(40)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
            sector_name="KRX 반도체",
            sector_ohlcv_df=None,
        )
        assert packet.sector_context is None

    def test_sector_context_omitted_when_only_ohlcv_no_name(self):
        df = _make_ohlcv([100 + i for i in range(40)])
        sector_df = _make_ohlcv([200 + i for i in range(40)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
            sector_name=None,
            sector_ohlcv_df=sector_df,
        )
        assert packet.sector_context is None

    def test_sector_context_built_when_both_provided(self):
        # Stock: +10% over 5 days
        stock = _make_ohlcv([100, 101, 102, 103, 104, 110])
        # Sector: +5% over 5 days → stock outperforms by 4.55 pp
        sector = _make_ohlcv([200, 201, 202, 203, 204, 210])

        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=stock,
            sector_name="KRX 반도체",
            sector_ohlcv_df=sector,
        )

        assert packet.sector_context is not None
        ctx = packet.sector_context
        assert ctx["sector_name"] == "KRX 반도체"
        assert ctx["sector_change_5d_pct"] == pytest.approx(5.0, abs=0.01)
        assert ctx["stock_relative_5d_pct"] is not None
        assert ctx["stock_relative_5d_pct"] > 0  # outperforming
        assert ctx["outperforming_sector_short_term"] is True

        # A sector signal bullet should be added to the signals list
        assert any("KRX 반도체" in s for s in packet.signals)

    def test_investor_flow_context_included_when_provided(self):
        df = _make_ohlcv([100 + i for i in range(40)])
        flow = pd.DataFrame(
            {
                "Date": [
                    "2026-04-06",
                    "2026-04-07",
                    "2026-04-08",
                    "2026-04-09",
                    "2026-04-10",
                ],
                "Close": [136, 137, 138, 139, 140],
                "ForeignNetBuyShares": [-1000, -2000, -3000, -4000, -5000],
                "InstitutionNetBuyShares": [500, 600, 700, 800, 900],
            }
        )
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
            investor_flow_df=flow,
        )

        assert packet.investor_flow is not None
        assert packet.investor_flow["streaks"]["foreign_net_sell_days"] == 5
        assert (
            packet.investor_flow["latest"]["absorption"]
            == "institution_absorbing_foreign_selling"
        )
        assert any("외국인 5거래일 연속 순매도" in s for s in packet.signals)

    def test_sector_context_underperformance(self):
        # Stock: +2% over 5 days
        stock = _make_ohlcv([100, 100.5, 101, 101.5, 101.8, 102])
        # Sector: +8% over 5 days → stock underperforms
        sector = _make_ohlcv([200, 203, 206, 209, 212, 216])

        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=stock,
            sector_name="KRX 반도체",
            sector_ohlcv_df=sector,
        )

        assert packet.sector_context is not None
        ctx = packet.sector_context
        assert ctx["stock_relative_5d_pct"] < 0
        assert ctx["outperforming_sector_short_term"] is False
        assert any("underperform" in s for s in packet.signals)

    def test_sector_context_omitted_when_sector_history_too_short(self):
        df = _make_ohlcv([100 + i for i in range(40)])
        # Only 3 days of sector data — insufficient for 5d change
        short_sector = _make_ohlcv([200, 201, 202])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
            sector_name="KRX 반도체",
            sector_ohlcv_df=short_sector,
        )
        # _compute_sector_context returns None for <6 closes
        assert packet.sector_context is None

    def test_macro_highlights_extracted_from_text(self):
        macro = (
            "=== Korea Macro Summary (ECOS) ===\n"
            "[주요 경제지표 - 최신값]\n"
            "  [통화] 기준금리: 3.50 % (M)\n"
            "  [환율] 원/달러 환율: 1380 원 (D)\n"
            "  [증시] KOSPI 지수: 2780 pt (D)\n"
            "  [기타] 무관한 라인입니다\n"
        )
        df = _make_ohlcv([100 + i for i in range(40)])
        packet = build_market_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            ohlcv_df=df,
            macro_text=macro,
        )

        joined = " ".join(packet.macro_highlights)
        assert "기준금리" in joined
        assert "원/달러" in joined
        assert "KOSPI" in joined
        # Unrelated line is filtered out
        assert "무관한" not in joined


# ----------------------------------------------------------------------
# Regime classification unit tests (no DataFrame needed)
# ----------------------------------------------------------------------


class TestComputeSectorContext:
    """Unit tests for the deterministic sector context calculator."""

    def test_returns_none_for_empty_dataframe(self):
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=pd.DataFrame(),
            stock_change_5d_pct=5.0,
            stock_change_20d_pct=10.0,
        )
        assert result is None


    def test_returns_none_for_too_short_history(self):
        # 5 closes is exactly at the boundary; we require >= 6 for 5d change
        df = pd.DataFrame({"Close": [100, 101, 102, 103, 104]})
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=df,
            stock_change_5d_pct=5.0,
            stock_change_20d_pct=None,
        )
        assert result is None

    def test_basic_5d_calculation(self):
        # 6 closes → 5-day change
        df = pd.DataFrame({"Close": [100, 102, 104, 106, 108, 110]})
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=df,
            stock_change_5d_pct=15.0,
            stock_change_20d_pct=None,
        )
        assert result is not None
        assert result["sector_change_5d_pct"] == pytest.approx(10.0, abs=0.01)
        # stock 15% - sector 10% = +5pp relative
        assert result["stock_relative_5d_pct"] == pytest.approx(5.0, abs=0.01)
        assert result["outperforming_sector_short_term"] is True
        # No 20d data → 20d fields are None
        assert result["sector_change_20d_pct"] is None
        assert result["stock_relative_20d_pct"] is None
        assert result["outperforming_sector_medium_term"] is None

    def test_20d_calculation_when_history_long_enough(self):
        # 21 closes → both 5d and 20d work
        closes = [100 + i for i in range(21)]  # 100 → 120
        df = pd.DataFrame({"Close": closes})
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=df,
            stock_change_5d_pct=10.0,
            stock_change_20d_pct=25.0,
        )
        assert result is not None
        # Sector 20d: (120 - 100) / 100 = 20%
        assert result["sector_change_20d_pct"] == pytest.approx(20.0, abs=0.01)
        # Stock 25% - sector 20% = +5pp
        assert result["stock_relative_20d_pct"] == pytest.approx(5.0, abs=0.01)
        assert result["outperforming_sector_medium_term"] is True

    def test_underperformance_flagged(self):
        df = pd.DataFrame({"Close": [100, 102, 104, 106, 108, 110]})
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=df,
            stock_change_5d_pct=2.0,
            stock_change_20d_pct=None,
        )
        # stock 2% - sector 10% = -8pp
        assert result["stock_relative_5d_pct"] == pytest.approx(-8.0, abs=0.01)
        assert result["outperforming_sector_short_term"] is False

    def test_handles_none_stock_change(self):
        df = pd.DataFrame({"Close": [100, 102, 104, 106, 108, 110]})
        result = _compute_sector_context(
            sector_name="KRX 반도체",
            sector_ohlcv_df=df,
            stock_change_5d_pct=None,
            stock_change_20d_pct=None,
        )
        # We still build the sector_change_5d_pct, but relative calc is None
        assert result is not None
        assert result["sector_change_5d_pct"] is not None
        assert result["stock_relative_5d_pct"] is None
        assert result["outperforming_sector_short_term"] is None


class TestInvestorFlowContext:
    def test_returns_none_for_missing_columns(self):
        result = _compute_investor_flow_context(pd.DataFrame({"Date": ["2026-04-10"]}))
        assert result is None

    def test_detects_foreign_buying_with_both_buying_absorption(self):
        df = pd.DataFrame(
            {
                "Date": ["2026-04-08", "2026-04-09", "2026-04-10"],
                "Close": [100, 101, 102],
                "ForeignNetBuyShares": [10, 20, 30],
                "InstitutionNetBuyShares": [5, 6, 7],
            }
        )
        ctx = _compute_investor_flow_context(df)

        assert ctx is not None
        assert ctx["latest"]["foreign_net_buy_shares"] == 30
        assert ctx["latest"]["absorption"] == "both_buying"
        assert ctx["streaks"]["foreign_net_buy_days"] == 3
        signals = _investor_flow_signals(ctx)
        assert any("외국인 3거래일 연속 순매수" in s for s in signals)
        assert any("외국인·기관 동반 순매수" in s for s in signals)


class TestSectorContextSignals:
    def test_empty_for_none_input(self):
        assert _sector_context_signals(None) == []

    def test_outperformance_bullet(self):
        ctx = {
            "sector_name": "KRX 반도체",
            "sector_change_5d_pct": 3.0,
            "stock_relative_5d_pct": 4.0,
            "sector_change_20d_pct": None,
            "stock_relative_20d_pct": None,
        }
        signals = _sector_context_signals(ctx)
        assert any("outperform" in s and "KRX 반도체" in s for s in signals)

    def test_underperformance_bullet(self):
        ctx = {
            "sector_name": "KRX 반도체",
            "sector_change_5d_pct": 5.0,
            "stock_relative_5d_pct": -3.0,
            "sector_change_20d_pct": None,
            "stock_relative_20d_pct": None,
        }
        signals = _sector_context_signals(ctx)
        assert any("underperform" in s for s in signals)

    def test_in_line_with_sector_when_relative_small(self):
        ctx = {
            "sector_name": "KRX 반도체",
            "sector_change_5d_pct": 3.0,
            "stock_relative_5d_pct": 0.3,  # within +/- 1%
            "sector_change_20d_pct": None,
            "stock_relative_20d_pct": None,
        }
        signals = _sector_context_signals(ctx)
        assert any("동조" in s for s in signals)

    def test_medium_term_bullet_emitted_when_significant(self):
        ctx = {
            "sector_name": "KRX 반도체",
            "sector_change_5d_pct": 1.0,
            "stock_relative_5d_pct": 0.2,
            "sector_change_20d_pct": 5.0,
            "stock_relative_20d_pct": 4.5,
        }
        signals = _sector_context_signals(ctx)
        # Both short-term in-line bullet and medium-term outperform bullet
        assert any("중기" in s and "outperform" in s for s in signals)


class TestRegimeClassifier:
    def test_above_both_ma_with_momentum(self):
        regime = _classify_regime(
            above_ma20=True, above_ma60=True, change_5d_pct=2.0, change_20d_pct=10.0
        )
        assert regime["label"] == "trending_up"

    def test_above_both_no_momentum(self):
        regime = _classify_regime(
            above_ma20=True, above_ma60=True, change_5d_pct=1.0, change_20d_pct=2.0
        )
        assert regime["label"] == "above_trend"

    def test_above_ma20_below_ma60_with_rally(self):
        regime = _classify_regime(
            above_ma20=True, above_ma60=False, change_5d_pct=5.0, change_20d_pct=3.0
        )
        assert regime["label"] == "recovering_after_drawdown"

    def test_pullback_in_uptrend(self):
        regime = _classify_regime(
            above_ma20=False, above_ma60=True, change_5d_pct=-2.0, change_20d_pct=5.0
        )
        assert regime["label"] == "pullback_in_uptrend"

    def test_breaking_down(self):
        regime = _classify_regime(
            above_ma20=False, above_ma60=False, change_5d_pct=-5.0, change_20d_pct=-10.0
        )
        assert regime["label"] == "breaking_down"

    def test_insufficient_history(self):
        regime = _classify_regime(
            above_ma20=None, above_ma60=None, change_5d_pct=None, change_20d_pct=None
        )
        assert regime["label"] == "insufficient_history"


# ----------------------------------------------------------------------
# Fundamentals packet — happy path
# ----------------------------------------------------------------------


class TestFundamentalsPacketHappyPath:
    def test_strong_company_packet(self):
        # EPS / BPS live in financial_ratio, NOT stock_info. PER / PBR are
        # computed from last_close_price + EPS / BPS.
        # 'grs' is the KIS column name for revenue YoY growth.
        ratio = pd.DataFrame(
            [
                {
                    "roe_val": "15.2",
                    "lblt_rate": "30.5",
                    "ntin_inrt": "22.3",
                    "grs": "12.0",
                    "bsop_prfi_inrt": "18.5",
                    "eps": "16320",
                    "bps": "156900",
                }
            ]
        )

        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            last_close_price=204000.0,
        )

        assert isinstance(packet, FundamentalsPacket)
        # PER = 204000 / 16320 = 12.5
        assert packet.valuation["per"] == 12.5
        # PBR = 204000 / 156900 = 1.30
        assert packet.valuation["pbr"] == 1.3
        assert packet.valuation["eps"] == 16320.0
        assert packet.valuation["bps"] == 156900.0
        assert packet.profitability["roe_pct"] == 15.2
        assert packet.balance_sheet["debt_ratio_pct"] == 30.5
        assert packet.earnings_momentum["revenue_yoy_pct"] == 12.0
        # roe_class / stability / narrative_alignment were intentionally
        # removed in Phase 4-C-B because they applied market-wide thresholds
        # that ignored industry context. Their replacement is peer_context.
        assert "roe_class" not in packet.profitability
        assert "stability" not in packet.balance_sheet
        assert not hasattr(packet, "narrative_alignment") or packet.peer_context is None

        # peer_context is None when caller doesn't pass one
        assert packet.peer_context is None
        # operating_margin / current_ratio are sourced from peer_context
        # only — None when no peer context
        assert packet.profitability["operating_margin_pct"] is None
        assert packet.balance_sheet["current_ratio_pct"] is None

        # Cashflow proxy warning must always be present
        assert any("proxy" in note.lower() or "현금흐름" in note for note in packet.data_quality_notes)

        # When peer_context is absent, packet must explicitly note that
        assert any("peer_context 없음" in note for note in packet.data_quality_notes)

    def test_weak_company_packet(self):
        # weak company — ratios live in financial_ratio. current_ratio is
        # NOT in KIS so the "유동비율" signal can only fire via peer_context.
        ratio = pd.DataFrame(
            [
                {
                    "roe_val": "2.1",
                    "lblt_rate": "180",
                    "ntin_inrt": "-30",
                    "grs": "-12",
                    "eps": "1200",
                    "bps": "60000",
                }
            ]
        )

        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            last_close_price=54000.0,
        )

        # Raw values still present
        assert packet.profitability["roe_pct"] == 2.1
        assert packet.balance_sheet["debt_ratio_pct"] == 180.0
        assert packet.earnings_momentum["net_income_yoy_pct"] == -30.0
        # Sharply deteriorating earnings still flagged
        assert any("실적 급격히 둔화" in s for s in packet.signals)

    def test_per_pbr_computed_from_close_and_eps_bps(self):
        ratio = pd.DataFrame([{"roe_val": "10", "eps": "5000", "bps": "50000"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            last_close_price=100000.0,
        )
        # PER = 100000 / 5000 = 20.0
        assert packet.valuation["per"] == 20.0
        # PBR = 100000 / 50000 = 2.0
        assert packet.valuation["pbr"] == 2.0

    def test_per_pbr_none_when_close_missing(self):
        ratio = pd.DataFrame([{"eps": "5000", "bps": "50000"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            last_close_price=None,
        )
        assert packet.valuation["per"] is None
        assert packet.valuation["pbr"] is None
        # but raw EPS/BPS still surfaced
        assert packet.valuation["eps"] == 5000.0
        assert packet.valuation["bps"] == 50000.0
        # data_quality_notes explains why
        assert any("최근 종가" in note for note in packet.data_quality_notes)

    def test_per_pbr_none_when_eps_zero(self):
        ratio = pd.DataFrame([{"eps": "0", "bps": "50000"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            last_close_price=100000.0,
        )
        # Division-by-zero protection
        assert packet.valuation["per"] is None
        assert packet.valuation["pbr"] == 2.0  # BPS still computes

    def test_grs_alias_for_revenue_yoy(self):
        # The bug we fixed: KIS uses 'grs' (Growth Rate of Sales), not
        # 'sale_account_rate' or '매출액증가율'.
        ratio = pd.DataFrame([{"grs": "8.5"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
        )
        assert packet.earnings_momentum["revenue_yoy_pct"] == 8.5

    def test_operating_margin_sourced_from_peer_context(self):
        # KIS financial-ratio does not expose operating margin. It must come
        # from peer_context.target_vs_peer.operating_margin.value_pct, which
        # is computed deterministically from DART line items
        # (영업이익 / 매출액).
        peer_ctx = {
            "sector": "KRX 반도체",
            "peer_count": 3,
            "peer_median": {},
            "target_vs_peer": {
                "operating_margin": {
                    "value_pct": 13.07,
                    "diff_vs_peer_median_pp": -5.0,
                    "rank": "middle_third",
                },
                "current_ratio": {
                    "value_pct": 232.77,
                    "diff_vs_peer_median_pp": 30.0,
                    "rank": "top_third",
                },
            },
            "interpretation": "(test)",
            "fiscal_period": {"bsns_year": "2025", "reprt_code": "11011"},
        }
        ratio = pd.DataFrame([{"roe_val": "10"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
            peer_context=peer_ctx,
        )
        # operating_margin pulled from peer_context, NOT from misinterpreted
        # bsop_prfi_inrt (which is operating-profit growth rate, not margin)
        assert packet.profitability["operating_margin_pct"] == 13.07
        # current_ratio also pulled from peer_context
        assert packet.balance_sheet["current_ratio_pct"] == 232.77

    def test_operating_profit_yoy_unaffected_by_margin_fix(self):
        # bsop_prfi_inrt is the CORRECT field for operating profit YoY
        # growth — that lookup must still work after the fix.
        ratio = pd.DataFrame([{"bsop_prfi_inrt": "33.23"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
        )
        assert packet.earnings_momentum["operating_profit_yoy_pct"] == 33.23
        # And it must NOT have leaked into operating_margin (the original bug)
        assert packet.profitability["operating_margin_pct"] is None

    def test_packet_serializes_to_prompt_block(self):
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=pd.DataFrame(
                [{"roe_val": "10", "lblt_rate": "40", "ntin_inrt": "8", "eps": "1000", "bps": "30000"}]
            ),
            last_close_price=10000.0,
        )
        block = packet.to_prompt_block()
        body = block.strip("`").lstrip("json").strip()
        parsed = json.loads(body)
        # PER = 10000 / 1000 = 10
        assert parsed["valuation"]["per"] == 10.0
        assert parsed["peer_context"] is None
        # Verify deleted labels are NOT present
        assert "narrative_alignment" not in parsed
        assert "roe_class" not in parsed["profitability"]
        assert "stability" not in parsed["balance_sheet"]


class TestFundamentalsPacketWithPeerContext:
    """Phase 4-C-B: peer_context block integration."""

    def _make_peer_context(self):
        return {
            "sector": "KRX 은행",
            "fiscal_period": {"bsns_year": "2025", "reprt_code": "11011"},
            "peer_count": 5,
            "peer_median": {
                "roe_pct": 8.5,
                "debt_ratio_pct": 880.0,
                "operating_margin_pct": 35.0,
                "net_income_yoy_pct": 12.0,
            },
            "target_vs_peer": {
                "roe": {
                    "value_pct": 12.0,
                    "diff_vs_peer_median_pp": 3.5,
                    "rank": "top_third",
                },
                "debt_ratio": {
                    "value_pct": 850.0,
                    "diff_vs_peer_median_pp": -30.0,
                    "rank": "bottom_third",
                },
                "operating_margin": {
                    "value_pct": 38.0,
                    "diff_vs_peer_median_pp": 3.0,
                    "rank": "middle_third",
                },
                "net_income_yoy": {
                    "value_pct": 18.0,
                    "diff_vs_peer_median_pp": 6.0,
                },
            },
            "interpretation": "수익성(ROE) 섹터 내 상위 / 영업이익률 중위 / 재무 안정성 낮은 편(안정)",
        }

    def test_peer_context_attached_to_packet(self):
        ctx = self._make_peer_context()
        packet = build_fundamentals_packet_from_dataframes(
            instrument={"name": "KB금융", "stock_code": "105560"},
            as_of="2026-04-10",
            stock_info_df=pd.DataFrame([{"per": "8", "pbr": "0.6"}]),
            financial_ratio_df=pd.DataFrame([{"roe_val": "12", "lblt_rate": "850"}]),
            peer_context=ctx,
        )
        assert packet.peer_context == ctx
        # Interpretation bullet appended to signals
        assert any("peer 비교" in s for s in packet.signals)
        # ROE bullet uses peer rank, not market threshold
        assert any("섹터 내 상위 1/3" in s for s in packet.signals)
        # Debt ratio uses flipped polarity
        assert any("부채 비중 낮음" in s for s in packet.signals)
        # data_quality_notes does NOT have the "peer_context 없음" warning
        assert not any("peer_context 없음" in note for note in packet.data_quality_notes)

    def test_peer_context_signal_uses_diff(self):
        ctx = self._make_peer_context()
        packet = build_fundamentals_packet_from_dataframes(
            instrument={"name": "KB금융", "stock_code": "105560"},
            as_of="2026-04-10",
            financial_ratio_df=pd.DataFrame([{"roe_val": "12"}]),
            peer_context=ctx,
        )
        roe_bullets = [s for s in packet.signals if s.startswith("ROE")]
        assert len(roe_bullets) == 1
        # Bullet should mention the peer median diff (+3.50pp)
        assert "3.5" in roe_bullets[0]

    def test_packet_serializes_with_peer_context(self):
        ctx = self._make_peer_context()
        packet = build_fundamentals_packet_from_dataframes(
            instrument={"name": "KB금융", "stock_code": "105560"},
            as_of="2026-04-10",
            financial_ratio_df=pd.DataFrame([{"roe_val": "12", "lblt_rate": "850"}]),
            peer_context=ctx,
        )
        block = packet.to_prompt_block()
        parsed = json.loads(block.strip("`").lstrip("json").strip())
        assert parsed["peer_context"]["sector"] == "KRX 은행"
        assert parsed["peer_context"]["peer_count"] == 5
        assert parsed["peer_context"]["target_vs_peer"]["roe"]["rank"] == "top_third"


# ----------------------------------------------------------------------
# Fundamentals packet — degenerate cases
# ----------------------------------------------------------------------


class TestFundamentalsPacketEdgeCases:
    def test_empty_dataframes_still_produces_valid_packet(self):
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            stock_info_df=pd.DataFrame(),
            financial_ratio_df=pd.DataFrame(),
        )
        # All numeric fields are None
        assert packet.valuation["per"] is None
        assert packet.profitability["roe_pct"] is None
        # data_quality_notes warns about both missing sources
        notes_joined = " ".join(packet.data_quality_notes)
        assert "EPS/BPS" in notes_joined  # valuation cannot be computed
        assert "재무비율" in notes_joined
        # Signals still has at least one entry (the fallback message)
        assert len(packet.signals) >= 1

    def test_korean_column_names_are_matched(self):
        # If KIS responds with Korean labels instead of romanized keys,
        # _get_field still finds the value via substring match.
        ratio = pd.DataFrame([{"부채비율": "55", "ROE": "12", "유동비율": "180"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
        )
        assert packet.balance_sheet["debt_ratio_pct"] == 55.0
        assert packet.profitability["roe_pct"] == 12.0
        # stability label was removed in Phase 4-C-B
        assert "stability" not in packet.balance_sheet

    def test_string_with_commas_parses_as_float(self):
        ratio = pd.DataFrame([{"roe_val": "1,234.56"}])
        packet = build_fundamentals_packet_from_dataframes(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            financial_ratio_df=ratio,
        )
        assert packet.profitability["roe_pct"] == 1234.56


# ----------------------------------------------------------------------
# Macro highlight parser unit tests
# ----------------------------------------------------------------------


class TestMacroHighlightParser:
    def test_returns_empty_for_none(self):
        assert _parse_macro_highlights(None) == []
        assert _parse_macro_highlights("") == []

    def test_filters_to_known_indicators(self):
        text = (
            "[통화] 기준금리: 3.50 % (M)\n"
            "[환율] 원/달러 환율: 1380 원 (D)\n"
            "[기타] 도시가스 사용량: 100 (D)\n"
        )
        out = _parse_macro_highlights(text)
        assert any("기준금리" in line for line in out)
        assert any("원/달러" in line for line in out)
        assert all("도시가스" not in line for line in out)

    def test_caps_at_max_items(self):
        text = "\n".join(
            f"기준금리 line {i}" for i in range(20)
        )
        out = _parse_macro_highlights(text, max_items=3)
        assert len(out) == 3
