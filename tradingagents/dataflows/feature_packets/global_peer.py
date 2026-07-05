"""Global peer context builder using SEC EDGAR metadata.

This is a compact overseas read-through card. It is separate from the DART
`peer_context`, which remains the authoritative domestic financial peer
comparison for Korean companies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_ALLOWED_FORMS_DEFAULT = {"10-K", "10-Q", "8-K", "20-F", "6-K"}
_MAX_FILINGS = 8


def _parse_date(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d")
    except ValueError:
        return None


def _recent_filings_for_ticker(
    *,
    ticker: str,
    submissions: dict,
    as_of: str,
    allowed_forms: set[str],
    lookback_days: int = 180,
) -> list[dict]:
    recent = ((submissions or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accession_numbers = recent.get("accessionNumber") or []
    descriptions = recent.get("primaryDocDescription") or []
    company = submissions.get("name") or ticker

    as_of_dt = datetime.strptime(as_of, "%Y-%m-%d")
    start_dt = as_of_dt - timedelta(days=lookback_days)
    out = []

    for idx, form in enumerate(forms):
        form = str(form or "").strip()
        if form not in allowed_forms:
            continue
        filed_dt = _parse_date(filing_dates[idx] if idx < len(filing_dates) else None)
        if filed_dt is None or filed_dt > as_of_dt or filed_dt < start_dt:
            continue
        description = descriptions[idx] if idx < len(descriptions) else ""
        accession = accession_numbers[idx] if idx < len(accession_numbers) else ""
        out.append(
            {
                "ticker": ticker,
                "company": company,
                "form": form,
                "filed_at": filed_dt.strftime("%Y-%m-%d"),
                "headline": str(description or f"recent {form} filing"),
                "accession_number": accession,
                "relevance": "global_peer",
                "expected_readthrough": "unknown",
                "confidence": "low" if form in {"8-K", "6-K"} else "medium",
            }
        )

    return out


def _unit_items(facts: dict, concept_names: list[str]) -> list[dict]:
    us_gaap = ((facts or {}).get("facts") or {}).get("us-gaap") or {}
    for concept in concept_names:
        concept_block = us_gaap.get(concept) or {}
        units = concept_block.get("units") or {}
        for unit_name in ("USD", "shares", "USD/shares"):
            items = units.get(unit_name)
            if items:
                return items
    return []


def _annual_yoy_pct(items: list[dict]) -> Optional[float]:
    annual = []
    seen_end = set()
    for item in items or []:
        if item.get("fp") != "FY":
            continue
        end = item.get("end")
        val = item.get("val")
        if end in seen_end or val is None:
            continue
        parsed = _parse_date(end)
        if parsed is None:
            continue
        seen_end.add(end)
        annual.append((parsed, float(val)))

    annual = sorted(annual, key=lambda x: x[0])
    if len(annual) < 2:
        return None
    latest = annual[-1][1]
    previous = annual[-2][1]
    if previous == 0:
        return None
    return round((latest - previous) / abs(previous) * 100, 2)


def _peer_snapshot(ticker: str, facts: dict) -> dict:
    revenue_items = _unit_items(
        facts,
        [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        ],
    )
    net_income_items = _unit_items(facts, ["NetIncomeLoss"])
    return {
        "ticker": ticker,
        "revenue_yoy_pct": _annual_yoy_pct(revenue_items),
        "net_income_yoy_pct": _annual_yoy_pct(net_income_items),
        "data_quality": "companyfacts",
    }


def _readthrough_from_snapshot(snapshot: dict) -> str:
    revenue = snapshot.get("revenue_yoy_pct")
    net_income = snapshot.get("net_income_yoy_pct")
    positives = sum(1 for v in (revenue, net_income) if v is not None and v > 5)
    negatives = sum(1 for v in (revenue, net_income) if v is not None and v < -5)
    if positives and not negatives:
        return "positive"
    if negatives and not positives:
        return "negative"
    if positives and negatives:
        return "mixed"
    return "unknown"


def _interpretation(snapshots: list[dict], filings: list[dict]) -> str:
    known = [_readthrough_from_snapshot(s) for s in snapshots]
    positive = known.count("positive")
    negative = known.count("negative")
    mixed = known.count("mixed")

    parts = []
    if positive > negative:
        parts.append("글로벌 peer의 최근 연간 매출/순이익 흐름은 우호적")
    elif negative > positive:
        parts.append("글로벌 peer의 최근 연간 실적 흐름은 부담 요인")
    elif mixed or positive or negative:
        parts.append("글로벌 peer 실적 read-through는 혼재")

    if filings:
        forms = sorted({f["form"] for f in filings})
        parts.append(f"최근 SEC filing 이벤트({', '.join(forms)})는 원문 확인이 필요한 보조 신호")

    if not parts:
        return "글로벌 peer context는 생성됐지만 뚜렷한 read-through는 제한적."
    return " / ".join(parts) + "."


def build_global_peer_context_from_sec_payloads(
    *,
    sector: str,
    target_stock_code: str,
    peer_universe: list[str],
    submissions_by_ticker: dict[str, dict],
    facts_by_ticker: Optional[dict[str, dict]] = None,
    as_of: str,
    allowed_forms: Optional[list[str]] = None,
) -> Optional[dict]:
    allowed = set(allowed_forms or _ALLOWED_FORMS_DEFAULT)
    facts_by_ticker = facts_by_ticker or {}

    filings = []
    snapshots = []
    notes = []

    for ticker in peer_universe:
        submissions = submissions_by_ticker.get(ticker) or {}
        if submissions:
            filings.extend(
                _recent_filings_for_ticker(
                    ticker=ticker,
                    submissions=submissions,
                    as_of=as_of,
                    allowed_forms=allowed,
                )
            )
        else:
            notes.append(f"{ticker}: SEC submissions 없음")

        facts = facts_by_ticker.get(ticker)
        if facts:
            snapshots.append(_peer_snapshot(ticker, facts))

    filings = sorted(filings, key=lambda item: item["filed_at"], reverse=True)[:_MAX_FILINGS]

    readthrough_by_ticker = {
        snapshot["ticker"]: _readthrough_from_snapshot(snapshot)
        for snapshot in snapshots
    }
    for filing in filings:
        readthrough = readthrough_by_ticker.get(filing["ticker"])
        if readthrough and readthrough != "unknown":
            filing["expected_readthrough"] = readthrough
            filing["confidence"] = "medium"

    if not filings and not snapshots:
        return None

    return {
        "sector": sector,
        "target_stock_code": target_stock_code,
        "peer_universe": list(peer_universe),
        "recent_filings": filings,
        "peer_fundamental_snapshot": snapshots,
        "interpretation": _interpretation(snapshots, filings),
        "data_quality_notes": notes,
    }


def build_global_peer_context(stock_code: str, trade_date: str) -> Optional[dict]:
    """Live builder. Returns None when disabled, unmapped, or unavailable."""
    from tradingagents.dataflows.global_peers import get_global_peer_universe
    from tradingagents.dataflows.sec_edgar_api import (
        get_company_facts,
        get_company_submissions,
        resolve_cik_for_ticker,
        sec_edgar_available,
    )

    if not sec_edgar_available():
        return None

    universe = get_global_peer_universe(stock_code)
    if not universe:
        return None

    submissions_by_ticker: dict[str, dict] = {}
    facts_by_ticker: dict[str, dict] = {}
    notes = []

    for ticker in universe["peers"]:
        try:
            cik = resolve_cik_for_ticker(ticker)
            if not cik:
                notes.append(f"{ticker}: CIK resolve 실패")
                continue
            submissions_by_ticker[ticker] = get_company_submissions(cik)
            try:
                facts_by_ticker[ticker] = get_company_facts(cik)
            except Exception as exc:
                notes.append(f"{ticker}: companyfacts 실패 ({exc})")
        except Exception as exc:
            logger.warning("SEC peer %s skipped: %s", ticker, exc)
            notes.append(f"{ticker}: SEC 조회 실패 ({exc})")

    context = build_global_peer_context_from_sec_payloads(
        sector=universe["sector"],
        target_stock_code=stock_code,
        peer_universe=universe["peers"],
        submissions_by_ticker=submissions_by_ticker,
        facts_by_ticker=facts_by_ticker,
        as_of=trade_date,
        allowed_forms=universe.get("sec_forms"),
    )
    if context and notes:
        context["data_quality_notes"].extend(notes)
    return context
