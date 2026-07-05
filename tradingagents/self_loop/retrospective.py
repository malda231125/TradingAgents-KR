from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from tradingagents.dataflows.kis_vendor import get_kis_ohlcv_dataframe

from .records import parse_date


PriceFetcher = Callable[[str, str, str], Any]
AIReviewer = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
# evidence_builder(decision_record, *, check_date, price_result) -> evidence packet dict
EvidenceBuilder = Callable[..., dict[str, Any]]


def run_retrospective(
    decision_record: dict[str, Any],
    *,
    as_of_date: str | date | None = None,
    price_fetcher: PriceFetcher | None = None,
    ai_reviewer: AIReviewer | None = None,
    evidence_builder: EvidenceBuilder | None = None,
    price_direction_threshold: float = 0.0,
) -> dict[str, Any]:
    ticker = str(decision_record["ticker"])
    analysis_date = parse_date(decision_record["analysis_date"])
    review_due = parse_date(decision_record.get("review_due") or analysis_date)
    check_date = parse_date(as_of_date) if as_of_date else review_due
    if check_date < analysis_date:
        check_date = analysis_date

    fetcher = price_fetcher or get_kis_ohlcv_dataframe
    price_result = _evaluate_price_move(ticker, analysis_date, check_date, fetcher)
    checklist_results = _evaluate_checklist(decision_record, price_result)
    overall = _classify_overall(
        decision_record.get("decision"),
        price_result,
        checklist_results,
        threshold=price_direction_threshold,
    )

    retrospective = {
        "schema_version": "self-loop-retrospective-v1",
        "ticker": ticker,
        "analysis_date": analysis_date.isoformat(),
        "check_date": check_date.isoformat(),
        "review_due": review_due.isoformat(),
        "decision": decision_record.get("decision"),
        "overall": overall,
        "price_result": price_result,
        "checklist_results": checklist_results,
        "evidence": None,
        "data_quality": None,
        "missing_evidence": None,
        "lesson": _build_lesson(decision_record, overall, price_result, checklist_results),
        "ai_review": None,
    }

    # The evidence packet exists to give the AI reviewer non-price context
    # (flow/DART/news/macro). It is only collected when a reviewer will consume
    # it, so the deterministic-only path stays free of extra vendor calls.
    if ai_reviewer is not None:
        builder = evidence_builder or _default_evidence_builder
        try:
            packet = builder(decision_record, check_date=check_date.isoformat(), price_result=price_result)
        except Exception as exc:  # noqa: BLE001 - evidence is best-effort
            packet = {"error": f"{type(exc).__name__}: {exc}"}
        retrospective["evidence"] = packet.get("evidence")
        retrospective["data_quality"] = packet.get("data_quality")
        retrospective["missing_evidence"] = packet.get("missing_evidence")
        _apply_ai_review(retrospective, decision_record, ai_reviewer)
    return retrospective


def _default_evidence_builder(
    decision_record: dict[str, Any],
    *,
    check_date: str,
    price_result: dict[str, Any],
) -> dict[str, Any]:
    from .evidence import build_evidence_packet

    return build_evidence_packet(
        decision_record,
        check_date=check_date,
        price_result=price_result,
    )


