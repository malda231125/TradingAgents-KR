# Contributing to TradingAgents Korea

Thanks for your interest in contributing! This project adapts
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
to the Korean equity market (KOSPI/KOSDAQ). It is a **research/education**
project — not investment advice or an automated trading system.

## Getting started

```bash
# Clone, create a venv, install in editable mode with test deps
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"

# Configure secrets locally (never commit real keys)
cp .env.example .env   # then fill in your own API keys

# Run the test suite (mocks all vendor APIs + the CLI subprocess; no network)
.venv/bin/python -m pytest tests/ -q
```

A single analysis: `.venv/bin/python main.py [TICKER] [YYYY-MM-DD]`
(report saved under `results/<ticker>/<date>/complete_report.md`).
See [`README.md`](README.md) and [`docs/`](docs/) for architecture details.

## Ground rules

- **Never commit secrets.** API keys, tokens, KIS account identifiers and
  token-cache files belong in `.env` (gitignored). See [SECURITY.md](SECURITY.md).
- **Keep the Korea-first data contract.** Structured data (price, indicators,
  fundamentals, macro) routes to one primary vendor and should fail loudly
  rather than silently substitute another source. Add new sources through the
  vendor-routing tables in `tradingagents/dataflows/interface.py` and
  `default_config.py` — don't call vendor APIs directly from agents.
- **Tests must pass and stay network-free.** Use the existing mocking patterns;
  CI runs `pytest tests/` on Python 3.10–3.12.
- **No investment-advice framing.** Keep outputs clearly labeled as research.

## Pull requests

1. Fork and branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. Keep changes focused; update/add tests for behavior changes.
3. Run `pytest tests/ -q` locally before pushing.
4. Open a PR using the template; describe the change and link any issue.

## Reporting bugs / requesting features

Use the GitHub issue templates (Bug report / Feature request). For security
issues, **do not** open a public issue — see [SECURITY.md](SECURITY.md).
