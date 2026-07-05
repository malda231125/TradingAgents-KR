"""Open DART (금융감독원 전자공시) API integration.

Provides access to official Korean corporate disclosure data:
- Company disclosure search
- Financial statements
- Major shareholder changes
- Key business events

API reference: https://opendart.fss.or.kr
Rate limit: 10,000 calls/day, 100 calls/min
Requires: DART_API_KEY environment variable
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DART_BASE_URL = "https://opendart.fss.or.kr/api"


def _get_dart_key() -> str:
    return os.environ.get("DART_API_KEY", "")


def _dart_available() -> bool:
    return bool(_get_dart_key())


def _dart_request(endpoint: str, params: dict) -> dict:
    """Make a request to the Open DART API."""
    api_key = _get_dart_key()
    if not api_key:
        raise RuntimeError(
            "DART API key not configured. Set DART_API_KEY environment variable."
        )

    params["crtfc_key"] = api_key
    url = f"{DART_BASE_URL}/{endpoint}.json"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # DART uses status codes in response body
        status = data.get("status", "")
        if status == "013":
            return {"status": "no_data", "message": "조회된 데이터가 없습니다.", "list": []}
        if status != "000" and status != "":
            msg = data.get("message", f"DART API error: status {status}")
            raise RuntimeError(msg)

        return data
    except requests.RequestException as e:
        raise RuntimeError(f"DART API request failed: {e}")


def get_dart_disclosures(
    corp_code: str,
    start_date: str,
    end_date: str,
    page_count: int = 10,
) -> str:
    """Search recent disclosures for a company.

    Args:
        corp_code: DART corporation code (8 digits) or stock code
        start_date: Start date (yyyymmdd)
        end_date: End date (yyyymmdd)
        page_count: Number of results per page

    Returns:
        Formatted string of disclosure list
    """
    if not _dart_available():
        raise RuntimeError("DART API key not configured")

    params = {
        "corp_code": corp_code,
        "bgn_de": start_date.replace("-", ""),
        "end_de": end_date.replace("-", ""),
        "page_count": str(page_count),
    }

    data = _dart_request("list", params)
    items = data.get("list", [])

    if not items:
        return f"No DART disclosures found for {corp_code} ({start_date} to {end_date})."

    # Use classifier to add impact labels
    from tradingagents.dataflows.dart_classifier import format_classified_disclosures

    header = f"Period: {start_date} to {end_date} | Corp: {corp_code}\n\n"
    classified = format_classified_disclosures(items)

    return header + classified


def get_dart_company_info(corp_code: str) -> str:
    """Get company overview from DART.

    Args:
        corp_code: DART corporation code

    Returns:
        Formatted company info string
    """
    if not _dart_available():
        raise RuntimeError("DART API key not configured")

    data = _dart_request("company", {"corp_code": corp_code})

    if data.get("status") == "no_data":
        return f"No company info found for {corp_code}."

    lines = ["=== DART Company Info ==="]
    fields = [
        ("corp_name", "Company"),
        ("corp_name_eng", "English Name"),
        ("stock_name", "Stock Name"),
        ("stock_code", "Stock Code"),
        ("ceo_nm", "CEO"),
        ("corp_cls", "Corp Class"),
        ("est_dt", "Established"),
        ("acc_mt", "Fiscal Month"),
        ("induty_code", "Industry Code"),
    ]

    for key, label in fields:
        val = data.get(key, "")
        if val:
            lines.append(f"  {label}: {val}")

    return "\n".join(lines)


def get_dart_financial_statements(
    corp_code: str,
    year: str,
    report_code: str = "11013",
) -> str:
    """Get financial statements from DART.

    Args:
        corp_code: DART corporation code
        year: Business year (e.g. "2025")
        report_code: Report type
            11013 = 1Q, 11012 = 2Q(반기), 11014 = 3Q, 11011 = 연간

    Returns:
        Formatted financial statement string
    """
    if not _dart_available():
        raise RuntimeError("DART API key not configured")

    params = {
        "corp_code": corp_code,
        "bsns_year": year,
        "reprt_code": report_code,
    }

    data = _dart_request("fnlttSinglAcntAll", params)
    items = data.get("list", [])

    if not items:
        return f"No financial statements found for {corp_code} ({year})."

    report_names = {
        "11013": "1Q",
        "11012": "Semi-Annual",
        "11014": "3Q",
        "11011": "Annual",
    }

    lines = [f"=== DART Financial Statement ({report_names.get(report_code, report_code)}) ==="]
    lines.append(f"Corp: {corp_code} | Year: {year}\n")

    for item in items[:30]:  # Limit output
        account_nm = item.get("account_nm", "")
        thstrm_amount = item.get("thstrm_amount", "")
        frmtrm_amount = item.get("frmtrm_amount", "")
        sj_nm = item.get("sj_nm", "")  # statement type (BS, IS, CF)

        if account_nm and thstrm_amount:
            lines.append(f"  [{sj_nm}] {account_nm}: {thstrm_amount} (prev: {frmtrm_amount})")

    if len(items) > 30:
        lines.append(f"\n  ... ({len(items) - 30} more items)")

    return "\n".join(lines)


def get_dart_multi_company_financials(
    corp_codes: list[str],
    bsns_year: str,
    reprt_code: str = "11011",
) -> dict[str, dict[str, dict[str, float]]]:
    """Fetch BS/IS line items for up to 100 companies in a single API call.

    Wraps DART's `fnlttMultiAcnt` endpoint, which is the only DART entry
    point that supports multi-company queries. We use it to fetch peer
    financials for the FundamentalsPacket peer_context block in one round
    trip rather than N per-company calls.

    Args:
        corp_codes: list of 8-digit DART corp_codes. DART caps a single
            request at 100 — we silently truncate the list to 100.
        bsns_year: business year as 4-digit string (e.g. "2025").
        reprt_code: report type code:
            "11011" = annual (사업보고서)
            "11014" = Q3 (3분기보고서)
            "11012" = semi-annual (반기보고서)
            "11013" = Q1 (1분기보고서)

    Returns:
        Nested dict keyed first by corp_code, then by Korean account name.
        Each leaf is a dict with "thstrm" (current period) and "frmtrm"
        (prior period) numeric values, in raw KRW (no comma formatting).
        Companies that DART has no data for are absent from the result.
        Duplicate account names within a single company (DART returns
        당기순이익(손실) twice) are deduped — first occurrence wins.

    Returns an empty dict if the API request fails or returns no data.
    """
    if not _dart_available():
        raise RuntimeError("DART API key not configured")

    if not corp_codes:
        return {}

    truncated = list(dict.fromkeys(corp_codes))[:100]

    try:
        data = _dart_request(
            "fnlttMultiAcnt",
            {
                "corp_code": ",".join(truncated),
                "bsns_year": str(bsns_year),
                "reprt_code": str(reprt_code),
            },
        )
    except RuntimeError as exc:
        logger.warning("DART fnlttMultiAcnt failed: %s", exc)
        return {}

    if data.get("status") == "no_data":
        return {}

    items = data.get("list") or []
    if not items:
        return {}

    result: dict[str, dict[str, dict[str, float]]] = {}

    def _parse_amount(raw: str | None) -> float | None:
        if raw is None:
            return None
        cleaned = str(raw).replace(",", "").strip()
        if cleaned in ("", "-"):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    for item in items:
        corp_code = item.get("corp_code")
        if not corp_code:
            continue
        account_nm = (item.get("account_nm") or "").strip()
        if not account_nm:
            continue

        company = result.setdefault(corp_code, {})
        # First occurrence wins — DART returns 당기순이익(손실) twice for some
        # filers (consolidated and standalone variants under the same name).
        if account_nm in company:
            continue

        company[account_nm] = {
            "thstrm": _parse_amount(item.get("thstrm_amount")),
            "frmtrm": _parse_amount(item.get("frmtrm_amount")),
        }

    return result


# Convenience function for TradingAgents interface
def get_dart_events(ticker: str, start_date: str, end_date: str) -> str:
    """Get DART disclosures for a ticker (interface-compatible function).

    Automatically resolves stock codes and company names to DART corp_codes.
    """
    from tradingagents.dataflows.korea_ticker import get_corp_code

    # Try to resolve to corp_code if input looks like a stock code or name
    corp_code = ticker
    if len(ticker) == 6 and ticker.isdigit():
        resolved = get_corp_code(ticker)
        if resolved:
            corp_code = resolved
    elif not (len(ticker) == 8 and ticker.isdigit()):
        # Probably a company name
        resolved = get_corp_code(ticker)
        if resolved:
            corp_code = resolved

    return get_dart_disclosures(corp_code, start_date, end_date)
