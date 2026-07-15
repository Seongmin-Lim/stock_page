"""KIS Developers OpenAPI client for optional broker integration.

The integration is inactive until KIS_APP_KEY and KIS_APP_SECRET are configured.
Without them, every public call degrades gracefully so the rest of the application
continues to work with its key-free data sources. Domestic quotes are implemented;
account, order, WebSocket, and US-market calls remain future work.
"""

from __future__ import annotations

import time

import requests

from backend import config

_REAL = "https://openapi.koreainvestment.com:9443"
_MOCK = "https://openapivts.koreainvestment.com:29443"
_TOKEN_EXPIRY_MARGIN_SECONDS = 300.0

_token_value: str | None = None
_token_expires_at = 0.0


def base_url() -> str:
    """Return the configured real or mock KIS API base URL."""
    return _MOCK if config.KIS_MOCK else _REAL


def available() -> bool:
    """Return whether the minimum KIS credentials are configured."""
    return config.has_kis()


def _get_token() -> str | None:
    """Return a cached OAuth token, or ``None`` when issuance fails."""
    global _token_expires_at, _token_value

    if not available():
        return None

    now = time.time()
    if _token_value is not None and now < _token_expires_at:
        return _token_value

    try:
        # KIS rejects rapid token re-issuance (roughly within one minute), so a
        # valid token is always reused and refreshed only after its safe expiry.
        response = requests.post(
            f"{base_url()}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": config.KIS_APP_KEY,
                "appsecret": config.KIS_APP_SECRET,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            return None
        expires_in = float(data.get("expires_in", 86400))
        _token_value = token
        _token_expires_at = now + max(
            0.0, expires_in - _TOKEN_EXPIRY_MARGIN_SECONDS
        )
        return token
    except Exception:  # noqa: BLE001 - optional integration must remain non-fatal
        return None


def _headers(tr_id: str) -> dict[str, str] | None:
    """Build authenticated headers for one KIS transaction ID."""
    token = _get_token()
    if token is None:
        return None
    return {
        "authorization": f"Bearer {token}",
        "appkey": config.KIS_APP_KEY or "",
        "appsecret": config.KIS_APP_SECRET or "",
        "tr_id": tr_id,
        "content-type": "application/json",
    }


def quote(symbol: str) -> dict[str, float] | None:
    """Fetch a domestic stock quote and normalize its numeric fields."""
    headers = _headers("FHKST01010100")
    if headers is None:
        return None
    try:
        # KIS applies per-second limits (EGW00201). Add a tiny courtesy sleep or
        # retry/backoff hook here if this call becomes part of a batch workflow.
        response = requests.get(
            f"{base_url()}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=headers,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        output = data.get("output")
        if not isinstance(output, dict):
            return None
        return {
            "price": float(output["stck_prpr"]),
            "high": float(output["stck_hgpr"]),
            "low": float(output["stck_lwpr"]),
            "volume": float(output["acml_vol"]),
        }
    except Exception:  # noqa: BLE001 - quote failure must degrade gracefully
        return None


def status() -> dict[str, object]:
    """Return the lightweight KIS configuration and connection status."""
    if not available():
        return {
            "configured": False,
            "mock": config.KIS_MOCK,
            "connected": False,
            "account": config.KIS_ACCOUNT,
            "message": (
                "KIS API 키가 설정되지 않았습니다. "
                ".env에 KIS_APP_KEY/KIS_APP_SECRET를 입력하세요."
            ),
        }

    connected = _get_token() is not None
    return {
        "configured": True,
        "mock": config.KIS_MOCK,
        "connected": connected,
        "account": config.KIS_ACCOUNT,
        "message": (
            "KIS OpenAPI 연결됨"
            + (" (모의투자)" if config.KIS_MOCK else " (실거래)")
            if connected
            else "KIS 토큰 발급에 실패했습니다. 키와 네트워크 상태를 확인하세요."
        ),
    }


# Future integrations:
# def balance() -> dict[str, object] | None: ...
# def order(...) -> dict[str, object] | None: ...
# def websocket(...) -> None: ...
# def us_quote(symbol: str) -> dict[str, float] | None: ...  # TODO: confirm tr_id
