# 🛡️ Public Release Guide

English · [한국어](public-release-guide.ko.md)

This guide describes recommended checks before making the repository public.

## 1. Run the security checklist

Read and complete:

```text
SECURITY_PUBLIC_RELEASE_CHECKLIST.md
```

Do not proceed if real API keys, tokens, account identifiers, private Notion links or personal local paths are still present.

## 2. Verify public positioning

Recommended GitHub description:

```text
English-friendly multi-agent AI research framework for Korean equities, built on TradingAgents, KIS, DART, ECOS and Naver News
```

Recommended topics:

```text
tradingagents
korean-equities
korean-stocks
korea-finance
krx
kospi
kosdaq
dart
kis
opendart
ecos
naver-news
llm-agents
ai-research-agent
investment-research
financial-analysis
codex-cli
notion
stock-analysis
multi-agent
```

## 3. Check examples

Public examples should live under:

```text
examples/reports/
```

They must be sanitized and clearly marked as examples, not investment advice.

## 4. Confirm attribution

Keep upstream credits visible:

- README
- NOTICE.md
- CREDITS.md
- LICENSE

## 5. Suggested first release

```bash
git tag v0.1.0
git push origin v0.1.0
```

Suggested release title:

```text
v0.1.0 — Korean equities multi-agent research workflow
```

Release notes should mention:

- Korean-equity workflow
- KIS / DART / ECOS / Naver integration
- Codex CLI support
- Notion export helper
- known limitations

Related docs:

- [v0.1.0 release notes](release-notes-v0.1.0.md)
- [API key guide](api-keys.md)
