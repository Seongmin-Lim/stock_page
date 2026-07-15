"""Network-free regression tests for batch fetch fan-out and caching."""

from __future__ import annotations

import sys
import time
from collections import Counter
from collections.abc import Callable
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

import backend.cycles as cycles
import backend.recommend as recommend
import backend.scanner as scanner
import backend.sources as sources
import backend.universe as universe


def _fake_metrics(symbol: str) -> dict[str, float | None]:
    score = float(ord(symbol[-1]))
    return {
        "price": score,
        "change_pct": 1.0,
        "per": 10.0,
        "pbr": 1.0,
        "roe": 12.0,
        "rev_growth": 8.0,
        "op_margin": 15.0,
        "debt_ratio": 30.0,
        "ret_1y": score,
        "ret_3m": 4.0,
        "prox52": 80.0,
        "above200": 5.0,
        "vol_ratio": 1.2,
        "reclaimed_200": 1.0,
        "momentum": score,
        "trend": 60.0,
        "value": 55.0,
        "quality": 65.0,
        "financial": 70.0,
        "reversal": 75.0,
    }


def _small_recommend_build(
    monkeypatch: pytest.MonkeyPatch,
    max_workers: int,
    failing_symbol: str | None = None,
) -> tuple[dict[str, object], Counter[str]]:
    buckets = [
        ("bluechip", {"AAA": "Alpha", "BBB": "Beta", "BAD": "Bad"}),
        ("value", {"BBB": "Beta", "CCC": "Gamma"}),
    ]
    calls: Counter[str] = Counter()
    delays = {"AAA": 0.03, "BBB": 0.01, "BAD": 0.02, "CCC": 0.0}

    def produce(
        symbol: str, market: str, kr_snap: pd.DataFrame
    ) -> dict[str, float | None] | None:
        del market, kr_snap
        calls[symbol] += 1
        time.sleep(delays[symbol])
        if symbol == failing_symbol:
            raise RuntimeError("injected failure")
        return _fake_metrics(symbol)

    monkeypatch.setitem(recommend._BUCKETS, "US", buckets)
    monkeypatch.setattr(recommend, "_metrics", produce)
    monkeypatch.setattr(universe, "sector_of", lambda symbol, market: "test")
    return recommend._build("US", max_workers=max_workers), calls


def test_recommend_fetches_each_unique_symbol_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls = _small_recommend_build(monkeypatch, max_workers=5)

    assert result["categories"]
    assert calls == Counter({"AAA": 1, "BBB": 1, "BAD": 1, "CCC": 1})


def test_recommend_skips_one_failing_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    result, calls = _small_recommend_build(
        monkeypatch, max_workers=5, failing_symbol="BAD"
    )

    symbols = {
        pick["symbol"]
        for category in result["categories"]
        for pick in category["picks"]
    }
    assert calls["BAD"] == 1
    assert "BAD" not in symbols
    assert symbols == {"AAA", "BBB", "CCC"}


def test_recommend_parallel_output_matches_serial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serial, _ = _small_recommend_build(monkeypatch, max_workers=1)
    parallel, _ = _small_recommend_build(monkeypatch, max_workers=5)
    serial["generated"] = "stable"
    parallel["generated"] = "stable"

    assert parallel == serial


def test_kr_fundamental_snapshot_produced_once_for_many_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Counter[str] = Counter()
    frame = pd.DataFrame(
        {
            "PER": [10.0, 11.0, 12.0],
            "PBR": [1.0, 1.1, 1.2],
            "EPS": [100.0, 110.0, 120.0],
            "BPS": [1000.0, 1000.0, 1000.0],
            "DIV": [2.0, 2.1, 2.2],
            "DPS": [20.0, 21.0, 22.0],
        },
        index=["000001", "000002", "000003"],
    )
    stock = SimpleNamespace(
        get_nearest_business_day_in_a_week=lambda: "20260715",
        get_market_fundamental_by_ticker=lambda date, market: (
            calls.update([market]) or frame.copy()
        ),
    )
    pykrx = ModuleType("pykrx")
    pykrx.stock = stock
    cached: dict[str, pd.DataFrame] = {}

    def fake_cache_df(
        key: str, ttl_sec: float, producer: Callable[[], pd.DataFrame]
    ) -> pd.DataFrame:
        del ttl_sec
        if key not in cached:
            cached[key] = producer()
        return cached[key]

    monkeypatch.setitem(sys.modules, "pykrx", pykrx)
    monkeypatch.setattr(sources, "cache_df", fake_cache_df)
    monkeypatch.setattr(sources, "_KR_FUND_SNAPSHOTS", {})

    rows = [sources._kr_fundamentals(symbol) for symbol in frame.index]

    assert all(row for row in rows)
    assert calls == Counter({"KOSPI": 1})


