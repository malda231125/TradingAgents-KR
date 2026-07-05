#!/usr/bin/env python3
"""Event-driven self-loop review.

The fixed review horizon is only a timeout. A prediction should be scored as
soon as its thesis is confirmed or broken by a Key Risk Trigger. A daily
verification job can call this script with ``--trigger-fired`` to run the
retrospective immediately, append the lesson, and mark the decision record
resolved so it is not reviewed twice.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load the repo .env so the retrospective's data fetchers (KIS/DART/Naver/ECOS,
# Toss/yfinance/SEC/FRED) get their API keys even when this script is invoked
# standalone by the verify cron (without it, all evidence fetches fail and the
# review silently scores 'uncertain'). Explicit path = CWD-independent.
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from tradingagents.self_loop.lessons import append_lesson
from tradingagents.self_loop.records import (
    find_latest_decision_record,
    parse_date,
    save_decision_record,
)
from tradingagents.self_loop.retrospective import (
    run_retrospective,
    save_retrospective_markdown,
)
from tradingagents.self_loop.reviewer import review_with_subscription_ai

KST = ZoneInfo("Asia/Seoul")


def should_review(record: dict[str, Any], as_of_date: str, trigger_fired: bool) -> bool:
    """Review now if a trigger fired, or when the timeout date is reached."""
    if record.get("resolved"):
        return False
    if trigger_fired:
        return True
    review_due = record.get("review_due") or record.get("analysis_date")
    return parse_date(as_of_date) >= parse_date(review_due)


def review_open_prediction(
    *,
    ticker: str,
    as_of_date: str,
    trigger_fired: bool = False,
    base_dir: str | Path = ".",
    use_ai_review: bool = True,
    price_fetcher: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Review the latest unresolved prediction for ``ticker`` when due or triggered."""
    found = find_latest_decision_record(ticker, base_dir=base_dir, before_date=as_of_date)
    if not found:
        return {"status": "none", "ticker": ticker}

    _path, record = found
    if record.get("resolved"):
        return {
            "status": "already_resolved",
            "ticker": ticker,
            "analysis_date": record.get("analysis_date"),
        }
    if not should_review(record, as_of_date, trigger_fired):
        return {
            "status": "pending",
            "ticker": ticker,
            "analysis_date": record.get("analysis_date"),
            "review_due": record.get("review_due"),
        }

    retro_kwargs: dict[str, Any] = {
        "as_of_date": as_of_date,
        "ai_reviewer": review_with_subscription_ai if use_ai_review else None,
    }
    if price_fetcher is not None:
        retro_kwargs["price_fetcher"] = price_fetcher
    retrospective = run_retrospective(record, **retro_kwargs)

    # Data-outage guard: if the close price could not be fetched (e.g. API
    # credential outage → KIS HTTP 500, DART/Naver/ECOS missing), we cannot
    # score the prediction. Do NOT resolve or append a zero-signal lesson —
    # leave the record open so the next cycle retries once data is healthy.
    price_result = retrospective.get("price_result") or {}
    if price_result.get("start_close") is None or price_result.get("end_close") is None:
        save_retrospective_markdown(retrospective, base_dir=base_dir)
        return {
            "status": "deferred_no_data",
            "ticker": ticker,
            "analysis_date": record.get("analysis_date"),
            "message": price_result.get("message") or "price unavailable; review deferred",
        }

    retrospective_path = save_retrospective_markdown(retrospective, base_dir=base_dir)
    lesson = retrospective.get("lesson")
    if lesson:
        append_lesson(
            ticker=ticker,
            lesson=lesson,
            source={
                "analysis_date": retrospective.get("analysis_date"),
                "check_date": retrospective.get("check_date"),
                "overall": retrospective.get("overall"),
                "trigger_fired": trigger_fired,
            },
            base_dir=base_dir,
        )

    record["resolved"] = True
    record["resolved_on"] = parse_date(as_of_date).isoformat()
    record["resolved_reason"] = "trigger_fired" if trigger_fired else "review_due"
    if retrospective_path:
        record["retrospective_path"] = str(retrospective_path)
    save_decision_record(record, base_dir=base_dir)

    return {
        "status": "reviewed",
        "ticker": ticker,
        "analysis_date": record.get("analysis_date"),
        "overall": retrospective.get("overall"),
        "lesson": lesson,
        "reason": record["resolved_reason"],
        "retrospective_path": str(retrospective_path) if retrospective_path else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument(
        "as_of_date",
        nargs="?",
        default=dt.datetime.now(KST).date().isoformat(),
        help="Check date YYYY-MM-DD, default today KST.",
    )
    parser.add_argument(
        "--trigger-fired",
        action="store_true",
        help="Review immediately because a Key Risk Trigger fired.",
    )
    parser.add_argument("--no-ai-review", action="store_true", help="Use deterministic review only.")
    parser.add_argument("--base-dir", default=".")
    args = parser.parse_args()

    result = review_open_prediction(
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        trigger_fired=args.trigger_fired,
        base_dir=args.base_dir,
        use_ai_review=not args.no_ai_review,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
