"""Reversal-score ordering tests — the heart of the turnaround scanner.

A bottom-turner must outrank both an already-run momentum name and a still-dead name.
Pure arithmetic (no network).
"""

from __future__ import annotations

from backend.recommend import _reversal_score


def _bottom_turner() -> float:
    # oversold-then-turning: down over 12M, small +3M, mid 52w, just reclaimed 200DMA, volume in
    return _reversal_score(
        ret_1y=-30.0,
        ret_3m=5.0,
        prox52=60.0,
        above200=2.0,
        reclaimed_200=True,
        vol_ratio=1.3,
    )


def _already_ran() -> float:
    return _reversal_score(
        ret_1y=300.0,
        ret_3m=150.0,
        prox52=99.0,
        above200=40.0,
        reclaimed_200=False,
        vol_ratio=1.0,
    )


def _still_dead() -> float:
    return _reversal_score(
        ret_1y=-50.0,
        ret_3m=-15.0,
        prox52=20.0,
        above200=-25.0,
        reclaimed_200=False,
        vol_ratio=0.7,
    )


def test_bottom_turner_beats_already_ran():
    assert _bottom_turner() > _already_ran()


def test_bottom_turner_beats_still_dead():
    assert _bottom_turner() > _still_dead()


def test_scores_bounded():
    for v in (_bottom_turner(), _already_ran(), _still_dead()):
        assert 0.0 <= v <= 100.0
