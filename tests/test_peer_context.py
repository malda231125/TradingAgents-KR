"""Tests for the peer financial context builder.

Stays on the pure-data path (`build_peer_context_from_metrics` and
`compute_metrics_from_accounts`) so no network access or DART key is
required. The live `build_peer_context` is exercised separately by
the live verification script.
"""

import pytest

from tradingagents.dataflows.feature_packets.peer_context import (
    _default_bsns_year,
    _peer_median,
    _rank_in_peers,
    build_peer_context_from_metrics,
    compute_metrics_from_accounts,
)


# ----------------------------------------------------------------------
# compute_metrics_from_accounts — turn raw line items into ratios
# ----------------------------------------------------------------------


class TestComputeMetricsFromAccounts:
    def test_samsung_2025_annual(self):
        """Real Samsung 2025 annual numbers from the DART probe."""
        accounts = {
            "매출액": {"thstrm": 333605938000000.0, "frmtrm": 300870903000000.0},
            "영업이익": {"thstrm": 43601051000000.0, "frmtrm": 32725961000000.0},
            "당기순이익": {"thstrm": 45206805000000.0, "frmtrm": 34451351000000.0},
            "자산총계": {"thstrm": 566942110000000.0, "frmtrm": 514531948000000.0},
            "부채총계": {"thstrm": 130621773000000.0, "frmtrm": 112339878000000.0},
            "자본총계": {"thstrm": 436320337000000.0, "frmtrm": 402192070000000.0},
            "유동자산": {"thstrm": 247684612000000.0, "frmtrm": 227062266000000.0},
            "유동부채": {"thstrm": 106411348000000.0, "frmtrm": 93326299000000.0},
        }
        m = compute_metrics_from_accounts(accounts)

        # ROE = 45.2T / 436.3T * 100
        assert m["roe_pct"] == pytest.approx(10.36, abs=0.05)
        # Debt ratio = 130.6T / 436.3T * 100
        assert m["debt_ratio_pct"] == pytest.approx(29.94, abs=0.05)
        # Current ratio = 247.7T / 106.4T * 100
        assert m["current_ratio_pct"] == pytest.approx(232.77, abs=0.5)
        # Operating margin = 43.6T / 333.6T * 100
        assert m["operating_margin_pct"] == pytest.approx(13.07, abs=0.05)
        # Net margin = 45.2T / 333.6T * 100
        assert m["net_margin_pct"] == pytest.approx(13.55, abs=0.05)
        # Revenue YoY = (333.6 - 300.9) / 300.9 * 100
        assert m["revenue_yoy_pct"] == pytest.approx(10.88, abs=0.05)
        # Net income YoY = (45.2 - 34.5) / 34.5 * 100
        assert m["net_income_yoy_pct"] == pytest.approx(31.22, abs=0.05)

    def test_handles_loss_accounts_with_alternate_name(self):
        """DART sometimes returns 당기순이익(손실) instead of 당기순이익."""
        accounts = {
            "당기순이익(손실)": {"thstrm": 1000000000.0, "frmtrm": 800000000.0},
            "자본총계": {"thstrm": 10000000000.0, "frmtrm": 9500000000.0},
        }
        m = compute_metrics_from_accounts(accounts)
        # Substring lookup finds 당기순이익(손실) when we ask for 당기순이익
        assert m["roe_pct"] == pytest.approx(10.0, abs=0.01)

    def test_missing_data_returns_none(self):
        m = compute_metrics_from_accounts({})
        assert m["roe_pct"] is None
        assert m["debt_ratio_pct"] is None
        assert m["current_ratio_pct"] is None
        assert m["operating_margin_pct"] is None
        assert m["net_margin_pct"] is None
        assert m["revenue_yoy_pct"] is None

    def test_zero_denominator_returns_none(self):
        accounts = {
            "당기순이익": {"thstrm": 1000.0, "frmtrm": 0.0},
            "자본총계": {"thstrm": 0.0, "frmtrm": 0.0},
            "매출액": {"thstrm": 1000.0, "frmtrm": 0.0},
        }
        m = compute_metrics_from_accounts(accounts)
        assert m["roe_pct"] is None
        assert m["net_margin_pct"] is not None  # 1000/1000 → fine
        assert m["revenue_yoy_pct"] is None  # frmtrm == 0


