# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI running the test suite on Python 3.10–3.12.
- Community health files: `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, issue/PR templates.

### Changed
- The self-improvement loop is now **always on** in `main.py` (the opt-in
  `--self-loop` flag was removed); the retrospective is auto-skipped on the
  first run for a ticker.
- Skill ports moved to each framework's native directory
  (`.claude/`, `.codex/`, `.hermes/`, `.agents/`); script paths are
  env-driven via `$TRADINGAGENTS_KOREA_REPO`.

### Fixed
- Claude CLI failures now surface the real cause (the `claude` binary writes
  usage-limit/auth/overload errors to stdout, not stderr).

## [0.2.2]

### Added
- **Self-improvement loop**: decision records, deterministic + AI-assisted
  retrospective scoring, lesson accumulation, event-driven and daily
  trigger-based review (`tradingagents/self_loop/`, `scripts/`).
- **Claude CLI** backend with reasoning-effort control (`--effort`,
  `TRADINGAGENTS_CLI_EFFORT`) alongside the existing Codex CLI path.
- **Feature packets**: compact structured analyst inputs that replace large raw
  text dumps (`tradingagents/dataflows/feature_packets/`).
- KIS foreign/institutional investor-flow signal in the market packet.
- Overseas context MVP (FRED macro, SEC EDGAR) as optional enrichment only.

### Changed
- Vendor-routing data layer hardened: structured data fails loudly; news is
  multi-source by design.

## [0.1.0]

Initial Korea-market adaptation of
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).

### Added
- Korean-equities multi-agent research workflow (KOSPI/KOSDAQ).
- KIS structured market data, DART disclosures, ECOS macro, Naver News +
  yfinance supplemental news.
- Korean ticker/company resolver.
- Codex CLI execution support.
- OpenClaw helper skill for long-running reports + optional Notion export.
- Public-release documentation and security checklist.

[Unreleased]: https://github.com/malda231125/TradingAgents-KR/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/malda231125/TradingAgents-KR/releases/tag/v0.2.2
[0.1.0]: https://github.com/malda231125/TradingAgents-KR/releases/tag/v0.1.0
