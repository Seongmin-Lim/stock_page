"""DART disclosure summary (KR) — collect recent filings, LLM tags + summarizes.

Collection is via the DART OpenAPI (key in .env). The LLM (Gemini) reads the filing titles
and produces a short "무슨 일이 있었나" summary + tags each filing (실적/주주환원/자금조달/지분/기타).
Pure language task; falls back to a plain list when no key.
"""

from __future__ import annotations

from datetime import datetime

from backend.schema import DisclosureItem, DisclosureSummary
from backend.sources import detect_market
from backend.universe import name_of

_TAGS = ["실적", "주주환원", "자금조달", "지분", "기타"]
_TAG_RULES = [
    ("실적", ["실적", "영업(잠정)", "매출액", "손익", "잠정"]),
    ("주주환원", ["자기주식", "자사주", "배당", "소각", "취득"]),
    ("자금조달", ["유상증자", "전환사채", "신주인수권", "회사채", "사채", "차입"]),
    ("지분", ["최대주주", "주식등의대량보유", "임원ㆍ주요주주", "지분", "특수관계"]),
]


def _rule_tag(report: str) -> str:
    for tag, keys in _TAG_RULES:
        if any(k in report for k in keys):
            return tag
    return "기타"


def get_disclosures(symbol: str) -> DisclosureSummary:
    market = detect_market(symbol)
    name = name_of(symbol)
    if market != "KR":
        return DisclosureSummary(
            symbol=symbol,
            name=name,
            market=market,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
            note="공시 요약은 한국 종목(DART)만 제공됩니다.",
        )

    from backend.dart import recent_disclosures

    raw = recent_disclosures(symbol)
    if not raw:
        return DisclosureSummary(
            symbol=symbol,
            name=name,
            market=market,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
            note="최근 공시를 불러오지 못했습니다(DART 키 미설정 또는 공시 없음).",
        )

    llm_summary, tags = _llm_summary(name, raw)
    items = [
        DisclosureItem(
            date=r["date"],
            report=r["report"],
            rcept_no=r["rcept_no"],
            tag=tags.get(r["rcept_no"]) or _rule_tag(r["report"]),
            link=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"
            if r["rcept_no"]
            else "",
        )
        for r in raw
    ]
    return DisclosureSummary(
        symbol=symbol,
        name=name,
        market=market,
        items=items,
        llm_summary=llm_summary,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _llm_summary(name: str, raw: list[dict]) -> tuple[str | None, dict]:
    from backend import llm

    if not llm.available():
        return None, {}
    lines = "\n".join(
        f"{i + 1}. [{r['date']}] {r['report']} (no={r['rcept_no']})"
        for i, r in enumerate(raw)
    )
    data = f"종목: {name}\n최근 공시 목록:\n{lines}"
    system = (
        "너는 한국 주식 투자자를 돕는 애널리스트다. 아래 DART 공시 목록만 근거로 응답하라. "
        "출력 형식(엄수):\n"
        "요약: (최근 공시에서 투자자가 알아야 할 핵심을 3문장 이내로. 실적·자사주·유증·지분변동 등 "
        "중요 이벤트 위주)\n"
        "분류:\n"
        "- <no 번호> => 실적|주주환원|자금조달|지분|기타\n"
        "(각 공시를 한 줄씩 분류). 규칙: 공시 제목 외 정보·수치를 지어내지 말 것, 투자 권유 금지."
    )
    key = f"disc:{name}:{len(raw)}:{raw[0]['rcept_no'] if raw else ''}"
    text = llm.comment(prompt=data, system=system, cache_key=key, ttl=3600)
    if not text:
        return None, {}
    return _parse(text, raw)


def _parse(text: str, raw: list[dict]) -> tuple[str | None, dict]:
    summary = None
    tags: dict[str, str] = {}
    nos = [r["rcept_no"] for r in raw]
    for line in text.splitlines():
        ls = line.strip()
        if ls.startswith("요약:"):
            summary = ls[3:].strip()
        elif "=>" in ls or "⇒" in ls:
            frag, _, tg = ls.lstrip("- ").replace("⇒", "=>").partition("=>")
            tag = next((t for t in _TAGS if t in tg), "")
            digits = "".join(ch for ch in frag if ch.isdigit())
            if tag and digits:
                for no in nos:
                    if no.endswith(digits[-6:]) or digits in no:
                        tags[no] = tag
                        break
    return summary, tags