# ----------------------------------------------------------------------
# _rank_in_peers — top/middle/bottom third bucketing
# ----------------------------------------------------------------------


class TestRankInPeers:
    def test_top_third(self):
        # Target beats 4 of 5 peers (80% > 2/3) → top_third
        assert _rank_in_peers(15.0, [5, 8, 10, 11, 14]) == "top_third"

    def test_middle_third(self):
        # Target beats 2 of 5 peers (40%) → middle_third
        assert _rank_in_peers(10.0, [5, 8, 11, 14, 18]) == "middle_third"

    def test_bottom_third(self):
        # Target beats 0 of 5 peers → bottom_third
        assert _rank_in_peers(3.0, [5, 8, 10, 11, 14]) == "bottom_third"

    def test_target_beats_all_peers(self):
        assert _rank_in_peers(100.0, [5, 8, 10]) == "top_third"

    def test_target_below_all_peers(self):
        assert _rank_in_peers(1.0, [5, 8, 10]) == "bottom_third"

    def test_none_target_returns_none(self):
        assert _rank_in_peers(None, [5, 8, 10]) is None

    def test_empty_peers_returns_none(self):
        assert _rank_in_peers(10.0, []) is None


# ----------------------------------------------------------------------
# _peer_median — median of available values
# ----------------------------------------------------------------------


class TestPeerMedian:
    def test_basic_median(self):
        peers = [{"roe_pct": 5}, {"roe_pct": 10}, {"roe_pct": 15}]
        assert _peer_median(peers, "roe_pct") == 10.0

    def test_filters_none_values(self):
        peers = [{"roe_pct": 5}, {"roe_pct": None}, {"roe_pct": 15}]
        assert _peer_median(peers, "roe_pct") == 10.0

    def test_all_none_returns_none(self):
        peers = [{"roe_pct": None}, {"roe_pct": None}]
        assert _peer_median(peers, "roe_pct") is None

    def test_missing_key_returns_none(self):
        peers = [{"other": 5}]
        assert _peer_median(peers, "roe_pct") is None


# ----------------------------------------------------------------------
# build_peer_context_from_metrics — full pure-data builder
# ----------------------------------------------------------------------