def render_retrospective_markdown(retrospective: dict[str, Any]) -> str:
    price = retrospective.get("price_result") or {}
    lines = [
        f"# Self-loop retrospective — {retrospective.get('ticker')} / {retrospective.get('analysis_date')}",
        "",
        f"- Check date: {retrospective.get('check_date')}",
        f"- Prior decision: {retrospective.get('decision')}",
        f"- Overall: **{retrospective.get('overall')}**",
        "",
        "## Price Result",
        "",
        f"- Status: {price.get('status')}",
        f"- Start close: {price.get('start_close')}",
        f"- End close: {price.get('end_close')}",
        f"- Return pct: {price.get('return_pct')}",
        f"- Message: {price.get('message')}",
        "",
        "## Checklist",
        "",
    ]
    for item in retrospective.get("checklist_results") or []:
        lines.append(f"- `{item.get('status')}` {item.get('item')} — {item.get('reason')}")

    data_quality = retrospective.get("data_quality") or {}
    if data_quality:
        lines.extend(["", "## Evidence Quality", ""])
        for category, status in data_quality.items():
            lines.append(f"- {category}: {status}")
        missing = retrospective.get("missing_evidence") or []
        if missing:
            lines.append(f"- missing: {', '.join(missing)}")

    lesson = retrospective.get("lesson")
    if lesson:
        lines.extend(["", "## Lesson", "", lesson])
    ai_review = retrospective.get("ai_review") or {}
    if ai_review:
        lines.extend(
            [
                "",
                "## AI Review",
                "",
                f"- Status: {ai_review.get('status')}",
                f"- Overall: {ai_review.get('overall')}",
                f"- Confidence: {ai_review.get('confidence')}",
                f"- Reasoning: {ai_review.get('reasoning')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _apply_ai_review(
    retrospective: dict[str, Any],
    decision_record: dict[str, Any],
    ai_reviewer: AIReviewer,
) -> None:
    try:
        review = ai_reviewer(decision_record, retrospective)
    except Exception as exc:
        retrospective["ai_review"] = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
        return

    ai_overall = str(review.get("overall") or "uncertain").lower()
    if ai_overall in {"hit", "miss", "partial", "uncertain"}:
        retrospective["overall"] = ai_overall
    ai_checklist = review.get("checklist_results")
    if isinstance(ai_checklist, list) and ai_checklist:
        retrospective["checklist_results"] = ai_checklist
    ai_lesson = review.get("lesson")
    if ai_lesson:
        retrospective["lesson"] = str(ai_lesson)
    retrospective["ai_review"] = {
        "status": "completed",
        "overall": retrospective["overall"],
        "reasoning": str(review.get("reasoning") or ""),
        "lesson": retrospective.get("lesson"),
        "confidence": str(review.get("confidence") or "medium"),
    }


def save_retrospective_markdown(
    retrospective: dict[str, Any],
    *,
    base_dir: str | Path = ".",
) -> Path:
    path = (
        Path(base_dir)
        / "retrospectives"
        / str(retrospective["check_date"])
        / f"{retrospective['ticker']}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_retrospective_markdown(retrospective), encoding="utf-8")
    return path


def _evaluate_price_move(
    ticker: str,
    start_date: date,
    end_date: date,
    price_fetcher: PriceFetcher,
) -> dict[str, Any]:
    fetch_start = (start_date - timedelta(days=7)).isoformat()
    fetch_end = (end_date + timedelta(days=7)).isoformat()
    try:
        raw = price_fetcher(ticker, fetch_start, fetch_end)
        df = _coerce_price_frame(raw)
    except Exception as exc:
        return {
            "status": "uncertain",
            "message": f"price fetch failed: {type(exc).__name__}: {exc}",
            "start_close": None,
            "end_close": None,
            "return_pct": None,
        }

    if df.empty or "date" not in df or "close" not in df:
        return {
            "status": "uncertain",
            "message": "price data unavailable",
            "start_close": None,
            "end_close": None,
            "return_pct": None,
        }

    start_row = _nearest_on_or_after(df, start_date)
    end_row = _nearest_on_or_before(df, end_date)
    if start_row is None or end_row is None:
        return {
            "status": "uncertain",
            "message": "no comparable trading bars in review window",
            "start_close": None,
            "end_close": None,
            "return_pct": None,
        }

    start_close = float(start_row["close"])
    end_close = float(end_row["close"])
    if start_close <= 0:
        return {
            "status": "uncertain",
            "message": "invalid start close",
            "start_close": start_close,
            "end_close": end_close,
            "return_pct": None,
        }

    return_pct = round((end_close - start_close) / start_close * 100, 4)
    return {
        "status": "available",
        "message": "price move evaluated",
        "start_date": start_row["date"].isoformat(),
        "end_date": end_row["date"].isoformat(),
        "start_close": start_close,
        "end_close": end_close,
        "return_pct": return_pct,
    }


def _coerce_price_frame(raw: Any) -> pd.DataFrame:
    if isinstance(raw, pd.DataFrame):
        df = raw.copy()
    elif isinstance(raw, list):
        df = pd.DataFrame(raw)
    else:
        return pd.DataFrame()

    columns = {str(col).lower(): col for col in df.columns}
    date_col = columns.get("date")
    close_col = columns.get("close")
    if date_col is None or close_col is None:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce").dt.date,
            "close": pd.to_numeric(df[close_col], errors="coerce"),
        }
    ).dropna()
    return out.sort_values("date").reset_index(drop=True)


