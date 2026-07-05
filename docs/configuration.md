# ⚙️ Configuration

English · [한국어](configuration.ko.md)

TradingAgents Korea is configured primarily through environment variables.

Start from the example file:

```bash
cp .env.example .env
```

> Never commit `.env`.

## LLM runtime

Recommended public default:

```bash
TRADINGAGENTS_LLM_PROVIDER=codex-cli
TRADINGAGENTS_QUICK_MODEL=gpt-5.5
TRADINGAGENTS_DEEP_MODEL=gpt-5.5
TRADINGAGENTS_CLI_TIMEOUT=1800
```

Supported CLI providers depend on your local setup:

- `codex-cli`
- `claude-cli`

The CLI must already be installed and authenticated locally.

Run this preflight check to verify local CLI and env setup:

```bash
.venv/bin/tradingagents doctor
```

If both `codex` and `claude` are missing, install and log in to one runtime:

```bash
npm install -g @openai/codex
codex login
```

```bash
npm install -g @anthropic-ai/claude-code
claude
```

Node.js/npm is required. Login is interactive and owned by the user; do not put credentials in chat or logs.

## Data credentials

Official issuance links are collected in the [API key guide](api-keys.md).

### KIS

Used for Korean stock prices, OHLCV, indicators and structured market data.

```bash
KIS_APP_KEY=
KIS_APP_SECRET=
```

Keep account identifiers private. Public examples should not include real account values.

### Naver News API

Used for Korean domestic news coverage.

```bash
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

### DART

Used for disclosures, corporate identifiers and event-style signals.

```bash
DART_API_KEY=
```

### ECOS

Used for Korean macro context.

```bash
ECOS_API_KEY=
```

### Optional global context

```bash
FRED_API_KEY=
SEC_USER_AGENT="TradingAgentsKorea/0.1 contact@example.com"
```

SEC EDGAR does not require an API key, but automated access should use a clear User-Agent.

## Output paths

```bash
TRADINGAGENTS_RESULTS_DIR=./results
```

Local outputs such as `results/`, `reports/` and `notion_exports/` should usually stay out of public commits.

## Notion export

Only set these when using the Notion publishing helper.

```bash
NOTION_API_TOKEN=
TRADINGAGENTS_NOTION_PAGE_ID=
```

Do not include tokens or private page URLs in the public repository.

## Quick run checklist

1. Copy `.env.example` to `.env`
2. Install and authenticate Codex CLI
3. Fill KIS / Naver / DART / ECOS keys
4. Run `pip install -e .`
5. Run `tradingagents doctor` to check CLI and env gaps
6. Run `python main.py` or `python -m cli.main`

Related docs:

- [API key guide](api-keys.md)
- [Data sources](data-sources.md)
- [Public release guide](public-release-guide.md)