class TestBuildPeerContextFromMetrics:
    def _make_kb_target(self):
        return {
            "roe_pct": 12.0,
            "debt_ratio_pct": 850.0,
            "current_ratio_pct": 110.0,
            "operating_margin_pct": 38.0,
            "net_margin_pct": 18.0,
            "revenue_yoy_pct": 8.5,
            "operating_profit_yoy_pct": 22.0,
            "net_income_yoy_pct": 18.0,
        }

    def _make_bank_peers(self):
        # 5 bank peers with varying metrics
        return {
            "00382199": {"roe_pct": 8.0, "debt_ratio_pct": 920.0, "operating_margin_pct": 32.0, "net_income_yoy_pct": 10.0, "current_ratio_pct": 100.0, "operating_profit_yoy_pct": 8.0, "net_margin_pct": 12.0, "revenue_yoy_pct": 5.0},
            "00524836": {"roe_pct": 9.5, "debt_ratio_pct": 880.0, "operating_margin_pct": 35.0, "net_income_yoy_pct": 12.0, "current_ratio_pct": 105.0, "operating_profit_yoy_pct": 11.0, "net_margin_pct": 14.0, "revenue_yoy_pct": 6.0},
            "00928210": {"roe_pct": 7.5, "debt_ratio_pct": 900.0, "operating_margin_pct": 30.0, "net_income_yoy_pct": 5.0, "current_ratio_pct": 102.0, "operating_profit_yoy_pct": 6.0, "net_margin_pct": 11.0, "revenue_yoy_pct": 4.0},
            "00691150": {"roe_pct": 8.5, "debt_ratio_pct": 870.0, "operating_margin_pct": 33.0, "net_income_yoy_pct": 14.0, "current_ratio_pct": 108.0, "operating_profit_yoy_pct": 13.0, "net_margin_pct": 13.0, "revenue_yoy_pct": 7.0},
            "00148651": {"roe_pct": 6.5, "debt_ratio_pct": 950.0, "operating_margin_pct": 28.0, "net_income_yoy_pct": 8.0, "current_ratio_pct": 95.0, "operating_profit_yoy_pct": 7.0, "net_margin_pct": 10.0, "revenue_yoy_pct": 3.0},
        }

    def test_kb_financial_top_third_roe(self):
        target = self._make_kb_target()
        peers = self._make_bank_peers()

        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11011",
        )

        assert ctx is not None
        assert ctx["sector"] == "KRX 은행"
        assert ctx["peer_count"] == 5
        # Median ROE of [6.5, 7.5, 8.0, 8.5, 9.5] is 8.0
        assert ctx["peer_median"]["roe_pct"] == 8.0
        # KB at 12% beats all 5 → top_third
        assert ctx["target_vs_peer"]["roe"]["rank"] == "top_third"
        # Diff = 12 - 8 = +4.0
        assert ctx["target_vs_peer"]["roe"]["diff_vs_peer_median_pp"] == 4.0
        # KB debt 850 vs peer median (sorted: 870, 880, 900, 920, 950) median 900
        # KB at 850 beats 0 peers → bottom_third (which means LOW debt, GOOD)
        assert ctx["target_vs_peer"]["debt_ratio"]["rank"] == "bottom_third"
        assert ctx["target_vs_peer"]["debt_ratio"]["diff_vs_peer_median_pp"] == -50.0

    def test_returns_none_if_too_few_peers(self):
        target = self._make_kb_target()
        # Only 1 peer — below default min_peer_count=2
        peers = {"00382199": {"roe_pct": 8.0}}

        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11011",
        )
        assert ctx is None

    def test_excludes_target_from_peer_set_if_included(self):
        """If caller accidentally includes target in peer dict, it's dropped."""
        target = self._make_kb_target()
        peers = self._make_bank_peers()
        # Add target itself to the peer dict
        peers["00691150_target"] = target

        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11011",
        )
        # Still 5 peers (target excluded)
        assert ctx["peer_count"] == 5

    def test_interpretation_string_built(self):
        target = self._make_kb_target()
        peers = self._make_bank_peers()
        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11011",
        )
        interp = ctx["interpretation"]
        assert "수익성" in interp
        # KB ROE is top third → "상위"
        assert "상위" in interp
        # KB debt is bottom third (LOWER) → flipped to "낮은 편"
        assert "낮은 편" in interp

    def test_fiscal_period_passed_through(self):
        target = self._make_kb_target()
        peers = self._make_bank_peers()
        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11014",
        )
        assert ctx["fiscal_period"]["bsns_year"] == "2025"
        assert ctx["fiscal_period"]["reprt_code"] == "11014"

    def test_handles_none_target_metrics_gracefully(self):
        target = {"roe_pct": None, "debt_ratio_pct": None}
        peers = self._make_bank_peers()
        ctx = build_peer_context_from_metrics(
            sector_name="KRX 은행",
            target_corp_code="00691150_target",
            target_metrics=target,
            peer_metrics_by_corp=peers,
            bsns_year="2025",
            reprt_code="11011",
        )
        # Still produces a context block, but rank is None
        assert ctx is not None
        assert ctx["target_vs_peer"]["roe"]["rank"] is None
        assert ctx["target_vs_peer"]["roe"]["value_pct"] is None


# ----------------------------------------------------------------------
# _default_bsns_year heuristic
# ----------------------------------------------------------------------


class TestDefaultBsnsYear:
    def test_april_or_later_uses_year_minus_1(self):
        assert _default_bsns_year("2026-04-10") == "2025"
        assert _default_bsns_year("2026-12-31") == "2025"

    def test_jan_to_march_uses_year_minus_2(self):
        assert _default_bsns_year("2026-01-15") == "2024"
        assert _default_bsns_year("2026-03-30") == "2024"

    def test_invalid_format_falls_back_to_2024(self):
        assert _default_bsns_year("nonsense") == "2024"
        assert _default_bsns_year("") == "2024"
        assert _default_bsns_year(None) == "2024"
