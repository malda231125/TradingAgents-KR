# 🔑 API 키 발급 및 설정 링크

[English](api-keys.md) · 한국어

TradingAgents Korea는 일부 키가 없어도 실행할 수 있지만, 한국 주식 분석 워크플로우를 제대로 사용하려면 아래 데이터 API 설정을 권장합니다.

> 실제 키는 반드시 `.env`에만 저장하세요. API key, token, 계좌 식별자, 개인 URL은 커밋하면 안 됩니다.

## 🇰🇷 한국 주식 분석에 권장

### KIS / 한국투자증권 Open API

용도:

- 국내 주식 가격 / OHLCV
- 기술지표
- 구조화된 시장·재무 데이터

환경 변수:

```bash
KIS_APP_KEY=
KIS_APP_SECRET=
```

공식 링크:

- KIS Developers 포털: <https://apiportal.koreainvestment.com/>
- API 서비스 페이지: <https://apiportal.koreainvestment.com/apiservice-apiservice>
- 공식 샘플 저장소: <https://github.com/koreainvestment/open-trading-api>

주의사항:

- 한국투자증권 계좌가 필요할 수 있습니다.
- 공개 예시는 읽기 전용 데이터 흐름 위주로 구성하세요.
- 계좌번호, 실거래 credential, token cache 파일은 절대 커밋하지 마세요.

### Naver Developers / Search API

용도:

- 네이버 검색/뉴스 API 기반 국내 한국어 뉴스 수집

환경 변수:

```bash
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

공식 링크:

- Naver Developers: <https://developers.naver.com/main/>
- 뉴스 검색 API 문서: <https://developers.naver.com/docs/serviceapi/search/news/news.md>
- 애플리케이션 등록: <https://developers.naver.com/apps/#/register>

주의사항:

- 애플리케이션을 등록하고 Search API 권한을 활성화해야 합니다.
- Naver API 호출 제한과 이용약관을 지켜야 합니다.

## ✅ 강력 권장

### OpenDART / 금융감독원

용도:

- 공시
- 기업 고유번호
- 이벤트/공시 맥락

환경 변수:

```bash
DART_API_KEY=
```

공식 링크:

- OpenDART: <https://opendart.fss.or.kr/>
- API 가이드: <https://opendart.fss.or.kr/guide/main.do>
- API 키 발급: <https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do>

### ECOS / 한국은행 경제통계시스템

용도:

- 금리, 환율, 거시 환경 등 한국 매크로 맥락

환경 변수:

```bash
ECOS_API_KEY=
```

공식 링크:

- ECOS Open API: <https://ecos.bok.or.kr/api/>

## 🌐 선택 설정

### FRED

용도:

- 글로벌 매크로 보조 지표

환경 변수:

```bash
FRED_API_KEY=
```

공식 링크:

- FRED API key: <https://fred.stlouisfed.org/docs/api/api_key.html>

### SEC EDGAR

SEC EDGAR는 API key는 필요 없지만, 자동 요청에는 식별 가능한 User-Agent가 필요합니다.

```bash
SEC_USER_AGENT="TradingAgentsKorea/0.1 contact@example.com"
```

공식 링크:

- SEC EDGAR 접근 가이드: <https://www.sec.gov/os/accessing-edgar-data>

## 🗂️ 선택 연동

### Notion export

용도:

- 생성된 리포트를 Notion 페이지로 발행

환경 변수:

```bash
NOTION_API_TOKEN=
TRADINGAGENTS_NOTION_PAGE_ID=
```

공식 링크:

- Notion internal integrations: <https://developers.notion.com/guides/get-started/internal-connections>

### Telegram bot

용도:

- 알림/봇 연동

환경 변수:

```bash
TELEGRAM_BOT_TOKEN=
```

공식 링크:

- BotFather: <https://t.me/BotFather>
- Telegram Bot API: <https://core.telegram.org/bots/api>

## 🛡️ 커밋 전 확인

아래 항목은 공개 저장소에 포함하지 마세요.

- `.env`
- 실제 API key / token
- KIS 계좌번호 또는 실거래 식별자
- Notion private page URL
- Telegram bot token / chat ID
- token cache 파일(`kis-token.json`, `*.token.json` 등)

관련 문서:

- [설정 가이드](configuration.ko.md)
- [공개 배포 가이드](public-release-guide.ko.md)
