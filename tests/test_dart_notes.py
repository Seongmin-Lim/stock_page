"""State-accurate notes for DART-backed features."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from backend import cache, config, dart, disclosure, sources, universe
from backend.dart import DisclosureFetch
from backend.schema import DisclosureSummary


class _EmptyClient:
    def list(self, symbol: str, *, start: str) -> pd.DataFrame:
        return pd.DataFrame()


class _RowsClient:
    def list(self, symbol: str, *, start: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "rcept_dt": "20260715",
                    "report_nm": "주요사항보고서",
                    "rcept_no": "20260715000123",
                }
            ]
        )


def _uncached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_producer(
        key: str, ttl_sec: float, producer: Callable[[], DisclosureFetch]
    ) -> DisclosureFetch:
        return producer()

    monkeypatch.setattr(dart, "cache_json", run_producer)


def _disclosures(monkeypatch: pytest.MonkeyPatch) -> DisclosureSummary:
    monkeypatch.setattr(disclosure, "name_of", lambda symbol: "테스트")
    monkeypatch.setattr(disclosure, "_llm_summary", lambda name, raw: (None, {}))
    return disclosure.get_disclosures("005930")


def test_disclosure_note_when_dart_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _uncached(monkeypatch)
    monkeypatch.setattr(config, "has_dart", lambda: False)
    result = _disclosures(monkeypatch)

    assert result.note == (
        "DART API 키가 설정되지 않아 공시를 불러올 수 없습니다"
        "(.env의 DART_API_KEY 참고)."
    )


def test_disclosure_note_when_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _uncached(monkeypatch)
    monkeypatch.setattr(config, "has_dart", lambda: True)
    monkeypatch.setattr(dart, "_client", lambda: None)
    result = _disclosures(monkeypatch)

    assert result.note == (
        "DART 공시 조회가 일시적으로 실패했습니다. 잠시 후 다시 시도해주세요."
    )


def test_disclosure_note_when_fetch_succeeds_without_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _uncached(monkeypatch)
    monkeypatch.setattr(config, "has_dart", lambda: True)
    monkeypatch.setattr(dart, "_client", _EmptyClient)
    result = _disclosures(monkeypatch)

    assert result.note == "최근 120일 내 공시가 없습니다."


def test_disclosure_has_no_note_when_rows_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _uncached(monkeypatch)
    monkeypatch.setattr(config, "has_dart", lambda: True)
    monkeypatch.setattr(dart, "_client", _RowsClient)
    result = _disclosures(monkeypatch)

    assert result.note is None
    assert len(result.items) == 1


def test_recent_disclosures_ignores_old_plain_list_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "has_dart", lambda: True)
    monkeypatch.setattr(dart, "_client", _EmptyClient)
    old_path = cache._key_path("dart-list:005930", ".json")
    old_path.write_text('[{"report": "stale"}]', encoding="utf-8")

    result = dart.recent_disclosures("005930")

    assert result == {"ok": True, "rows": []}
    assert cache._key_path("dart-list2:005930", ".json").exists()


@pytest.mark.parametrize(
    ("has_key", "expected"),
    [
        (
            False,
            "DART API 키가 설정되지 않아 재무제표를 불러올 수 없습니다"
            "(.env의 DART_API_KEY 참고). 기초지표만 표시합니다.",
        ),
        (
            True,
            "DART 재무제표를 일시적으로 불러오지 못했습니다. "
            "기초지표만 표시합니다.",
        ),
    ],
)
def test_kr_fundamentals_note_reflects_key_state(
    monkeypatch: pytest.MonkeyPatch, has_key: bool, expected: str
) -> None:
    monkeypatch.setattr(config, "has_dart", lambda: has_key)
    monkeypatch.setattr(sources, "kr_listing_snapshot", pd.DataFrame)
    monkeypatch.setattr(sources, "_kr_fundamentals", lambda symbol: {})
    monkeypatch.setattr(dart, "kr_statement_table", lambda symbol, year: ([], {}))
    monkeypatch.setattr(universe, "name_of", lambda symbol: "테스트")

    result = sources.get_fundamentals("005930")

    assert result.note == expected
