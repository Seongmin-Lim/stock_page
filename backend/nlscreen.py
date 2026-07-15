"""Natural-language screener — Gemini converts a plain query into a ScreenSpec, then the
existing (deterministic) screener runs it. The LLM only parses language into structured
filters; it never invents results or numbers beyond what the user asked.

Falls back to a keyword parser when no key / parse fails, so it still works key-free.
"""

from __future__ import annotations

import json
import re

from backend.schema import (
    NLScreenResult,
    ScreenFilter,
    ScreenResult,
    ScreenSpec,
)
from backend.screener import run_screen

_FIELDS = {"per", "pbr", "roe", "marketcap", "price", "rsi", "ret_1y", "above_ma200"}
_OPS = {"lt", "lte", "gt", "gte", "between", "true"}

# broad sectors the screener understands (KR labels; US mapped to same 한글 in snapshot)
_SECTORS = [
    "반도체",
    "전자",
    "2차전지",
    "배터리",
    "자동차",
    "기계",
    "금융",
    "은행",
    "증권",
    "보험",
    "제약",
    "바이오",
    "화학",
    "소재",
    "철강",
    "건설",
    "부동산",
    "음식료",
    "유통",
    "소비재",
    "에너지",
    "유틸리티",
    "운송",
    "물류",
    "미디어",
    "엔터",
    "IT",
    "소프트웨어",
    "헬스케어",
]


def _llm_spec(query: str, market: str) -> dict | None:
    from backend import llm

    if not llm.available():
        return None
    system = (
        "너는 주식 스크리너 파서다. 사용자의 자연어 질의를 아래 JSON 스키마로만 변환하라. "
        "설명 없이 JSON만 출력.\n"
        '스키마: {"filters":[{"field":F,"op":O,"value":숫자,"value2":숫자(선택)}], '
        '"sector":문자열|null, "mode":"hard"|"score", "limit":정수}\n'
        f"F(field)는 반드시 이 중 하나: {sorted(_FIELDS)}. "
        "의미: per=PER, pbr=PBR, roe=ROE(%), marketcap=시가총액(원/달러), price=주가, "
        "rsi=RSI, ret_1y=1년수익률(%), above_ma200(200일선 위, op는 'true').\n"
        f"O(op)는 이 중 하나: {sorted(_OPS)}.\n"
        "sector는 업종 키워드(예: '반도체','금융','2차전지','바이오') 또는 null. "
        "규칙: (1) 스키마에 없는 개념(배당·부채 등)은 무시. (2) '저평가'는 per<15 & pbr<1.5 같은 "
        "합리적 기본값으로, '고ROE'는 roe>15 등으로 해석. (3) 숫자가 명시되면 그 값 사용. "
        "(4) 시가총액 단위: 한국이면 원, 미국이면 달러. '대형주'≈시총 상위이므로 필터 대신 정렬로 두고 "
        "굳이 marketcap 필터를 만들지 말 것. (5) JSON만."
    )
    text = llm.comment(
        prompt=f"시장: {market}\n질의: {query}",
        system=system,
        cache_key=f"nlscreen:{market}:{query}",
        ttl=1800,
    )
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _keyword_spec(query: str) -> dict:
    """Deterministic fallback: pull a few common intents out of the text."""
    q = query.lower()
    filters: list[dict] = []
    if "저평가" in query or "저 per" in q or "저per" in query:
        filters.append({"field": "per", "op": "lt", "value": 15})
        filters.append({"field": "pbr", "op": "lt", "value": 1.5})
    m = re.search(r"per\s*([0-9]+)\s*(이하|미만|under|below)", q)
    if m:
        filters.append({"field": "per", "op": "lt", "value": float(m.group(1))})
    m = re.search(r"roe\s*([0-9]+)\s*(이상|초과|over|above)", q)
    if m:
        filters.append({"field": "roe", "op": "gt", "value": float(m.group(1))})
    if "과매도" in query:
        filters.append({"field": "rsi", "op": "lt", "value": 30})
    if "정배열" in query or "200일선" in query or "상승추세" in query:
        filters.append({"field": "above_ma200", "op": "true"})
    sector = next((s for s in _SECTORS if s in query), None)
    if not filters and not sector:
        filters.append({"field": "per", "op": "lt", "value": 15})
    return {"filters": filters, "sector": sector, "mode": "hard", "limit": 50}


def _sanitize(raw: dict, market: str) -> ScreenSpec:
    filters: list[ScreenFilter] = []
    for f in raw.get("filters", []) or []:
        field = str(f.get("field", "")).strip()
        op = str(f.get("op", "")).strip()
        if field not in _FIELDS or op not in _OPS:
            continue
        filters.append(
            ScreenFilter(
                field=field,
                op=op,
                value=_numf(f.get("value")),
                value2=_numf(f.get("value2")),
            )
        )
    sector = raw.get("sector")
    sector = str(sector).strip() if sector else None
    mode = raw.get("mode") if raw.get("mode") in ("hard", "score") else "hard"
    limit = int(raw.get("limit") or 50)
    return ScreenSpec(
        market=market,
        mode=mode,
        filters=filters,
        sector=sector,
        limit=max(1, min(100, limit)),
    )


def _interpret(spec: ScreenSpec) -> str:
    labels = {
        "per": "PER",
        "pbr": "PBR",
        "roe": "ROE",
        "marketcap": "시총",
        "price": "주가",
        "rsi": "RSI",
        "ret_1y": "1년수익률",
        "above_ma200": "200일선 위",
    }
    op_s = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥", "between": "범위", "true": ""}
    bits = []
    if spec.sector:
        bits.append(f"[{spec.sector}]")
    for f in spec.filters:
        if f.op == "true":
            bits.append(labels.get(f.field, f.field))
        elif f.op == "between":
            bits.append(f"{labels.get(f.field, f.field)} {f.value}~{f.value2}")
        else:
            bits.append(
                f"{labels.get(f.field, f.field)} {op_s.get(f.op, f.op)} {f.value:g}"
            )
    return " · ".join(bits) if bits else "조건 없음"


def nl_screen(query: str, market: str) -> NLScreenResult:
    market = "US" if market.upper() == "US" else "KR"
    raw = _llm_spec(query, market)
    used_llm = raw is not None
    if raw is None:
        raw = _keyword_spec(query)
    spec = _sanitize(raw, market)
    if not spec.filters and not spec.sector:
        return NLScreenResult(
            spec=spec,
            result=ScreenResult(rows=[], scanned=0),
            interpreted="(해석 실패)",
            note="질의에서 스크리너 조건을 찾지 못했습니다. 예: 'PER 10 이하 ROE 15 이상 반도체'.",
        )
    result = run_screen(spec)
    note = None if used_llm else "LLM 없이 키워드 파서로 해석했습니다(대략적)."
    return NLScreenResult(
        spec=spec, result=result, interpreted=_interpret(spec), note=note
    )


def _numf(v: object) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None
