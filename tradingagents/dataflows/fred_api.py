"""FRED API integration for US macro context.

This module is intentionally small: it fetches selected FRED time series and
returns typed DataFrames for feature-packet builders. The Korea runtime treats
FRED as optional overseas enrichment, not as a replacement for ECOS.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd
import requests

from tradingagents.dataflows.config import get_config

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
FRED_CACHE_TTL_SECONDS = 3600


class FREDApiError(RuntimeError):
    pass


def _get_fred_key() -> str:
    return os.environ.get("FRED_API_KEY", "").strip()


def fred_available() -> bool:
    return bool(_get_fred_key())


def _get_cache_dir() -> str:
    config = get_config()
    cache_dir = os.path.join(config.get("data_cache_dir", "/tmp"), "fred_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _cache_key(series_id: str, start_date: str, end_date: str) -> str:
    raw = json.dumps(
        {"series_id": series_id, "start_date": start_date, "end_date": end_date},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _cache_get(key: str, end_date: str) -> pd.DataFrame | None:
    path = os.path.join(_get_cache_dir(), f"{key}.json")
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if end_date >= date.today().isoformat():
        age = time.time() - entry.get("ts", 0)
        if age > FRED_CACHE_TTL_SECONDS:
            return None

    rows = entry.get("rows") or []
    if not rows:
        return pd.DataFrame(columns=["Date", "value"])
    return pd.DataFrame(rows)


def _cache_set(key: str, df: pd.DataFrame) -> None:
    path = os.path.join(_get_cache_dir(), f"{key}.json")
    try:
        rows = df.to_dict(orient="records")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "rows": rows}, f, ensure_ascii=False)
    except OSError as exc:
        logger.debug("FRED cache write failed for %s: %s", key, exc)


def get_fred_series(
    series_id: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch a FRED series as `Date, value` rows sorted ascending."""
    api_key = _get_fred_key()
    if not api_key:
        raise FREDApiError("FRED_API_KEY is not configured")

    key = _cache_key(series_id, start_date, end_date)
    cached = _cache_get(key, end_date)
    if cached is not None:
        return cached

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
        "sort_order": "asc",
    }
    try:
        response = requests.get(
            f"{FRED_BASE_URL}/series/observations",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise FREDApiError(f"FRED request failed for {series_id}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FREDApiError(f"FRED returned invalid JSON for {series_id}") from exc

    if "error_code" in payload:
        message = payload.get("error_message") or payload.get("error_code")
        raise FREDApiError(f"FRED error for {series_id}: {message}")

    rows = []
    for item in payload.get("observations") or []:
        raw_value = str(item.get("value", "")).strip()
        if raw_value in ("", "."):
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        raw_date = item.get("date")
        try:
            parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        rows.append({"Date": parsed_date, "value": value})

    df = pd.DataFrame(rows, columns=["Date", "value"])
    _cache_set(key, df)
    return df


def get_fred_latest_window(
    series_ids: Iterable[str],
    trade_date: str,
    *,
    lookback_days: int = 120,
) -> dict[str, pd.DataFrame]:
    """Fetch a lookback window for multiple series.

    Individual series failures are logged and omitted so optional overseas
    enrichment can degrade without breaking the main Korea-market packet.
    """
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    frames: dict[str, pd.DataFrame] = {}

    for series_id in series_ids:
        try:
            frames[series_id] = get_fred_series(series_id, start_date, trade_date)
        except Exception as exc:
            logger.warning("FRED series %s skipped: %s", series_id, exc)

    return frames
