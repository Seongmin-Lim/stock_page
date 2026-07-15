"""Network-free tests for the optional KIS OpenAPI integration."""

from __future__ import annotations

import pytest
import requests

from backend import config, kis


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _configure(monkeypatch: pytest.MonkeyPatch, *, mock: bool = False) -> None:
    monkeypatch.setattr(config, "KIS_APP_KEY", "test-key")
    monkeypatch.setattr(config, "KIS_APP_SECRET", "test-secret")
    monkeypatch.setattr(config, "KIS_MOCK", mock)


def _clear_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kis, "_token_value", None)
    monkeypatch.setattr(kis, "_token_expires_at", 0.0)


def test_no_keys_are_unavailable_with_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "KIS_APP_KEY", None)
    monkeypatch.setattr(config, "KIS_APP_SECRET", None)
    monkeypatch.setattr(config, "KIS_ACCOUNT", None)

    result = kis.status()

    assert kis.available() is False
    assert result["configured"] is False
    assert "KIS" in str(result["message"])
    assert "KIS_APP_KEY/KIS_APP_SECRET" in str(result["message"])


def test_token_is_cached_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    _clear_token(monkeypatch)
    calls = 0

    def fake_post(
        url: str, *, json: dict[str, str | None], timeout: int
    ) -> _Response:
        nonlocal calls
        calls += 1
        return _Response({"access_token": "cached-token", "expires_in": 86400})

    monkeypatch.setattr(kis.requests, "post", fake_post)

    assert kis._get_token() == "cached-token"
    assert kis._get_token() == "cached-token"
    assert calls == 1


def test_quote_parses_domestic_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis, "_headers", lambda tr_id: {"tr_id": tr_id})

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> _Response:
        return _Response(
            {
                "output": {
                    "stck_prpr": "73500",
                    "stck_hgpr": "74100",
                    "stck_lwpr": "72800",
                    "acml_vol": "1234567",
                }
            }
        )

    monkeypatch.setattr(kis.requests, "get", fake_get)

    assert kis.quote("005930") == {
        "price": 73500.0,
        "high": 74100.0,
        "low": 72800.0,
        "volume": 1234567.0,
    }


def test_quote_returns_none_on_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis, "_headers", lambda tr_id: {"tr_id": tr_id})

    def fail_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> _Response:
        raise requests.RequestException("offline")

    monkeypatch.setattr(kis.requests, "get", fail_get)

    assert kis.quote("005930") is None


def test_mock_switches_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "KIS_MOCK", False)
    assert kis.base_url() == "https://openapi.koreainvestment.com:9443"

    monkeypatch.setattr(config, "KIS_MOCK", True)
    assert kis.base_url() == "https://openapivts.koreainvestment.com:29443"
