from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.kis_auth import KISAuthManager
from tradingagents.dataflows.kis_vendor import (
    _to_dataframe,
    _find_value,
    _summarize_frame,
    _normalize_date_window,
    get_kis_investor_flow_dataframe,
    get_kis_ohlcv_dataframe,
    get_kis_sector_index_dataframe,
)


def test_kis_auth_manager_defaults_to_production_url():
    manager = KISAuthManager(app_key="dummy", app_secret="dummy")
    assert manager.base_url == "https://openapi.koreainvestment.com:9443"


def test_to_dataframe_handles_dict_payload():
    df = _to_dataframe({"ticker": "005930", "value": "100"})
    assert not df.empty
    assert list(df.columns) == ["ticker", "value"]
    assert df.iloc[0]["ticker"] == "005930"


def test_to_dataframe_handles_list_payload():
    df = _to_dataframe([
        {"ticker": "005930", "value": "100"},
        {"ticker": "000660", "value": "200"},
    ])
    assert len(df) == 2


def test_find_value_prefers_direct_column_match():
    df = _to_dataframe({"net_income": "12345", "revenue": "99999"})
    assert _find_value(df, ["net_income", "당기순이익"]) == "12345"


def test_find_value_can_match_embedded_row_text():
    df = _to_dataframe([
        {"account_name": "당기순이익", "amount": "12345"},
        {"account_name": "매출액", "amount": "99999"},
    ])
    value = _find_value(df, ["당기순이익"])
    assert value is not None
    assert "12345" in value


def test_summarize_frame_limits_rows_and_columns():
    df = _to_dataframe([
        {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7},
        {"a": 11, "b": 12, "c": 13, "d": 14, "e": 15, "f": 16, "g": 17},
        {"a": 21, "b": 22, "c": 23, "d": 24, "e": 25, "f": 26, "g": 27},
        {"a": 31, "b": 32, "c": 33, "d": 34, "e": 35, "f": 36, "g": 37},
        {"a": 41, "b": 42, "c": 43, "d": 44, "e": 45, "f": 46, "g": 47},
        {"a": 51, "b": 52, "c": 53, "d": 54, "e": 55, "f": 56, "g": 57},
    ])
    summary = _summarize_frame(df)
    assert len(summary) == 5
    assert list(summary.columns) == ["a", "b", "c", "d", "e", "f"]


def test_normalize_date_window_returns_compact_dates():
    end_dt, start_dt, start_compact, end_compact = _normalize_date_window("2026-03-27", 10)
    assert end_compact == "20260327"
    assert start_compact == "20260317"
    assert end_dt > start_dt


# ----------------------------------------------------------------------
# get_kis_sector_index_dataframe — mock the underlying _request to avoid
# network access while still exercising the rename / type / filter logic.
# ----------------------------------------------------------------------


def _make_mock_kis_sector_response(rows):
    """Build a KIS-shaped response dict around the given output2 rows."""
    return {"rt_cd": "0", "output1": {}, "output2": rows}


# ----------------------------------------------------------------------
# get_kis_ohlcv_dataframe — verify the inquire-daily-itemchartprice endpoint
# is called with the right params and parses output2 rows correctly.
# ----------------------------------------------------------------------


@patch("tradingagents.dataflows.kis_vendor._request")
def test_ohlcv_dataframe_calls_itemchartprice_endpoint(mock_request):
    """Verify we use the long-history endpoint, not the legacy 30-row one."""
    mock_request.return_value = {
        "rt_cd": "0",
        "output1": {},
        "output2": [
            {
                "stck_bsop_date": "20260410",
                "stck_oprc": "208500",
                "stck_hgpr": "211000",
                "stck_lwpr": "205500",
                "stck_clpr": "206000",
                "acml_vol": "18229163",
            },
            {
                "stck_bsop_date": "20260409",
                "stck_oprc": "204000",
                "stck_hgpr": "205500",
                "stck_lwpr": "201000",
                "stck_clpr": "204000",
                "acml_vol": "15000000",
            },
        ],
    }

    df = get_kis_ohlcv_dataframe("005930", "2025-12-11", "2026-04-10")

    # Endpoint + TR_ID
    call_args = mock_request.call_args
    assert call_args[0][0] == "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    assert call_args[0][1] == "FHKST03010100"

    # Params include explicit date range and adjusted-price flag
    params = call_args[0][2]
    assert params["FID_COND_MRKT_DIV_CODE"] == "J"
    assert params["FID_INPUT_ISCD"] == "005930"
    assert params["FID_INPUT_DATE_1"] == "20251211"
    assert params["FID_INPUT_DATE_2"] == "20260410"
    assert params["FID_PERIOD_DIV_CODE"] == "D"
    assert params["FID_ORG_ADJ_PRC"] == "1"

    # Parsed correctly and sorted ascending
    assert len(df) == 2
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert df.iloc[0]["Date"] == "2026-04-09"
    assert df.iloc[1]["Date"] == "2026-04-10"
    assert df.iloc[1]["Close"] == 206000.0


