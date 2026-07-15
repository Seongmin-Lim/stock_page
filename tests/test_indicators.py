"""Pure-function tests — no network, no data libraries needed."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.indicators import bollinger, ema, macd, rsi, sma


def _close() -> pd.Series:
    rng = np.random.default_rng(0)
    return pd.Series(100 + np.cumsum(rng.normal(0, 1, 300)))


def test_sma_window():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert out.iloc[2] == 2.0
    assert out.iloc[4] == 4.0
    assert pd.isna(out.iloc[0])


def test_ema_len():
    s = _close()
    assert len(ema(s, 12)) == len(s)


def test_rsi_bounds():
    r = rsi(_close()).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_macd_shapes():
    line, sig, hist = macd(_close())
    assert len(line) == len(sig) == len(hist)
    assert np.allclose((line - sig).dropna(), hist.dropna())


def test_bollinger_order():
    up, mid, low = bollinger(_close())
    valid = up.dropna().index
    assert (up.loc[valid] >= mid.loc[valid]).all()
    assert (mid.loc[valid] >= low.loc[valid]).all()
