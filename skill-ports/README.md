# skill-ports — index (skills now live in framework-native locations)

The `korean-stock-analysis` skill (KRX analysis → 📐 Slack/Telegram report → 국내주식.md ledger →
next-trading-day verification) is packaged for three agent frameworks. **Each port now lives in its
framework's native, auto-discovered skills directory** (project-level, in this repo) rather than
under `skill-ports/` — so each is directly installable/usable in place.

| Framework | Native location (in this repo) | Personal install | Docs |
| --- | --- | --- | --- |
| Claude Code | `.claude/skills/korean-stock-analysis/` | `~/.claude/skills/` | https://code.claude.com/docs/ko/skills |
| Codex CLI | `.codex/skills/korean-stock-analysis/` (+ mirrored `.agents/skills/`) | `~/.codex/skills/` | https://developers.openai.com/codex/skills |
| Hermes Agent | `.hermes/skills/finance/korean-stock-analysis/` | `~/.hermes/skills/` | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |

The canonical OpenClaw/Claude skill remains at `.openclaw/skills/korean-stock-analysis/` (proven in
production — delivers Telegram reports); the three ports mirror its proven behavior in each
framework's format/conventions.

## Each port is self-contained

Every native skill folder bundles its own `scripts/` so it works in place:

```
<native-skill-dir>/
  SKILL.md
  scripts/
    analyze_kr_stock.sh       # detached single-stock runner → main.py → complete_report.md + sentinels
    analyze_kr_watchlist.sh   # sequential multi-stock (watchlist) runner
    kr_is_open.py             # KRX trading-day calendar (KIS chk-holiday); supports `next`
    kr_preflight.py           # standalone KIS data check (ad-hoc; main.py has its own pre-flight)
    kr_foreign_flow.py        # foreign/institutional net-buy streak
```

- **Codex** additionally has `agents/openai.yaml` (presentation/policy) and `references/report-format.md` (the 📐 template, single source).
- **Hermes** sits under the required `finance/` category folder and references scripts via `${HERMES_SKILL_DIR}/scripts/…`.
- **Claude** references scripts via `${CLAUDE_SKILL_DIR}/scripts/…` so paths resolve regardless of cwd.

## Path/config notes

- The bundled scripts are **path-portable** versions of the canonical `.openclaw/skills/
  korean-stock-analysis/scripts/`: project-level skill copies auto-detect the repo root by walking
  up from their own script path. If a skill folder is copied into a personal skills directory,
  export `$TRADINGAGENTS_KOREA_REPO` to point at the repo checkout. The `.openclaw` originals are
  left untouched.
- `self_loop_review.py` is **not** bundled — it lives in the repo (`scripts/self_loop_review.py`)
  and depends on the `tradingagents` package, so it is invoked from the repo, not the skill folder.
- Proven verification path = the 국내주식.md ledger + reasoning-based verdict (⚠️ 놓친 점 / ✅ 정확);
  the repo's internal AI self-loop is optional.

## Install elsewhere

**One-shot (recommended).** From the repo checkout, run the bundled installer — it copies the
native skill folder into the framework's personal skills dir and auto-wires this checkout's path
into the runner scripts (no manual `export TRADINGAGENTS_KOREA_REPO` needed):

```bash
scripts/install-skill.sh claude      # or: codex | agents | hermes | openclaw | all
```

The checkout still needs a configured `.env` (KIS keys + a CLI runtime); check with
`tradingagents doctor`.

**Manual.** Alternatively, copy the native folder into the target tool's personal skills dir
(`~/.claude/skills/`, `~/.agents/skills/`, or `~/.hermes/skills/`), ensure the `TradingAgents-KR`
repo is present and configured, and export `TRADINGAGENTS_KOREA_REPO` to point the scripts at that
checkout.

## Platforms

The skill runners are POSIX shell scripts, so they run on **Linux and macOS** (and on
**Windows via WSL or Git Bash**). Native Windows `cmd`/PowerShell is not supported for the skill
runners.
