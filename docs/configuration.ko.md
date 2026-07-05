# ⚙️ 설정 가이드

[English](configuration.md) · 한국어

TradingAgents Korea는 주로 환경 변수로 설정합니다.

먼저 예시 파일을 복사하세요.

```bash
cp .env.example .env
```

> `.env`는 절대 커밋하지 마세요.

## LLM runtime

공개 저장소 기준 권장 기본값은 Codex CLI입니다.

```bash
TRADINGAGENTS_LLM_PROVIDER=codex-cli
TRADINGAGENTS_QUICK_MODEL=gpt-5.5
TRADINGAGENTS_DEEP_MODEL=gpt-5.5
TRADINGAGENTS_CLI_TIMEOUT=1800
```

지원 가능한 CLI provider는 로컬 설치 상태에 따라 달라집니다.

- `codex-cli`
- `claude-cli`

CLI는 미리 설치되어 있고 로컬 인증이 완료되어 있어야 합니다.

설치/로그인 상태를 한 번에 확인하려면 다음을 실행하세요.

```bash
.venv/bin/tradingagents doctor
```

`codex`와 `claude`가 모두 없으면 아래 중 하나를 설치하고 로그인하세요.

```bash
npm install -g @openai/codex
codex login
```

```bash
npm install -g @anthropic-ai/claude-code
claude
```

Node.js/npm이 필요합니다. 로그인은 사용자 계정으로 직접 완료해야 하며, credential을 채팅이나 로그에 남기지 마세요.

## 데이터 credential

공식 발급 링크는 [API 키 발급 가이드](api-keys.ko.md)에 정리되어 있습니다.

### KIS

국내 주식 가격, OHLCV, 기술지표, 구조화 시장 데이터에 사용합니다.

```bash
KIS_APP_KEY=
KIS_APP_SECRET=
```

계좌 식별자는 private하게 관리하세요. 공개 예시에 실제 계좌값을 넣으면 안 됩니다.

### Naver News API

국내 한국어 뉴스 수집에 사용합니다.

```bash
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

### DART

공시, 기업 식별자, 이벤트성 신호에 사용합니다.

```bash
DART_API_KEY=
```

### ECOS

한국 매크로 맥락에 사용합니다.

```bash
ECOS_API_KEY=
```

### 선택 글로벌 맥락

```bash
FRED_API_KEY=
SEC_USER_AGENT="TradingAgentsKorea/0.1 contact@example.com"
```

SEC EDGAR는 API key가 필요 없지만, 자동 접근 시 명확한 User-Agent를 요구합니다.

## 출력 경로

```bash
TRADINGAGENTS_RESULTS_DIR=./results
```

`results/`, `reports/`, `notion_exports/` 같은 로컬 결과물은 공개 커밋에서 제외하는 것을 권장합니다.

## Notion export

Notion 발행 helper를 사용할 때만 설정합니다.

```bash
NOTION_API_TOKEN=
TRADINGAGENTS_NOTION_PAGE_ID=
```

토큰과 private page URL은 공개 저장소에 포함하지 마세요.

## 빠른 실행 체크리스트

1. `.env.example`을 `.env`로 복사
2. Codex CLI 설치 및 로그인 확인
3. KIS / Naver / DART / ECOS 키 입력
4. `pip install -e .` 실행
5. `tradingagents doctor`로 CLI와 env 누락 확인
6. `python main.py` 또는 `python -m cli.main` 실행

관련 문서:

- [API 키 발급 가이드](api-keys.ko.md)
- [데이터 소스](data-sources.ko.md)
- [공개 배포 가이드](public-release-guide.ko.md)
