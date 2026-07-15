"""Natural-language screener parser tests — deterministic pieces, no LLM/network."""

from __future__ import annotations

from backend.nlscreen import _interpret, _keyword_spec, _sanitize
from backend.schema import ScreenSpec


def _fields(spec: ScreenSpec) -> set[str]:
    return {f.field for f in spec.filters}


def test_keyword_spec_undervalued():
    raw = _keyword_spec("저평가 종목")
    fields = {f["field"] for f in raw["filters"]}
    assert "per" in fields and "pbr" in fields


def test_keyword_spec_per_roe_regex():
    raw = _keyword_spec("PER 10 이하 ROE 15 이상")
    per = next(f for f in raw["filters"] if f["field"] == "per")
    roe = next(f for f in raw["filters"] if f["field"] == "roe")
    assert per["op"] == "lt" and per["value"] == 10
    assert roe["op"] == "gt" and roe["value"] == 15


def test_keyword_spec_oversold_and_trend():
    raw = _keyword_spec("과매도 정배열")
    fields = {f["field"] for f in raw["filters"]}
    assert "rsi" in fields
    assert "above_ma200" in fields


def test_keyword_spec_sector_detection():
    raw = _keyword_spec("반도체 저평가")
    assert raw["sector"] == "반도체"


def test_sanitize_drops_unknown_fields_and_ops():
    raw = {
        "filters": [
            {"field": "per", "op": "lt", "value": 10},
            {"field": "dividend", "op": "gt", "value": 3},  # unknown field → drop
            {"field": "roe", "op": "wat", "value": 5},  # unknown op → drop
        ],
        "sector": "금융",
        "mode": "hard",
        "limit": 9999,
    }
    spec = _sanitize(raw, "KR")
    assert _fields(spec) == {"per"}
    assert spec.sector == "금융"
    assert spec.limit == 100  # clamped to <=100


def test_sanitize_clamps_limit_low():
    # negative limit → clamped up to the floor of 1
    spec = _sanitize({"filters": [], "limit": -5}, "KR")
    assert spec.limit == 1


def test_interpret_renders_korean_labels():
    spec = _sanitize(
        {
            "filters": [
                {"field": "per", "op": "lt", "value": 10},
                {"field": "above_ma200", "op": "true"},
            ],
            "sector": "반도체",
        },
        "KR",
    )
    text = _interpret(spec)
    assert "[반도체]" in text
    assert "PER" in text and "<" in text
    assert "200일선 위" in text
