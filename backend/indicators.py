"""Technical indicators (pure pandas). Output is tagged by chart pane.

Indicator math mirrors the specs in Claude_database/finance/technical-indicators.md.
"""

from __future__ import annotations

import pandas as pd

from backend.schema import IndicatorLine, IndicatorsResponse, LinePoint
from backend.sources import get_ohlcv_df

DEFAULT_NAMES = ("ma", "bb", "macd", "rsi")


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def bollinger(close: pd.Series, window: int = 20, k: float = 2.0):
    mid = sma(close, window)
    sd = close.rolling(window).std()
    return mid + k * sd, mid, mid - k * sd


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(
        axis=1
    )
    return tr.rolling(window).mean()


def _line(
    name: str, pane: str, series: pd.Series, index: pd.DatetimeIndex
) -> IndicatorLine:
    pts: list[LinePoint] = []
    for ts, v in series.items():
        if pd.notna(v):
            pts.append(LinePoint(time=ts.strftime("%Y-%m-%d"), value=float(v)))
    return IndicatorLine(name=name, pane=pane, data=pts)


def compute_indicators(
    symbol: str, period: str, interval: str, names: tuple[str, ...] | None = None
) -> IndicatorsResponse:
    names = names or DEFAULT_NAMES
    df = get_ohlcv_df(symbol, period, interval)
    lines: list[IndicatorLine] = []
    if df.empty:
        return IndicatorsResponse(symbol=symbol, lines=lines)
    close, idx = df["Close"], df.index

    if "ma" in names:
        for w, nm in ((20, "MA20"), (60, "MA60"), (120, "MA120")):
            lines.append(_line(nm, "price", sma(close, w), idx))
    if "ema" in names:
        for w, nm in ((12, "EMA12"), (26, "EMA26")):
            lines.append(_line(nm, "price", ema(close, w), idx))
    if "bb" in names:
        up, mid, low = bollinger(close)
        lines.append(_line("BB_upper", "price", up, idx))
        lines.append(_line("BB_mid", "price", mid, idx))
        lines.append(_line("BB_lower", "price", low, idx))
    if "macd" in names:
        line, sig, hist = macd(close)
        lines.append(_line("MACD", "macd", line, idx))
        lines.append(_line("Signal", "macd", sig, idx))
        lines.append(_line("Hist", "macd", hist, idx))
    if "rsi" in names:
        lines.append(_line("RSI", "rsi", rsi(close), idx))
    if "atr" in names:
        lines.append(_line("ATR", "atr", atr(df), idx))

    return IndicatorsResponse(symbol=symbol, lines=lines)
