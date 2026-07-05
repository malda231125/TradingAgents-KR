from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


DECISIONS_DIR = "decisions"

VALID_DECISIONS = {"buy_review", "sell_review", "hold", "watch"}
VALID_CONFIDENCE = {"low", "medium", "high"}

# extractor(final_state) -> {decision, confidence, thesis, key_risk_triggers, prediction_checklist}
DecisionExtractor = Callable[[dict[str, Any]], dict[str, Any]]
# trading_day_fn(start_date, n) -> date that is n market-open days after start_date
TradingDayFn = Callable[[date, int], date]


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def decision_record_path(base_dir: str | Path, analysis_date: str | date, ticker: str) -> Path:
    return Path(base_dir) / DECISIONS_DIR / parse_date(analysis_date).isoformat() / f"{ticker}.json"


def save_decision_record(record: dict[str, Any], base_dir: str | Path = ".") -> Path:
    ticker = str(record["ticker"])
    analysis_date = parse_date(record["analysis_date"]).isoformat()
    path = decision_record_path(base_dir, analysis_date, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_decision_record(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_latest_decision_record(
    ticker: str,
    *,
    base_dir: str | Path = ".",
    before_date: str | date | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    decisions_root = Path(base_dir) / DECISIONS_DIR
    if not decisions_root.exists():
        return None

    cutoff = parse_date(before_date) if before_date else None
    candidates: list[tuple[date, Path]] = []
    for path in decisions_root.glob(f"*/{ticker}.json"):
        try:
            record_date = parse_date(path.parent.name)
        except ValueError:
            continue
        if cutoff is not None and record_date >= cutoff:
            continue
        candidates.append((record_date, path))

    if not candidates:
        return None

    _, latest_path = sorted(candidates, key=lambda item: item[0])[-1]
    return latest_path, load_decision_record(latest_path)


def build_decision_record(
    *,
    ticker: str,
    analysis_date: str | date,
    signal: str | None,
    final_state: dict[str, Any],
    report_path: str | Path,
    review_horizon_days: int,
    retrospective_path: str | Path | None = None,
    extractor: DecisionExtractor | None = None,
    trading_day_fn: TradingDayFn | None = None,
    use_ai_extraction: bool = True,
) -> dict[str, Any]:
    """Build a decision record.

    ``extractor`` infers decision/confidence/thesis/risks/checklist via AI
    reasoning (no keyword matching). When it is ``None`` or fails, a
    deterministic keyword fallback is used and ``extraction_mode`` is set to
    ``"fallback"`` so callers can tell. ``trading_day_fn`` computes
    ``review_due`` as ``review_horizon_days`` market-open days ahead (KIS
    holiday calendar by default); on failure it falls back to skipping weekends.
    """
    analysis_dt = parse_date(analysis_date)
    fields, extraction_mode = _resolve_decision_fields(
        signal=signal, final_state=final_state, extractor=extractor, use_ai=use_ai_extraction
    )
    review_due, review_due_basis = _resolve_review_due(
        analysis_dt, int(review_horizon_days), trading_day_fn
    )
    data_quality = _derive_data_quality(final_state)

    return {
        "schema_version": "self-loop-decision-v1",
        "ticker": ticker,
        "analysis_date": analysis_dt.isoformat(),
        "review_due": review_due.isoformat(),
        "review_horizon_days": int(review_horizon_days),
        "review_horizon_trading_days": int(review_horizon_days),
        "review_due_basis": review_due_basis,
        "decision": fields["decision"],
        "confidence": fields["confidence"],
        "thesis": fields["thesis"],
        "key_risk_triggers": fields["key_risk_triggers"],
        "prediction_checklist": fields["prediction_checklist"],
        "extraction_mode": extraction_mode,
        "data_sources": _derive_data_sources(data_quality),
        "data_quality": data_quality,
        "report_path": str(report_path),
        "retrospective_path": str(retrospective_path) if retrospective_path else None,
        "raw_signal": signal,
        "resolved": False,
    }


def _derive_data_quality(final_state: dict[str, Any]) -> dict[str, str]:
    """Report which analyst sections were actually produced.

    Honest signal derived from the run's own output instead of a hardcoded
    source list, so a missing analyst surfaces in the record rather than being
    silently claimed as available.
    """
    def _status(key: str) -> str:
        return "available" if str(final_state.get(key) or "").strip() else "missing"

    return {
        "market": _status("market_report"),
        "news": _status("news_report"),
        "fundamentals": _status("fundamentals_report"),
    }


def _derive_data_sources(data_quality: dict[str, str]) -> list[str]:
    sources: set[str] = set()
    if data_quality.get("market") == "available":
        sources.add("KIS")
    if data_quality.get("fundamentals") == "available":
        sources.update({"KIS", "DART"})
    if data_quality.get("news") == "available":
        sources.add("Naver")
    return sorted(sources)


def _resolve_decision_fields(
    *,
    signal: str | None,
    final_state: dict[str, Any],
    extractor: DecisionExtractor | None,
    use_ai: bool = True,
) -> tuple[dict[str, Any], str]:
    if not use_ai and extractor is None:
        return _fallback_decision_fields(signal, final_state), "fallback"
    if extractor is None:
        extractor = _default_decision_extractor
    try:
        normalized = _normalize_extracted_fields(extractor(final_state))
        if normalized is not None:
            return normalized, "ai"
    except Exception:
        pass
    return _fallback_decision_fields(signal, final_state), "fallback"


def _default_decision_extractor(final_state: dict[str, Any]) -> dict[str, Any]:
    from .reviewer import extract_decision_with_ai

    return extract_decision_with_ai(final_state)


def _normalize_extracted_fields(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    decision = str(result.get("decision") or "").strip().lower()
    if decision not in VALID_DECISIONS:
        return None
    confidence = str(result.get("confidence") or "").strip().lower()
    if confidence not in VALID_CONFIDENCE:
        confidence = "medium"
    checklist = _as_str_list(result.get("prediction_checklist"))
    return {
        "decision": decision,
        "confidence": confidence,
        "thesis": " ".join(str(result.get("thesis") or "").split())[:500],
        "key_risk_triggers": _as_str_list(result.get("key_risk_triggers")),
        "prediction_checklist": checklist or _default_prediction_checklist(),
    }


def _as_str_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = " ".join(str(item).split())[:300]
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _fallback_decision_fields(
    signal: str | None,
    final_state: dict[str, Any],
) -> dict[str, Any]:
    final_decision = str(final_state.get("final_trade_decision") or "")
    investment_plan = str(final_state.get("investment_plan") or "")
    trader_plan = str(final_state.get("trader_investment_plan") or "")
    combined_text = "\n".join([investment_plan, trader_plan, final_decision])
    return {
        "decision": _normalize_decision(signal, final_decision),
        "confidence": _extract_confidence(combined_text),
        "thesis": _extract_thesis(investment_plan, trader_plan, final_decision),
        "key_risk_triggers": _extract_key_lines(combined_text, kind="risk"),
        "prediction_checklist": _extract_prediction_checklist(combined_text),
    }


def _resolve_review_due(
    analysis_dt: date,
    horizon: int,
    trading_day_fn: TradingDayFn | None,
) -> tuple[date, str]:
    """Return (review_due, basis).

    ``basis`` records HOW the date was derived so the record is auditable:
    ``"same_day"`` (zero horizon), ``"trading_day"`` (KIS market calendar), or
    ``"weekday_fallback"`` (weekends skipped when the calendar is unavailable).
    """
    if horizon <= 0:
        return analysis_dt, "same_day"
    if trading_day_fn is None:
        trading_day_fn = _default_trading_day_fn
    try:
        due = trading_day_fn(analysis_dt, horizon)
        if isinstance(due, datetime):
            due = due.date()
        if isinstance(due, date):
            return due, "trading_day"
    except Exception:
        pass
    return _add_weekdays(analysis_dt, horizon), "weekday_fallback"


def _default_trading_day_fn(start_date: date, n: int) -> date:
    from tradingagents.dataflows.kis_vendor import add_trading_days

    return add_trading_days(start_date, n)


def _add_weekdays(start: date, n: int) -> date:
    cursor = start
    remaining = int(n)
    while remaining > 0:
        cursor = cursor + timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def _default_prediction_checklist() -> list[str]:
    from tradingagents.i18n import get_default_prediction_checklist

    return get_default_prediction_checklist()


def _normalize_decision(signal: str | None, final_decision: str) -> str:
    text = f"{signal or ''} {final_decision}".lower()
    if any(token in text for token in ("strong buy", "buy", "매수", "add", "bullish")):
        return "buy_review"
    if any(token in text for token in ("sell", "매도", "reduce", "bearish")):
        return "sell_review"
    if any(token in text for token in ("hold", "보유")):
        return "hold"
    return "watch"


def _extract_confidence(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("high confidence", "confidence: high", "확신도 높", "높은 확신")):
        return "high"
    if any(token in lower for token in ("low confidence", "confidence: low", "확신도 낮", "낮은 확신")):
        return "low"
    return "medium"


def _extract_thesis(*parts: str) -> str:
    for part in parts:
        cleaned = " ".join(str(part).strip().split())
        if cleaned:
            return cleaned[:500]
    return ""


def _extract_key_lines(text: str, *, kind: str) -> list[str]:
    keywords = {
        "risk": ("risk", "리스크", "위험", "조건", "trigger", "invalidation", "훼손"),
    }[kind]
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" -\t")
        if not line:
            continue
        lower = line.lower()
        if any(keyword in lower or keyword in line for keyword in keywords):
            lines.append(line[:300])
        if len(lines) >= 8:
            break
    return lines


def _extract_prediction_checklist(text: str) -> list[str]:
    checklist = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" -\t")
        if not line:
            continue
        if re.search(r"(거래일|days?|수익률|return|외국인|기관|공시|뉴스|환율|금리)", line, re.I):
            checklist.append(line[:300])
        if len(checklist) >= 8:
            break

    if checklist:
        return checklist

    return _default_prediction_checklist()
