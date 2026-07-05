from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import requests

KST = timezone(timedelta(hours=9))


class KISAuthError(RuntimeError):
    pass


@dataclass
class KISToken:
    access_token: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return datetime.now(KST) < (self.expires_at - timedelta(minutes=10))


class KISAuthManager:
    """Handles KIS access token issuance and reuse for downstream REST calls."""

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_path: Optional[str] = None,
    ) -> None:
        self.app_key = app_key or os.getenv("KIS_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("KIS_APP_SECRET", "")
        self.base_url = base_url or "https://openapi.koreainvestment.com:9443"
        self.cache_path = Path(
            cache_path
            or os.getenv(
                "KIS_TOKEN_CACHE_PATH",
                str(Path.home() / ".tradingagents-korea" / "kis-token.json"),
            )
        )
        self._lock = threading.Lock()

    def _ensure_credentials(self) -> None:
        if not self.app_key or not self.app_secret:
            raise KISAuthError(
                "KIS credentials are missing. Set KIS_APP_KEY and KIS_APP_SECRET."
            )

    def _load_cached_token(self) -> Optional[KISToken]:
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
            token = KISToken(
                access_token=data["access_token"],
                expires_at=datetime.fromisoformat(data["expires_at"]),
            )
            return token if token.is_valid else None
        except Exception:
            return None

    def _save_token(self, token: KISToken) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {
                    "access_token": token.access_token,
                    "expires_at": token.expires_at.isoformat(),
                    "saved_at": datetime.now(KST).isoformat(),
                    "base_url": self.base_url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def issue_token(self) -> KISToken:
        self._ensure_credentials()
        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "TradingAgents-Korea/0.1",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            raise KISAuthError(
                f"Failed to issue KIS token: HTTP {resp.status_code} {resp.text}"
            )
        data = resp.json()
        token = data.get("access_token")
        expires_raw = data.get("access_token_token_expired")
        if not token or not expires_raw:
            raise KISAuthError("KIS token response missing access_token or expiry")
        expires_at = datetime.strptime(expires_raw, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=KST
        )
        token_obj = KISToken(access_token=token, expires_at=expires_at)
        self._save_token(token_obj)
        return token_obj

    def get_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if not force_refresh:
                cached = self._load_cached_token()
                if cached and cached.is_valid:
                    return cached.access_token
            return self.issue_token().access_token

    def build_headers(
        self,
        tr_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        token = self.get_token(force_refresh=force_refresh)
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "user-agent": "TradingAgents-Korea/0.1",
        }
        if tr_id:
            headers["tr_id"] = tr_id
        if extra_headers:
            headers.update(extra_headers)
        return headers


_default_manager: Optional[KISAuthManager] = None


def get_kis_auth_manager() -> KISAuthManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = KISAuthManager()
    return _default_manager
