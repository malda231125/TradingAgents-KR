"""ECOS Open API (한국은행 경제통계) integration.

Provides access to Bank of Korea economic statistics:
- Interest rates (기준금리, 시장금리)
- Exchange rates (원/달러, 원/엔 등)
- Monetary aggregates / liquidity
- Key economic indicators

API reference: https://ecos.bok.or.kr/api/
Auth: API key in URL path
Requires: ECOS_API_KEY environment variable (or use "sample" for test data)
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ECOS_BASE_URL = "https://ecos.bok.or.kr/api"

# Key macro stat codes for Korean market analysis
MACRO_STAT_CODES = {
    "base_rate": {
        "stat_code": "722Y001",
        "item_code": "0101000",
        "cycle": "M",
        "label": "기준금리 (한국은행)",
    },
    "usd_krw": {
        "stat_code": "731Y003",
        "item_code": "0000001",
        "cycle": "D",
        "label": "원/달러 환율",
    },
    "kospi": {
        "stat_code": "802Y001",
        "item_code": "0001000",
        "cycle": "D",
        "label": "KOSPI 지수",
    },
    "cpi": {
        "stat_code": "901Y009",
        "item_code": "0",
        "cycle": "M",
        "label": "소비자물가지수",
    },
    "m2": {
        "stat_code": "101Y003",
        "item_code": "BBGA00",
        "cycle": "M",
        "label": "M2 광의통화",
    },
}


def _get_ecos_key() -> str:
    return os.environ.get("ECOS_API_KEY", "")


def _ecos_available() -> bool:
    return bool(_get_ecos_key())


def _ecos_request(
    service: str,
    stat_code: str,
    cycle: str,
    start_date: str,
    end_date: str,
    item_code: str = "",
    start_count: int = 1,
    end_count: int = 20,
) -> dict:
    """Make a request to the ECOS API.

    ECOS uses path-based parameters:
    /api/{service}/{key}/{format}/{lang}/{start}/{end}/{stat_code}/{cycle}/{start_date}/{end_date}/{item_code}
    """
    api_key = _get_ecos_key()
    if not api_key:
        raise RuntimeError(
            "ECOS API key not configured. Set ECOS_API_KEY environment variable."
        )

    # Format dates based on cycle:
    # D (daily) → YYYYMMDD, M (monthly) → YYYYMM, Q (quarterly) → YYYYQ#, A (annual) → YYYY
    raw_start = start_date.replace("-", "")
    raw_end = end_date.replace("-", "")

    if cycle == "M":
        raw_start = raw_start[:6]  # YYYYMM
        raw_end = raw_end[:6]
    elif cycle == "A":
        raw_start = raw_start[:4]  # YYYY
        raw_end = raw_end[:4]
    # D and Q use YYYYMMDD as-is

    # Build URL with path parameters
    parts = [
        ECOS_BASE_URL,
        service,
        api_key,
        "json",
        "kr",
        str(start_count),
        str(end_count),
        stat_code,
        cycle,
        raw_start,
        raw_end,
    ]
    if item_code:
        parts.append(item_code)

    url = "/".join(parts)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check for ECOS error response
        if "RESULT" in data:
            result = data["RESULT"]
            code = result.get("CODE", "")
            if code != "INFO-000":
                msg = result.get("MESSAGE", f"ECOS error: {code}")
                if "데이터가 없습니다" in msg:
                    return {"StatisticSearch": {"row": []}}
                raise RuntimeError(msg)

        return data
    except requests.RequestException as e:
        raise RuntimeError(f"ECOS API request failed: {e}")


def get_ecos_stat(
    stat_code: str,
    item_code: str,
    cycle: str,
    start_date: str,
    end_date: str,
    count: int = 20,
) -> str:
    """Get a specific ECOS statistic.

    Args:
        stat_code: ECOS statistic table code
        item_code: Item code within the table
        cycle: Frequency (D=daily, M=monthly, Q=quarterly, A=annual)
        start_date: Start date (yyyy-mm-dd or yyyymmdd)
        end_date: End date
        count: Max number of data points

    Returns:
        Formatted string of statistical data
    """
    if not _ecos_available():
        raise RuntimeError("ECOS API key not configured")

    data = _ecos_request(
        "StatisticSearch",
        stat_code,
        cycle,
        start_date,
        end_date,
        item_code,
        1,
        count,
    )

    rows = data.get("StatisticSearch", {}).get("row", [])

    if not rows:
        return f"No ECOS data found for stat {stat_code} ({start_date} to {end_date})."

    stat_name = rows[0].get("STAT_NAME", stat_code)
    item_name = rows[0].get("ITEM_NAME1", item_code)

    lines = [f"=== ECOS: {stat_name} — {item_name} ==="]
    lines.append(f"Period: {start_date} to {end_date}\n")

    for row in rows:
        time_val = row.get("TIME", "")
        data_val = row.get("DATA_VALUE", "")
        unit = row.get("UNIT_NAME", "")
        lines.append(f"  {time_val}: {data_val} {unit}")

    return "\n".join(lines)


def get_korea_macro_summary(trade_date: str, lookback_months: int = 3) -> str:
    """Get a summary of key Korean macro indicators.

    Uses KeyStatisticList API for a single efficient call, then supplements
    with StatisticSearch for historical trend data on key indicators.

    Args:
        trade_date: Current trading date (yyyy-mm-dd)
        lookback_months: How many months of history to include

    Returns:
        Formatted macro summary string
    """
    if not _ecos_available():
        raise RuntimeError("ECOS API key not configured")

    sections = ["=== Korea Macro Summary (ECOS) ==="]
    sections.append(f"As of: {trade_date}\n")

    # 1) Try KeyStatisticList first — single call gets all key stats
    try:
        api_key = _get_ecos_key()
        url = f"{ECOS_BASE_URL}/KeyStatisticList/{api_key}/json/kr/1/100/"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        rows = data.get("KeyStatisticList", {}).get("row", [])
        if rows:
            sections.append("[주요 경제지표 - 최신값]")
            for row in rows:
                class_name = row.get("CLASS_NAME", "")
                stat_name = row.get("KEYSTAT_NAME", "")
                value = row.get("DATA_VALUE", "")
                unit = row.get("UNIT_NAME", "")
                cycle = row.get("CYCLE", "")
                sections.append(f"  [{class_name}] {stat_name}: {value} {unit} ({cycle})")

            return "\n".join(sections)

    except Exception as e:
        logger.warning("KeyStatisticList failed, falling back to StatisticSearch: %s", e)

    # 2) Fallback: individual StatisticSearch calls per indicator
    from datetime import datetime, timedelta

    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_dt = dt - timedelta(days=lookback_months * 30)

    sections.append("[주요 경제지표 - 개별 조회]")

    for key, spec in MACRO_STAT_CODES.items():
        try:
            start_fmt = start_dt.strftime("%Y-%m-%d")
            end_fmt = dt.strftime("%Y-%m-%d")

            data = _ecos_request(
                "StatisticSearch",
                spec["stat_code"],
                spec["cycle"],
                start_fmt,
                end_fmt,
                spec["item_code"],
                1,
                10,
            )

            rows = data.get("StatisticSearch", {}).get("row", [])
            if rows:
                latest = rows[-1]
                time_val = latest.get("TIME", "")
                data_val = latest.get("DATA_VALUE", "")
                unit = latest.get("UNIT_NAME", "")
                sections.append(f"  {spec['label']}: {data_val} {unit} ({time_val})")
            else:
                sections.append(f"  {spec['label']}: 데이터 없음")

        except Exception as e:
            logger.warning("ECOS fetch failed for %s: %s", key, e)
            sections.append(f"  {spec['label']}: [Error: {e}]")

    return "\n".join(sections)