@patch("tradingagents.dataflows.kis_vendor._request")
def test_ohlcv_dataframe_empty_output2(mock_request):
    mock_request.return_value = {"rt_cd": "0", "output1": {}, "output2": []}
    df = get_kis_ohlcv_dataframe("005930", "2025-12-11", "2026-04-10")
    assert df.empty
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]


@patch("tradingagents.dataflows.kis_vendor._request")
def test_ohlcv_dataframe_filters_zero_close_sentinels(mock_request):
    """KIS sometimes returns rows with Close=0 for non-trading days."""
    mock_request.return_value = {
        "rt_cd": "0",
        "output1": {},
        "output2": [
            {
                "stck_bsop_date": "20260410",
                "stck_oprc": "208500",
                "stck_hgpr": "211000",
                "stck_lwpr": "205500",
                "stck_clpr": "206000",
                "acml_vol": "18229163",
            },
            {
                "stck_bsop_date": "20260411",  # weekend / holiday
                "stck_oprc": "0",
                "stck_hgpr": "0",
                "stck_lwpr": "0",
                "stck_clpr": "0",
                "acml_vol": "0",
            },
        ],
    }
    df = get_kis_ohlcv_dataframe("005930", "2025-12-11", "2026-04-11")
    assert len(df) == 1
    assert df.iloc[0]["Date"] == "2026-04-10"


@patch("tradingagents.dataflows.kis_vendor._request")
def test_sector_index_dataframe_parses_output2_rows(mock_request):
    mock_request.return_value = _make_mock_kis_sector_response(
        [
            {
                "stck_bsop_date": "20260408",
                "bstp_nmix_oprc": "1500.50",
                "bstp_nmix_hgpr": "1520.00",
                "bstp_nmix_lwpr": "1495.00",
                "bstp_nmix_prpr": "1510.25",
                "acml_vol": "12345678",
            },
            {
                "stck_bsop_date": "20260409",
                "bstp_nmix_oprc": "1510.00",
                "bstp_nmix_hgpr": "1535.50",
                "bstp_nmix_lwpr": "1505.00",
                "bstp_nmix_prpr": "1530.75",
                "acml_vol": "13456789",
            },
        ]
    )

    df = get_kis_sector_index_dataframe("4003", "2026-04-08", "2026-04-09")

    assert len(df) == 2
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert df.iloc[0]["Date"] == "2026-04-08"
    assert df.iloc[0]["Close"] == 1510.25
    assert df.iloc[1]["Close"] == 1530.75
    # Type checks
    assert df["Close"].dtype.kind == "f"
    assert df["Volume"].dtype.kind in ("f", "i")

    # Verify the request was made with the right parameters
    call_args = mock_request.call_args
    assert call_args[0][0] == "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"
    assert call_args[0][1] == "FHKUP03500100"
    params = call_args[0][2]
    assert params["FID_COND_MRKT_DIV_CODE"] == "U"
    assert params["FID_INPUT_ISCD"] == "4003"
    assert params["FID_INPUT_DATE_1"] == "20260408"
    assert params["FID_INPUT_DATE_2"] == "20260409"
    assert params["FID_PERIOD_DIV_CODE"] == "D"


@patch("tradingagents.dataflows.kis_vendor._request")
def test_sector_index_dataframe_empty_response(mock_request):
    mock_request.return_value = {"rt_cd": "0", "output1": {}, "output2": []}
    df = get_kis_sector_index_dataframe("4003", "2026-04-08", "2026-04-09")
    assert df.empty
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]


