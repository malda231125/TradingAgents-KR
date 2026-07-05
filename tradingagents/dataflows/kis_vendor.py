from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO
from typing import Annotated, Any

import pandas as pd
import requests

from .kis_auth import get_kis_auth_manager
from .korea_ticker import get_stock_code
from .stockstats_utils import _clean_dataframe, wrap


class KISVendorError(RuntimeError):
    pass


DEFAULT_INVEST_OPINION_LOOKBACK_DAYS = 180
DEFAULT_SIGNAL_LOOKBACK_DAYS = 90
KIS_MARKET_DIVISION_CODE = "J"
KIS_PRODUCT_TYPE_CODE = "300"
KIS_PROGRAM_OPINION_SCREEN_CODE = "16633"
KIS_HOLIDAY_TR_ID = "CTCA0903R"


def _request(path: str, tr_id: str, params: dict | None = None) -> dict:
    """Execute a KIS REST request with token reuse and single refresh-on-401 logic."""
    auth = get_kis_auth_manager()
    url = f"{auth.base_url}{path}"
    headers = auth.build_headers(tr_id=tr_id)
    resp = requests.get(url, headers=headers, params=params or {}, timeout=20)

    if resp.status_code == 401:
        headers = auth.build_headers(tr_id=tr_id, force_refresh=True)
        resp = requests.get(url, headers=headers, params=params or {}, timeout=20)

    if resp.status_code != 200:
        raise KISVendorError(f"KIS request failed: HTTP {resp.status_code} {resp.text}")

    data = resp.json()
    rt_cd = data.get("rt_cd")
    if rt_cd not in ("0", 0, None):
        raise KISVendorError(
            f"KIS business error: {data.get('msg_cd')} {data.get('msg1')}"
        )
    return data


def _to_dataframe(payload: Any) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        return pd.DataFrame([payload])
    return pd.DataFrame()


def _empty_frame_message(title: str) -> str:
    return f"## {title}\n\nNo data found."


def _summarize_frame(df: pd.DataFrame, max_columns: int = 6) -> pd.DataFrame:
    if df.empty:
        return df
    preview_cols = list(df.columns[:max_columns])
    return df[preview_cols].head(5).copy()


def _format_frame(title: str, df: pd.DataFrame) -> str:
    if df.empty:
        return _empty_frame_message(title)
    summary = _summarize_frame(df)
    return (
        f"## {title}\n\n"
        f"Rows: {len(df)} | Columns: {len(df.columns)}\n\n"
        f"### Preview\n{summary.to_csv(index=False)}\n"
        f"### Full Data\n{df.to_csv(index=False)}"
    )


def _format_sections(sections: list[tuple[str, pd.DataFrame]]) -> str:
    rendered = []
    for title, frame in sections:
        rendered.append(_format_frame(title, frame))
    return "\n\n".join(rendered)


def _normalize_date_window(curr_date: str, look_back_days: int) -> tuple[datetime, datetime, str, str]:
    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=look_back_days)
    return end_dt, start_dt, start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")


def _find_value(df: pd.DataFrame, candidate_keys: list[str]) -> str | None:
    if df.empty:
        return None

    normalized = {str(c).lower(): c for c in df.columns}
    for key in candidate_keys:
        if key.lower() in normalized:
            col = normalized[key.lower()]
            val = df.iloc[0][col]
            if pd.notna(val):
                return str(val)

    for _, row in df.iterrows():
        joined = " | ".join([str(v) for v in row.values if pd.notna(v)]).lower()
        for key in candidate_keys:
            if key.lower() in joined:
                non_null = [str(v) for v in row.values if pd.notna(v)]
                if non_null:
                    return " | ".join(non_null)
    return None


def _safe_get_report_title(prefix: str, ticker: str, detail: str | None = None) -> str:
    return f"KIS {prefix} for {ticker}" + (f" ({detail})" if detail else "")


