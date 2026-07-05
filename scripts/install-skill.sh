#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for the repo-bundled `korean-stock-analysis` skill into an
# agent framework's *personal* skills directory, so the skill is usable from
# outside this checkout.
#
# Usage:
#   scripts/install-skill.sh <framework> [more...]
#   scripts/install-skill.sh all
#
# Frameworks:
#   claude | codex | agents | hermes | openclaw | all
#
# What it does:
#   - copies the framework-native skill folder into that framework's personal
#     skills dir (e.g. ~/.claude/skills/korean-stock-analysis)
#   - auto-wires the repo path into the copied runner scripts, so the skill
#     resolves this checkout WITHOUT any manual `export TRADINGAGENTS_KOREA_REPO`
#     (your own exported value still wins).
#
# The repo checkout still needs a configured `.env` (KIS keys + a logged-in CLI
# runtime). Verify with:  (cd <repo> && .venv/bin/tradingagents doctor)
#
# Env overrides:
#   TRADINGAGENTS_KOREA_REPO  path to the repo checkout (default: auto-detected)
#   HERMES_HOME               Hermes runtime home (default: $HOME/.hermes)

usage() {
  cat >&2 <<EOF
Usage: scripts/install-skill.sh <claude|codex|agents|hermes|openclaw|all> [...]
EOF
  exit 2
}

[ "$#" -ge 1 ] || usage

SKILL="korean-stock-analysis"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

# --- resolve repo root --------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${TRADINGAGENTS_KOREA_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
if [ ! -f "$REPO/main.py" ] || [ ! -f "$REPO/pyproject.toml" ]; then
  echo "ERROR: TradingAgents-KR repo root not found at '$REPO'." >&2
  echo "Run this from the repo checkout, or set TRADINGAGENTS_KOREA_REPO." >&2
  exit 3
fi

src_for() {
  case "$1" in
    claude)   echo "$REPO/.claude/skills/$SKILL" ;;
    codex)    echo "$REPO/.codex/skills/$SKILL" ;;
    agents)   echo "$REPO/.agents/skills/$SKILL" ;;
    openclaw) echo "$REPO/.openclaw/skills/$SKILL" ;;
    hermes)   echo "$REPO/.hermes/skills/finance/$SKILL" ;;
    *) return 1 ;;
  esac
}

dst_for() {
  case "$1" in
    claude)   echo "$HOME/.claude/skills/$SKILL" ;;
    codex)    echo "$HOME/.codex/skills/$SKILL" ;;
    agents)   echo "$HOME/.agents/skills/$SKILL" ;;
    openclaw) echo "$HOME/.openclaw/skills/$SKILL" ;;
    hermes)   echo "$HERMES_HOME/skills/finance/$SKILL" ;;
    *) return 1 ;;
  esac
}

AUTOWIRE_MARKER="# >>> tradingagents-korea repo autowire (added by install-skill.sh) >>>"

autowire_repo() {
  # Inject a default for TRADINGAGENTS_KOREA_REPO right after the shebang of the
  # copied runner scripts. `:=` only defaults when unset, so a user-exported
  # value still wins. Idempotent via the marker.
  local script="$1"
  [ -f "$script" ] || return 0
  grep -qF "$AUTOWIRE_MARKER" "$script" && return 0
  local tmp
  tmp="$(mktemp)"
  {
    head -n 1 "$script"
    printf '%s\n: "${TRADINGAGENTS_KOREA_REPO:=%s}"\nexport TRADINGAGENTS_KOREA_REPO\n' "$AUTOWIRE_MARKER" "$REPO"
    tail -n +2 "$script"
  } >"$tmp"
  cat "$tmp" >"$script"
  rm -f "$tmp"
  chmod +x "$script"
}

install_one() {
  local fw="$1" src dst
  src="$(src_for "$fw")" || { echo "ERROR: unknown framework '$fw'" >&2; return 2; }
  dst="$(dst_for "$fw")"
  if [ ! -d "$src" ]; then
    echo "ERROR: skill source missing for '$fw': $src" >&2
    return 4
  fi
  rm -rf "$dst"
  mkdir -p "$dst"
  ( cd "$src" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - . ) | tar -C "$dst" -xf -
  find "$dst" -path '*/scripts/*.sh' -type f -exec chmod +x {} \; 2>/dev/null || true
  find "$dst" -path '*/scripts/*.py' -type f -exec chmod +x {} \; 2>/dev/null || true
  autowire_repo "$dst/scripts/analyze_kr_stock.sh"
  autowire_repo "$dst/scripts/analyze_kr_watchlist.sh"
  [ -f "$dst/SKILL.md" ] || { echo "ERROR: install failed (no SKILL.md at $dst)" >&2; return 5; }
  echo "OK  $fw  ->  $dst"
}

# Expand args (support 'all').
FRAMEWORKS=()
for a in "$@"; do
  if [ "$a" = "all" ]; then
    FRAMEWORKS+=(claude codex agents hermes openclaw)
  else
    FRAMEWORKS+=("$a")
  fi
done

for fw in "${FRAMEWORKS[@]}"; do
  install_one "$fw"
done

cat <<EOF

Installed skill(s) point at repo: $REPO
Make sure that checkout has a configured .env (KIS keys + a CLI runtime).
Check with:  (cd "$REPO" && .venv/bin/tradingagents doctor)
EOF
