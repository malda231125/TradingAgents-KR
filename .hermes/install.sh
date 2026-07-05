#!/usr/bin/env bash
set -euo pipefail

# Install the repository-bundled Hermes skill into a Hermes runtime.
#
# This is a thin, backward-compatible wrapper around scripts/install-skill.sh
# (the single source of truth for installing the skill into any framework's
# personal skills dir, including repo path auto-wiring).
#
# Destination: $HERMES_HOME/skills/finance/korean-stock-analysis
#              (default HERMES_HOME=$HOME/.hermes; override via the HERMES_HOME env var)

REPO="${TRADINGAGENTS_KOREA_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
exec "$REPO/scripts/install-skill.sh" hermes
