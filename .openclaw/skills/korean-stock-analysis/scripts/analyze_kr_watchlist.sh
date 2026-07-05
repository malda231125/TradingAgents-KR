#!/usr/bin/env bash
# Sequentially run TradingAgents-KR for the daily watchlist, fully detached.
# Usage: analyze_kr_watchlist.sh <yyyy-mm-dd> [codes...]
# Default codes: 005930(삼성전자) 000660(SK하이닉스) 068270(셀트리온)
# Writes per-code sentinels (via analyze_kr_stock.sh) and a combined marker:
#   results/.DONE_watchlist_<date>
export PATH="$HOME/.local/bin:$PATH"
DATE="${1:?need yyyy-mm-dd}"; shift || true
CODES=("$@"); [ ${#CODES[@]} -eq 0 ] && CODES=(005930 000660)
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
cd "$REPO" 2>/dev/null || {
  echo "FATAL: cannot cd to repo root '$REPO' (set TRADINGAGENTS_KOREA_REPO)" >&2
  mkdir -p results 2>/dev/null
  echo "exit_code=99 (cd failed: repo not found at '$REPO')" > "results/.FAIL_watchlist_${DATE}" 2>/dev/null
  exit 99
}
rm -f "results/.DONE_watchlist_${DATE}"
for code in "${CODES[@]}"; do
  bash "$HERE/analyze_kr_stock.sh" "$code" "$DATE"
done
touch "results/.DONE_watchlist_${DATE}"
