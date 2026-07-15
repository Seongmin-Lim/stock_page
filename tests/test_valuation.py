"""DCF valuation tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.fundamentals import run_dcf
from backend.schema import DCFRequest


def test_dcf_basic():
    req = DCFRequest(
        symbol="X",
        fcf=1000.0,
        growth=0.08,
        years=5,
        terminal_growth=0.025,
        wacc=0.09,
        net_debt=0.0,
        shares=100.0,
    )
    r = run_dcf(req)
    assert r.enterprise_value > 0
    assert r.fair_value_per_share == pytest.approx(r.equity_value / 100.0)
    assert r.pv_terminal > r.pv_explicit  # terminal usually dominates


def test_dcf_net_debt_reduces_equity():
    base = DCFRequest(symbol="X", fcf=1000.0, shares=100.0)
    levered = DCFRequest(symbol="X", fcf=1000.0, shares=100.0, net_debt=5000.0)
    assert run_dcf(levered).equity_value < run_dcf(base).equity_value


def test_dcf_rejects_bad_wacc():
    with pytest.raises(HTTPException):
        run_dcf(DCFRequest(symbol="X", fcf=1000.0, wacc=0.02, terminal_growth=0.03))
