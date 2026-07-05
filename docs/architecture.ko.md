# 🏗️ 아키텍처

[English](architecture.md) · 한국어

TradingAgents Korea는 원본 TradingAgents의 멀티에이전트 투자 리서치 구조를 한국 주식 시장에 맞게 확장합니다.

## 전체 흐름

```text
사용자 요청
  ↓
종목 코드 / 회사명 정규화
  ↓
데이터 사전 수집
  - KIS
  - DART
  - ECOS
  - Naver News
  - yfinance
  ↓
Feature packet 구성
  - 시장 데이터
  - 재무 데이터
  - 뉴스 데이터
  - 매크로 / 공시 맥락
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
Markdown / Notion 리포트
```

## 설계 원칙

### 1. 한국 종목 식별자는 소스마다 다릅니다

하나의 사용자 입력은 여러 식별자로 분리될 수 있습니다.

- 회사명: `삼성전자`
- 종목코드: `005930`
- DART 고유번호
- yfinance 후보 심볼: `005930.KS`
- Naver 뉴스 검색어: 회사명 중심 키워드

따라서 모든 소스에 하나의 ticker 문자열을 억지로 쓰지 않고, 소스별 식별자를 분리해서 관리합니다.

### 2. LLM 추론 전에 데이터를 먼저 구성합니다

각 analyst node는 보고서를 작성하기 전에 작고 명확한 데이터 블록을 받아야 합니다. 이렇게 하면 숫자 hallucination을 줄이고, 누락된 데이터도 리포트에 명확히 드러낼 수 있습니다.

### 3. 뉴스는 다중 소스 관점으로 봅니다

국내 한국어 뉴스와 yfinance 기반 글로벌/외부 시각은 서로 다른 맥락을 제공합니다. 뉴스는 단순 fallback이 아니라 여러 관점을 합치는 방식으로 다룹니다.

### 4. 구조화 데이터는 의미를 조용히 바꾸지 않습니다

가격, 재무, 지표, 공시, 매크로 데이터는 출처별 의미가 중요합니다. 주요 소스가 실패했을 때 다른 소스로 조용히 대체하기보다, 실패 사실을 리포트에 명확히 드러내는 쪽을 선호합니다.

## OpenClaw skill 연동

저장소에는 OpenClaw용 helper skill이 포함되어 있습니다.

```text
.openclaw/skills/tradingagents-korea-analysis/
```

이 skill은 한국/해외 주식 라우팅, 장시간 분석 실행, Codex CLI 요구사항, Notion export helper를 문서화합니다.

관련 문서:

- [데이터 소스](data-sources.ko.md)
- [설정 가이드](configuration.ko.md)
