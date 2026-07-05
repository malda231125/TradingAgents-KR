# 🔑 API Keys and Setup Links

English · [한국어](api-keys.ko.md)

TradingAgents Korea can run with partial credentials, but the intended Korean-equity workflow works best when the following data APIs are configured.

> Keep real credentials in `.env` only. Do not commit API keys, tokens, account identifiers, private URLs, or token cache files.

## Recommended for Korean equity research

### KIS / Korea Investment Open API

Purpose:

- Korean stock prices / OHLCV
- technical indicators
- structured market and fundamental data

Environment variables:

```bash
KIS_APP_KEY=
KIS_APP_SECRET=
```

Official links:

- KIS Developers portal: <https://apiportal.koreainvestment.com/>
- API service page: <https://apiportal.koreainvestment.com/apiservice-apiservice>
- Official sample repository: <https://github.com/koreainvestment/open-trading-api>

Notes:

- A Korea Investment & Securities account may be required.
- Public examples should stay read-only and avoid account/order flows.
- Do not commit account numbers, live-trading credentials, or token cache files.

### Naver Developers / Search API

Purpose:

- Korean domestic news through Naver Search / News APIs

Environment variables:

```bash
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

Official links:

- Naver Developers: <https://developers.naver.com/main/>
- News Search API docs: <https://developers.naver.com/docs/serviceapi/search/news/news.md>
- Application registration: <https://developers.naver.com/apps/#/register>

Notes:

- Register an application and enable Search API access.
- Respect Naver API rate limits and terms.

## Strongly recommended

### OpenDART / Financial Supervisory Service

Purpose:

- disclosures
- corporate identifiers
- event/disclosure context

Environment variable:

```bash
DART_API_KEY=
```

Official links:

- OpenDART: <https://opendart.fss.or.kr/>
- API guide: <https://opendart.fss.or.kr/guide/main.do>
- API key page: <https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do>

### ECOS / Bank of Korea Economic Statistics System

Purpose:

- Korean rates, FX, macro environment and economic-statistics context

Environment variable:

```bash
ECOS_API_KEY=
```

Official link:

- ECOS Open API: <https://ecos.bok.or.kr/api/>

## Optional global context

### FRED

Purpose:

- supplemental global macro indicators

Environment variable:

```bash
FRED_API_KEY=
```

Official link:

- FRED API key: <https://fred.stlouisfed.org/docs/api/api_key.html>

### SEC EDGAR

SEC EDGAR does not require an API key, but automated requests should use an identifying User-Agent.

```bash
SEC_USER_AGENT="TradingAgentsKorea/0.1 contact@example.com"
```

Official link:

- SEC EDGAR access guide: <https://www.sec.gov/os/accessing-edgar-data>

## Optional integrations

### Notion export

Purpose:

- publish generated reports to a Notion page

Environment variables:

```bash
NOTION_API_TOKEN=
TRADINGAGENTS_NOTION_PAGE_ID=
```

Official link:

- Notion internal integrations: <https://developers.notion.com/guides/get-started/internal-connections>

### Telegram bot

Purpose:

- notifications / bot integration

Environment variable:

```bash
TELEGRAM_BOT_TOKEN=
```

Official links:

- BotFather: <https://t.me/BotFather>
- Telegram Bot API: <https://core.telegram.org/bots/api>

## Before committing

Do not include the following in a public repository:

- `.env`
- real API keys or tokens
- KIS account numbers or live-trading identifiers
- Notion private page URLs
- Telegram bot tokens or chat IDs
- token cache files such as `kis-token.json` or `*.token.json`

Related docs:

- [Configuration](configuration.md)
- [Public release guide](public-release-guide.md)