def _normalize_kis_symbol(symbol: str) -> str:
    normalized = get_stock_code(symbol)
    if normalized:
        return normalized
    stripped = str(symbol).strip()
    if len(stripped) == 6 and stripped.isdigit():
        return stripped
    raise KISVendorError(f"Unable to resolve Korean stock code for '{symbol}'")


def get_kis_ohlcv_dataframe(
    symbol: Annotated[str, "Korean stock code like 005930"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> pd.DataFrame:
    """Fetch KIS daily OHLCV data and return it as a typed pandas DataFrame.

    Returns columns: Date (str yyyy-mm-dd), Open, High, Low, Close, Volume.
    Returns an empty DataFrame if KIS reports no rows for the symbol/window.

    Uses `inquire-daily-itemchartprice` (TR_ID `FHKST03010100`) which accepts
    an explicit start/end date range and returns up to ~100 trading days in
    the `output2` array. The previously-used `inquire-daily-price`
    (FHKST01010400) endpoint capped responses at ~30 trading days, which was
    not enough to compute the 60-day moving average that the regime
    classifier needs — ma60 was always None and the regime always fell
    through to `insufficient_history` for live data.

    Adjusted prices are requested (`FID_ORG_ADJ_PRC=1`) so split / dividend
    adjustments are already applied.
    """
    symbol = _normalize_kis_symbol(symbol)

    raw_start = start_date.replace("-", "")
    raw_end = end_date.replace("-", "")

    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        "FHKST03010100",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": raw_start,
            "FID_INPUT_DATE_2": raw_end,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "1",
        },
    )
    rows = data.get("output2") or []
    if not rows:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    df = pd.DataFrame(rows)
    rename_map = {
        "stck_bsop_date": "Date",
        "stck_oprc": "Open",
        "stck_hgpr": "High",
        "stck_lwpr": "Low",
        "stck_clpr": "Close",
        "acml_vol": "Volume",
    }
    df = df.rename(columns=rename_map)
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # KIS sometimes returns sentinel non-trading rows with Close=0; drop them.
    if "Close" in df.columns:
        df = df[df["Close"].notna() & (df["Close"] > 0)].reset_index(drop=True)

    return df


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def get_kis_holidays(
    start_date: Annotated[str | date, "Calendar start date (inclusive)"],
) -> dict[date, bool]:
    """Return a {date: is_market_open} map from the KIS domestic-holiday API.

    Uses `chk-holiday` (TR_ID `CTCA0903R`), which returns one page (~a month
    of consecutive calendar days) starting at ``BASS_DT``. Each row exposes
    ``opnd_yn`` (개장일 여부); we treat ``opnd_yn == 'Y'`` as a trading day so
    weekends and exchange holidays are excluded. A single call covers far more
    than the typical review horizon, so we do not paginate here — callers fall
    back to a weekday heuristic for any day the page does not cover.
    """
    start = _coerce_date(start_date)
    data = _request(
        "/uapi/domestic-stock/v1/quotations/chk-holiday",
        KIS_HOLIDAY_TR_ID,
        {"BASS_DT": start.strftime("%Y%m%d"), "CTX_AREA_NK": "", "CTX_AREA_FK": ""},
    )
    out: dict[date, bool] = {}
    for row in data.get("output") or []:
        bass = row.get("bass_dt")
        if not bass:
            continue
        try:
            day = datetime.strptime(str(bass), "%Y%m%d").date()
        except ValueError:
            continue
        out[day] = str(row.get("opnd_yn", "")).strip().upper() == "Y"
    return out


def is_trading_day(
    day: str | date,
    *,
    holidays: dict[date, bool] | None = None,
) -> bool:
    """Whether the Korean equity market is open on ``day``.

    Prefers the KIS holiday calendar; if the day is not covered, falls back to
    a weekday heuristic (Mon-Fri open).
    """
    target = _coerce_date(day)
    if holidays is None:
        holidays = get_kis_holidays(target)
    if target in holidays:
        return holidays[target]
    return target.weekday() < 5


