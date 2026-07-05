# 🛡️ 공개 배포 가이드

[English](public-release-guide.md) · 한국어

이 문서는 저장소를 공개로 전환하기 전에 권장하는 점검 절차입니다.

## 1. 보안 체크리스트 실행

먼저 아래 파일을 확인하고 완료하세요.

```text
SECURITY_PUBLIC_RELEASE_CHECKLIST.md
```

실제 API key, token, 계좌 식별자, private Notion 링크, 로컬 개인 경로가 남아 있다면 공개하면 안 됩니다.

## 2. 공개 포지셔닝 확인

추천 GitHub description:

```text
Korean equities research agents powered by KIS, DART, ECOS and Codex CLI.
```

추천 topics:

```text
tradingagents
korean-stocks
krx
kospi
kosdaq
dart
kis
opendart
llm-agents
financial-analysis
codex-cli
notion
stock-analysis
multi-agent
```

## 3. 예시 리포트 점검

공개 예시는 아래 경로에 두는 것을 권장합니다.

```text
examples/reports/
```

예시는 반드시 민감 정보를 제거하고, 투자 조언이 아니라 예시임을 명시해야 합니다.

## 4. 원본 attribution 확인

원본 프로젝트 credit은 아래 파일에 계속 표시되어야 합니다.

- README
- NOTICE.md
- CREDITS.md
- LICENSE

## 5. 첫 release 제안

```bash
git tag v0.1.0
git push origin v0.1.0
```

추천 release title:

```text
v0.1.0 — Korean equities multi-agent research workflow
```

릴리스 노트에 포함할 항목:

- 한국 주식 workflow
- KIS / DART / ECOS / Naver 연동
- Codex CLI 지원
- Notion export helper
- 알려진 한계

관련 문서:

- [v0.1.0 릴리스 노트](release-notes-v0.1.0.ko.md)
- [API 키 발급 가이드](api-keys.ko.md)
