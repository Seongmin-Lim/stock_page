"""Valuation helpers — 2-stage FCFF DCF. Data fetch lives in sources.get_fundamentals.

DCF follows Claude_database/finance/intrinsic-valuation.md.
"""

from __future__ import annotations

from fastapi import HTTPException

from backend.schema import DCFRequest, DCFResult


def run_dcf(req: DCFRequest) -> DCFResult:
    if req.wacc <= req.terminal_growth:
        raise HTTPException(
            status_code=400,
            detail="WACC는 영구성장률(terminal growth)보다 커야 합니다.",
        )
    if req.years < 1 or req.shares <= 0:
        raise HTTPException(
            status_code=400, detail="years는 1 이상, shares는 0보다 커야 합니다."
        )

    pv_explicit = 0.0
    fcf_t = req.fcf
    for t in range(1, req.years + 1):
        fcf_t = fcf_t * (1 + req.growth)
        pv_explicit += fcf_t / ((1 + req.wacc) ** t)

    terminal_value = (
        fcf_t * (1 + req.terminal_growth) / (req.wacc - req.terminal_growth)
    )
    pv_terminal = terminal_value / ((1 + req.wacc) ** req.years)

    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - req.net_debt
    fair = equity_value / req.shares
    return DCFResult(
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        fair_value_per_share=fair,
        pv_explicit=pv_explicit,
        pv_terminal=pv_terminal,
    )
