"""Rule-based AI synthesis for a single stock — NO LLM, deterministic, key-free.

Pulls every signal the app already computes (technical momentum/trend, value, quality,
financial statements, KR investor flows, and the stock's industry-cycle phase) and folds
them into one composite score + a plain-Korean verdict, strengths/weaknesses/cautions.

This is the "AI 분석" card on the overview — it reads like an analyst note but is 100%
arithmetic over the existing factors, so it's free, instant, and reproducible.
"""

from __future__ import annotations

from datetime import datetime

import backend.recommend as R
from backend.schema import AnalysisFactor, StockAnalysis
from backend.sources import detect_market, get_quote, kr_listing_snapshot
from backend.universe import name_of, sector_of

# weights for the overall score (renormalized over available factors)
_W = {
    "momentum": 0.22,
    "trend": 0.18,
    "value": 0.15,
    "quality": 0.15,
    "financial": 0.18,
    "flow": 0.12,
}


def _flow_score(symbol: str, market: str) -> tuple[float | None, str]:
    """KR investor flow → 0~100 (foreign+institution 20d net buying). US: n/a."""
    if market != "KR":
        return None, ""
    try:
        from backend.flows import get_flows

        f = get_flows(symbol)
    except Exception:  # noqa: BLE001
        return None, ""
    if not f.days:
        return None, ""
    fr, inst = f.foreign_sum_20d, f.inst_sum_20d
    if fr is None and inst is None:
        return None, ""
    net = (fr or 0) + (inst or 0)
    # score: both buying → high; magnitude vs 20d volume hard to normalize key-free, so use sign+blend
    pos = sum(1 for x in (fr, inst) if x is not None and x > 0)
    neg = sum(1 for x in (fr, inst) if x is not None and x < 0)
    score = 50.0 + (pos - neg) * 22.0  # both buy→94, both sell→6, mixed→50
    fr_t = "외국인 순매수" if (fr or 0) > 0 else "외국인 순매도"
    inst_t = "기관 순매수" if (inst or 0) > 0 else "기관 순매도"
    return max(0.0, min(100.0, score)), f"20일 {fr_t}·{inst_t}"


def _cycle_phase(symbol: str, market: str, sector: str) -> str | None:
    """Look up this stock's industry-cycle phase by matching its sector to a cycle theme."""
    try:
        from backend.cycles import cycles

        res = cycles(market)
    except Exception:  # noqa: BLE001
        return None
    # match by member symbol first (most reliable), else by sector-name keyword
    for t in res.themes:
        if symbol in t.members:
            return f"{t.phase_emoji} {t.name} {t.phase}"
    return None


