<a name="readme-top"></a>

<div align="center">

# TradingAgents Korea 🇰🇷

**그냥 분석하고 끝나지 않습니다. 기억하고, 스스로 채점하고, 덜 틀려집니다.**

지난 판단을 기록하고 hit/miss로 **스스로 채점해** 다음 판단을 고치는 한국 주식 리서치 에이전트.
KIS(한국투자증권) · DART(공시) · ECOS(한국은행) · 네이버 뉴스 **실데이터** 위에서 멀티에이전트가 토론하고,
Claude Code / Codex 구독형 CLI로 돌아갑니다.

[![Self-improving loop](https://img.shields.io/badge/Self--improving-loop-ff6b6b.svg)](#-핵심-차별점-ai-리서치-자가개선-루프)
[![CI](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml/badge.svg)](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)
[![TradingAgents](https://img.shields.io/badge/Based%20on-TradingAgents-14C290.svg)](https://github.com/TauricResearch/TradingAgents)
[![Korea Market](https://img.shields.io/badge/Market-KRX%20%7C%20KOSPI%20%7C%20KOSDAQ-red.svg)](#-왜-tradingagents-korea인가요)

[English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [中文](README.zh.md)

[빠른 시작](#-빠른-시작) · [API 키](#-api-키) · [아키텍처](#-아키텍처) · [예시 리포트](examples/reports/ko/samsung-005930-2026-06-30.md) · [문서](docs/)

</div>

---

> [!CAUTION]
> TradingAgents Korea는 연구·교육·개인 리서치 보조 목적의 오픈소스 프로젝트입니다. 투자 조언, 매수/매도 추천, 자동매매 시스템이 아닙니다. 모든 투자 판단과 책임은 사용자에게 있습니다.

## 🔎 프로젝트 소개

TradingAgents Korea는 원본 [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents)를 **한국 주식 시장에 맞게 확장한 fork**입니다.

원본 TradingAgents가 멀티에이전트 금융 분석 프레임워크라면, 이 프로젝트는 그 구조를 한국 시장에 맞춰 다음 데이터와 실행 방식을 연결합니다.

- **KIS**: 국내 가격, OHLCV, 기술지표, 재무/시장 데이터
- **DART**: 공시, 기업 식별자, 이벤트성 신호
- **ECOS**: 한국은행 경제통계 기반 매크로 맥락
- **Naver News**: 한국어 국내 뉴스
- **yfinance**: 보조적인 글로벌/외부 시각
- **Claude Code / Codex CLI**: 직접 LLM API key를 넣는 대신 로컬 구독/로그인 기반 CLI로 실행
- **Notion export**: 생성된 리포트를 Notion으로 발행하는 선택형 helper

```text
삼성전자 분석해줘
       ↓
005930 / DART corp code / Naver query / yfinance symbol 정규화
       ↓
KIS + DART + ECOS + Naver News 데이터 수집
       ↓
시장·뉴스·재무·거시 feature packet 구성
       ↓
TradingAgents 멀티에이전트 토론 / 리스크 검토
       ↓
한국어 Markdown / Notion 리포트
```

> ⏱️ **보고서 한 편은 평균 15분 이상 걸릴 수 있습니다** (GPT-5.5 또는 Claude Opus 4.8 최대 추론 기준). 정상입니다 — 짧은 요약 도구가 아니라 깊은 리서치 프레임워크라서 그렇습니다. **오래 걸린다고 문제가 생긴 게 아닙니다.**

## ❓ 왜 그냥 ChatGPT한테 "삼성전자 어때?"라고 안 묻나요?

AI 주식 분석에서 제일 별로인 건, **그럴듯한 리포트 한 장 쓰고 끝나는 것**이라고 봤습니다.

오늘 "삼성전자 좋아 보인다"고 분석해 놓고, 내일이 되면 그 판단을 기억조차 못 합니다. 맞았는지 틀렸는지 아무도 채점하지 않고, 다음 분석은 또 백지에서 시작합니다.

그래서 만들었습니다. **TradingAgents Korea의 핵심은 단순 AI 종목 분석이 아닙니다.**

> **매일 분석 → 예측 기록 → 다음 날 검증 → 틀리면 회고 → 다음 분석에 반영**

이 **AI 리서치 자가개선 루프**가 핵심입니다.

| 그냥 AI에게 물어보면 | TradingAgents Korea |
|---|---|
| 매번 백지에서 시작, 지난 판단을 기억 못 함 | 지난 판단을 기록하고 다음 실행에서 **회고** |
| 맞았는지 아무도 채점 안 함 | **hit / miss / partial**로 스스로 채점 |
| 한 번의 양비론("리스크가 있으니 신중히") | 시장·뉴스·재무·Bull/Bear·리스크 **멀티에이전트 토론** |
| 그럴듯한 가짜 숫자(환각) | **feature packet**으로 근거 데이터를 먼저 고정 |

## 🔄 핵심 차별점: AI 리서치 자가개선 루프

대부분의 AI 분석 도구는 "분석 → 리포트"에서 멈춥니다. TradingAgents Korea는 그 뒤를 닫습니다.

```text
매일 분석
   ↓
예측 기록        decisions/YYYY-MM-DD/<ticker>.json     ← 구조화된 판단 기록
   ↓
다음 날 검증      이전 thesis를 증거 패킷과 대조
   ↓
틀리면 회고       retrospectives/YYYY-MM-DD/<ticker>.md  → hit / miss / partial / uncertain
   ↓
다음 분석에 반영   lessons/<ticker>.jsonl                 → 다음 실행 프롬프트에 주입
```

대화형 CLI는 이 루프를 **자동으로** 돕니다. 매 실행마다 해당 종목의 가장 최근 판단 기록을 찾아 회고를 돌리고, 그 교훈을 다음 분석에 주입한 뒤, 새 판단 기록을 저장합니다 (첫 실행에는 회고를 건너뜁니다).

```bash
# 자가개선 루프 단독 실행
.venv/bin/python scripts/run_self_loop.py --ticker 005930 --date YYYY-MM-DD
```

회고 판정(`hit` / `miss` / `partial` / `uncertain`)은 기본적으로 구독형 CLI LLM이 결정론적 증거 패킷을 검토해 내립니다. `--no-ai-review`로 결정론적 폴백만 돌릴 수도 있습니다. 장기 배치 실행에서는 누적 교훈이 프롬프트를 넘치게 하지 않도록 `lessons/<ticker>.summary.md` 요약본 + 최근 교훈만 컨텍스트로 사용합니다.

> 우리는 수익률을 자랑하지 않습니다. 대신 **AI가 자기 과거 판단을 채점한 기록을 공개**합니다.

## 🇰🇷 왜 TradingAgents Korea인가요?

미국 주식 중심의 금융 agent는 많지만, 한국 주식 분석은 데이터 소스와 해석 방식이 다릅니다.

| 문제 | TradingAgents Korea의 접근 |
|---|---|
| 한국 종목은 `005930`, `삼성전자`, `005930.KS`처럼 식별자가 나뉨 | 입력을 한국 종목코드/회사명/보조 심볼로 분리해 처리 |
| 가격·재무 데이터는 Yahoo Finance만으로 부족할 수 있음 | KIS를 구조화 market data의 중심으로 사용 |
| 국내 공시는 DART 기준으로 봐야 함 | DART 이벤트/공시 맥락을 별도 데이터 계층으로 분리 |
| 한국 매크로는 BOK/ECOS 맥락이 중요 | ECOS 기반 금리·환율·거시 환경 연결 |
| LLM이 숫자를 그럴듯하게 지어낼 위험 | 사전 수집 데이터와 feature packet으로 근거 데이터를 먼저 구성 |
| 프리미엄 멀티에이전트 리포트는 API 종량 과금으로 돌리기 부담스러움 | Claude Code / Codex CLI 구독형 runtime으로 장시간 리포트 생성 |
| 영어권 리포트는 국내 투자자에게 읽기 불편하고, 글로벌 사용자는 다국어 문서가 필요함 | 영어/한국어/중국어 README와 한국어 장문 리포트 지원 |

## ✨ 주요 특징

- 🇰🇷 **한국 주식 우선** — `005930`, `000660`, `삼성전자`, `SK하이닉스` 같은 국내 입력에 맞춤
- 🧩 **멀티에이전트 리서치 흐름** — 시장, 뉴스, 재무, 상승/하락 논리, 트레이더, 리스크, 포트폴리오 매니저 역할 분리
- 📡 **한국 데이터 스택** — KIS, DART, ECOS, Naver News 중심
- 🧠 **CLI-first LLM 실행** — 모든 agent 단계를 API 종량 과금으로 보내지 않고 Claude Code / Codex CLI 기반으로 실행
- 🧾 **프리미엄 리포트 중심 출력** — 사람이 읽기 좋은 한국어 장문 Markdown 리포트 생성
- 🗂️ **Notion 발행 helper** — OpenClaw skill 기반 Notion 발행 흐름 포함
- 🛡️ **공개 배포 보안 문서** — API key, `.env`, Notion token 노출 방지 체크리스트 포함

## 🧠 왜 CLI-first인가요?

프리미엄 멀티에이전트 리서치는 토큰 사용량이 큽니다.

TradingAgents Korea의 한 번의 전체 실행은 시장 분석, 뉴스 분석, 재무 분석, 상승/하락 논리, 트레이딩 플랜, 리스크 검토, 포트폴리오 매니저 판단, 장문 Markdown 리포트 생성을 포함할 수 있습니다. 이 전체 흐름을 LLM API 종량 과금으로만 돌리면 비용이 빠르게 커질 수 있습니다.

TradingAgents Korea는 Claude Code와 Codex CLI runtime을 중심으로 설계되어, 무거운 추론 경로를 사용자의 로컬 CLI 구독/로그인 환경에서 실행할 수 있습니다. 즉, 모든 agent 호출을 매번 per-token API 비용으로 처리하는 구조가 아니라, 이미 사용하는 CLI 실행 환경을 활용해 반복적인 프리미엄 리포트 생성을 현실적으로 만듭니다.

KIS, Naver, DART, ECOS 같은 데이터 API 설정은 여전히 필요합니다. 또한 CLI 사용은 각 provider의 구독 조건과 사용량 제한을 따릅니다. 핵심은 단순 자동 요약이 아니라, 장시간 실행되는 깊은 리서치 리포트를 개인 사용자가 감당 가능한 방식으로 만드는 것입니다.

## 🚀 빠른 시작

설치 명령어를 외울 필요 없습니다.

개발자가 아니어도 괜찮습니다. Claude Code나 Codex에게 설치를 맡기면 됩니다.

Claude Code나 Codex를 쓰고 있다면, 저장소를 받은 뒤 아래 한 줄만 요청하세요.

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
```

그리고 Claude Code 또는 Codex에게 이렇게 말하면 됩니다.

```text
llm.txt를 읽고 이 프로젝트를 내 컴퓨터에 설치해줘.
```

설치 세부 절차는 [llm.txt](llm.txt)에 AI 에이전트용으로 정리해두었습니다. Python 버전, 가상환경, 의존성 설치, 환경 변수, 실행 확인까지 에이전트가 그대로 따라 할 수 있게 작성되어 있습니다.

설치 후에는 이렇게 요청하면 됩니다.

```text
삼성전자 분석해줘
하이닉스 국내주식 분석해줘
005930 리포트 뽑아줘
```

TradingAgents Korea는 짧은 자동 요약 도구가 아니라 프리미엄 리서치 보고서 생성 프레임워크입니다. 종목과 데이터 상태에 따라 실행 시간이 길어질 수 있고, 깊은 보고서를 뽑는 쪽에 맞춰 설계되어 있습니다.

### 🔧 수동 설치 (에이전트 없이 직접)

Claude Code / Codex가 없다면 아래 순서대로 직접 설치할 수 있습니다.

**macOS / Linux / WSL**

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
cp .env.example .env          # 그런 다음 .env 에 API 키 입력
.venv/bin/python main.py 005930
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
copy .env.example .env         # 그런 다음 .env 에 API 키 입력
.venv\Scripts\python main.py 005930
```

> 우분투/데비안에서 `python3 -m venv` 가 `ensurepip is not available` 로 실패하면
> `sudo apt install -y python3-venv` 후 다시 시도하세요.

LLM 런타임 기본값은 Codex CLI입니다. **Claude Code**를 쓰면 `.env` 의 런타임 블록을 아래로 바꾸세요.

```bash
TRADINGAGENTS_LLM_PROVIDER=claude-cli
TRADINGAGENTS_QUICK_MODEL=sonnet
TRADINGAGENTS_DEEP_MODEL=opus
```

설치 후에는 프리플라이트 체크를 먼저 돌려보세요.

```bash
.venv/bin/tradingagents doctor
```

이 명령은 실제 API key 값을 출력하지 않고, 다음만 확인합니다.

- `codex` 또는 `claude` CLI가 설치되어 있는지
- KIS / Naver / DART / ECOS 권장 키가 `.env`에 채워져 있는지
- 빠진 항목이 있으면 README와 발급 링크를 어디서 보면 되는지

둘 다 설치되어 있지 않으면 아래 중 하나를 설치하고 로그인하세요.

```bash
npm install -g @openai/codex
codex login
```

```bash
npm install -g @anthropic-ai/claude-code
claude
```

CLI 설치에는 Node.js/npm이 필요합니다. 계정 로그인은 사용자 본인이 직접 완료해야 하며, 비밀번호나 token을 채팅에 붙여넣지 마세요.

## ⚙️ 준비물

설치 자체는 Claude Code나 Codex에게 맡기면 됩니다. 사용자가 준비할 것은 아래 정도입니다.

- **Claude Code 또는 Codex CLI**: 로그인된 구독형 CLI runtime
- **KIS API key**: 국내 가격, OHLCV, 기술지표, 재무/시장 데이터
- **Naver Developers key**: 국내 뉴스 검색
- **DART API key**: 공시, 기업 식별자, 이벤트 맥락
- **ECOS API key**: 한국은행 거시 데이터

API key는 한 번만 발급해 `.env`에 넣으면 됩니다. 발급 링크는 아래 [API 키](#-api-키) 섹션에 정리되어 있습니다.

전체 설정은 다음 문서를 참고하세요.

- [`.env.example`](.env.example)
- [AI 에이전트 설치 지침](llm.txt)
- [설정 가이드](docs/configuration.ko.md)
- [API 키 발급 가이드](docs/api-keys.ko.md)

한국어 문서 바로가기:

- [아키텍처](docs/architecture.ko.md)
- [데이터 소스](docs/data-sources.ko.md)
- [공개 배포 가이드](docs/public-release-guide.ko.md)
- [v0.1.0 릴리스 노트](docs/release-notes-v0.1.0.ko.md)

## 🔑 API 키

공개 레포 사용자가 바로 따라 할 수 있도록 발급 링크를 정리했습니다.

| 키 | 용도 | 필요 여부 | 발급 링크 |
|---|---|---:|---|
| `KIS_APP_KEY`, `KIS_APP_SECRET` | 국내 가격/OHLCV/지표/재무 데이터 | 권장 | [KIS Developers](https://apiportal.koreainvestment.com/) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 국내 뉴스 검색 | 권장 | [Naver Developers](https://developers.naver.com/apps/#/register) |
| `DART_API_KEY` | 공시/기업 식별/이벤트 맥락 | 권장 | [OpenDART](https://opendart.fss.or.kr/) |
| `ECOS_API_KEY` | 한국 매크로 통계 | 권장 | [ECOS Open API](https://ecos.bok.or.kr/api/) |
| `FRED_API_KEY` | 글로벌 매크로 보조 지표 | 선택 | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `SEC_USER_AGENT` | SEC EDGAR 접근 시 식별자 | 선택 | [SEC guide](https://www.sec.gov/os/accessing-edgar-data) |
| `NOTION_API_TOKEN` | Notion report export | 선택 | [Notion integrations](https://developers.notion.com/guides/get-started/internal-connections) |
| `TELEGRAM_BOT_TOKEN` | 알림/봇 연동 | 선택 | [BotFather](https://t.me/BotFather) |

자세한 발급 방법과 주의사항은 [`docs/api-keys.ko.md`](docs/api-keys.ko.md)에 있습니다.

## 🧪 사용 예시

> 해외/미국 주식(`AAPL`, `SPCX`, “애플 해외 주식” 등)은 별도 `TradingAgents-us` 워크플로우를 사용하세요.

지원 입력 예시:

```text
005930
삼성전자
000660
SK하이닉스
```

요청 예시:

```text
삼성전자 국내 주식 분석해줘
하이닉스 국내주식 분석해줘
005930 분석해줘
```

OpenClaw / Notion helper:

```bash
python .openclaw/skills/tradingagents-korea-analysis/scripts/run_analysis_to_notion.py \
  --ticker 005930 \
  --date YYYY-MM-DD \
  --timeout 7200
```

## 🏗️ 아키텍처

```text
사용자 요청
  ↓
종목 코드 / 회사명 정규화
  ↓
데이터 사전 수집
  ├─ KIS
  ├─ DART
  ├─ ECOS
  ├─ Naver News
  └─ yfinance
  ↓
Feature packet 구성
  ├─ 시장 데이터 묶음
  ├─ 재무 데이터 묶음
  ├─ 뉴스 데이터 묶음
  └─ 매크로 / 공시 맥락
  ↓
TradingAgents 분석 흐름
  ├─ 시장 분석가
  ├─ 뉴스 분석가
  ├─ 재무 분석가
  ├─ Bull / Bear 리서처
  ├─ 트레이더
  ├─ 리스크 매니저
  └─ 포트폴리오 매니저
  ↓
Markdown / Notion 리포트
```

<p align="center">
  <img src="assets/schema.png" alt="TradingAgents framework schema" width="90%">
</p>

자세한 설명:

- [아키텍처 문서](docs/architecture.ko.md)
- [데이터 소스 문서](docs/data-sources.ko.md)
- [데이터 소스 아키텍처](docs/data-source-architecture.md)

## 🔀 원본 TradingAgents와의 차이

| 구분 | 원본 TradingAgents | TradingAgents Korea |
|---|---|---|
| 시장 초점 | 글로벌/미국 중심 종목 분석 흐름 | 한국 주식 우선 |
| 주요 시장 데이터 | 범용 시장 데이터 제공자 | KIS 중심 한국 시장 데이터 |
| 공시 맥락 | 일반적인 기업/뉴스 맥락 | DART 공시·이벤트 맥락 |
| 매크로 맥락 | 글로벌 매크로/뉴스 | ECOS/BOK 기반 한국 매크로 계층 |
| 뉴스 | 글로벌/소셜/뉴스 소스 | Naver News + yfinance 보조 관점 |
| 언어 | 주로 영어 분석 흐름 | 영어/한국어/중국어 문서 + 한국어 리포트 흐름 |
| LLM 실행 | API 제공자 중심 | Claude Code / Codex CLI 구독형 runtime 우선 |
| 출력 | CLI/package 결과 | 장문 프리미엄 Markdown + 선택형 Notion export |

## 📝 예시 리포트

민감 정보를 제거한 공개용 예시 리포트는 여기에서 확인할 수 있습니다.

- [삼성전자 005930 리포트 — 2026-06-30](examples/reports/ko/samsung-005930-2026-06-30.md)
- [SK하이닉스 000660 리포트 — 2026-06-30](examples/reports/ko/sk-hynix-000660-2026-06-30.md)
- [이전 삼성전자 005930 데모 리포트](examples/reports/samsung-005930-demo.md)

예시 리포트 구성:

- 시장 및 기술적 맥락
- 뉴스와 심리 맥락
- 재무 및 공시 맥락
- 매크로 환경
- 상승 시나리오 / 하락 시나리오
- 트레이더 관점의 실행 계획
- 리스크 검토
- 포트폴리오 매니저 최종 판단

## 🗂️ 저장소 구조

```text
TradingAgents-KR/
├── tradingagents/          # 핵심 agent, graph, dataflow
├── cli/                    # 대화형 CLI
├── docs/                   # 공개 문서와 설계 노트
├── examples/reports/       # 언어별 민감 정보 제거 예시 리포트
├── .openclaw/skills/       # OpenClaw helper skill
├── main.py                 # 루트 실행 파일
├── llm.txt                 # AI 에이전트용 상세 설치 지침
├── .env.example            # 안전한 환경 변수 템플릿
├── README.md
├── README.ko.md
└── README.zh.md
```

## 🛡️ 공개 배포 전 보안 점검

저장소를 공개하기 전에 아래 문서를 먼저 확인하세요.

- [공개 배포 보안 체크리스트](SECURITY_PUBLIC_RELEASE_CHECKLIST.md)
- [공개 배포 가이드](docs/public-release-guide.ko.md)

절대 커밋하면 안 되는 항목:

- `.env`
- API key 또는 token
- KIS 계좌 식별자
- Notion token 또는 비공개 page URL
- Telegram bot token
- 비공개 리포트 export 파일
- 개인 로컬 경로

## 🧭 로드맵

- [ ] KRX 섹터 로테이션 packet
- [ ] DART XBRL 기반 TTM 재무 데이터
- [ ] ECOS 매크로 국면 model
- [ ] KIS 실시간 시장 snapshot
- [ ] 백테스팅 / 평가 harness
- [ ] MCP 서버 모드
- [ ] 웹 대시보드
- [ ] 영어 리포트 모드

## 🙏 크레딧

이 프로젝트는 원본 TradingAgents 프레임워크를 기반으로 합니다.

- 원본 저장소: <https://github.com/TauricResearch/TradingAgents>
- 원본 논문: <https://arxiv.org/abs/2412.20138>

한국 시장 데이터 연동과 워크플로우 변경 사항은 이 fork에서 관리합니다.

자세한 내용은 [크레딧](CREDITS.md)과 [NOTICE](NOTICE.md)를 참고하세요.

## 📄 라이선스

Apache License 2.0을 따릅니다. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.

---

<div align="center">

한국 주식 리서치 흐름에 도움이 되었다면 ⭐로 응원해 주세요

[맨 위로](#readme-top)

</div>
