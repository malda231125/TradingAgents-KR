#!/usr/bin/env python3
"""Daily-check open self-loop Key Risk Triggers without a fresh analysis."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from tradingagents.self_loop.records import parse_date
from tradingagents.self_loop.evidence import build_evidence_packet
from tradingagents.self_loop.retrospective import run_retrospective
from tradingagents.self_loop.reviewer import detect_key_risk_trigger_with_subscription_ai
from scripts.self_loop_review import review_open_prediction


KST = ZoneInfo("Asia/Seoul")


def today_kst() -> str:
    return dt.datetime.now(KST).date().isoformat()


def iter_open_records(base_dir: Path, *, as_of_date: str, ticker: str | None = None):
    decisions_root = base_dir / "decisions"
    if not decisions_root.exists():
        return
    as_of = parse_date(as_of_date)
    for path in sorted(decisions_root.glob("*/*.json")):
        if ticker and path.stem.upper() != ticker.upper():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            analysis_date = parse_date(record["analysis_date"])
        except Exception:
            continue
        if not record.get("resolved") and analysis_date <= as_of:
            yield path, record


def _is_due(record: dict, as_of_date: str) -> bool:
    review_due = parse_date(record.get("review_due") or record["analysis_date"])
    return review_due <= parse_date(as_of_date)


def _trigger_check(record: dict, as_of_date: str, *, use_ai_review: bool) -> dict:
    preliminary = run_retrospective(record, as_of_date=as_of_date, ai_reviewer=None)
    if not use_ai_review:
        return {
            "status": "skipped",
            "trigger_fired": False,
            "matched_triggers": [],
            "reasoning": "AI trigger check disabled.",
            "confidence": "low",
            "price_result": preliminary.get("price_result"),
        }
    evidence_packet = build_evidence_packet(
        record,
        check_date=as_of_date,
        price_result=preliminary.get("price_result"),
    )
    result = detect_key_risk_trigger_with_subscription_ai(record, evidence_packet)
    result["price_result"] = preliminary.get("price_result")
    result["data_quality"] = evidence_packet.get("data_quality")
    result["missing_evidence"] = evidence_packet.get("missing_evidence")
    return result


def run_daily_check(
    *,
    base_dir: str | Path,
    as_of_date: str,
    ticker: str | None = None,
    use_ai_review: bool = True,
) -> dict:
    base = Path(base_dir)
    checked = []
    for record_path, record in iter_open_records(base, as_of_date=as_of_date, ticker=ticker) or []:
        if _is_due(record, as_of_date):
            result = review_open_prediction(
                ticker=str(record["ticker"]),
                as_of_date=as_of_date,
                trigger_fired=False,
                base_dir=base,
                use_ai_review=use_ai_review,
            )
            item = {
                "ticker": record.get("ticker"),
                "analysis_date": record.get("analysis_date"),
                "review_due": record.get("review_due"),
                "status": result.get("status"),
                "trigger_status": "review_due",
                "trigger_fired": False,
                "overall": result.get("overall"),
                "reason": result.get("reason"),
                "retrospective_path": result.get("retrospective_path"),
                "record_path": str(record_path),
            }
        else:
            trigger = _trigger_check(record, as_of_date, use_ai_review=use_ai_review)
            result = None
            if trigger.get("trigger_fired"):
                result = review_open_prediction(
                    ticker=str(record["ticker"]),
                    as_of_date=as_of_date,
                    trigger_fired=True,
                    base_dir=base,
                    use_ai_review=use_ai_review,
                )
            item = {
                "ticker": record.get("ticker"),
                "analysis_date": record.get("analysis_date"),
                "review_due": record.get("review_due"),
                "status": (result or {}).get("status", "pending"),
                "trigger_status": trigger.get("status"),
                "trigger_fired": bool(trigger.get("trigger_fired")),
                "matched_triggers": trigger.get("matched_triggers") or [],
                "trigger_reasoning": trigger.get("reasoning"),
                "trigger_confidence": trigger.get("confidence"),
                "overall": (result or {}).get("overall"),
                "reason": (result or {}).get("reason"),
                "retrospective_path": (result or {}).get("retrospective_path"),
                "record_path": str(record_path),
            }
        checked.append(item)
    digest_path = base / "reports" / as_of_date / "daily_trigger_check.md"
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Daily self-loop trigger check — {as_of_date}", ""]
    if not checked:
        lines.append("No open decision records.")
    for item in checked:
        suffix = ""
        if item.get("matched_triggers"):
            suffix = f" triggers={'; '.join(item['matched_triggers'])}"
        elif item.get("trigger_reasoning"):
            suffix = f" reason={item['trigger_reasoning']}"
        lines.append(
            f"- {item['ticker']} / {item['analysis_date']} due {item['review_due']}: "
            f"trigger={item.get('trigger_status')} fired={item.get('trigger_fired')} "
            f"status={item.get('status')} overall={item.get('overall')} "
            f"retrospective={item.get('retrospective_path')}{suffix}"
        )
    digest_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"as_of_date": as_of_date, "checked": checked, "digest_path": str(digest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--as-of-date", default=today_kst())
    parser.add_argument("--ticker")
    parser.add_argument("--no-ai-review", action="store_true")
    args = parser.parse_args()
    result = run_daily_check(
        base_dir=args.base_dir,
        as_of_date=args.as_of_date,
        ticker=args.ticker,
        use_ai_review=not args.no_ai_review,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
