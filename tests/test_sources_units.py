"""Unit-normalization tests for market data sources."""

from __future__ import annotations

import pytest

from backend.sources import _div_yield_pct


def test_div_yield_pct_from_trailing_ratio():
    assert _div_yield_pct({"trailingAnnualDividendYield": 0.0245}) == pytest.approx(2.45)


def test_div_yield_pct_falls_back_to_percent_value():
    info = {"trailingAnnualDividendYield": None, "dividendYield": 2.52}
    assert _div_yield_pct(info) == pytest.approx(2.52)


def test_div_yield_pct_missing_values():
    assert _div_yield_pct({}) is None
