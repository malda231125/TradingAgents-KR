from unittest.mock import patch

import pytest

from tradingagents.dataflows.global_peers import get_global_peer_universe
from tradingagents.dataflows.feature_packets.global_peer import (
    build_global_peer_context,
    build_global_peer_context_from_sec_payloads,
)
from tradingagents.dataflows.sec_edgar_api import SECEdgarError, get_sec_user_agent


def _submissions(name: str, forms=None, dates=None):
    return {
        "name": name,
        "filings": {
            "recent": {
                "form": forms or ["10-Q", "8-K", "4"],
                "filingDate": dates or ["2026-04-02", "2026-03-10", "2026-03-01"],
                "accessionNumber": ["0001", "0002", "0003"],
                "primaryDocDescription": ["Quarterly report", "Current report", "Ownership"],
            }
        },
    }


def _facts(revenues: list[float], net_income: list[float]):
    years = ["2024-12-31", "2025-12-31"]
    return {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"fp": "FY", "end": years[0], "val": revenues[0]},
                            {"fp": "FY", "end": years[1], "val": revenues[1]},
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"fp": "FY", "end": years[0], "val": net_income[0]},
                            {"fp": "FY", "end": years[1], "val": net_income[1]},
                        ]
                    }
                },
            }
        }
    }


def test_global_peer_universe_maps_semiconductor_stock():
    universe = get_global_peer_universe("005930")

    assert universe is not None
    assert universe["sector"] == "KRX 반도체"
    assert "NVDA" in universe["peers"]
    assert "10-Q" in universe["sec_forms"]


def test_global_peer_context_from_sec_payloads_filters_forms_and_builds_snapshot():
    ctx = build_global_peer_context_from_sec_payloads(
        sector="KRX 반도체",
        target_stock_code="005930",
        peer_universe=["NVDA", "MU"],
        submissions_by_ticker={
            "NVDA": _submissions("NVIDIA Corp"),
            "MU": _submissions("Micron Technology", forms=["20-F"], dates=["2026-04-01"]),
        },
        facts_by_ticker={
            "NVDA": _facts([100.0, 130.0], [20.0, 40.0]),
            "MU": _facts([80.0, 70.0], [10.0, 8.0]),
        },
        as_of="2026-05-11",
        allowed_forms=["10-Q", "8-K", "20-F"],
    )

    assert ctx is not None
    assert ctx["sector"] == "KRX 반도체"
    assert len(ctx["recent_filings"]) == 3
    assert {item["form"] for item in ctx["recent_filings"]} == {"10-Q", "8-K", "20-F"}
    nvda = next(item for item in ctx["peer_fundamental_snapshot"] if item["ticker"] == "NVDA")
    assert nvda["revenue_yoy_pct"] == pytest.approx(30.0)
    assert nvda["net_income_yoy_pct"] == pytest.approx(100.0)
    assert "글로벌 peer" in ctx["interpretation"]


def test_global_peer_context_returns_none_without_payloads():
    ctx = build_global_peer_context_from_sec_payloads(
        sector="KRX 반도체",
        target_stock_code="005930",
        peer_universe=["NVDA"],
        submissions_by_ticker={},
        facts_by_ticker={},
        as_of="2026-05-11",
    )

    assert ctx is None


def test_sec_user_agent_uses_single_env_var():
    with patch.dict("os.environ", {"SEC_USER_AGENT": "TradingAgentsKorea/0.1 test@example.com"}):
        assert get_sec_user_agent() == "TradingAgentsKorea/0.1 test@example.com"

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SECEdgarError):
            get_sec_user_agent()


@patch.dict("os.environ", {"SEC_USER_AGENT": "TradingAgentsKorea/0.1 test@example.com"})
@patch("tradingagents.dataflows.global_peers.get_global_peer_universe")
@patch("tradingagents.dataflows.sec_edgar_api.resolve_cik_for_ticker")
@patch("tradingagents.dataflows.sec_edgar_api.get_company_submissions")
@patch("tradingagents.dataflows.sec_edgar_api.get_company_facts")
def test_live_builder_with_mocked_sec_calls(
    mock_facts,
    mock_submissions,
    mock_resolve,
    mock_universe,
):
    mock_universe.return_value = {
        "sector": "KRX 반도체",
        "peers": ["NVDA"],
        "sec_forms": ["10-Q"],
    }
    mock_resolve.return_value = "0001045810"
    mock_submissions.return_value = _submissions("NVIDIA Corp", forms=["10-Q"], dates=["2026-04-02"])
    mock_facts.return_value = _facts([100.0, 120.0], [20.0, 25.0])

    ctx = build_global_peer_context("005930", "2026-05-11")

    assert ctx is not None
    assert ctx["peer_universe"] == ["NVDA"]
    assert ctx["recent_filings"][0]["ticker"] == "NVDA"
