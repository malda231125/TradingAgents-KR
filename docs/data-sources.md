# 📡 Data Sources

English · [한국어](data-sources.ko.md)

TradingAgents Korea uses different data sources for different meanings. This is intentional: Korean equity analysis should not silently swap a domestic source for a foreign source if that changes interpretation.

## Source map

| Category | Primary source | Purpose |
|---|---|---|
| Market price / OHLCV | KIS | Korean stock price and volume data |
| Technical indicators | KIS | Korea-market indicators |
| Fundamentals / base data | KIS | Structured financial and market data |
| Disclosures / events | DART | Corporate filings and event signals |
| Korea macro | ECOS | Macro context from Bank of Korea statistics |
| Domestic news | Naver News API | Korean-language market and company news |
| Supplemental outside news | yfinance | External/global framing for Korean equities |

## Why not use one universal fallback?

A missing KIS price response and a yfinance response are not always semantically equivalent. Silent fallback can make reports look confident while mixing different data definitions.

Preferred behavior:

- structured market data: use the configured primary source and surface failures clearly
- news: merge multiple sources intentionally because media framing is multi-perspective
- macro/disclosure: keep source-specific context explicit

## Required credentials

- KIS: market/fundamental data
- Naver: domestic news
- DART: disclosures
- ECOS: macro

See the [configuration guide](configuration.md) for details.

## Public examples

Public sample reports may cite data source categories, but they should not include private credentials or raw API responses.

Related docs:

- [API key guide](api-keys.md)
- [Architecture](architecture.md)
