"""Kiwoom REST OpenAPI client (https://openapi.kiwoom.com).

Skeleton built on the standard OAuth2 token pattern (same shape as KIS). It is INACTIVE
until KIWOOM_APP_KEY / KIWOOM_APP_SECRET land in .env — every call degrades gracefully so
the rest of the app keeps working key-free.

⚠️ Endpoint paths / TR ids / field names below are placeholders to be confirmed against the
official Kiwoom REST docs once the keys arrive (api-id, request/response JSON schema). The
auth flow and structure follow Kiwoom's published REST spec; fill `_TR` + parsing then.
"""

from __future__ import annotations

import time

from backend import config

_REAL = "https://api.kiwoom.com"
_MOCK = "https://mockapi.kiwoom.com"

# token cache (in-memory)
_token: dict[str, float | str | None] = {"value": None, "expires": 0.0}


def base_url() -> str:
    return _MOCK if config.KIWOOM_MOCK else _REAL


def available() -> bool:
    return config.has_kiwoom()


def _get_token() -> str | None:
    """OAuth2 client_credentials token, cached until ~expiry. None if no keys/blocked."""
    if not available():
        return None
    now = time.time()
    if _token["value"] and now < float(_token["expires"]):
        return str(_token["value"])
    try:
        import requests

        r = requests.post(
            f"{base_url()}/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "appkey": config.KIWOOM_APP_KEY,
                "secretkey": config.KIWOOM_APP_SECRET,
            },
            timeout=10,
        )
        data = r.json()
        tok = data.get("token") or data.get("access_token")
        if not tok:
            return None
        # expires_dt (e.g. seconds) — default 1h, refresh 5min early
        ttl = float(data.get("expires_in", 3600))
        _token["value"] = tok
        _token["expires"] = now + max(60.0, ttl - 300.0)
        return str(tok)
    except Exception:  # noqa: BLE001 - auth optional; keep app alive
        return None


def _headers(api_id: str) -> dict[str, str] | None:
    tok = _get_token()
    if not tok:
        return None
    return {
        "authorization": f"Bearer {tok}",
        "appkey": config.KIWOOM_APP_KEY or "",
        "secretkey": config.KIWOOM_APP_SECRET or "",
        "api-id": api_id,  # TR code — confirm per endpoint from official docs
        "content-type": "application/json;charset=UTF-8",
    }


def status() -> dict:
    """Lightweight status for the UI: configured? mock? token obtainable?"""
    if not available():
        return {
            "configured": False,
            "mock": config.KIWOOM_MOCK,
            "connected": False,
            "message": "키움 API 키가 설정되지 않았습니다. .env에 KIWOOM_APP_KEY/SECRET를 넣으세요.",
        }
    ok = _get_token() is not None
    return {
        "configured": True,
        "mock": config.KIWOOM_MOCK,
        "connected": ok,
        "account": config.KIWOOM_ACCOUNT,
        "message": (
            "키움 REST 연결됨" + (" (모의투자)" if config.KIWOOM_MOCK else " (실거래)")
        )
        if ok
        else "키 설정됨 — 토큰 발급 실패(키/네트워크 확인 또는 엔드포인트 확정 필요).",
    }


# ── data calls (to be wired once docs/keys are confirmed) ─────────────
# def quote(symbol: str) -> dict: ...        # 주식 현재가
# def daily_ohlcv(symbol: str) -> list: ...  # 일봉
# def balance() -> dict: ...                 # 계좌 잔고
# def order(...) -> dict: ...                # 주문 (실계좌 — 확인 후 신중히)
