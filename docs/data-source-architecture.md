# Data Source Architecture

## Purpose
This document records the intended data-source design for the Korea-focused workflow so future changes do not drift back toward an unclear fallback-heavy model.

## Core Principle
- News uses multiple sources on purpose and gets merged.
- Price, fundamentals, indicators, disclosures, and macro each use one primary source.
- Silent cross-domain fallback should be avoided when it changes the meaning of the data.

## Intended Source Map
- Market price / OHLCV: `KIS`
- Technical indicators: `KIS`
- Fundamentals / statements: `KIS`
- Disclosures / event-style filings: `DART`
- Korea macro summary: `ECOS`
- Company news: `Naver` as the domestic primary source
- Supplemental outside view on Korean equities: `yfinance` news

## Why News Is Different
Korean-equity news is intentionally multi-perspective:
- `Naver` captures domestic media coverage, local keywords, and Korea-market framing.
- `yfinance` can still return news for Korean tickers such as `005930.KS`, `000660.KS`, and `035420.KS`.
- The `yfinance` side is useful as an external or overseas-market lens rather than as a replacement for domestic news.

Because of that, the main news flow should aggregate both sources instead of forcing a single winner.

## Current Code Path
- Main news analyst path: [prefetch.py](../tradingagents/dataflows/prefetch.py)
  - `prefetch_news_data()` uses the configured multi-source news vendor set and merges results.
  - `prefetch_social_data()` now follows the same company-news merge model.
- Vendor registry: [interface.py](../tradingagents/dataflows/interface.py)
  - `get_news` currently includes `naver`, `alpha_vantage`, and `yfinance`
  - `get_global_news` currently includes `naver`, `yfinance`, and `alpha_vantage`
- Domestic news source implementation: [naver_news.py](../tradingagents/dataflows/naver_news.py)
- Supplemental/global news source implementation: [yfinance_news.py](../tradingagents/dataflows/yfinance_news.py)

## Important Clarification
The code now distinguishes two news concepts in [default_config.py](../tradingagents/default_config.py):
- `data_vendors.news_data`
  - ordered direct-route behavior for `route_to_vendor("get_news", ...)`
  - currently `naver,yfinance`
- `multi_source_vendors`
  - explicit merged source sets used by `prefetch_news_data()` and `prefetch_social_data()`
  - currently `get_news -> naver,yfinance`
  - currently `get_global_news -> naver,yfinance`

This makes merged-news behavior explicit instead of relying on implicit fallback language.

## Routing Semantics
- Structured data methods use explicit configured primary sources.
- `route_to_vendor()` no longer appends every remaining vendor automatically.
- If multiple vendors are configured for a direct route, that is treated as an opt-in fallback order.
- Event/disclosure-style `get_insider_transactions` currently uses a tool-level override to prefer `dart`.

## Instrument Normalization
- Korean company names, stock codes, corp codes, and exchange-qualified symbols are now normalized through [korea_ticker.py](../tradingagents/dataflows/korea_ticker.py).
- The canonical profile separates identifiers by use:
  - `stock_code` for `KIS`
  - `corp_code` for `DART`
  - `news_query` for domestic-news search such as `Naver`
  - `yfinance_symbol` / candidate symbols for `yfinance`
- This avoids forcing a single ticker string to mean the same thing across every vendor.

## Recommended Design Direction
### Keep
- Multi-source merged news collection
- Single primary source for each structured data category

### Avoid
- General-purpose fallback chains that silently swap `KIS` market data for another provider
- Hidden substitution between domestic and foreign news sources

## Practical Interpretation
- If `Naver` is unavailable, the news layer may still surface `yfinance` results, but that should be understood as degraded coverage, not equivalent replacement.
- If `KIS` is unavailable for price/fundamentals/indicators, the system should usually surface that failure clearly instead of silently shifting to a different data interpretation.

## Cleanup Tasks
1. Keep docs and config comments aligned with the merged-news model.
2. Review direct `route_to_vendor()` news callers and decide whether they should also become merge-based.
3. Re-evaluate whether `alpha_vantage` still belongs in the Korea-default news/vendor registry.
4. Decide whether `get_insider_transactions` should stay as a tool-level override or be moved into its own disclosure/event category.
5. Reduce or remove fallback language in docs where the real behavior is explicit multi-source aggregation.
