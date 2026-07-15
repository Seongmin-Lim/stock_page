"""Screener regression tests with network-free snapshot fixtures."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import screener
from backend.schema import ScreenFilter, ScreenSpec
from backend.server import app


def _snapshot(market: str = "US") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "LOW",
                "name": "Low",
                "market": market,
                "sector": "기술",
                "price": 10.0 if market == "KR" else None,
                "marketcap": 100.0 if market == "KR" else None,
                "change_pct": 0.0,
            },
            {
                "symbol": "HIGH",
                "name": "High",
                "market": market,
                "sector": "금융",
                "price": 100.0 if market == "KR" else None,
                "marketcap": 1_000.0 if market == "KR" else None,
                "change_pct": 0.0,
            },
        ]
    )


@pytest.mark.parametrize(
    ("field", "threshold"),
    [("price", 50.0), ("marketcap", 500.0)],
)
def test_us_enriched_cheap_filters_are_applied(
    monkeypatch: pytest.MonkeyPatch, field: str, threshold: float
) -> None:
    monkeypatch.setattr(screener, "_us_snapshot", _snapshot)
    monkeypatch.setattr(
        screener,
        "_us_fund_row",
        lambda symbol: {
            "per": 10.0,
            "pbr": 1.0,
            "roe": 12.0,
            "price": 10.0 if symbol == "LOW" else 100.0,
            "marketcap": 100.0 if symbol == "LOW" else 1_000.0,
        },
    )

    result = screener.run_screen(
        ScreenSpec(
            market="US",
            filters=[ScreenFilter(field=field, op="gt", value=threshold)],
        )
    )

    assert [row.symbol for row in result.rows] == ["HIGH"]


def test_kr_dividend_filter_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screener, "_kr_snapshot", lambda: _snapshot("KR"))
    monkeypatch.setattr(
        screener,
        "_kr_fund_row",
        lambda symbol, marketcap: {
            "per": 10.0,
            "pbr": 1.0,
            "roe": 12.0,
            "div": 1.0 if symbol == "LOW" else 3.0,
        },
    )

    result = screener.run_screen(
        ScreenSpec(
            market="KR",
            filters=[ScreenFilter(field="div", op="gt", value=2.0)],
        )
    )

    assert [(row.symbol, row.div) for row in result.rows] == [("HIGH", 3.0)]


def test_us_dividend_filter_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screener, "_us_snapshot", _snapshot)
    monkeypatch.setattr(
        screener,
        "_us_fund_row",
        lambda symbol: {
            "price": 10.0,
            "marketcap": 100.0,
            "div": 1.0 if symbol == "LOW" else 3.0,
        },
    )

    result = screener.run_screen(
        ScreenSpec(
            market="US",
            filters=[ScreenFilter(field="div", op="gt", value=2.0)],
        )
    )

    assert [(row.symbol, row.div) for row in result.rows] == [("HIGH", 3.0)]


def test_us_fund_row_reuses_dividend_unit_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticker = SimpleNamespace(
        info={
            "currentPrice": 50.0,
            "marketCap": 1_000.0,
            "trailingAnnualDividendYield": 0.025,
        }
    )
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        SimpleNamespace(Ticker=lambda symbol: ticker),
    )

    assert screener._us_fund_row("TEST")["div"] == 2.5


@pytest.mark.parametrize(
    "filter_data",
    [
        {"field": "not_a_field", "op": "gt", "value": 1.0},
        {"field": "per", "op": "not_an_op", "value": 1.0},
    ],
)
def test_unknown_filter_contract_is_rejected(filter_data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ScreenSpec(filters=[filter_data])


@pytest.mark.parametrize("key", ["field", "op"])
def test_unknown_filter_returns_http_422(key: str) -> None:
    filter_data = {"field": "per", "op": "gt", "value": 1.0}
    filter_data[key] = "unsupported"

    response = TestClient(app).post(
        "/api/screener",
        json={"market": "KR", "filters": [filter_data]},
    )

    assert response.status_code == 422


def test_unmatched_sector_returns_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screener, "_kr_snapshot", lambda: _snapshot("KR"))

    result = screener.run_screen(ScreenSpec(market="KR", sector="없는업종"))

    assert result.rows == []
    assert result.scanned == 2
    assert result.note is not None
    assert "없는업종" in result.note
    assert "일치하는 종목" in result.note


def test_filter_value_shapes_are_validated() -> None:
    with pytest.raises(ValidationError):
        ScreenFilter(field="per", op="between", value=1.0)
    with pytest.raises(ValidationError):
        ScreenFilter(field="per", op="true")
    with pytest.raises(ValidationError):
        ScreenFilter(field="above_ma200", op="true", value=2.0)
    ScreenFilter(field="above_ma200", op="true", value=1.0)
    with pytest.raises(ValidationError):
        ScreenSpec(limit=0)


@pytest.mark.parametrize(
    "spec_data",
    [{"market": "JP"}, {"mode": "maybe"}, {"limit": 101}],
)
def test_screen_spec_contract_is_rejected(spec_data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ScreenSpec(**spec_data)


def test_us_cap_reports_actual_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = pd.DataFrame(
        {
            "symbol": [f"S{i:03d}" for i in range(125)],
            "name": [f"Stock {i}" for i in range(125)],
            "market": "US",
            "sector": "기술",
        }
    )
    monkeypatch.setattr(screener, "_us_snapshot", lambda: snapshot)
    monkeypatch.setattr(
        screener,
        "_us_fund_row",
        lambda symbol: {"price": 10.0, "marketcap": 100.0},
    )

    result = screener.run_screen(ScreenSpec(market="US", limit=100))

    assert result.scanned == 120
    assert result.note is not None
    assert "120" in result.note
