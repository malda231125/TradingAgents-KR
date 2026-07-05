<a name="readme-top"></a>

<div align="center">

# TradingAgents Korea 🇰🇷

**It doesn't just analyze. It remembers, scores itself, and gets less wrong.**

A Korean-equity research agent that records its past calls, grades them hit/miss, and fixes its own reasoning next time — multi-agent debate on real KIS, DART, ECOS and Naver News data, running on your Claude Code / Codex subscription.

[![Self-improving loop](https://img.shields.io/badge/Self--improving-loop-ff6b6b.svg)](#-the-core-an-ai-research-self-improvement-loop)
[![CI](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml/badge.svg)](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)
[![TradingAgents](https://img.shields.io/badge/Based%20on-TradingAgents-14C290.svg)](https://github.com/TauricResearch/TradingAgents)
[![Korea Market](https://img.shields.io/badge/Market-KRX%20%7C%20KOSPI%20%7C%20KOSDAQ-red.svg)](#why-tradingagents-korea)

[English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [中文](README.zh.md)

[Quick Start](#quick-start) · [API Keys](#api-keys) · [Architecture](#architecture) · [Example Report](examples/reports/en/samsung-005930-2026-06-30.md)

</div>

---

> [!CAUTION]
> TradingAgents Korea is an open-source research and education project. It is not investment advice, a buy/sell recommendation system, or an automated trading system. All investment decisions remain the user's responsibility.

## What is this?

TradingAgents Korea is a Korea-market adaptation of [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents).

The original TradingAgents project introduced a multi-agent financial research workflow. This fork connects that idea to the Korean equity market by combining local data sources, Korean company identifiers, and report-first output.

- **KIS**: Korean stock prices, OHLCV, indicators and structured market data
- **DART**: disclosures, company identifiers and event context
- **ECOS**: Bank of Korea macroeconomic context
- **Naver News**: Korean-language domestic news
- **yfinance**: supplemental global/outside perspective
- **Claude Code / Codex CLI**: local subscription/login-based LLM execution path
- **Notion export**: optional helper flow for publishing generated reports

```text
"Analyze Samsung Electronics"
       ↓
005930 / DART corp code / Naver query / yfinance symbol resolution
       ↓
KIS + DART + ECOS + Naver News data prefetch
       ↓
Market / news / fundamentals / macro feature packets
       ↓
TradingAgents multi-agent debate and risk review
       ↓
Markdown / Notion research report
```

> ⏱️ **A full report can take 15+ minutes on average** (with GPT-5.5 or Claude Opus 4.8 at max reasoning). That's expected — this is a deep research framework, not a quick summarizer. **A long run does not mean something is broken.**

## ❓ Why not just ask ChatGPT "how's Samsung looking?"

The worst thing about AI stock analysis is that it **writes a plausible-looking report and stops there.**

It analyzes "Samsung looks good" today, and tomorrow it doesn't even remember that call. Nobody checks whether it was right or wrong, and the next analysis starts from a blank page again.

So we built this. **The core of TradingAgents Korea is not one-off AI stock analysis.**

> **Analyze daily → record the prediction → verify the next day → reflect when wrong → feed it back into the next analysis**

This **AI research self-improvement loop** is the point.

| Just asking an AI | TradingAgents Korea |
|---|---|
| Starts blank every time, no memory of past calls | Records each call and **reflects** on it on the next run |
| Nobody ever scores it | Grades itself **hit / miss / partial** |
| One fence-sitting answer ("there are risks, be careful") | Market · news · fundamentals · bull/bear · risk **multi-agent debate** |
| Plausible fake numbers (hallucination) | **Feature packets** pin down the evidence first |

## 🔄 The core: an AI research self-improvement loop

Most AI analysis tools stop at "analyze → report." TradingAgents Korea closes the loop after that.

```text
Analyze daily
   ↓
Record prediction     decisions/YYYY-MM-DD/<ticker>.json      ← structured decision record
   ↓
Verify next day       compare the prior thesis against the evidence packet
   ↓
Reflect when wrong    retrospectives/YYYY-MM-DD/<ticker>.md   → hit / miss / partial / uncertain
   ↓
Feed back forward     lessons/<ticker>.jsonl                  → injected into the next run's prompt
```

The interactive CLI drives this loop **automatically**: every run finds the latest prior decision for the ticker, runs the retrospective, injects its lessons into the next analysis, then saves a fresh decision record (the retrospective is skipped on the first run).

```bash
# Run the self-improvement loop on its own
.venv/bin/python scripts/run_self_loop.py --ticker 005930 --date YYYY-MM-DD
```

The retrospective verdict (`hit` / `miss` / `partial` / `uncertain`) is decided by the subscription CLI LLM reviewing a deterministic evidence packet by default; use `--no-ai-review` for the deterministic fallback only. On long batch runs, prompt context uses a compact `lessons/<ticker>.summary.md` plus the most recent lessons so accumulated lessons never flood the prompt.

> We don't brag about returns. Instead, we **publish the record of the AI grading its own past calls.**

## Why TradingAgents Korea?

There are many US/global-stock AI finance agents, but Korean equity research has a different data and interpretation stack.

| Challenge | TradingAgents Korea approach |
|---|---|
| Korean stocks may be referenced as `005930`, `삼성전자`, or `005930.KS` | Resolve and keep source-specific identifiers separately |
| Yahoo Finance alone can be insufficient for Korean market data | Use KIS as the structured Korean market data layer |
| Korean disclosures should be read through DART | Keep DART disclosure/event context as its own layer |
| Korea macro context depends on BOK/ECOS data | Add ECOS-based rates, FX and macro context |
| LLMs can hallucinate plausible-looking numbers | Build explicit feature packets before reasoning |
| Premium multi-agent reports can become expensive with metered LLM APIs | Run heavy report generation through Claude Code / Codex CLI subscription runtimes |
| Local investors need Korean-language reports, while global developers need multilingual docs | English, Korean, Japanese and Chinese README docs with multilingual report support |

## Highlights

- 🇰🇷 **Korean equities first** — handles inputs such as `005930`, `000660`, `삼성전자`, `SK하이닉스`
- 🧩 **Multi-agent research workflow** — market, news, fundamentals, bull/bear, trader, risk and portfolio manager roles
- 📡 **Korea data stack** — KIS, DART, ECOS and Naver News as first-class sources
- 🧠 **CLI-first LLM execution** — run long workflows through Claude Code / Codex CLI instead of pushing every agent step through metered API calls
- 🧾 **Premium report-first output** — generates long-form Markdown research reports, with Korean report output supported
- 🗂️ **Notion export helper** — optional OpenClaw-based publishing flow
- 🛡️ **Public-release safety docs** — checklists for avoiding API key, `.env`, Notion token and local-path leaks

## Why CLI-first?

Premium multi-agent research is token-heavy.

A full TradingAgents Korea run can include market analysis, news analysis, fundamentals, bull/bear debate, trading plan, risk review, portfolio judgment and a long-form Markdown report. Running that whole workflow through metered LLM APIs can become expensive quickly.

TradingAgents Korea is designed around Claude Code and Codex CLI runtimes, so the heavy reasoning path can use the user's existing local CLI subscription/login environment instead of requiring per-token API billing for every agent step.

This does not remove the need for data credentials such as KIS, Naver, DART and ECOS. It also remains subject to each CLI provider's subscription terms and usage limits. The point is practical: make deep, premium research reports viable for repeated personal use.

## Positioning

This repository is not just a data connector or an MCP tool server.

It is intended as a **multi-agent research framework for Korean equities**:

- Data libraries such as FinanceDataReader are useful building blocks.
- MCP servers are useful for exposing tools to Claude/Cursor.
- TradingAgents Korea aims to orchestrate the end-to-end research process: data prefetch → analyst roles → debate → risk review → final report.

In short:

> Premium Korean equity research, optimized for Claude Code and Codex CLI rather than short API-metered demos.

## Quick Start

You do not need to memorize the installation commands.

Non-developers can let Claude Code or Codex do the setup.

Clone the repository:

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
```

Then ask Claude Code or Codex:

```text
Read llm.txt and install this project on my machine. Set up the Python virtual environment, install dependencies, create .env, and verify that it runs.
```

Detailed setup instructions live in [llm.txt](llm.txt). It is written for AI agents and includes the Python version, virtual environment, dependency installation, environment variables, and verification steps.

After installation, ask for the report you want:

```text
Analyze Samsung Electronics Korean stock.
Analyze 005930.
Generate a Korean equity research report for SK hynix.
```

TradingAgents Korea is not a short daily-summary tool. It is built for premium long-form research reports, so a full run can take a while depending on the ticker and data availability.

### Manual install (without an agent)

If you do not use Claude Code / Codex, you can install it yourself.

**macOS / Linux / WSL**

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
cp .env.example .env          # then edit .env and add your API keys
.venv/bin/python main.py 005930
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
copy .env.example .env         # then edit .env and add your API keys
.venv\Scripts\python main.py 005930
```

> On Debian/Ubuntu, if `python3 -m venv` fails with `ensurepip is not available`,
> run `sudo apt install -y python3-venv` and retry.

The default LLM runtime is Codex CLI. If you use Claude Code instead, switch the runtime block in `.env`:

```bash
TRADINGAGENTS_LLM_PROVIDER=claude-cli
TRADINGAGENTS_QUICK_MODEL=sonnet
TRADINGAGENTS_DEEP_MODEL=opus
```

After installation, run the preflight check:

```bash
.venv/bin/tradingagents doctor
```

The command never prints real API key values. It only checks whether:

- `codex` or `claude` CLI is installed
- recommended KIS / Naver / DART / ECOS keys are filled in `.env`
- missing items point back to the README and issuance links

If neither CLI is installed, install and log in to one runtime:

```bash
npm install -g @openai/codex
codex login
```

```bash
npm install -g @anthropic-ai/claude-code
claude
```

CLI installation requires Node.js/npm. Account login is interactive and user-owned; do not paste passwords or tokens into chat.

## What You Need

Let Claude Code or Codex handle the installation. You mainly need to prepare:

- **Claude Code or Codex CLI**: authenticated subscription-based CLI runtime
- **KIS API key**: Korean prices, OHLCV, indicators, fundamentals and market data
- **Naver Developers key**: Korean domestic news search
- **DART API key**: disclosures, corporate identifiers and event context
- **ECOS API key**: Bank of Korea macro data

Put the keys into `.env` once. Issuance links are listed in the [API Keys](#api-keys) section.

See also:

- [AI agent installation guide](llm.txt)
- [`.env.example`](.env.example)
- [Configuration guide](docs/configuration.md)
- [API key guide](docs/api-keys.md)
- [Korean README](README.ko.md)
- [Chinese README](README.zh.md)

## API Keys

| Key | Used for | Required? | Get it |
|---|---|---:|---|
| `KIS_APP_KEY`, `KIS_APP_SECRET` | Korean price/OHLCV/indicator/market data | Recommended | [KIS Developers](https://apiportal.koreainvestment.com/) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | Korean domestic news search | Recommended | [Naver Developers](https://developers.naver.com/apps/#/register) |
| `DART_API_KEY` | Disclosures, company identifiers, event context | Recommended | [OpenDART](https://opendart.fss.or.kr/) |
| `ECOS_API_KEY` | Korean macroeconomic statistics | Recommended | [ECOS Open API](https://ecos.bok.or.kr/api/) |
| `FRED_API_KEY` | Supplemental global macro indicators | Optional | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `SEC_USER_AGENT` | Identifier for SEC EDGAR access | Optional | [SEC guide](https://www.sec.gov/os/accessing-edgar-data) |
| `NOTION_API_TOKEN` | Notion report export | Optional | [Notion integrations](https://developers.notion.com/guides/get-started/internal-connections) |
| `TELEGRAM_BOT_TOKEN` | Notifications / bot integration | Optional | [BotFather](https://t.me/BotFather) |

For setup details and safety notes, see [docs/api-keys.md](docs/api-keys.md).

## Usage examples

Supported Korean equity inputs:

```text
005930
Samsung Electronics
삼성전자
000660
SK hynix
SK하이닉스
```

Example requests:

```text
Analyze Samsung Electronics Korean stock
삼성전자 국내 주식 분석해줘
Analyze 005930
```

OpenClaw / Notion helper:

```bash
python .openclaw/skills/tradingagents-korea-analysis/scripts/run_analysis_to_notion.py \
  --ticker 005930 \
  --date YYYY-MM-DD \
  --timeout 7200
```

> US/overseas stocks such as `AAPL`, `SPCX`, or “Apple overseas stock” should use a separate US/overseas workflow.

## Architecture

```text
User request
  ↓
Ticker / company resolver
  ↓
Data prefetch
  ├─ KIS
  ├─ DART
  ├─ ECOS
  ├─ Naver News
  └─ yfinance
  ↓
Feature packets
  ├─ Market packet
  ├─ Fundamentals packet
  ├─ News packet
  └─ Macro / disclosure context
  ↓
TradingAgents workflow
  ├─ Market Analyst
  ├─ News Analyst
  ├─ Fundamentals Analyst
  ├─ Bull / Bear Researchers
  ├─ Trader
  ├─ Risk Manager
  └─ Portfolio Manager
  ↓
Markdown / Notion report
```

<p align="center">
  <img src="assets/schema.png" alt="TradingAgents framework schema" width="90%">
</p>

More details:

- [Architecture](docs/architecture.md)
- [Data sources](docs/data-sources.md)
- [Data source architecture](docs/data-source-architecture.md)

## How this differs from upstream TradingAgents

| Area | Upstream TradingAgents | TradingAgents Korea |
|---|---|---|
| Market focus | Global/US-oriented ticker workflow | Korean equities first |
| Primary market data | General market data providers | KIS-centered Korean market data |
| Disclosure context | Generic company/news context | DART disclosure and event context |
| Macro context | Global macro/news | ECOS/BOK Korea macro layer |
| News | Global/social/news sources | Naver News + supplemental yfinance |
| Language | Mostly English workflows | English/Korean/Japanese/Chinese docs + multilingual report output |
| LLM execution | API-provider oriented | Claude Code / Codex CLI subscription-runtime first |
| Output | CLI/package results | Long-form premium Markdown + optional Notion export |

## Example reports

Sanitized public example reports are available here:

- [Samsung Electronics 005930 report — 2026-06-30](examples/reports/en/samsung-005930-2026-06-30.md)
- [SK hynix 000660 report — 2026-06-30](examples/reports/en/sk-hynix-000660-2026-06-30.md)
- [Older Samsung Electronics 005930 demo report](examples/reports/samsung-005930-demo.md)

Example report sections:

- Market and technical context
- News and sentiment context
- Fundamentals and disclosure context
- Macro environment
- Bull case / bear case
- Trader plan
- Risk review
- Portfolio manager final decision

## Repository map

```text
TradingAgents-KR/
├── tradingagents/          # Core agents, graph, dataflows
├── cli/                    # Interactive CLI
├── docs/                   # Public docs and design notes
├── examples/reports/       # Localized sanitized sample reports
├── .openclaw/skills/       # OpenClaw helper skill
├── main.py                 # Root entry point
├── llm.txt                 # Detailed setup guide for AI agents
├── .env.example            # Safe env template
├── README.md               # English-first README
├── README.ko.md            # Korean README
└── README.zh.md            # Simplified Chinese README
```

## Public release safety

Before making this repository public, review:

- [Security public release checklist](SECURITY_PUBLIC_RELEASE_CHECKLIST.md)
- [Public release guide](docs/public-release-guide.md)

Never commit:

- `.env`
- API keys or tokens
- KIS account identifiers
- Notion tokens or private page URLs
- Telegram bot tokens
- private report exports
- personal local paths

## Roadmap

- [ ] KRX sector rotation packet
- [ ] DART XBRL TTM fundamentals
- [ ] ECOS macro regime model
- [ ] KIS realtime market snapshot
- [ ] Backtesting / evaluation harness
- [ ] MCP server mode
- [ ] Web dashboard
- [ ] English report mode

## Credits

This project is based on the original TradingAgents framework:

- Upstream: <https://github.com/TauricResearch/TradingAgents>
- Upstream paper: <https://arxiv.org/abs/2412.20138>

Korea-market integrations and workflow changes are maintained in this fork.

See [CREDITS.md](CREDITS.md) and [NOTICE.md](NOTICE.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

<div align="center">

If this project helps your Korean equity research workflow, a star is appreciated ⭐

[Back to top](#readme-top)

</div>
