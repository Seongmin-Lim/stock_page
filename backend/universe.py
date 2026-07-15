"""Symbol universe + search (ticker / Korean name / English name).

Listings come from FinanceDataReader (key-free) and are cached daily. `name_of` and
`search` read the cached frames; if listings can't be fetched, they degrade to the raw symbol.
"""

from __future__ import annotations

import pandas as pd

from backend.cache import cache_df
from backend.schema import SearchHit

_UNIVERSE_TTL = 60 * 60 * 12  # 12h
_name_cache: dict[str, str] | None = None
_kr_sector_cache: dict[str, str] | None = None


def _pick(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None


def _load_kr() -> pd.DataFrame:
    def produce() -> pd.DataFrame:
        import FinanceDataReader as fdr

        raw = fdr.StockListing("KRX")
        code = _pick(raw, ["Code", "Symbol", "code"])
        name = _pick(raw, ["Name", "name"])
        if code is None or name is None:
            return pd.DataFrame(columns=["Symbol", "Name", "Market"])
        out = pd.DataFrame(
            {
                "Symbol": raw[code].astype(str).str.zfill(6),
                "Name": raw[name].astype(str),
            }
        )
        out["Market"] = "KR"
        return out.dropna().drop_duplicates("Symbol")

    return cache_df("universe:KR", _UNIVERSE_TTL, produce)


def _load_us() -> pd.DataFrame:
    def produce() -> pd.DataFrame:
        import FinanceDataReader as fdr

        frames: list[pd.DataFrame] = []
        for ex in ("NASDAQ", "NYSE", "AMEX"):
            try:
                raw = fdr.StockListing(ex)
            except Exception:  # noqa: BLE001
                continue
            sym = _pick(raw, ["Symbol", "Code"])
            name = _pick(raw, ["Name"])
            if sym is None or name is None:
                continue
            frames.append(
                pd.DataFrame(
                    {"Symbol": raw[sym].astype(str), "Name": raw[name].astype(str)}
                )
            )
        if not frames:
            return pd.DataFrame(columns=["Symbol", "Name", "Market"])
        out = pd.concat(frames, ignore_index=True)
        out["Market"] = "US"
        return out.dropna().drop_duplicates("Symbol")

    return cache_df("universe:US", _UNIVERSE_TTL, produce)


def _all() -> pd.DataFrame:
    try:
        return pd.concat([_load_kr(), _load_us()], ignore_index=True)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["Symbol", "Name", "Market"])


def _names() -> dict[str, str]:
    global _name_cache
    if _name_cache is None:
        df = _all()
        _name_cache = dict(zip(df["Symbol"], df["Name"])) if not df.empty else {}
    return _name_cache


def name_of(symbol: str) -> str:
    return _names().get(symbol, symbol)


# ── sector classification (key-free) ─────────────────────────────────
# KRX 'Industry' (세분 업종명) → 트레이더용 대분류 섹터. 부분일치 키워드 매핑.
_KR_SECTOR_MAP: list[tuple[tuple[str, ...], str]] = [
    (
        ("반도체", "전자부품", "디스플레이", "표시장치", "특수 목적용 기계"),
        "반도체·전자",
    ),
    (("통신 및 방송 장비", "컴퓨터", "통신장비", "전자제품"), "IT·하드웨어"),
    (("소프트웨어", "정보서비스", "포털", "자료처리", "게임"), "IT·소프트웨어"),
    (("자동차", "차체", "운송장비", "기계"), "자동차·기계"),
    (("금융", "은행", "보험", "증권", "신탁"), "금융"),
    (("의약", "바이오", "생물학", "의료"), "제약·바이오"),
    (("화학", "석유", "정유", "고무", "플라스틱"), "화학·소재"),
    (("철강", "금속", "비금속", "시멘트"), "철강·소재"),
    (("건설", "건축", "토목", "부동산"), "건설·부동산"),
    (("식료품", "음료", "담배", "농업"), "음식료"),
    (("유통", "도매", "소매", "백화점"), "유통·소비재"),
    (("전기", "가스", "발전", "에너지"), "유틸리티·에너지"),
    (("운수", "운송", "항공", "해운", "물류"), "운송·물류"),
    (("섬유", "의복", "화장품"), "소비재"),
    (("엔터", "미디어", "방송", "광고"), "미디어·엔터"),
]