@patch("tradingagents.dataflows.kis_vendor._request")
def test_sector_index_dataframe_filters_zero_close_rows(mock_request):
    """KIS sometimes returns sentinel/non-trading rows with Close=0; drop them."""
    mock_request.return_value = _make_mock_kis_sector_response(
        [
            {
                "stck_bsop_date": "20260407",
                "bstp_nmix_oprc": "0",
                "bstp_nmix_hgpr": "0",
                "bstp_nmix_lwpr": "0",
                "bstp_nmix_prpr": "0",
                "acml_vol": "0",
            },
            {
                "stck_bsop_date": "20260408",
                "bstp_nmix_oprc": "1500",
                "bstp_nmix_hgpr": "1520",
                "bstp_nmix_lwpr": "1495",
                "bstp_nmix_prpr": "1510",
                "acml_vol": "12345",
            },
        ]
    )
    df = get_kis_sector_index_dataframe("4003", "2026-04-07", "2026-04-08")
    assert len(df) == 1
    assert df.iloc[0]["Date"] == "2026-04-08"
    assert df.iloc[0]["Close"] == 1510.0


@patch("tradingagents.dataflows.kis_vendor._request")
def test_sector_index_dataframe_sorts_ascending(mock_request):
    """Verify rows are sorted by date even if KIS returns them descending."""
    mock_request.return_value = _make_mock_kis_sector_response(
        [
            {
                "stck_bsop_date": "20260409",
                "bstp_nmix_oprc": "1510",
                "bstp_nmix_hgpr": "1535",
                "bstp_nmix_lwpr": "1505",
                "bstp_nmix_prpr": "1530",
                "acml_vol": "13000",
            },
            {
                "stck_bsop_date": "20260408",
                "bstp_nmix_oprc": "1500",
                "bstp_nmix_hgpr": "1520",
                "bstp_nmix_lwpr": "1495",
                "bstp_nmix_prpr": "1510",
                "acml_vol": "12000",
            },
        ]
    )
    df = get_kis_sector_index_dataframe("4003", "2026-04-08", "2026-04-09")
    assert df.iloc[0]["Date"] == "2026-04-08"
    assert df.iloc[1]["Date"] == "2026-04-09"


@patch("tradingagents.dataflows.kis_vendor._request")
def test_investor_flow_dataframe_parses_recent_rows(mock_request):
    mock_request.return_value = {
        "rt_cd": "0",
        "output": [
            {
                "stck_bsop_date": "20260410",
                "stck_clpr": "206000",
                "frgn_ntby_qty": "-12345",
                "orgn_ntby_qty": "23456",
            },
            {
                "stck_bsop_date": "20260409",
                "stck_clpr": "204000",
                "frgn_ntby_qty": "1000",
                "orgn_ntby_qty": "-2000",
            },
        ],
    }

    df = get_kis_investor_flow_dataframe("005930")

    call_args = mock_request.call_args
    assert call_args[0][0] == "/uapi/domestic-stock/v1/quotations/inquire-investor"
    assert call_args[0][1] == "FHKST01010900"
    params = call_args[0][2]
    assert params["FID_COND_MRKT_DIV_CODE"] == "J"
    assert params["FID_INPUT_ISCD"] == "005930"

    assert list(df.columns) == [
        "Date",
        "Close",
        "ForeignNetBuyShares",
        "InstitutionNetBuyShares",
    ]
    assert df.iloc[0]["Date"] == "2026-04-09"
    assert df.iloc[1]["Date"] == "2026-04-10"
    assert df.iloc[1]["ForeignNetBuyShares"] == -12345
    assert df.iloc[1]["InstitutionNetBuyShares"] == 23456


@patch("tradingagents.dataflows.kis_vendor._request")
def test_investor_flow_dataframe_empty_response(mock_request):
    mock_request.return_value = {"rt_cd": "0", "output": []}
    df = get_kis_investor_flow_dataframe("005930")
    assert df.empty
    assert list(df.columns) == [
        "Date",
        "Close",
        "ForeignNetBuyShares",
        "InstitutionNetBuyShares",
    ]