def add_trading_days(
    start_date: str | date,
    n: int,
    *,
    holidays: dict[date, bool] | None = None,
) -> date:
    """Return the date ``n`` market-open days after ``start_date``.

    ``n`` counts only trading days (weekends/holidays skipped). For ``n <= 0``
    the start date is returned unchanged. Uses the KIS holiday calendar with a
    weekday fallback for uncovered days; bounded to one year to avoid loops.
    """
    cursor = _coerce_date(start_date)
    remaining = int(n)
    if remaining <= 0:
        return cursor
    if holidays is None:
        holidays = get_kis_holidays(cursor)
    for _ in range(366):
        cursor = cursor + timedelta(days=1)
        if cursor in holidays:
            market_open = holidays[cursor]
        else:
            market_open = cursor.weekday() < 5
        if market_open:
            remaining -= 1
            if remaining == 0:
                return cursor
    return cursor


def get_kis_stock_data(
    symbol: Annotated[str, "Korean stock code like 005930"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    symbol_normalized = _normalize_kis_symbol(symbol)
    df = get_kis_ohlcv_dataframe(symbol_normalized, start_date, end_date)
    if df.empty:
        return f"No KIS stock data found for symbol '{symbol_normalized}'"
    return _format_frame(
        _safe_get_report_title("stock data", symbol_normalized, f"{start_date} to {end_date}"),
        df,
    )


def get_kis_stock_info_dataframe(symbol: str) -> pd.DataFrame:
    """Public DataFrame accessor for KIS stock info (PER/PBR/EPS/BPS-bearing rows)."""
    return _get_kis_stock_info(_normalize_kis_symbol(symbol))


def get_kis_financial_ratio_dataframe(
    symbol: str, period_type: str = "1"
) -> pd.DataFrame:
    """Public DataFrame accessor for KIS financial ratios."""
    return _get_kis_financial_ratio(_normalize_kis_symbol(symbol), period_type=period_type)


def get_kis_balance_sheet_dataframe(
    symbol: str, period_type: str = "1"
) -> pd.DataFrame:
    """Public DataFrame accessor for KIS balance-sheet rows."""
    return _get_kis_balance_sheet(_normalize_kis_symbol(symbol), period_type=period_type)


def get_kis_income_statement_dataframe(
    symbol: str, period_type: str = "1"
) -> pd.DataFrame:
    """Public DataFrame accessor for KIS income-statement rows."""
    return _get_kis_income_statement(_normalize_kis_symbol(symbol), period_type=period_type)


def get_kis_sector_index_dataframe(
    sector_code: Annotated[str, "4-digit KIS sector index code, e.g. '4003' for KRX 반도체"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> pd.DataFrame:
    """Fetch a KIS sector / industry index daily history as a typed DataFrame.

    Uses `inquire-daily-indexchartprice` (TR_ID `FHKUP03500100`) which expects
    `FID_COND_MRKT_DIV_CODE="U"` (업종) and accepts an explicit start/end
    date range. Returns columns: Date (yyyy-mm-dd), Open, High, Low, Close,
    Volume.

    The 4-digit `sector_code` value comes from KIS's `idxcode.mst` master file
    (see `tradingagents/dataflows/sector_index.py` for the verified mapping
    of common sector names to codes).

    Returns an empty DataFrame if KIS reports no rows.
    """
    raw_start = start_date.replace("-", "")
    raw_end = end_date.replace("-", "")

    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
        "FHKUP03500100",
        {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": sector_code,
            "FID_INPUT_DATE_1": raw_start,
            "FID_INPUT_DATE_2": raw_end,
            "FID_PERIOD_DIV_CODE": "D",
        },
    )

    rows = data.get("output2") or []
    if not rows:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    df = pd.DataFrame(rows)
    rename_map = {
        "stck_bsop_date": "Date",
        "bstp_nmix_oprc": "Open",
        "bstp_nmix_hgpr": "High",
        "bstp_nmix_lwpr": "Low",
        "bstp_nmix_prpr": "Close",
        "acml_vol": "Volume",
    }
    df = df.rename(columns=rename_map)
    keep = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["Date"])
        # KIS sector chart returns rows that may include zero / sentinel values
        # for non-trading days; drop those by requiring a positive close.
        df = df.sort_values("Date").reset_index(drop=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Close" in df.columns:
        df = df[df["Close"].notna() & (df["Close"] > 0)].reset_index(drop=True)

    return df


def get_kis_investor_flow_dataframe(
    symbol: Annotated[str, "Korean stock code like 005930"],
) -> pd.DataFrame:
    """Fetch recent KRX investor flow for a Korean stock from KIS.

    Uses KIS `inquire-investor` (TR_ID `FHKST01010900`) and returns the
    investor categories that matter most for short-term Korea equity reads:
    foreign and institutional net buy/sell shares. The KIS response is usually
    most-recent first; callers should not rely on ordering beyond the Date
    column.
    """
    symbol = _normalize_kis_symbol(symbol)
    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        "FHKST01010900",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_INPUT_ISCD": symbol,
        },
    )
    rows = data.get("output") or []
    if not rows:
        return pd.DataFrame(
            columns=[
                "Date",
                "Close",
                "ForeignNetBuyShares",
                "InstitutionNetBuyShares",
            ]
        )

    df = pd.DataFrame(rows)
    rename_map = {
        "stck_bsop_date": "Date",
        "stck_clpr": "Close",
        "frgn_ntby_qty": "ForeignNetBuyShares",
        "orgn_ntby_qty": "InstitutionNetBuyShares",
    }
    df = df.rename(columns=rename_map)
    keep = [
        c
        for c in [
            "Date",
            "Close",
            "ForeignNetBuyShares",
            "InstitutionNetBuyShares",
        ]
        if c in df.columns
    ]
    df = df[keep].copy()

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    for col in ["Close", "ForeignNetBuyShares", "InstitutionNetBuyShares"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def get_kis_indicators(
    symbol: Annotated[str, "Korean stock code"],
    indicator: Annotated[str, "technical indicator"],
    curr_date: Annotated[str, "current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "look back window"],
) -> str:
    symbol = _normalize_kis_symbol(symbol)
    start_dt = datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(
        days=max(look_back_days * 3, 90)
    )
    stock_text = get_kis_stock_data(symbol, start_dt.strftime("%Y-%m-%d"), curr_date)
    if stock_text.startswith("No KIS stock data"):
        return stock_text

    if "### Full Data\n" not in stock_text:
        return f"No indicator data found for {symbol}"

    payload = stock_text.split("### Full Data\n", 1)[1]
    df = pd.read_csv(StringIO(payload))
    if df.empty:
        return f"No indicator data found for {symbol}"

    df["Date"] = pd.to_datetime(df["Date"])
    df = _clean_dataframe(df)
    stock_df = wrap(df)
    stock_df[indicator]

    start_limit = datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
    stock_df = stock_df[stock_df["Date"] >= pd.Timestamp(start_limit)]

    report_df = pd.DataFrame(
        {
            "Date": stock_df["Date"].dt.strftime("%Y-%m-%d"),
            indicator: stock_df[indicator],
        }
    )
    return _format_frame(_safe_get_report_title(f"indicator {indicator}", symbol), report_df)


def _get_kis_stock_info(symbol: str) -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/search-stock-info",
        "CTPF1002R",
        {
            "PRDT_TYPE_CD": KIS_PRODUCT_TYPE_CODE,
            "PDNO": symbol,
        },
    )
    return _to_dataframe(data.get("output"))


def _get_kis_balance_sheet(symbol: str, period_type: str = "1") -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/finance/balance-sheet",
        "FHKST66430100",
        {
            "FID_DIV_CLS_CODE": period_type,
            "fid_cond_mrkt_div_code": KIS_MARKET_DIVISION_CODE,
            "fid_input_iscd": symbol,
        },
    )
    return _to_dataframe(data.get("output"))


def _get_kis_income_statement(symbol: str, period_type: str = "1") -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/finance/income-statement",
        "FHKST66430200",
        {
            "FID_DIV_CLS_CODE": period_type,
            "fid_cond_mrkt_div_code": KIS_MARKET_DIVISION_CODE,
            "fid_input_iscd": symbol,
        },
    )
    return _to_dataframe(data.get("output"))