def _nearest_on_or_after(df: pd.DataFrame, target: date) -> dict[str, Any] | None:
    rows = df[df["date"] >= target]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def _nearest_on_or_before(df: pd.DataFrame, target: date) -> dict[str, Any] | None:
    rows = df[df["date"] <= target]
    if rows.empty:
        return None
    return rows.iloc[-1].to_dict()


def _evaluate_checklist(
    decision_record: dict[str, Any],
    price_result: dict[str, Any],
) -> list[dict[str, str]]:
    """Build preliminary checklist rows without keyword analysis.

    Qualitative items are not pattern-matched here; they are left ``uncertain``
    and handed to the AI reviewer (which judges meaning) as evidence. When no
    AI reviewer is used, the price-direction outcome is derived numerically at
    the overall level in ``_classify_overall``.
    """
    items = decision_record.get("prediction_checklist") or []
    if not items:
        items = ["review horizon 내 가격 방향이 decision과 일치하는가?"]

    if price_result.get("status") == "available":
        reason = "deferred to AI review; price direction scored at the overall level"
    else:
        reason = price_result.get("message", "")
    return [{"item": str(item), "status": "uncertain", "reason": reason} for item in items]


def _classify_price_direction(
    decision: str | None,
    return_pct: Any,
    *,
    threshold: float = 0.0,
) -> str:
    """Numeric (non-keyword) price-direction outcome.

    ``threshold`` is the flat band in percent; |move| within the band is treated
    as no directional move. Defaults to 0.0 (pure sign) instead of the previous
    hardcoded ±1.0% so the cutoff is an explicit, caller-tunable input.
    """
    if return_pct is None:
        return "uncertain"
    value = float(return_pct)
    band = abs(float(threshold))
    normalized = str(decision or "").lower()
    if normalized in {"buy_review", "hold"}:
        if value > band:
            return "hit"
        if value < -band:
            return "miss"
        return "partial"
    if normalized == "sell_review":
        if value < -band:
            return "hit"
        if value > band:
            return "miss"
        return "partial"
    # watch / unknown: thesis was "no actionable directional move"
    if abs(value) <= band:
        return "hit"
    return "partial"


def _classify_overall(
    decision: str | None,
    price_result: dict[str, Any],
    checklist_results: list[dict[str, str]],
    *,
    threshold: float = 0.0,
) -> str:
    statuses = [item["status"] for item in checklist_results]
    if statuses and all(status == "uncertain" for status in statuses):
        if price_result.get("status") == "available":
            return _classify_price_direction(decision, price_result.get("return_pct"), threshold=threshold)
        return "uncertain"
    if "miss" in statuses:
        return "miss"
    if "partial" in statuses:
        return "partial"
    if statuses and all(status == "hit" for status in statuses):
        return "hit"
    return "uncertain"


def _build_lesson(
    decision_record: dict[str, Any],
    overall: str,
    price_result: dict[str, Any],
    checklist_results: list[dict[str, str]],
) -> str | None:
    if overall == "hit":
        return None
    misses = [item for item in checklist_results if item.get("status") in {"miss", "partial", "uncertain"}]
    reason = "; ".join(f"{item['item']} => {item['status']}" for item in misses[:3])
    return (
        f"{decision_record.get('ticker')} {decision_record.get('analysis_date')} decision "
        f"{decision_record.get('decision')} was {overall}. "
        f"Price return={price_result.get('return_pct')}. "
        f"Next analysis should explicitly address: {reason or 'insufficient evidence'}."
    )
