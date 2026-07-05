"""Pre-flight data check for a KRX ticker (KIS).

Prints "OK" (exit 0) when the core market packet is usable — i.e. KIS returns a
non-empty current price AND a non-empty recent daily OHLCV series. Otherwise
prints "EMPTY: <reason>" (exit 1) so the runner can abort instead of producing a
no_data report.

Run from TradingAgents-KR via uv. Reuses the repo's cached KIS token.
"""
from __future__ import annotations
import os

import json
import sys
import time
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
    import datetime
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
                      json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec},
                      timeout=20)
    r.raise_for_status()
    data = r.json(); tok = data["access_token"]
    try:
        OWN_TOKEN.parent.mkdir(parents=True, exist_ok=True)
        OWN_TOKEN.write_text(json.dumps({"appkey": key, "token": tok,
                                         "expires_at": time.time() + int(data.get("expires_in") or 86400)}))
        OWN_TOKEN.chmod(0o600)
    except Exception:
        pass
    return tok


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else ""
    if not code:
        print("EMPTY: no code"); sys.exit(1)
    try:
        key, sec = _keys()
        tok = _token(key, sec)
        h = {"authorization": f"Bearer {tok}", "appkey": key, "appsecret": sec, "custtype": "P"}
        # 1) current price
        r = requests.get(f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
                         headers={**h, "tr_id": "FHKST01010100"},
                         params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}, timeout=20)
        price = (r.json().get("output") or {}).get("stck_prpr") if r.status_code == 200 else None
        if not price or str(price).strip() in ("", "0"):
            print(f"EMPTY: no current price (stck_prpr={price})"); sys.exit(1)
        # 2) recent daily OHLCV series non-empty
        r2 = requests.get(f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-price",
                          headers={**h, "tr_id": "FHKST01010400"},
                          params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                  "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}, timeout=20)
        rows = r2.json().get("output") or [] if r2.status_code == 200 else []
        valid = [x for x in rows if str(x.get("stck_clpr") or "").strip() not in ("", "0")]
        if len(valid) < 1:
            print(f"EMPTY: no daily OHLCV rows ({len(rows)} raw)"); sys.exit(1)
        print(f"OK price={price} daily_rows={len(valid)}")
        sys.exit(0)
    except Exception as e:
        print(f"EMPTY: error {repr(e)[:120]}"); sys.exit(1)


if __name__ == "__main__":
    main()
