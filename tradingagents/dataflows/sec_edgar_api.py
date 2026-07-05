"""SEC EDGAR public JSON API helpers.

SEC EDGAR is used as optional overseas peer context. It does not require an
API key, but automated requests must include an identifying User-Agent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Optional

import requests

from tradingagents.dataflows.config import get_config

logger = logging.getLogger(__name__)

SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_WWW_BASE_URL = "https://www.sec.gov"
SEC_MIN_REQUEST_INTERVAL_SECONDS = 0.12

_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
_TICKER_CIK_CACHE: dict[str, str] | None = None

_CACHE_TTL_SUBMISSIONS_SECONDS = 3600
_CACHE_TTL_COMPANYFACTS_SECONDS = 86400
_CACHE_TTL_TICKER_MAP_SECONDS = 86400


class SECEdgarError(RuntimeError):
    pass


def get_sec_user_agent() -> str:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent:
        raise SECEdgarError("SEC_USER_AGENT is not configured")
    return user_agent


def sec_edgar_available() -> bool:
    return bool(os.environ.get("SEC_USER_AGENT", "").strip())


def _rate_limit() -> None:
    global _LAST_REQUEST_AT
    with _REQUEST_LOCK:
        now = time.time()
        wait = SEC_MIN_REQUEST_INTERVAL_SECONDS - (now - _LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_AT = time.time()


def _headers() -> dict[str, str]:
    return {
        "User-Agent": get_sec_user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }


def _get_cache_dir() -> str:
    config = get_config()
    cache_dir = os.path.join(config.get("data_cache_dir", "/tmp"), "sec_edgar_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def _cache_get(url: str, ttl_seconds: int) -> Optional[dict]:
    path = os.path.join(_get_cache_dir(), f"{_cache_key(url)}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    age = time.time() - entry.get("ts", 0)
    if age > ttl_seconds:
        return None
    data = entry.get("data")
    return data if isinstance(data, dict) else None


def _cache_set(url: str, data: dict) -> None:
    path = os.path.join(_get_cache_dir(), f"{_cache_key(url)}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except OSError as exc:
        logger.debug("SEC cache write failed for %s: %s", url, exc)


def _request_json(url: str, *, ttl_seconds: int) -> dict:
    cached = _cache_get(url, ttl_seconds)
    if cached is not None:
        return cached

    _rate_limit()
    try:
        response = requests.get(url, headers=_headers(), timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise SECEdgarError(f"SEC request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise SECEdgarError(f"SEC returned invalid JSON for {url}") from exc
    _cache_set(url, data)
    return data


def _normalize_cik(cik: str | int) -> str:
    return str(cik).strip().lstrip("CIK").zfill(10)


def _load_ticker_cik_map() -> dict[str, str]:
    global _TICKER_CIK_CACHE
    if _TICKER_CIK_CACHE is not None:
        return _TICKER_CIK_CACHE

    payload = _request_json(
        f"{SEC_WWW_BASE_URL}/files/company_tickers.json",
        ttl_seconds=_CACHE_TTL_TICKER_MAP_SECONDS,
    )
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = str(item.get("ticker", "")).strip().upper()
        cik = item.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = _normalize_cik(cik)
    _TICKER_CIK_CACHE = mapping
    return mapping


def resolve_cik_for_ticker(ticker: str) -> Optional[str]:
    if not ticker:
        return None
    mapping = _load_ticker_cik_map()
    return mapping.get(ticker.strip().upper())


def get_company_submissions(cik: str | int) -> dict:
    normalized = _normalize_cik(cik)
    return _request_json(
        f"{SEC_DATA_BASE_URL}/submissions/CIK{normalized}.json",
        ttl_seconds=_CACHE_TTL_SUBMISSIONS_SECONDS,
    )


def get_company_facts(cik: str | int) -> dict:
    normalized = _normalize_cik(cik)
    return _request_json(
        f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK{normalized}.json",
        ttl_seconds=_CACHE_TTL_COMPANYFACTS_SECONDS,
    )