def test_us_info_is_shared_by_recommend_and_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = {"sector": "Technology", "trailingPE": 20.0}
    monkeypatch.setattr(sources, "get_us_info", lambda symbol: info)

    assert recommend._us_fundamentals("AAA")["per"] == 20.0
    assert universe.sector_of("AAA", "US") == "IT·기술"


def test_scanner_parallel_output_matches_serial_and_skips_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = {"AAA": 0.03, "BBB": 0.01, "BAD": 0.02, "CCC": 0.0}

    def reversal_inputs(symbol: str) -> dict[str, float | bool | None]:
        time.sleep(delays[symbol])
        if symbol == "BAD":
            raise RuntimeError("injected failure")
        return {
            "ret_1y": -10.0,
            "ret_3m": float(ord(symbol[-1]) % 10),
            "prox52": 70.0,
            "above200": 1.0,
            "reclaimed_200": True,
            "vol_ratio": 1.2,
        }

    def metrics(
        symbol: str, market: str, kr_snap: pd.DataFrame
    ) -> dict[str, float | None]:
        del market, kr_snap
        time.sleep(delays[symbol])
        return _fake_metrics(symbol)

    monkeypatch.setattr(scanner, "kr_listing_snapshot", pd.DataFrame)
    monkeypatch.setattr(
        scanner, "_stage1_pool", lambda market, snap: ["AAA", "BBB", "BAD", "CCC"]
    )
    monkeypatch.setattr(scanner, "_reversal_inputs", reversal_inputs)
    monkeypatch.setattr(scanner, "_metrics", metrics)
    monkeypatch.setattr(scanner, "name_of", lambda symbol: symbol)
    monkeypatch.setattr(scanner, "sector_of", lambda symbol, market: "test")

    serial = scanner._build("US", max_workers=1)
    parallel = scanner._build("US", max_workers=5)
    serial["generated"] = "stable"
    parallel["generated"] = "stable"

    assert parallel == serial
    assert parallel["scanned"] == 3
    assert "BAD" not in {pick["symbol"] for pick in parallel["picks"]}


def test_cycles_parallel_output_matches_serial_and_skips_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    members = ["AAA", "BBB", "BAD", "CCC"]
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    delays = {"AAA": 0.03, "BBB": 0.01, "BAD": 0.02, "CCC": 0.0}

    def history(symbol: str, period: str, interval: str) -> pd.DataFrame:
        del period, interval
        if symbol == "US500":
            return pd.DataFrame({"Close": range(100, 360)}, index=dates)
        time.sleep(delays[symbol])
        if symbol == "BAD":
            raise RuntimeError("injected failure")
        offset = ord(symbol[-1]) % 5
        return pd.DataFrame(
            {"Close": [float(value + offset) for value in range(100, 360)]},
            index=dates,
        )

    def metrics(
        symbol: str, market: str, kr_snap: pd.DataFrame | None
    ) -> dict[str, float | None]:
        del market, kr_snap
        time.sleep(delays[symbol])
        if symbol == "BAD":
            raise RuntimeError("injected failure")
        return _fake_metrics(symbol)

    monkeypatch.setitem(cycles._THEMES, "US", [("test", "Test", members)])
    monkeypatch.setattr(cycles, "get_ohlcv_df", history)
    monkeypatch.setattr(recommend, "_metrics", metrics)
    monkeypatch.setattr(universe, "name_of", lambda symbol: symbol)

    serial = cycles._build("US", max_workers=1)
    parallel = cycles._build("US", max_workers=5)
    serial["generated"] = "stable"
    parallel["generated"] = "stable"

    assert parallel == serial
    assert len(parallel["themes"]) == 1
    assert "BAD" not in parallel["themes"][0]["leaders"]
