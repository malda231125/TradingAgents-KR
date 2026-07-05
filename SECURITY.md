# Security Policy

## Supported versions

This is an actively developed research project; only the latest `main` and the
most recent tagged release receive security fixes.

| Version | Supported |
| ------- | --------- |
| `main` (latest) | ✅ |
| `0.2.x` | ✅ |
| older   | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on this repository
(`https://github.com/malda231125/TradingAgents-KR/security/advisories/new`).

Include a description, reproduction steps, affected version/commit, and impact.
We aim to acknowledge within a few days and will coordinate a fix and
disclosure timeline with you.

## Handling secrets (important)

This project integrates with KIS, DART, ECOS, Naver News, FRED and (optionally)
Telegram. **All credentials live in `.env`, which is gitignored.**

- Never commit API keys, tokens, KIS account identifiers, or token-cache files
  (`*.kis-token.json`, `kis-token.json`, `*.token.json` are gitignored).
- Use `.env.example` as the template; it contains placeholders only.
- If you accidentally commit a secret, **rotate it immediately** at the
  provider and scrub it from history before pushing publicly.

Generated artifacts (`results/`, `reports/`, `decisions/`, `국내주식.md`) are
gitignored because they can contain account-specific or analysis context.
