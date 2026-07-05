#!/usr/bin/env bash
# Run a TradingAgents-KR analysis for one KRX stock, fully detached.
# Usage: analyze_kr_stock.sh <6-digit-code> <yyyy-mm-dd>
# Writes results/<code>/<date>/complete_report.md and a sentinel:
#   results/.DONE_<code>  on success   |   results/.FAIL_<code>  on failure
export PATH="$HOME/.local/bin:$PATH"
export TRADINGAGENTS_TIMING_LOGS=1
if [ -n "${TRADINGAGENTS_KOREA_REPO:-}" ]; then
  REPO="$TRADINGAGENTS_KOREA_REPO"
else
  # Auto-detect the repo root by walking up from this script's own location
  # (portable for in-place installs); fall back to the deployment default if
  # the skill was copied outside the repo tree.
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  while [ "$REPO" != "/" ] && ! { [ -f "$REPO/main.py" ] && [ -f "$REPO/pyproject.toml" ]; }; do
    REPO="$(dirname "$REPO")"
  done
  [ "$REPO" = "/" ] && REPO="$HOME/TradingAgents-KR"
fi
CODE="${1:?need 6-digit code}"
DATE="${2:?need yyyy-mm-dd}"
cd "$REPO" 2>/dev/null || {
  echo "FATAL: cannot cd to repo root '$REPO' (set TRADINGAGENTS_KOREA_REPO)" >&2
  mkdir -p results 2>/dev/null
  echo "exit_code=99 (cd failed: repo not found at '$REPO')" > "results/.FAIL_${CODE}" 2>/dev/null
  exit 99
}
rm -f "results/.DONE_${CODE}" "results/.FAIL_${CODE}"
# Data pre-flight is now inside main.py (reuses the cached market packet, no extra
# API call) — it exits non-zero with DATA_UNAVAILABLE when KIS returns empty data.
if [ -x ".venv/bin/python" ]; then
  PYTHON_CMD=(".venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
  PYTHON_CMD=(uv run python)
else
  PYTHON_CMD=(python3)
fi
"${PYTHON_CMD[@]}" main.py "$CODE" "$DATE" > "run_${CODE}.log" 2>&1
rc=$?
if [ "$rc" -eq 0 ] && [ -f "results/${CODE}/${DATE}/complete_report.md" ]; then
  touch "results/.DONE_${CODE}"
else
  echo "exit_code=$rc" > "results/.FAIL_${CODE}"
fi
