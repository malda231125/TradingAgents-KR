#!/usr/bin/env python3
"""Run a TradingAgents Korea self-loop analysis.

The self-loop does four things:
1. Find the latest prior decision record for the ticker.
2. Fact-check it with a retrospective scorer and append lessons when needed.
3. Run a fresh TradingAgents analysis with prior lessons in the initial context.
4. Save the report, new decision record, and a compact self-loop digest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from scripts.export_run_to_md import render_markdown
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.self_loop.lessons import (
    append_lesson,
    format_lessons_context,
    load_lesson_summary,
    load_lessons,
    save_lesson_summary,
)
from tradingagents.self_loop.records import (
    build_decision_record,
    find_latest_decision_record,
    save_decision_record,
)
from tradingagents.self_loop.retrospective import (
    run_retrospective,
    save_retrospective_markdown,
)
from tradingagents.self_loop.reviewer import (
    deterministic_lesson_summary,
    review_with_subscription_ai,
    summarize_lessons_with_subscription_ai,
)


KST = ZoneInfo("Asia/Seoul")


GraphRunner = Callable[[str, str, str | None], tuple[dict[str, Any], str]]


def today_kst() -> str:
    return dt.datetime.now(KST).date().isoformat()


def run_self_loop(
    *,
    ticker: str,
    analysis_date: str,
    review_horizon_days: int = 5,
    base_dir: str | Path = ".",
    graph_runner: GraphRunner | None = None,
    use_ai_review: bool = True,
    recent_lesson_limit: int = 5,
    lesson_summary_threshold: int = 50,
    decision_extractor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    trading_day_fn: Callable[[Any, int], Any] | None = None,
) -> dict[str, Any]:
    base_path = Path(base_dir)

    prior = find_latest_decision_record(ticker, base_dir=base_path, before_date=analysis_date)
    retrospective = None
    retrospective_path = None
    if prior is not None:
        _, prior_record = prior
        ai_reviewer = review_with_subscription_ai if use_ai_review else None
        retrospective = run_retrospective(
            prior_record,
            as_of_date=analysis_date,
            ai_reviewer=ai_reviewer,
        )
        retrospective_path = save_retrospective_markdown(retrospective, base_dir=base_path)
        lesson = retrospective.get("lesson")
        if lesson:
            append_lesson(
                ticker=ticker,
                lesson=lesson,
                source={
                    "analysis_date": retrospective.get("analysis_date"),
                    "check_date": retrospective.get("check_date"),
                    "overall": retrospective.get("overall"),
                },
                base_dir=base_path,
            )
            _maybe_update_lesson_summary(
                ticker=ticker,
                base_dir=base_path,
                threshold=lesson_summary_threshold,
                use_ai_review=use_ai_review,
            )

    lessons = load_lessons(ticker, base_dir=base_path, limit=recent_lesson_limit)
    lesson_summary = load_lesson_summary(ticker, base_dir=base_path)
    prior_context = _build_prior_context(retrospective, lessons, lesson_summary)

    if graph_runner is None:
        graph_runner = _default_graph_runner

    started = time.time()
    final_state, signal = graph_runner(ticker, analysis_date, prior_context or None)
    elapsed = time.time() - started

    report_path = _save_report(
        base_path=base_path,
        ticker=ticker,
        analysis_date=analysis_date,
        final_state=final_state,
        signal=signal,
        elapsed=elapsed,
        self_loop_context=prior_context,
        retrospective=retrospective,
    )

    decision_record = build_decision_record(
        ticker=ticker,
        analysis_date=analysis_date,
        signal=signal,
        final_state=final_state,
        report_path=report_path,
        review_horizon_days=review_horizon_days,
        retrospective_path=retrospective_path,
        extractor=decision_extractor,
        trading_day_fn=trading_day_fn,
        use_ai_extraction=use_ai_review,
    )
    decision_path = save_decision_record(decision_record, base_dir=base_path)
    digest_path = _save_digest(
        base_path=base_path,
        ticker=ticker,
        analysis_date=analysis_date,
        decision_record=decision_record,
        retrospective=retrospective,
        lessons=lessons,
        lesson_summary=lesson_summary,
    )

    return {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "report_path": str(report_path),
        "decision_path": str(decision_path),
        "digest_path": str(digest_path),
        "retrospective_path": str(retrospective_path) if retrospective_path else None,
        "signal": signal,
    }


def _default_graph_runner(
    ticker: str,
    analysis_date: str,
    prior_context: str | None,
) -> tuple[dict[str, Any], str]:
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = 1
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=True,
        config=config,
    )
    return graph.propagate(ticker, analysis_date, self_loop_context=prior_context)


def _build_prior_context(
    retrospective: dict[str, Any] | None,
    lessons: list[dict[str, Any]],
    lesson_summary: str = "",
) -> str:
    blocks = []
    if retrospective:
        blocks.append(
            "\n".join(
                [
                    "Self-loop retrospective from prior analysis:",
                    f"- Prior analysis date: {retrospective.get('analysis_date')}",
                    f"- Prior decision: {retrospective.get('decision')}",
                    f"- Outcome: {retrospective.get('overall')}",
                    f"- Lesson: {retrospective.get('lesson') or 'No lesson; prior thesis held.'}",
                ]
            )
        )
    lessons_context = format_lessons_context(lessons, summary=lesson_summary)
    if lessons_context:
        blocks.append(lessons_context)
    if not blocks:
        return ""
    return "\n\n".join(blocks)


def _save_report(
    *,
    base_path: Path,
    ticker: str,
    analysis_date: str,
    final_state: dict[str, Any],
    signal: str,
    elapsed: float,
    self_loop_context: str,
    retrospective: dict[str, Any] | None,
) -> Path:
    report_dir = base_path / "reports" / analysis_date
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{ticker}.md"
    markdown = render_markdown(
        {
            "ticker": ticker,
            "trade_date": analysis_date,
            "signal": signal,
            "wall_clock_seconds": elapsed,
            "cli_calls": [],
            "market_report": final_state.get("market_report") or "",
            "news_report": final_state.get("news_report") or "",
            "fundamentals_report": final_state.get("fundamentals_report") or "",
            "investment_plan": final_state.get("investment_plan") or "",
            "trader_investment_plan": final_state.get("trader_investment_plan") or "",
            "final_trade_decision": final_state.get("final_trade_decision") or "",
            "debate_state": final_state.get("investment_debate_state") or {},
            "risk_state": final_state.get("risk_debate_state") or {},
            "self_loop_context": self_loop_context,
            "self_loop_retrospective": retrospective or {},
        }
    )
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def _save_digest(
    *,
    base_path: Path,
    ticker: str,
    analysis_date: str,
    decision_record: dict[str, Any],
    retrospective: dict[str, Any] | None,
    lessons: list[dict[str, Any]],
    lesson_summary: str,
) -> Path:
    digest_dir = base_path / "reports" / analysis_date
    digest_dir.mkdir(parents=True, exist_ok=True)
    digest_path = digest_dir / "self_loop_digest.md"
    lines = [
        f"# Self-loop digest — {analysis_date}",
        "",
        f"## {ticker}",
        "",
        f"- Decision: {decision_record.get('decision')}",
        f"- Confidence: {decision_record.get('confidence')}",
        f"- Review due: {decision_record.get('review_due')}",
        f"- Report: {decision_record.get('report_path')}",
    ]
    if retrospective:
        lines.extend(
            [
                "",
                "## Prior Retrospective",
                "",
                f"- Prior date: {retrospective.get('analysis_date')}",
                f"- Outcome: {retrospective.get('overall')}",
                f"- Lesson: {retrospective.get('lesson') or 'No lesson'}",
            ]
        )
    if lessons:
        lines.extend(["", "## Recent Lessons", ""])
        for item in lessons[-5:]:
            lines.append(f"- {item.get('lesson')}")
    if lesson_summary:
        lines.extend(["", "## Long-term Lesson Summary", "", lesson_summary])
    digest_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return digest_path


def _maybe_update_lesson_summary(
    *,
    ticker: str,
    base_dir: Path,
    threshold: int,
    use_ai_review: bool,
) -> None:
    all_lessons = load_lessons(ticker, base_dir=base_dir, limit=None)
    if len(all_lessons) < int(threshold):
        return
    previous_summary = load_lesson_summary(ticker, base_dir=base_dir)
    try:
        if use_ai_review:
            summary = summarize_lessons_with_subscription_ai(
                ticker=ticker,
                lessons=all_lessons,
                previous_summary=previous_summary,
            )
        else:
            summary = deterministic_lesson_summary(ticker=ticker, lessons=all_lessons)
    except Exception:
        summary = deterministic_lesson_summary(ticker=ticker, lessons=all_lessons)
    save_lesson_summary(ticker, summary, base_dir=base_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TradingAgents Korea self-loop analysis.")
    parser.add_argument("--ticker", required=True, help="Korean ticker, e.g. 005930")
    parser.add_argument("--date", default=today_kst(), help="Analysis date YYYY-MM-DD")
    parser.add_argument("--review-horizon-days", type=int, default=5)
    parser.add_argument("--base-dir", default=".", help="Base directory for reports/decisions/lessons")
    parser.add_argument("--recent-lesson-limit", type=int, default=5)
    parser.add_argument("--lesson-summary-threshold", type=int, default=50)
    parser.add_argument(
        "--no-ai-review",
        action="store_true",
        help="Skip subscription CLI AI review and use deterministic retrospective only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_self_loop(
        ticker=args.ticker,
        analysis_date=args.date,
        review_horizon_days=args.review_horizon_days,
        base_dir=args.base_dir,
        use_ai_review=not args.no_ai_review,
        recent_lesson_limit=args.recent_lesson_limit,
        lesson_summary_threshold=args.lesson_summary_threshold,
    )
    print("Self-loop completed")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