def _get_kis_financial_ratio(symbol: str, period_type: str = "1") -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/finance/financial-ratio",
        "FHKST66430300",
        {
            "FID_DIV_CLS_CODE": period_type,
            "fid_cond_mrkt_div_code": KIS_MARKET_DIVISION_CODE,
            "fid_input_iscd": symbol,
        },
    )
    return _to_dataframe(data.get("output"))


def _get_kis_estimate_perform(symbol: str) -> list[pd.DataFrame]:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/estimate-perform",
        "HHKST668300C0",
        {"SHT_CD": symbol},
    )
    return [
        _to_dataframe(data.get("output1")),
        _to_dataframe(data.get("output2")),
        _to_dataframe(data.get("output3")),
        _to_dataframe(data.get("output4")),
    ]


def _get_kis_invest_opinion(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/invest-opinion",
        "FHKST663300C0",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_COND_SCR_DIV_CODE": KIS_PROGRAM_OPINION_SCREEN_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
        },
    )
    return _to_dataframe(data.get("output"))


def _get_kis_investor_trade_by_stock_daily(symbol: str, start_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily",
        "FHPTJ04160001",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_ORG_ADJ_PRC": "",
            "FID_ETC_CLS_CODE": "",
        },
    )
    return _to_dataframe(data.get("output1")), _to_dataframe(data.get("output2"))


