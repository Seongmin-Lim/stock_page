"""Watchlist daily briefing — code gathers each holding's signals, LLM writes the recap.

For every watchlist name we compute a quick quote + technical bias (reusing chartread), then
Gemini turns the table into a short "오늘 관심종목 한 눈 브리핑" (which are strong / which need
attention). Numbers are code-computed; the LLM only narrates. Cached briefly, falls back to
the plain table when no key.
"""

from __future__ import annotations

from datetime import datetime

from backend.schema import BriefResult, BriefRow
from backend.store import load_json

_WATCH_FILE = "watchlist.json"


def _row(symbol: str, name: str, market: str) -> BriefRow | None:
    from backend.chartread import read_chart
    from backend.sources import get_quote

    try:
        q = get_quote(symbol)
    except Exception:  # noqa: BLE001
        q = None
    try:
        c = read_chart(symbol)
    except Exception:  # noqa: BLE001
        c = None
    if q is None and c is None:
        return None
    # short signal tag from the code-detected chart signals
    sig = ""
    if c is not None and c.signals:
        bull = [s.label for s in c.signals if s.state == "bullish"]
        bear = [s.label for s in c.signals if s.state == "bearish"]
        parts = []
        if bull:
            parts.append("▲" + "·".join(bull[:2]))
        if bear:
            parts.append("▼" + "·".join(bear[:2]))
        sig = " ".join(parts)
    return BriefRow(
        symbol=symbol,
        name=name,
        market=market,
        price=(q.price if q else (c.price if c else None)),
        change_pct=(q.change_pct if q else None),
        ret_1y=None,
        signal=sig,
        bias=(c.bias if c else ""),
    )


def daily_brief() -> BriefResult:
    watch = load_json(_WATCH_FILE, [])
    if not watch:
        return BriefResult(
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
            note="관심종목이 없습니다. 종목을 추가하면 브리핑이 생성됩니다.",
        )
    rows: list[BriefRow] = []
    for w in watch[:15]:
        r = _row(w["symbol"], w.get("name", w["symbol"]), w.get("market", "KR"))
        if r is not None:
            rows.append(r)
    if not rows:
        return BriefResult(
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
            note="관심종목 데이터를 불러오지 못했습니다.",
        )
    llm_brief = _llm_brief(rows)
    return BriefResult(
        rows=rows,
        llm_brief=llm_brief,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _llm_brief(rows: list[BriefRow]) -> str | None:
    from backend import llm

    if not llm.available():
        return None
    lines = []
    for r in rows:
        chg = f"{r.change_pct:+.1f}%" if r.change_pct is not None else "-"
        lines.append(
            f"- {r.name}({r.market}): 등락 {chg}, 바이어스 {r.bias or '-'}, 신호 {r.signal or '-'}"
        )
    data = "관심종목 현황:\n" + "\n".join(lines)
    system = (
        "너는 한국 주식 트레이더의 관심종목을 브리핑하는 애널리스트다. 아래 '계산된 현황'만 근거로 "
        "한국어 브리핑을 써라. 형식: (1) 전반 분위기 1문장. (2) '오늘 강한 종목'과 '주의가 필요한 종목'을 "
        "각각 1~2개 이름과 함께 짚기. (3) 마지막에 '관찰 포인트' 1문장. 규칙: 주어진 등락·바이어스·신호 "
        "외 수치를 지어내지 말 것, 매수/매도 단정 금지, 4~5문장 이내."
    )
    key = "brief:" + ";".join(
        f"{r.symbol}:{r.bias}:{round(r.change_pct or 0, 1)}" for r in rows
    )
    return llm.comment(prompt=data, system=system, cache_key=key, ttl=1200)
