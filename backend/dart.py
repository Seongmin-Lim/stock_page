"""Korean financial statements via OpenDART (key required, loaded from .env).

Falls back gracefully to empty results when no key / network issue, so the app keeps
working key-free. Used to (a) fill the KR fundamentals tab with real statements and
(b) feed financial factors (growth, margin, leverage, ROE) into the recommender.
"""

from __future__ import annotations

import re

import pandas as pd

from backend.cache import cache_json
from backend.config import DART_API_KEY

_DART_TTL = 60 * 60 * 24 * 7  # 7 days — annual statements rarely change

# DART account_nm → our canonical label (consolidated CFS preferred)
_INCOME = {
    "매출액": "매출액",
    "수익(매출액)": "매출액",
    "영업수익": "매출액",
    "영업이익": "영업이익",
    "영업이익(손실)": "영업이익",
    "당기순이익": "당기순이익",
    "당기순이익(손실)": "당기순이익",
}
_BALANCE = {
    "자산총계": "자산총계",
    "부채총계": "부채총계",
    "자본총계": "자본총계",
}


def _client():
    if not DART_API_KEY:
        return None
    try:
        try:
            from opendartreader import OpenDartReader
        except ImportError:
            import OpenDartReader

        return OpenDartReader(DART_API_KEY)
    except Exception:  # noqa: BLE001
        return None


def recent_disclosures(symbol: str, days: int = 120, limit: int = 15) -> list[dict]:
    """Recent DART filings for a KR stock: [{date, report, rcept_no}]. Cached, key-free-safe."""

    def produce() -> list[dict]:
        from datetime import datetime, timedelta

        dart = _client()
        if dart is None:
            return []
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            dl = dart.list(
                symbol, start=start
            )  # no kind → 전체(정기·주요사항·지분·발행 등)
        except Exception:  # noqa: BLE001
            return []
        if dl is None or len(dl) == 0:
            return []
        rows: list[dict] = []
        for _, r in dl.head(limit).iterrows():
            rows.append(
                {
                    "date": str(r.get("rcept_dt", ""))[:10],
                    "report": str(r.get("report_nm", "")).strip(),
                    "rcept_no": str(r.get("rcept_no", "")),
                }
            )
        return rows

    return cache_json(f"dart-list:{symbol}", 3600, produce)


def _to_num(v: object) -> float | None:
    if v is None:
        return None
    s = re.sub(r"[,\s]", "", str(v))
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _raw_finstate(symbol: str, year: int) -> list[dict]:
    """Return a JSON-able list of {label, account, this, prev, sj_div} rows (CFS)."""
    dart = _client()
    if dart is None:
        return []
    try:
        fs = dart.finstate(symbol, year)
    except Exception:  # noqa: BLE001
        return []
    if fs is None or len(fs) == 0:
        return []
    if "fs_div" in fs.columns and (fs["fs_div"] == "CFS").any():
        fs = fs[fs["fs_div"] == "CFS"]
    cols = {"account_nm", "thstrm_amount", "frmtrm_amount", "sj_div"}
    if not cols.issubset(fs.columns):
        return []
    rows: list[dict] = []
    for _, r in fs.iterrows():
        rows.append(
            {
                "account": str(r["account_nm"]),
                "this": _to_num(r["thstrm_amount"]),
                "prev": _to_num(r.get("frmtrm_amount")),
                "sj_div": str(r.get("sj_div", "")),
            }
        )
    return rows


def finstate_rows(symbol: str, year: int) -> list[dict]:
    return cache_json(
        f"dart:{symbol}:{year}", _DART_TTL, lambda: _raw_finstate(symbol, year)
    )


def _pick(
    rows: list[dict], names: dict[str, str]
) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for r in rows:
        label = names.get(r["account"])
        if label and label not in out:
            out[label] = {"this": r["this"], "prev": r["prev"]}
    return out


def kr_financials(symbol: str, year: int) -> dict:
    """Structured KR financials + derived ratios. Empty dict if unavailable."""
    rows = finstate_rows(symbol, year)
    if not rows:
        return {}
    inc = _pick(rows, _INCOME)
    bal = _pick(rows, _BALANCE)
    rev = inc.get("매출액", {})
    op = inc.get("영업이익", {})
    ni = inc.get("당기순이익", {})
    assets = bal.get("자산총계", {}).get("this")
    liab = bal.get("부채총계", {}).get("this")
    equity = bal.get("자본총계", {}).get("this")

    def ratio(a: float | None, b: float | None) -> float | None:
        return (a / b * 100.0) if (a is not None and b not in (None, 0)) else None

    return {
        "year": year,
        "revenue": rev.get("this"),
        "revenue_prev": rev.get("prev"),
        "operating_income": op.get("this"),
        "net_income": ni.get("this"),
        "assets": assets,
        "liabilities": liab,
        "equity": equity,
        # derived ratios (%)
        "revenue_growth": ratio(
            (rev.get("this") - rev.get("prev"))
            if (rev.get("this") and rev.get("prev"))
            else None,
            rev.get("prev"),
        ),
        "operating_margin": ratio(op.get("this"), rev.get("this")),
        "net_margin": ratio(ni.get("this"), rev.get("this")),
        "debt_ratio": ratio(liab, equity),  # 부채비율
        "roe": ratio(ni.get("this"), equity),  # 당기순이익/자본
    }


def kr_statement_table(symbol: str, year: int) -> tuple[list[str], dict[str, list]]:
    """For the fundamentals tab: 2-year compare of key lines. Returns (periods, {section: rows})."""
    rows = finstate_rows(symbol, year)
    if not rows:
        return [], {}
    periods = [str(year), str(year - 1)]
    income = _pick(rows, _INCOME)
    balance = _pick(rows, _BALANCE)

    def fmt(
        section: dict[str, dict[str, float | None]], order: list[str]
    ) -> list[dict]:
        out = []
        for label in order:
            if label in section:
                out.append(
                    {
                        "label": label,
                        "values": [section[label]["this"], section[label]["prev"]],
                    }
                )
        return out

    return periods, {
        "income": fmt(income, ["매출액", "영업이익", "당기순이익"]),
        "balance": fmt(balance, ["자산총계", "부채총계", "자본총계"]),
    }
