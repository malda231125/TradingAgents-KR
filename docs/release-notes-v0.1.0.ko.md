# 🚀 v0.1.0 — Korean equities multi-agent research workflow

[English](release-notes-v0.1.0.md) · 한국어

TradingAgents Korea의 첫 공개 릴리스를 위한 제안 릴리스 노트입니다.

## 주요 내용

- 한국 주식 중심 TradingAgents workflow
- KIS 중심 구조화 시장 데이터 경로
- DART 공시/이벤트 맥락
- ECOS 기반 한국 매크로 맥락
- Naver News + yfinance 보조 뉴스 흐름
- 한국 종목코드/회사명 resolver
- Codex CLI 실행 지원
- 장시간 정식 리포트 생성을 위한 OpenClaw helper skill
- 선택형 Notion export workflow
- 공개 배포 문서와 보안 체크리스트

## 대상 사용자

- LLM 기반 금융 리서치 agent를 실험하는 개발자
- DART / KIS / ECOS 맥락이 필요한 한국 시장 리서처
- 한국 주식 리서치 자동화의 출발점이 필요한 builder

## 투자 조언 아님

생성된 리포트는 연구·교육 목적의 참고 자료입니다. 투자 조언, 매매 신호, 미래 성과 보장이 아닙니다.

## 알려진 한계

- 전체 workflow에는 외부 API credential이 필요합니다.
- 각 데이터 provider의 약관과 호출 제한을 사용자가 준수해야 합니다.
- 리포트 품질은 로컬 LLM/CLI 설정과 사용 가능한 데이터에 영향을 받습니다.
- Backtesting / evaluation harness는 아직 roadmap 항목입니다.

관련 문서:

- [README](../README.md)
- [설정 가이드](configuration.ko.md)
- [공개 배포 가이드](public-release-guide.ko.md)
