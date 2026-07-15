"""News collection + optional LLM summary / sentiment.

Collection is key-free: yfinance `.news` (US/global) and Naver Finance per-stock news (KR).
The LLM (Gemini) then summarizes the headlines and tags overall 호재/악재/중립 — a pure
language task that code can't do. Headlines are cached; LLM result falls back to none.
"""

from __future__ import annotations

import re
from datetime import datetime

from backend.cache import cache_json
from backend.schema import NewsItem, NewsSummary
from backend.sources import detect_market
from backend.universe import name_of

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _us_news(symbol: str) -> list[dict]:
    try:
        import yfinance as yf

        raw = yf.Ticker(symbol).news or []
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for n in raw[:12]:
        c = n.get("content", n)  # new yfinance nests under 'content'
        title = c.get("title") or n.get("title") or ""
        if not title:
            continue
        pub = (
            (c.get("provider", {}) or {}).get("displayName") or n.get("publisher") or ""
        )
        date = (c.get("pubDate") or "")[:10]
        link = (c.get("canonicalUrl", {}) or {}).get("url") or n.get("link") or ""
        out.append({"title": title, "publisher": pub, "date": date, "link": link})
    return out


def _kr_news(symbol: str) -> list[dict]:
    import html as _html

    try:
        import requests

        url = (
            f"https://finance.naver.com/item/news_news.naver?code={symbol}"
            "&page=1&sm=title_entity_id.basic&clusterId="
        )
        headers = {
            **_HEADERS,
            "Referer": f"https://finance.naver.com/item/news.naver?code={symbol}",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = "euc-kr"
        text = r.text
    except Exception:  # noqa: BLE001
        return []
    # news rows are <a href="...read...">제목</a>; titles carry HTML entities → unescape
    out: list[dict] = []
    seen: set[str] = set()
    for href, raw in re.findall(
        r'<a[^>]+href="([^"]*read[^"]*)"[^>]*>(.*?)</a>', text, re.S
    ):
        title = _html.unescape(re.sub(r"<.*?>", "", raw)).strip()
        if len(title) < 8 or title in seen:
            continue
        seen.add(title)
        link = href if href.startswith("http") else "https://finance.naver.com" + href
        out.append({"title": title, "publisher": "", "date": "", "link": link})
        if len(out) >= 12:
            break
    return out


def get_news(symbol: str) -> NewsSummary:
    market = detect_market(symbol)
    name = name_of(symbol)
    raw = cache_json(
        f"news:{symbol}",
        1800,
        lambda: _kr_news(symbol) if market == "KR" else _us_news(symbol),
    )
    if not raw:
        return NewsSummary(
            symbol=symbol,
            name=name,
            market=market,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
            note="뉴스를 불러오지 못했습니다(소스 응답 없음).",
        )

    llm_summary, overall, tagged = _llm_news(name, market, raw)
    items = [NewsItem(**{**n, "sentiment": tagged.get(n["title"], "")}) for n in raw]
    return NewsSummary(
        symbol=symbol,
        name=name,
        market=market,
        items=items,
        llm_summary=llm_summary,
        overall_sentiment=overall,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _llm_news(name, market, raw) -> tuple[str | None, str | None, dict]:
    from backend import llm

    if not llm.available():
        return None, None, {}
    headlines = "\n".join(f"{i + 1}. {n['title']}" for i, n in enumerate(raw))
    data = f"종목: {name} ({market})\n최근 뉴스 헤드라인:\n{headlines}"
    system = (
        "너는 한국 주식 트레이더를 돕는 애널리스트다. 아래 종목 뉴스 헤드라인만 근거로 응답하라. "
        "출력 형식(엄수):\n"
        "요약: (3문장 이내로 핵심 흐름)\n"
        "종합: (호재|악재|중립 중 하나)\n"
        "분류:\n"
        "- <헤드라인 앞 8~15자> => 호재|악재|중립\n"
        "(각 헤드라인을 한 줄씩 분류). 규칙: 주어진 헤드라인 외 정보·수치를 지어내지 말 것, "
        "투자 권유 금지, 사실 기반 톤."
    )
    key = f"news:{name}:{len(raw)}:{hash(tuple(n['title'] for n in raw)) & 0xFFFFFF}"
    text = llm.comment(prompt=data, system=system, cache_key=key, ttl=1800)
    if not text:
        return None, None, {}
    return _parse_news_llm(text, raw)


def _parse_news_llm(text: str, raw) -> tuple[str | None, str | None, dict]:
    summary = None
    overall = None
    tagged: dict[str, str] = {}
    for line in text.splitlines():
        ls = line.strip()
        if ls.startswith("요약:"):
            summary = ls[3:].strip()
        elif ls.startswith("종합:"):
            for s in ("호재", "악재", "중립"):
                if s in ls:
                    overall = s
                    break
        elif "=>" in ls or "=>" in ls.replace("⇒", "=>"):
            frag, _, sent = ls.lstrip("- ").partition("=>")
            frag = frag.strip()
            sent = next((s for s in ("호재", "악재", "중립") if s in sent), "")
            if frag and sent:
                # match to a real headline by prefix
                for n in raw:
                    if n["title"].startswith(frag[:8]) or frag[:8] in n["title"]:
                        tagged[n["title"]] = sent
                        break
    return summary, overall, tagged
