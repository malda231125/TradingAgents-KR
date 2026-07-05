"""KRX foreign/institutional net-buy flow for a ticker (KIS inquire-investor).

Prints the last N trading days of foreign & institutional net buy (shares) and a
consecutive foreign-net-SELL streak counter from the most recent day. Used by the
kr-foreign-flow-alert cron to flag "외국인 순매도 추세화 + 기관 흡수 약화".

Usage:  (run from TradingAgents-KR via uv)
  uv run python kr_foreign_flow.py <6-digit-code> [days=5]
Output last line:  STREAK=<n> FOREIGN_TODAY=<shares> INST_TODAY=<shares>
"""
from __future__ import annotations
import os

import json
import sys
import time
import datetime
from pathlib import Path

import requests

BASE = "https://openapi.koreainvestment.com:9443"
def _repo_root() -> Path:
    """Resolve the TradingAgents-KR checkout: explicit env var first, then
    the enclosing checkout (when run in-repo), then the documented default."""
    env = os.environ.get("TRADINGAGENTS_KOREA_REPO")
    if env:
        return Path(os.path.expanduser(env))
    for parent in Path(__file__).resolve().parents:
        if (parent / "main.py").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    return Path(os.path.expanduser("~/TradingAgents-KR"))


REPO = _repo_root()
ENV = REPO / ".env"
REPO_TOKEN = Path(os.path.expanduser("~/.tradingagents-korea/kis-token.json"))
OWN_TOKEN = Path(os.path.expanduser("~/.cache/tradingagents-korea/kis_token_cache.json"))


def _keys() -> tuple[str, str]:
    key = sec = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("KIS_APP_KEY="):
            key = s.split("=", 1)[1].strip().strip('"')
        elif s.startswith("KIS_APP_SECRET="):
            sec = s.split("=", 1)[1].strip().strip('"')
    return key, sec


def _token(key: str, sec: str) -> str:
    for cache in (REPO_TOKEN, OWN_TOKEN):
        try:
            c = json.loads(cache.read_text())
            exp = c.get("expires_at")
            if isinstance(exp, str):
                ok = datetime.datetime.fromisoformat(exp).timestamp() > time.time() + 600
            else:
                ok = float(exp or 0) > time.time() + 600 and c.get("appkey") == key
            if ok:
                return str(c.get("access_token") or c.get("token"))
        except Exception:
            pass
    r = requests.post(f"{BASE}/oauth2/tokenP",
                      json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else ""
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    if not code:
        print("STREAK=0 FOREIGN_TODAY=0 INST_TODAY=0 (no code)"); return
    key, sec = _keys(); tok = _token(key, sec)
    h = {"authorization": f"Bearer {tok}", "appkey": key, "appsecret": sec,
         "tr_id": "FHKST01010900", "custtype": "P"}
    r = requests.get(f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
                     headers=h, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}, timeout=20)
    rows = (r.json().get("output", []) or [])[:days]
    streak = 0
    broke = False
    for x in rows:
        f = int(x.get("frgn_ntby_qty") or 0)
        i = int(x.get("orgn_ntby_qty") or 0)
        print(f"{x.get('stck_bsop_date')} 외국인 {f:+,} 기관 {i:+,} 종가 {x.get('stck_clpr')}")
        if not broke:
            if f < 0:
                streak += 1
            else:
                broke = True
    ft = int(rows[0].get("frgn_ntby_qty") or 0) if rows else 0
    it = int(rows[0].get("orgn_ntby_qty") or 0) if rows else 0
    print(f"STREAK={streak} FOREIGN_TODAY={ft} INST_TODAY={it}")


if __name__ == "__main__":
    main()
