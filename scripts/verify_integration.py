#!/usr/bin/env python3
"""End-to-end integration verification of the full propagate() pipeline.

Run from repo root:
    source .venv/bin/activate
    python scripts/verify_integration.py

What it verifies:

  1. The full TradingAgentsGraph.propagate() completes without timeout
     using the new packet-based analyst inputs (Phase 4-A/B/C) and the
     deterministic SignalProcessor (Phase 1).
  2. Each node's prompt size is captured via the existing CLIChatModel
     INFO log so we can see the context-shrink in action.
  3. The wall-clock time per node and total are reported.
  4. The final rating, final trade decision, and all sub-reports are
     dumped for human inspection.

The script uses the same config as main.py (claude-cli + sonnet/sonnet,
1 debate round, 1 risk round) which is the configuration that previously
failed with timeouts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_SCRIPT_DIR))  # repo root
sys.path.insert(0, _SCRIPT_DIR)  # scripts/ (so we can reuse export_run_to_md)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ----------------------------------------------------------------------
# CLI call interception — capture prompt size + elapsed time per call
# ----------------------------------------------------------------------


_CLI_CALLS: list[dict] = []


class _CLICallCapture(logging.Handler):
    """A logging handler that pulls prompt-length info out of CLIChatModel
    INFO records and records each call to the global _CLI_CALLS list.

    The CLIChatModel logs lines like:
        CLI call attempt 1/2: claude --model sonnet (prompt length: 12345 chars, via stdin)
        CLI call succeeded (response length: 2345 chars)

    We pair the two and record start/elapsed times.
    """

    _ATTEMPT_RE = re.compile(
        r"CLI call attempt (\d+)/(\d+): \S+ --model (\S+) \(prompt length: (\d+) chars"
    )
    _SUCCESS_RE = re.compile(r"CLI call succeeded \(response length: (\d+) chars\)")

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._pending_start: float | None = None
        self._pending_prompt_chars: int | None = None
        self._pending_model: str | None = None
        self._pending_attempt: int | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            return

        attempt_match = self._ATTEMPT_RE.search(msg)
        if attempt_match:
            self._pending_start = time.time()
            self._pending_attempt = int(attempt_match.group(1))
            self._pending_model = attempt_match.group(3)
            self._pending_prompt_chars = int(attempt_match.group(4))
            return

        success_match = self._SUCCESS_RE.search(msg)
        if success_match and self._pending_start is not None:
            elapsed = time.time() - self._pending_start
            _CLI_CALLS.append(
                {
                    "model": self._pending_model,
                    "attempt": self._pending_attempt,
                    "prompt_chars": self._pending_prompt_chars,
                    "response_chars": int(success_match.group(1)),
                    "elapsed_s": round(elapsed, 2),
                }
            )
            self._pending_start = None
            self._pending_prompt_chars = None
            self._pending_model = None
            self._pending_attempt = None


# ----------------------------------------------------------------------
# Run the graph
# ----------------------------------------------------------------------


def main() -> int:
    # Wire up the capture handler before importing TradingAgentsGraph so
    # we don't miss the very first log line.
    cli_logger = logging.getLogger("tradingagents.llm_clients.cli_client")
    cli_logger.setLevel(logging.INFO)
    cli_logger.addHandler(_CLICallCapture())
    cli_logger.propagate = False  # don't double-log via root

    # Also enable INFO on root so we see normal progress
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"] = "sonnet"
    config["quick_think_llm"] = "sonnet"
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1

    ticker = os.environ.get("VERIFY_TICKER", "005930")
    trade_date = os.environ.get("VERIFY_TRADE_DATE", "2026-04-10")

    print(f"Integration verification — ticker={ticker}, trade_date={trade_date}")
    print(f"  config: provider={config['llm_provider']}, "
          f"deep={config['deep_think_llm']}, quick={config['quick_think_llm']}, "
          f"debate_rounds={config['max_debate_rounds']}")

    print()
    print("Constructing TradingAgentsGraph...")
    t_construct_start = time.time()
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=False,
        config=config,
    )
    print(f"  graph constructed in {time.time() - t_construct_start:.2f}s")

    print()
    print(f"Running propagate('{ticker}', '{trade_date}')...")
    t_propagate_start = time.time()
    try:
        final_state, signal = graph.propagate(ticker, trade_date)
    except Exception as exc:
        elapsed = time.time() - t_propagate_start
        print(f"\n  PROPAGATE FAILED after {elapsed:.1f}s: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    total_elapsed = time.time() - t_propagate_start
    print(f"  propagate completed in {total_elapsed:.1f}s")

    # ----------------------------------------------------------
    # Per-node CLI call summary
    # ----------------------------------------------------------
    print()
    print("=" * 76)
    print(" Per-call CLI summary")
    print("=" * 76)
    print(f"{'#':>3} {'model':>8} {'prompt_chars':>13} {'response_chars':>15} {'elapsed_s':>10}")
    total_prompt_chars = 0
    total_response_chars = 0
    total_call_time = 0.0
    for i, call in enumerate(_CLI_CALLS, start=1):
        print(
            f"{i:>3} {call['model']:>8} {call['prompt_chars']:>13,} "
            f"{call['response_chars']:>15,} {call['elapsed_s']:>10.2f}"
        )
        total_prompt_chars += call["prompt_chars"]
        total_response_chars += call["response_chars"]
        total_call_time += call["elapsed_s"]

    print("-" * 76)
    print(
        f"{'tot':>3} {'':>8} {total_prompt_chars:>13,} "
        f"{total_response_chars:>15,} {total_call_time:>10.2f}"
    )
    print(f"  total CLI calls: {len(_CLI_CALLS)}")
    print(f"  total prompt chars: {total_prompt_chars:,}")
    print(f"  total response chars: {total_response_chars:,}")
    print(f"  sum of CLI call elapsed (sequential equivalent): {total_call_time:.1f}s")
    print(f"  wall-clock propagate elapsed: {total_elapsed:.1f}s")

    # ----------------------------------------------------------
    # Final reports
    # ----------------------------------------------------------
    print()
    print("=" * 76)
    print(" Final outputs")
    print("=" * 76)
    print(f"  Signal (extracted rating): {signal}")
    print()

    sections: list[tuple[str, str]] = [
        ("market_report", final_state.get("market_report", "")),
        ("news_report", final_state.get("news_report", "")),
        ("fundamentals_report", final_state.get("fundamentals_report", "")),
        ("investment_plan", final_state.get("investment_plan", "")),
        ("trader_investment_plan", final_state.get("trader_investment_plan", "")),
        ("final_trade_decision", final_state.get("final_trade_decision", "")),
    ]
    for name, body in sections:
        print(f"  {name}: {len(body):,} chars")

    # ----------------------------------------------------------
    # Save the full state for human inspection
    # ----------------------------------------------------------
    out_dir = "eval_results/integration"
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path_json = os.path.join(out_dir, f"{ticker}_{trade_date}_{timestamp}.json")
    serializable = {
        "ticker": ticker,
        "trade_date": trade_date,
        "signal": signal,
        "wall_clock_seconds": round(total_elapsed, 2),
        "cli_calls": _CLI_CALLS,
        "sections": {name: body for name, body in sections},
    }
    with open(out_path_json, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print()
    print(f"  Full state saved to: {out_path_json}")

    # Also produce a human-readable markdown copy via the shared exporter.
    try:
        from export_run_to_md import render_markdown, _from_integration_dump

        md = render_markdown(_from_integration_dump(serializable))
        out_path_md = out_path_json.replace(".json", ".md")
        with open(out_path_md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"  Markdown report saved to: {out_path_md}")
    except Exception as exc:
        print(f"  WARNING: failed to write markdown copy: {exc}")

    print()
    print("=" * 76)
    print(" Final trade decision (full text)")
    print("=" * 76)
    print(final_state.get("final_trade_decision", ""))

    return 0


if __name__ == "__main__":
    sys.exit(main())
