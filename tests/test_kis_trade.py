"""Network-free tests for the domestic KIS trading layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend import config, kis_trade
from backend.schema import KisOrderRequest


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> None:
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _configure(monkeypatch: pytest.MonkeyPatch, *, mock: bool) -> None:
    monkeypatch.setattr(config, "KIS_MOCK", mock)
    monkeypatch.setattr(config, "KIS_ALLOW_REAL_ORDERS", False)
    monkeypatch.setattr(config, "KIS_ACCOUNT", "12345678-01")
    monkeypatch.setattr(kis_trade.kis, "_headers", lambda tr_id: {"tr_id": tr_id})


def test_real_order_is_refused_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, mock=False)
    called = False

    def fail_post(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal called
        called = True
        raise AssertionError("HTTP must not be called")

    monkeypatch.setattr(kis_trade.requests, "post", fail_post)
    result = kis_trade.order_cash("005930", 1, 70000.0, "limit", "buy")

    assert result["ok"] is False
    assert "KIS_ALLOW_REAL_ORDERS=true" in str(result["message"])
    assert called is False


def test_mock_buy_builds_payload_and_parses_order_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, mock=True)
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
        timeout: int,
    ) -> FakeResponse:
        captured.update(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse(
            {
                "rt_cd": "0",
                "msg_cd": "APBK0013",
                "msg1": "주문 전송 완료",
                "output": {"ODNO": "0000123456", "KRX_FWDG_ORD_ORGNO": "91252"},
            }
        )

    monkeypatch.setattr(kis_trade.requests, "post", fake_post)
    result = kis_trade.order_cash("005930", 2, 70100.0, "limit", "buy")

    assert captured["headers"] == {"tr_id": "VTTC0012U"}
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["ORD_QTY"] == "2"
    assert body["ORD_UNPR"] == "70100"
    assert body["EXCG_ID_DVSN_CD"] == "KRX"
    assert result["ok"] is True
    assert result["order_no"] == "0000123456"


def test_balance_concatenates_tr_cont_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, mock=True)
    pages = iter(
        [
            FakeResponse(
                {
                    "rt_cd": "0",
                    "output1": [
                        {"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "2"}
                    ],
                    "output2": [{"dnca_tot_amt": "1000", "tot_evlu_amt": "3000"}],
                    "ctx_area_fk100": "NEXT-FK",
                    "ctx_area_nk100": "NEXT-NK",
                },
                {"tr_cont": "M"},
            ),
            FakeResponse(
                {
                    "rt_cd": "0",
                    "output1": [
                        {"pdno": "000660", "prdt_name": "SK하이닉스", "hldg_qty": "1"}
                    ],
                    "output2": [{"dnca_tot_amt": "1000", "tot_evlu_amt": "3000"}],
                    "ctx_area_fk100": "",
                    "ctx_area_nk100": "",
                }
            ),
        ]
    )
    params_seen: list[dict[str, str]] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeResponse:
        params_seen.append(params)
        return next(pages)

    monkeypatch.setattr(kis_trade.requests, "get", fake_get)
    result = kis_trade.account()

    positions = result["positions"]
    assert isinstance(positions, list)
    symbols = []
    for position in positions:
        assert isinstance(position, dict)
        symbols.append(position["symbol"])
    assert symbols == ["005930", "000660"]
    assert params_seen[1]["CTX_AREA_FK100"] == "NEXT-FK"
    assert params_seen[1]["CTX_AREA_NK100"] == "NEXT-NK"


def test_order_api_error_surfaces_msg1(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, mock=True)
    monkeypatch.setattr(
        kis_trade.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {"rt_cd": "1", "msg_cd": "ERROR", "msg1": "주문 가능 수량 초과"}
        ),
    )
    result = kis_trade.order_cash("005930", 99, None, "market", "buy")

    assert result["ok"] is False
    assert result["message"] == "주문 가능 수량 초과"


@pytest.mark.parametrize(
    ("symbol", "qty"),
    [("5930", 1), ("ABCDEF", 1), ("005930", 0)],
)
def test_order_schema_rejects_bad_symbol_or_qty(symbol: str, qty: int) -> None:
    with pytest.raises(ValidationError):
        KisOrderRequest(
            symbol=symbol,
            qty=qty,
            side="buy",
            order_type="market",
        )