def _classify_kr(industry: str) -> str:
    for keys, label in _KR_SECTOR_MAP:
        if any(k in industry for k in keys):
            return label
    return "기타"


def _kr_sectors() -> dict[str, str]:
    """KR symbol → broad sector, derived from KRX-DESC 'Industry'. Cached daily."""
    global _kr_sector_cache
    if _kr_sector_cache is not None:
        return _kr_sector_cache

    def produce() -> pd.DataFrame:
        import FinanceDataReader as fdr

        raw = fdr.StockListing("KRX-DESC")
        if raw is None or raw.empty or "Code" not in raw.columns:
            return pd.DataFrame(columns=["Symbol", "Sector"])
        ind = raw["Industry"] if "Industry" in raw.columns else raw.get("Sector")
        return pd.DataFrame(
            {
                "Symbol": raw["Code"].astype(str).str.zfill(6),
                "Sector": ind.fillna("").astype(str).map(_classify_kr),
            }
        )

    df = cache_df("kr_sectors", _UNIVERSE_TTL, produce)
    _kr_sector_cache = dict(zip(df["Symbol"], df["Sector"])) if not df.empty else {}
    return _kr_sector_cache


# 영문 섹터 → 한글 (yfinance sector + FDR S&P500 GICS 명칭 모두 커버).
# 단일 소스 — screener._us_snapshot 와 sector_of 가 공통으로 사용한다.
US_SECTOR_KO = {
    # IT
    "Technology": "IT·기술",
    "Information Technology": "IT·기술",
    # 금융
    "Financial Services": "금융",
    "Financials": "금융",
    # 헬스케어
    "Healthcare": "헬스케어",
    "Health Care": "헬스케어",
    # 경기소비재
    "Consumer Cyclical": "경기소비재",
    "Consumer Discretionary": "경기소비재",
    # 필수소비재
    "Consumer Defensive": "필수소비재",
    "Consumer Staples": "필수소비재",
    # 커뮤니케이션
    "Communication Services": "커뮤니케이션",
    # 산업재
    "Industrials": "산업재",
    # 에너지
    "Energy": "에너지",
    # 소재
    "Basic Materials": "소재",
    "Materials": "소재",
    # 부동산·유틸리티
    "Real Estate": "부동산",
    "Utilities": "유틸리티",
}


def sector_of(symbol: str, market: str) -> str:
    if market == "KR":
        return _kr_sectors().get(symbol, "기타")
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        sec = info.get("sector") or ""
        return US_SECTOR_KO.get(sec, sec or "기타")
    except Exception:  # noqa: BLE001
        return "기타"


def search(q: str, limit: int = 15) -> list[SearchHit]:
    q = q.strip()
    if not q:
        return []
    df = _all()
    if df.empty:
        return [SearchHit(symbol=q, name=q, market="KR" if q.isdigit() else "US")]
    ql = q.lower()
    sym_l = df["Symbol"].str.lower()
    name_l = df["Name"].str.lower()
    exact = df[sym_l == ql]
    starts = df[sym_l.str.startswith(ql) | name_l.str.startswith(ql)]
    contains = df[
        sym_l.str.contains(ql, regex=False) | name_l.str.contains(ql, regex=False)
    ]
    ranked = pd.concat([exact, starts, contains]).drop_duplicates("Symbol").head(limit)
    return [
        SearchHit(symbol=r["Symbol"], name=r["Name"], market=r["Market"])
        for _, r in ranked.iterrows()
    ]
