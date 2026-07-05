import argparse
import datetime
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from scripts.export_run_to_md import render_markdown
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


KST = ZoneInfo("Asia/Seoul")
DEFAULT_TICKER = "005930"


def _build_export_state(final_state: dict, ticker: str, trade_date: str,
                        signal: str, wall_clock_seconds: float) -> dict:
    """Convert propagate() final_state into the shape render_markdown() expects."""
    debate = final_state.get("investment_debate_state") or {}
    risk = final_state.get("risk_debate_state") or {}
    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "signal": signal,
        "wall_clock_seconds": wall_clock_seconds,
        "cli_calls": [],  # not tracked in simple main.py runs
        "market_report": final_state.get("market_report") or "",
        "news_report": final_state.get("news_report") or "",
        "fundamentals_report": final_state.get("fundamentals_report") or "",
        "investment_plan": final_state.get("investment_plan") or "",
        "trader_investment_plan": final_state.get("trader_investment_plan") or "",
        "final_trade_decision": final_state.get("final_trade_decision") or "",
        "debate_state": {
            "history": debate.get("history") or "",
            "judge_decision": debate.get("judge_decision") or "",
        },
        "risk_state": {
            "history": risk.get("history") or "",
        },
    }


def _today_kst() -> str:
    return datetime.datetime.now(KST).date().isoformat()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a TradingAgents analysis. The self-improvement loop is always "
            "on: it retrospects on the prior decision record (skipped when none "
            "exists, e.g. the first run for a ticker), injects prior lessons, and "
            "writes a fresh decision record. The Markdown report is saved under "
            "results/<ticker>/<date>/complete_report.md."
        )
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        default=DEFAULT_TICKER,
        help=f"Ticker to analyze. Defaults to Samsung Electronics ({DEFAULT_TICKER}).",
    )
    parser.add_argument(
        "analysis_date",
        nargs="?",
        default=_today_kst(),
        help="Analysis date in YYYY-MM-DD. Defaults to today's date in Asia/Seoul.",
    )
    parser.add_argument(
        "--review-horizon-days",
        type=int,
        default=5,
        help="Trading-day review horizon for the self-loop decision record.",
    )
    return parser.parse_args()


def _write_markdown_report(
    config: dict,
    ticker: str,
    analysis_date: str,
    markdown: str,
) -> tuple[Path, Path]:
    timestamp = datetime.datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    results_dir = Path(config["results_dir"]) / ticker / analysis_date
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamped_path = results_dir / f"{ticker}_{analysis_date}_{timestamp}.md"
    complete_report_path = results_dir / "complete_report.md"

    timestamped_path.write_text(markdown, encoding="utf-8")
    complete_report_path.write_text(markdown, encoding="utf-8")
    return complete_report_path, timestamped_path


def main():
    args = _parse_args()
    ticker = args.ticker
    analysis_date = args.analysis_date

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = 1

    # Data pre-flight: reuse the (cached) market packet the analysts will consume
    # and abort before the expensive multi-agent run if KIS returned no usable
    # price data (e.g. queried before market open). The packet is cached, so the
    # Market Analyst reuses it with no extra API call — prevents no_data reports.
    from tradingagents.dataflows.prefetch import prefetch_market_packet
    _mp = prefetch_market_packet(ticker, analysis_date)
    if (getattr(_mp, "regime", None) or {}).get("label") == "no_data" or not getattr(_mp, "price", None):
        print(
            f"DATA_UNAVAILABLE: empty market packet for {ticker} {analysis_date} "
            f"(KIS OHLCV empty / no_data). Aborting before analysis — retry after market open. "
            f"If this keeps happening, check KIS_APP_KEY/KIS_APP_SECRET in .env "
            f"(run `tradingagents doctor`)."
        )
        raise SystemExit(2)

    # The self-improvement loop is always on (no opt-in flag). run_self_loop
    # retrospects on the prior decision record (auto-skipped when none exists,
    # e.g. the first run for this ticker), injects prior lessons via
    # ``self_loop_context``, and writes a fresh decision record + digest. The
    # actual multi-agent run is supplied as ``graph_runner`` so the same
    # propagate() call feeds both the report and the self-loop.
    from scripts.run_self_loop import run_self_loop

    captured: dict = {}

    def _graph_runner(_ticker, _analysis_date, self_loop_context):
        graph = TradingAgentsGraph(
            selected_analysts=["market", "news", "fundamentals"],
            debug=True,
            config=config,
        )
        t0 = time.time()
        final_state, decision = graph.propagate(
            _ticker, _analysis_date, self_loop_context=self_loop_context
        )
        captured["final_state"] = final_state
        captured["decision"] = decision
        captured["elapsed"] = time.time() - t0
        return final_state, decision

    loop_result = run_self_loop(
        ticker=ticker,
        analysis_date=analysis_date,
        review_horizon_days=args.review_horizon_days,
        graph_runner=_graph_runner,
    )

    final_state = captured.get("final_state") or {}
    decision = captured.get("decision", "")
    elapsed = captured.get("elapsed", 0.0)
    print(decision)

    # Preserve the canonical results/<ticker>/<date>/complete_report.md artifact
    # (the skill runner sentinel, Telegram bot, and report tooling rely on it),
    # alongside the self-loop's own reports/<date>/<ticker>.md.
    export_state = _build_export_state(
        final_state, ticker, analysis_date, decision, elapsed,
    )
    md = render_markdown(export_state)

    complete_report_path, timestamped_path = _write_markdown_report(
        config, ticker, analysis_date, md,
    )
    print(f"\nComplete report saved to: {complete_report_path.resolve()}")
    print(f"Timestamped copy saved to: {timestamped_path.resolve()}")
    print("\nSelf-loop:")
    for key, value in loop_result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
