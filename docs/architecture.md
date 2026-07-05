# 🏗️ Architecture

English · [한국어](architecture.ko.md)

TradingAgents Korea adapts the upstream TradingAgents multi-agent financial research workflow to Korean equities.

## High-level flow

```text
User request
  ↓
Ticker / company resolver
  ↓
Data prefetch
  - KIS
  - DART
  - ECOS
  - Naver News
  - yfinance
  ↓
Feature packets
  - Market packet
  - Fundamentals packet
  - News packet
  - Macro / disclosure context
  ↓
TradingAgents workflow
  - Market Analyst
  - News Analyst
  - Fundamentals Analyst
  - Bull / Bear Researchers
  - Trader
  - Risk Manager
  - Portfolio Manager
  ↓
Markdown / Notion report
```

## Design principles

### 1. Korean identifiers are source-specific

A single user input may map to several identifiers:

- company name: `삼성전자`
- stock code: `005930`
- DART corporation code
- yfinance symbol candidate: `005930.KS`
- Naver News query: company-name keyword

The resolver should keep these identities separate instead of forcing one ticker string everywhere.

### 2. Prefetch before LLM reasoning

Analyst nodes should receive compact, explicit data blocks before generating reports. This reduces hallucinated numbers and makes missing data visible.

### 3. News is multi-source by design

Domestic Korean news and global/yfinance coverage provide different perspectives. News data is intentionally merged rather than treated as a strict fallback.

### 4. Structured data should not silently change meaning

For price, fundamentals, indicators, disclosures and macro data, source semantics matter. When a primary source fails, the report should say so rather than quietly replacing it with an unrelated source.

## OpenClaw skill integration

The repository includes an OpenClaw helper skill under:

```text
.openclaw/skills/tradingagents-korea-analysis/
```

The skill documents Korea/overseas stock routing, long-running report execution, Codex CLI requirements and Notion export helpers.

Related docs:

- [Data sources](data-sources.md)
- [Configuration](configuration.md)