def analyze(symbol: str) -> StockAnalysis:
    market = detect_market(symbol)
    snap = kr_listing_snapshot() if market == "KR" else None
    quote = get_quote(symbol)
    name = quote.name or name_of(symbol)
    sector = sector_of(symbol, market)

    m = R._metrics(symbol, market, snap)
    if m is None:
        return StockAnalysis(
            symbol=symbol,
            name=name,
            market=market,
            sector=sector,
            overall=0.0,
            verdict="데이터 부족",
            headline="가격 데이터가 부족해 분석할 수 없습니다.",
            summary="해당 종목의 시계열 데이터를 충분히 확보하지 못했습니다.",
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    flow_s, flow_detail = _flow_score(symbol, market)
    sub = {
        "momentum": m["momentum"],
        "trend": m["trend"],
        "value": m["value"],
        "quality": m["quality"],
        "financial": m["financial"],
        "flow": flow_s,
    }
    # overall = weighted average over available sub-scores
    present = [(sub[k], _W[k]) for k in _W if sub[k] is not None]
    tot = sum(w for _, w in present)
    overall = round(sum(v * w for v, w in present) / tot, 1) if tot else 0.0

    cycle = _cycle_phase(symbol, market, sector)

    factors = [
        AnalysisFactor(
            key="momentum",
            label="모멘텀",
            score=_rnd(m["momentum"]),
            detail=(
                f"12개월 {m['ret_1y']:+.0f}%" if m.get("ret_1y") is not None else ""
            ),
        ),
        AnalysisFactor(
            key="trend",
            label="추세",
            score=_rnd(m["trend"]),
            detail=(
                "정배열"
                if m["trend"] >= 75
                else "추세 양호"
                if m["trend"] >= 40
                else "추세 약함"
            ),
        ),
        AnalysisFactor(
            key="value",
            label="밸류",
            score=_rnd(m["value"]),
            detail=_join(
                [
                    f"PER {m['per']:.0f}" if m.get("per") else "",
                    f"PBR {m['pbr']:.1f}" if m.get("pbr") else "",
                ]
            ),
        ),
        AnalysisFactor(
            key="quality",
            label="퀄리티",
            score=_rnd(m["quality"]),
            detail=(f"ROE {m['roe']:.0f}%" if m.get("roe") is not None else ""),
        ),
        AnalysisFactor(
            key="financial",
            label="재무",
            score=_rnd(m["financial"]),
            detail=_join(
                [
                    f"매출성장 {m['rev_growth']:+.0f}%"
                    if m.get("rev_growth") is not None
                    else "",
                    f"영업이익률 {m['op_margin']:.0f}%"
                    if m.get("op_margin") is not None
                    else "",
                ]
            ),
        ),
    ]
    if flow_s is not None:
        factors.append(
            AnalysisFactor(
                key="flow", label="수급", score=_rnd(flow_s), detail=flow_detail
            )
        )

    strengths, weaknesses, cautions = _diagnose(m, flow_s, cycle)
    verdict, vdesc = _verdict(overall)
    headline = f"{name} — {verdict} (종합 {overall:.0f}점)"
    summary = _summary(
        name, sector, m, overall, verdict, vdesc, cycle, strengths, weaknesses, cautions
    )
    llm_comment = _llm_comment(
        name,
        sector,
        market,
        overall,
        verdict,
        m,
        factors,
        strengths,
        weaknesses,
        cautions,
        cycle,
    )

    return StockAnalysis(
        symbol=symbol,
        name=name,
        market=market,
        sector=sector,
        overall=overall,
        verdict=verdict,
        headline=headline,
        summary=summary,
        factors=factors,
        strengths=strengths,
        weaknesses=weaknesses,
        cautions=cautions,
        cycle_phase=cycle,
        llm_comment=llm_comment,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _llm_comment(
    name,
    sector,
    market,
    overall,
    verdict,
    m,
    factors,
    strengths,
    weaknesses,
    cautions,
    cycle,
) -> str | None:
    """Gemini narrative — given the CODE-computed numbers, write a 2-3 sentence trader note.
    The model only rephrases/interprets; it must not invent figures. Falls back to None."""
    from backend import llm

    if not llm.available():
        return None
    facts = "; ".join(
        f"{f.label} {int(f.score)}점({f.detail})"
        for f in factors
        if f.score is not None
    )
    data = (
        f"종목: {name} ({sector}, {market})\n"
        f"종합점수: {overall:.0f}/100 → 판정: {verdict}\n"
        f"팩터: {facts}\n"
        f"강점: {', '.join(strengths) or '없음'}\n"
        f"약점: {', '.join(weaknesses) or '없음'}\n"
        f"주의: {', '.join(cautions) or '없음'}\n"
        f"소속 산업 사이클: {cycle or '미상'}"
    )
    system = (
        "너는 한국 주식 트레이더를 돕는 애널리스트다. 아래 '계산된 지표'만 근거로 2~3문장의 "
        "한국어 코멘트를 써라. 규칙: (1) 주어진 숫자/사실만 사용하고 새로운 수치·가격·전망을 "
        "절대 지어내지 마라. (2) 매수/매도 단정·투자권유 금지, 관찰·해석 위주. (3) 강점과 리스크를 "
        "균형있게, 트레이더가 바로 이해할 실전 톤으로. (4) 마지막에 한 줄로 '체크포인트'를 제시."
    )
    key = f"{name}:{overall:.0f}:{verdict}:{cycle}"
    return llm.comment(prompt=data, system=system, cache_key=key, ttl=3600)


def _diagnose(m: dict, flow_s: float | None, cycle: str | None):
    s, w, c = [], [], []
    if m["momentum"] >= 70:
        s.append("강한 가격 모멘텀")
    elif m["momentum"] <= 35:
        w.append("모멘텀 부진")
    if m["trend"] >= 75:
        s.append("정배열(상승 추세)")
    elif m["trend"] <= 30:
        w.append("추세 이탈/하락")
    if m["value"] >= 65:
        s.append("밸류에이션 매력")
    elif m["value"] <= 30:
        c.append("밸류에이션 부담(고평가)")
    if m["quality"] >= 70:
        s.append("높은 수익성(퀄리티)")
    elif m["quality"] <= 35:
        w.append("수익성 낮음")
    if m["financial"] >= 70:
        s.append("탄탄한 재무·성장")
    elif m["financial"] <= 35:
        w.append("재무 취약/성장 둔화")
    if flow_s is not None:
        if flow_s >= 70:
            s.append("수급 우호(외국인·기관 매수)")
        elif flow_s <= 30:
            c.append("수급 이탈(외국인·기관 매도)")
    if cycle:
        if "침체" in cycle:
            c.append(f"소속 산업 사이클 약세 ({cycle})")
        elif "확장" in cycle or "회복" in cycle:
            s.append(f"산업 사이클 우호 ({cycle})")
    # generic risk note when momentum strong but value weak (late-stage)
    if m["momentum"] >= 70 and m["value"] <= 25:
        c.append("급등 후 고평가 — 추격매수 시 손절 기준 필수")
    return s[:5], w[:4], c[:4]


def _verdict(overall: float):
    if overall >= 72:
        return "강한 매수후보", "여러 축이 동시에 강함"
    if overall >= 58:
        return "매수 관심", "강점이 약점을 앞섬"
    if overall >= 42:
        return "중립·관망", "강점과 약점이 혼재"
    return "비중축소·회피", "약점이 우세"


def _summary(name, sector, m, overall, verdict, vdesc, cycle, s, w, c) -> str:
    parts = [
        f"{name}({sector})은(는) 종합 {overall:.0f}점으로 '{verdict}' 구간입니다 — {vdesc}."
    ]
    if m.get("ret_1y") is not None:
        parts.append(
            f"최근 12개월 {m['ret_1y']:+.0f}%, "
            + ("정배열 추세" if m["trend"] >= 75 else "추세는 중립~약세")
            + "."
        )
    fin_bits = []
    if m.get("per") is not None:
        fin_bits.append(f"PER {m['per']:.0f}")
    if m.get("roe") is not None:
        fin_bits.append(f"ROE {m['roe']:.0f}%")
    if m.get("op_margin") is not None:
        fin_bits.append(f"영업이익률 {m['op_margin']:.0f}%")
    if fin_bits:
        parts.append("밸류·수익성은 " + ", ".join(fin_bits) + " 수준.")
    if cycle:
        parts.append(f"소속 산업은 {cycle} 국면.")
    if s:
        parts.append("강점은 " + ", ".join(s[:3]) + ".")
    if c:
        parts.append("다만 " + ", ".join(c[:2]) + " 점은 주의가 필요합니다.")
    return " ".join(parts)


def _rnd(v: float | None) -> float | None:
    return None if v is None else round(v, 0)


def _join(xs: list[str]) -> str:
    return " · ".join([x for x in xs if x])
