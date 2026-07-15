"""Position sizing / risk calculator tests — pure math, no network (symbol=None)."""

from __future__ import annotations

import math

import pytest
from fastapi import HTTPException

from backend.schema import PositionRequest
from backend.trade import size_position


def test_shares_from_risk_amount_pct_stop():
    # account 10M, risk 1% → risk_amount 100k. entry 100, 5% stop → risk/share 5.
    req = PositionRequest(
        account=10_000_000.0,
        risk_pct=1.0,
        entry=100.0,
        stop_mode="pct",
        stop_pct=5.0,
        rr=2.0,
        direction="long",
    )
    r = size_position(req)
    assert r.risk_amount == pytest.approx(100_000.0)
    assert r.risk_per_share == pytest.approx(5.0)
    assert r.shares == math.floor(100_000.0 / 5.0)  # 20000
    assert r.stop == pytest.approx(95.0)
    assert r.target == pytest.approx(110.0)  # entry + rr*risk = 100 + 2*5


def test_price_stop_mode_long():
    req = PositionRequest(
        account=1_000_000.0,
        risk_pct=2.0,
        entry=50.0,
        stop_mode="price",
        stop_price=45.0,
        rr=3.0,
    )
    r = size_position(req)
    assert r.risk_per_share == pytest.approx(5.0)
    assert r.risk_amount == pytest.approx(20_000.0)
    assert r.shares == math.floor(20_000.0 / 5.0)
    assert r.target == pytest.approx(65.0)  # 50 + 3*5


def test_short_direction_target_below_entry():
    req = PositionRequest(
        account=1_000_000.0,
        risk_pct=1.0,
        entry=100.0,
        stop_mode="pct",
        stop_pct=10.0,
        rr=2.0,
        direction="short",
    )
    r = size_position(req)
    # short: stop above entry, target below entry
    assert r.stop == pytest.approx(110.0)
    assert r.target < r.entry
    assert r.target == pytest.approx(80.0)  # 100 - 2*10


def test_missing_entry_raises():
    # symbol=None and entry=None → no way to derive a price → 400
    req = PositionRequest(
        account=1_000_000.0, risk_pct=1.0, stop_mode="pct", stop_pct=5.0
    )
    with pytest.raises(HTTPException):
        size_position(req)


def test_invalid_account_raises():
    req = PositionRequest(
        account=0.0, risk_pct=1.0, entry=100.0, stop_mode="pct", stop_pct=5.0
    )
    with pytest.raises(HTTPException):
        size_position(req)
