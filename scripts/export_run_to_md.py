#!/usr/bin/env python3
"""Export a saved TradingAgents propagate() run to a human-readable markdown report.

Usage:
    python scripts/export_run_to_md.py <input.json> [output.md]

Accepts either format:
  - The integration verification dump from `verify_integration.py`
    (`eval_results/integration/<ticker>_<date>_<timestamp>.json`)
  - The standard graph state log written by `TradingAgentsGraph._log_state`
    (`eval_results/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`)

Output structure:
  - Run metadata (ticker, date, timing, signal)
  - Per-call CLI summary (when available)
  - Each section in full: market / news / fundamentals reports,
    debate history, investment plan, trader plan, final decision
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime


# ----------------------------------------------------------------------
# Input adapters — both formats normalized into the same dict shape
# ----------------------------------------------------------------------


def _from_integration_dump(raw: dict) -> dict:
    """Adapt the verify_integration.py JSON into the unified shape."""
    sections = raw.get("sections") or {}
    return {
        "ticker": raw.get("ticker"),
        "trade_date": raw.get("trade_date"),
        "signal": raw.get("signal"),
        "wall_clock_seconds": raw.get("wall_clock_seconds"),
        "cli_calls": raw.get("cli_calls") or [],
        "market_report": sections.get("market_report") or "",
        "news_report": sections.get("news_report") or "",
        "fundamentals_report": sections.get("fundamentals_report") or "",
        "investment_plan": sections.get("investment_plan") or "",
        "trader_investment_plan": sections.get("trader_investment_plan") or "",
        "final_trade_decision": sections.get("final_trade_decision") or "",
        # Debate state isn't in the integration dump
        "debate_state": {},
        "risk_state": {},
    }


def _from_graph_state_log(raw: dict) -> dict:
    """Adapt the TradingAgentsGraph._log_state JSON into the unified shape.

    The log file is keyed by trade_date, so we take the (only) entry.
    """
    if not raw:
        return {}
    # File is `{trade_date_str: full_state_dict}`
    trade_date = next(iter(raw))
    state = raw[trade_date]
    return {
        "ticker": state.get("company_of_interest"),
        "trade_date": state.get("trade_date") or trade_date,
        "signal": None,  # not stored in the graph log
        "wall_clock_seconds": None,
        "cli_calls": [],
        "market_report": state.get("market_report") or "",
        "news_report": state.get("news_report") or "",
        "fundamentals_report": state.get("fundamentals_report") or "",
        "investment_plan": state.get("investment_plan") or "",
        "trader_investment_plan": state.get("trader_investment_decision")
        or state.get("trader_investment_plan")
        or "",
        "final_trade_decision": state.get("final_trade_decision") or "",
        "debate_state": state.get("investment_debate_state") or {},
        "risk_state": state.get("risk_debate_state") or {},
        "self_loop_context": state.get("self_loop_context") or "",
    }


def _normalize(raw: dict) -> dict:
    if "sections" in raw and "cli_calls" in raw:
        return _from_integration_dump(raw)
    return _from_graph_state_log(raw)


# ----------------------------------------------------------------------
# Markdown rendering
# ----------------------------------------------------------------------


def _section(title: str, body: str | None) -> list[str]:
    if not body:
        return []
    return [
        f"## {title}",
        "",
        body.strip(),
        "",
    ]


def _kv_table(rows: list[tuple[str, str]], strings: dict) -> list[str]:
    if not rows:
        return []
    out = [f"| {strings['kv_item']} | {strings['kv_value']} |", "|---|---|"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    out.append("")
    return out


def _format_cli_calls_table(calls: list[dict], strings: dict) -> list[str]:
    if not calls:
        return []
    out = [
        "## CLI Call Summary",
        "",
        "| # | model | prompt_chars | response_chars | elapsed_s |",
        "|---:|---|---:|---:|---:|",
    ]
    total_p = 0
    total_r = 0
    total_t = 0.0
    for i, c in enumerate(calls, start=1):
        p = int(c.get("prompt_chars") or 0)
        r = int(c.get("response_chars") or 0)
        t = float(c.get("elapsed_s") or 0)
        total_p += p
        total_r += r
        total_t += t
        out.append(
            f"| {i} | {c.get('model', '')} | {p:,} | {r:,} | {t:.2f} |"
        )
    out.append(
        f"| **{strings['total']}** | | **{total_p:,}** | **{total_r:,}** | **{total_t:.2f}** |"
    )
    out.append("")
    return out


def render_markdown(state: dict) -> str:
    from tradingagents.i18n import get_report_strings

    # Report language: explicit on the state if provided, else the active config.
    s = get_report_strings(state.get("report_language"))

    lines: list[str] = []

    title_ticker = state.get("ticker") or "(unknown)"
    title_date = state.get("trade_date") or "(unknown)"
    lines.append(f"# {s['run_title']} — {title_ticker} / {title_date}")
    lines.append("")
    lines.append(
        f"_{s['exported_at']} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    )
    lines.append("")

    metadata: list[tuple[str, str]] = []
    if state.get("ticker"):
        metadata.append((s["ticker"], state["ticker"]))
    if state.get("trade_date"):
        metadata.append((s["trade_date"], state["trade_date"]))
    if state.get("signal"):
        metadata.append((s["final_signal"], f"**{state['signal']}**"))
    if state.get("wall_clock_seconds") is not None:
        secs = state["wall_clock_seconds"]
        metadata.append((s["wall_clock"], f"{secs:.1f} s ({secs / 60:.1f} min)"))
    if state.get("cli_calls"):
        metadata.append((s["cli_calls"], str(len(state["cli_calls"]))))

    if metadata:
        lines.append(f"## {s['run_metadata']}")
        lines.append("")
        lines.extend(_kv_table(metadata, s))

    lines.extend(_format_cli_calls_table(state.get("cli_calls") or [], s))

    self_loop_context = state.get("self_loop_context")
    if self_loop_context:
        lines.extend(_section(s["sl_context"], self_loop_context))

    self_loop_retrospective = state.get("self_loop_retrospective") or {}
    if self_loop_retrospective:
        retro_lines = [
            f"- {s['sl_prior_date']}: {self_loop_retrospective.get('analysis_date')}",
            f"- {s['sl_prior_decision']}: {self_loop_retrospective.get('decision')}",
            f"- {s['sl_outcome']}: {self_loop_retrospective.get('overall')}",
        ]
        lesson = self_loop_retrospective.get("lesson")
        if lesson:
            retro_lines.append(f"- {s['sl_lesson']}: {lesson}")
        lines.extend(_section(s["sl_result"], "\n".join(retro_lines)))

    lines.extend(_section(s["market"], state.get("market_report")))
    lines.extend(_section(s["news"], state.get("news_report")))
    lines.extend(_section(s["fundamentals"], state.get("fundamentals_report")))

    debate = state.get("debate_state") or {}
    if debate.get("history"):
        lines.extend(_section(s["debate"], debate["history"]))

    plan = state.get("investment_plan") or ""
    judge = debate.get("judge_decision") or ""
    if judge.strip() and judge.strip() != plan.strip():
        lines.extend(_section(s["rm_decision"], judge))

    lines.extend(_section(s["investment_plan"], plan))
    lines.extend(_section(s["trader_plan"], state.get("trader_investment_plan")))

    risk = state.get("risk_state") or {}
    if risk.get("history"):
        lines.extend(_section(s["risk_debate"], risk["history"]))

    lines.extend(_section(f"**{s['final_decision']}**", state.get("final_trade_decision")))

    return "\n".join(lines)


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"input file not found: {input_path}", file=sys.stderr)
        return 1

    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    state = _normalize(raw)
    md = render_markdown(state)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        # Default: same path with .md extension
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"wrote {len(md):,} chars → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
