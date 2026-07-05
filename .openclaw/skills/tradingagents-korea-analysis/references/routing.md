# TradingAgents Korea/US Routing

Use the market wording and ticker/name to choose the skill before reading a repo or running analysis.

## Korea → tradingagents-korea-analysis

- 6-digit numeric ticker: `005930`, `000660`, `035420`
- Korean market words: 국내주식, 국내 주식, 한국 주식, 코스피, 코스닥, KRX
- Korean company names paired with domestic wording:
  - 삼성전자 국내 주식 분석해줘 → Korea
  - 하이닉스 국내주식 분석해줘 → Korea
  - SK하이닉스 한국 주식 분석해줘 → Korea
  - 현대차 국내 주식 분석해줘 → Korea
  - 네이버/카카오 국내주식 분석해줘 → Korea

## US/overseas → tradingagents-us-analysis

- English ticker: `AAPL`, `TSLA`, `NVDA`, `SPCX`, `SPY`, `QQQ`
- US market words: 미국 주식, 해외 주식, 해외주식, 나스닥, NASDAQ, NYSE, AMEX, ETF, US stock
- Korean names of overseas companies paired with overseas/US wording:
  - 애플 해외 주식 분석해줘 → US / AAPL
  - 애플 미국 주식 분석해줘 → US / AAPL
  - 구글 해외 주식 분석해줘 → US / GOOGL preferred unless user specifies GOOG
  - 알파벳 미국 주식 분석해줘 → US / GOOGL preferred unless user specifies GOOG
  - 테슬라 미국 주식 분석해줘 → US / TSLA
  - 엔비디아 해외주식 분석해줘 → US / NVDA
  - 마이크로소프트 미국 주식 분석해줘 → US / MSFT
  - 아마존 해외 주식 분석해줘 → US / AMZN
  - 메타 미국 주식 분석해줘 → US / META

## Ambiguous

Ask one concise clarification only when the market cannot be inferred.

Examples:

- “삼성전자 주식 분석” → Korea is likely, because it is a Korean listed company.
- “005930 분석” → Korea.
- “SPCX 주식 분석” → US.
- “AAPL 분석” → US.
- “애플 주식 분석” → likely US/AAPL, but if no overseas/US wording and there is any ambiguity, ask briefly.
- “구글 주식 분석” → likely US/GOOGL, but ask GOOG vs GOOGL only if share class matters.
- “주식 분석해줘” with no ticker/name → ask which ticker/market.
