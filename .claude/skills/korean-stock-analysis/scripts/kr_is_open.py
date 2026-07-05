"""KRX trading-day check via KIS (한국투자증권) holiday API.

Usage:
  python kr_is_open.py [YYYY-MM-DD]          -> prints "OPEN" or "CLOSED"
  python kr_is_open.py [YYYY-MM-DD] next     -> prints next open day (YYYY-MM-DD)

Reads KIS_APP_KEY / KIS_APP_SECRET from the repo .env. The repo location is
resolved from $TRADINGAGENTS_KOREA_REPO (falls back to the OpenClaw default) so
this script is portable across installs. Toss Open API is IP-allowlisted and
unavailable from this host, so KIS (`chk-holiday`, field opnd_yn) is the
trading-day source.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
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
TOKEN_CACHE = Path(os.path.expanduser("~/.cache/tradingagents-korea/kis_token_cache.json"))
# TradingAgents-KR writes its KIS token here; reuse it to avoid re-issuing
# (KIS throttles rapid token issuance).
REPO_TOKEN_CACHE = Path(os.path.expanduser("~/.tradingagents-korea/kis-token.json"))


def _load_keys() -> tuple[str, str]:
    key = sec = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("KIS_APP_KEY="):
            key = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("KIS_APP_SECRET="):
            sec = line.split("=", 1)[1].strip().strip('"')
    return key, sec


def _token(key: str, sec: str) -> str:
    # 1) Reuse TradingAgents-KR's token cache (expires_at is ISO-8601).
    try:
        c = json.loads(REPO_TOKEN_CACHE.read_text())
        exp = datetime.datetime.fromisoformat(c["expires_at"])
        if exp.timestamp() > time.time() + 600:
            return str(c["access_token"])
    except Exception:
        pass
    # 2) Reuse our own cache (KIS throttles rapid re-issue; tokens last ~24h).
    try:
        c = json.loads(TOKEN_CACHE.read_text())
        if c.get("appkey") == key and float(c.get("expires_at", 0)) > time.time() + 600:
            return str(c["token"])
    except Exception:
        pass
    r = requests.post(
        f"{BASE}/oauth2/tokenP",
        json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    try:
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(json.dumps({
            "appkey": key,
            "token": token,
            "expires_at": time.time() + int(data.get("expires_in") or 86400),
        }))
        TOKEN_CACHE.chmod(0o600)
    except Exception:
        pass
    return token


def _open_map(key: str, sec: str, token: str, bass_dt: str) -> dict[str, str]:
    """Return {YYYYMMDD: 'Y'/'N'} opnd_yn for a window starting at bass_dt."""
    h = {
        "authorization": f"Bearer {token}",
        "appkey": key,
        "appsecret": sec,
        "tr_id": "CTCA0903R",
        "custtype": "P",
    }
    p = {"BASS_DT": bass_dt, "CTX_AREA_NK": "", "CTX_AREA_FK": ""}
    r = requests.get(
        f"{BASE}/uapi/domestic-stock/v1/quotations/chk-holiday",
        headers=h, params=p, timeout=20,
    )
    r.raise_for_status()
    out = r.json().get("output", []) or []
    return {row["bass_dt"]: row.get("opnd_yn", "N") for row in out}


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(KST).date().isoformat()
    mode = sys.argv[2] if len(sys.argv) > 2 else "check"
    bass = date.replace("-", "")
    key, sec = _load_keys()
    token = _token(key, sec)
    om = _open_map(key, sec, token, bass)

    if mode == "next":
        # find the first open day strictly after `date`
        d = datetime.date.fromisoformat(date)
        for _ in range(20):
            d = d + datetime.timedelta(days=1)
            ymd = d.strftime("%Y%m%d")
            if ymd not in om:
                om = _open_map(key, sec, token, ymd)
            if om.get(ymd) == "Y":
                print(d.isoformat())
                return
        print(date)  # fallback
        return

    print("OPEN" if om.get(bass) == "Y" else "CLOSED")


if __name__ == "__main__":
    main()