def _get_kis_daily_short_sale(symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/daily-short-sale",
        "FHPST04830000",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
        },
    )
    return _to_dataframe(data.get("output1")), _to_dataframe(data.get("output2"))


def _get_kis_daily_loan_trans(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/daily-loan-trans",
        "HHPST074500C0",
        {
            "MRKT_DIV_CLS_CODE": "3",
            "MKSC_SHRN_ISCD": symbol,
            "START_DATE": start_date,
            "END_DATE": end_date,
            "CTS": "",
        },
    )
    return _to_dataframe(data.get("output1"))


def _get_kis_program_trade_by_stock_daily(symbol: str, start_date: str) -> pd.DataFrame:
    data = _request(
        "/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily",
        "FHPPG04650201",
        {
            "FID_COND_MRKT_DIV_CODE": KIS_MARKET_DIVISION_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
        },
    )
    return _to_dataframe(data.get("output"))


def get_kis_fundamentals(
    ticker: Annotated[str, "Korean stock code like 005930"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    info_df = _get_kis_stock_info(ticker)
    ratio_df = _get_kis_financial_ratio(ticker, period_type="1")
    estimate_frames = _get_kis_estimate_perform(ticker)

    sections = [
        (_safe_get_report_title("stock info", ticker), info_df),
        (_safe_get_report_title("financial ratios", ticker), ratio_df),
    ]

    for idx, frame in enumerate(estimate_frames, start=1):
        if not frame.empty:
            sections.append((_safe_get_report_title(f"estimate performance output{idx}", ticker), frame))

    return _format_sections(sections)


def get_kis_balance_sheet(
    ticker: Annotated[str, "Korean stock code like 005930"],
    freq: Annotated[str, "quarterly or annual"] = "quarterly",
    curr_date: Annotated[str | None, "Current date yyyy-mm-dd"] = None,
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    period_type = "1" if freq == "quarterly" else "0"
    df = _get_kis_balance_sheet(ticker, period_type=period_type)
    return _format_frame(_safe_get_report_title("balance sheet", ticker, freq), df)


def get_kis_income_statement(
    ticker: Annotated[str, "Korean stock code like 005930"],
    freq: Annotated[str, "quarterly or annual"] = "quarterly",
    curr_date: Annotated[str | None, "Current date yyyy-mm-dd"] = None,
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    period_type = "1" if freq == "quarterly" else "0"
    df = _get_kis_income_statement(ticker, period_type=period_type)
    return _format_frame(_safe_get_report_title("income statement", ticker, freq), df)


def get_kis_cashflow(
    ticker: Annotated[str, "Korean stock code like 005930"],
    freq: Annotated[str, "quarterly or annual"] = "quarterly",
    curr_date: Annotated[str | None, "Current date yyyy-mm-dd"] = None,
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    period_type = "1" if freq == "quarterly" else "0"
    balance_df = _get_kis_balance_sheet(ticker, period_type=period_type)
    income_df = _get_kis_income_statement(ticker, period_type=period_type)
    ratio_df = _get_kis_financial_ratio(ticker, period_type=period_type)

    proxy_rows = [
        {
            "ticker": ticker,
            "freq": freq,
            "proxy_type": "inferred_from_balance_sheet_income_statement_financial_ratios",
            "source_note": "KIS direct cashflow endpoint not confirmed from public docs/samples; this is an inferred proxy, not an official cashflow statement.",
            "profit_signal": _find_value(
                income_df,
                ["당기순이익", "순이익", "net_income", "net income", "영업이익", "operating_profit"],
            ),
            "revenue_signal": _find_value(income_df, ["매출액", "revenue", "sales"]),
            "asset_signal": _find_value(balance_df, ["자산총계", "total_assets", "total assets"]),
            "liability_signal": _find_value(balance_df, ["부채총계", "total_liabilities", "total liabilities"]),
            "equity_signal": _find_value(balance_df, ["자본총계", "total_equity", "total equity"]),
            "current_ratio_signal": _find_value(ratio_df, ["유동비율", "current_ratio", "current ratio"]),
            "debt_ratio_signal": _find_value(ratio_df, ["부채비율", "debt_ratio", "debt ratio"]),
            "stability_signal": _find_value(ratio_df, ["안정성", "stability"]),
            "profitability_signal": _find_value(ratio_df, ["수익성", "profitability"]),
        }
    ]
    proxy_df = pd.DataFrame(proxy_rows)

    sections = [
        (_safe_get_report_title("inferred cashflow proxy", ticker, freq), proxy_df),
        (_safe_get_report_title("income statement used for cashflow proxy", ticker, freq), income_df),
        (_safe_get_report_title("balance sheet used for cashflow proxy", ticker, freq), balance_df),
        (_safe_get_report_title("financial ratios used for cashflow proxy", ticker, freq), ratio_df),
    ]
    return _format_sections(sections)


def get_kis_invest_opinion_report(
    ticker: Annotated[str, "Korean stock code like 005930"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "look back window in days"] = DEFAULT_INVEST_OPINION_LOOKBACK_DAYS,
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    _, _, start_compact, end_compact = _normalize_date_window(curr_date, look_back_days)
    df = _get_kis_invest_opinion(ticker, start_compact, end_compact)
    return _format_frame(_safe_get_report_title("analyst opinions", ticker), df)


def get_kis_market_signals(
    ticker: Annotated[str, "Korean stock code like 005930"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "look back window in days"] = DEFAULT_SIGNAL_LOOKBACK_DAYS,
) -> str:
    ticker = _normalize_kis_symbol(ticker)
    _, _, start_compact, end_compact = _normalize_date_window(curr_date, look_back_days)

    investor_summary, investor_daily = _get_kis_investor_trade_by_stock_daily(ticker, start_compact)
    short_summary, short_daily = _get_kis_daily_short_sale(ticker, start_compact, end_compact)
    loan_daily = _get_kis_daily_loan_trans(ticker, start_compact, end_compact)
    program_daily = _get_kis_program_trade_by_stock_daily(ticker, start_compact)

    sections = [
        (_safe_get_report_title("investor flow summary", ticker), investor_summary),
        (_safe_get_report_title("investor flow daily data", ticker), investor_daily),
        (_safe_get_report_title("short-sale summary", ticker), short_summary),
        (_safe_get_report_title("short-sale daily data", ticker), short_daily),
        (_safe_get_report_title("securities lending / loan trend", ticker), loan_daily),
        (_safe_get_report_title("program trade daily data", ticker), program_daily),
    ]
    return _format_sections(sections)
