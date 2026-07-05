# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TradingAgents Korea is a Korea-market adaptation of `TauricResearch/TradingAgents` — a multi-agent LLM research workflow for KOSPI/KOSDAQ equities. It resolves Korean stock identifiers, prefetches data from Korean sources (KIS, DART, ECOS, Naver News) plus yfinance, builds compact feature packets, runs a LangGraph multi-agent debate, and emits a Markdown research report (Korean by default). It is a research/education project, **not** investment advice or an automated trading system.

## Common commands

```bash
# Setup (editable install into a venv)
python3 -m venv .venv
.venv/bin/python -m pip install -e .
cp .env.example .env          # then fill in API keys

# Run a single analysis (defaults: ticker 005930, today KST)
.venv/bin/python main.py [TICKER] [YYYY-MM-DD]
# Report saved under ./results/<ticker>/<date>/complete_report.md

# Interactive Rich CLI
.venv/bin/python -m cli.main      # or `tradingagents` after install

# Telegram bot
.venv/bin/python -m cli.bot       # requires TELEGRAM_BOT_TOKEN

# Tests (bare unittest — no pytest config, no conftest)
.venv/bin/python -m unittest discover -s tests        # all tests
.venv/bin/python -m unittest tests.test_prefetch_cache # one module
.venv/bin/python -m unittest tests.test_cli_client.TestFactoryRouting  # one case

# OpenClaw → Notion publishing helper
python .openclaw/skills/tradingagents-korea-analysis/scripts/run_analysis_to_notion.py \
  --ticker 005930 --date YYYY-MM-DD --timeout 7200
```

Enable runtime timing traces with `TRADINGAGENTS_TIMING_LOGS=1` (see `tradingagents/runtime_trace.py`).

## Architecture

The pipeline: **ticker resolution → data prefetch → feature packets → LangGraph agent workflow → Markdown/Notion report.**

### LLM execution — CLI-first, not API-first
The default provider is a local CLI backend, not a hosted API. `tradingagents/llm_clients/factory.py` routes `llm_provider` to a client; `claude-cli` and `codex-cli` both use `CLIClient`, which shells out to the `claude` or `codex` binary (see `CLI_BACKEND_SPECS` in `cli_client.py`) instead of sending an API key. `anthropic`/`openai`/`google` API clients also exist. Two model tiers are used everywhere: `quick_think_llm` and `deep_think_llm`. Provider/model defaults come from env vars (`TRADINGAGENTS_LLM_PROVIDER`, `TRADINGAGENTS_QUICK_MODEL`, `TRADINGAGENTS_DEEP_MODEL`) resolved in `tradingagents/default_config.py`.

### The graph (`tradingagents/graph/`)
`TradingAgentsGraph` (`trading_graph.py`) is the orchestrator. It builds two LLM clients, five `FinancialSituationMemory` stores, and wires sub-components:
- `setup.py` (`GraphSetup`) — builds the LangGraph `StateGraph`; nodes are wrapped with `_instrument_node` for tracing.
- `conditional_logic.py` — debate/risk loop continuation, bounded by `max_debate_rounds` / `max_risk_discuss_rounds`.
- `propagation.py` — runs the graph; `propagate(ticker, date)` returns `(final_state, decision)`.
- `signal_processing.py`, `reflection.py` — post-process the final signal and reflect on outcomes.

Agent nodes live in `tradingagents/agents/`: `analysts/` (market, news, fundamentals, social_media), `researchers/` (bull/bear), `risk_mgmt/` (aggressive/neutral/conservative debators), `trader/`, `managers/` (research + portfolio). `agents/__init__.py` re-exports them (the graph uses `from tradingagents.agents import *`).

### Data layer (`tradingagents/dataflows/`) — vendor routing
This is the most important Korea-specific abstraction. `interface.py` defines the routing tables:
- `TOOLS_CATEGORIES` groups logical methods (`get_stock_data`, `get_news`, `get_macro_summary`, …) into categories.
- `VENDOR_METHODS` maps each method × vendor → concrete callable (e.g. `get_stock_data` → `kis`/`yfinance`/`alpha_vantage`).
- Routing precedence (config in `default_config.py`): `tool_vendors` (per-method override) > `data_vendors` (per-category default). Use `route_to_vendor(method, ...)` / `get_vendor_callable(method, vendor)` to dispatch.
- **Structured data** (price, indicators, fundamentals, macro) routes to one primary vendor and should fail loudly rather than silently substitute another source. **News is multi-source by design** — `multi_source_vendors` merges `naver,yfinance` instead of treating one as a fallback.

Korean stock inputs (`005930`, `삼성전자`, `005930.KS`, DART corp code, Naver query) are resolved to source-specific identifiers via `korea_ticker.py` (`get_instrument_profile`); identifiers are kept separate per source rather than forced into one ticker string.

### Prefetch + feature packets
`dataflows/prefetch.py` collects all analyst data **before** any LLM call (replacing the bind_tools iterative-tool-call pattern), with file-based caching (past dates cached permanently; today's data has a 1-hour TTL). Two output shapes coexist: legacy `prefetch_*_data()` returns large human-readable text blobs; newer `prefetch_*_packet()` (in `dataflows/feature_packets/`) returns compact structured packets for LLM consumption. First-stage analysts use the packet path.

### Reports
`scripts/export_run_to_md.py` (`render_markdown`) turns a `propagate()` final state into the Markdown report; `main.py` calls it directly. `report_language` config (`"ko"` default, `"en"`) controls output language.

## Conventions

- Korean stocks are the primary target. US/overseas tickers (`AAPL`, etc.) are a separate workflow — global FRED/SEC-EDGAR sources under `global_data` are optional **enrichment only** and must not replace KIS/DART/ECOS.
- When adding a data source: register it in `VENDOR_LIST`, add the callable to the relevant `VENDOR_METHODS[method]` map, and wire defaults in `default_config.py` — don't call vendor APIs directly from agents.
- Tests use stdlib `unittest` with heavy mocking of vendor APIs and the CLI subprocess; there is no network access in tests.
- Docs are bilingual: many files have `.md` (English) and `.ko.md` (Korean) variants under `docs/`.
- Secrets live in `.env` (gitignored). See `SECURITY_PUBLIC_RELEASE_CHECKLIST.md` and `docs/public-release-guide.md` before any public-release work.
