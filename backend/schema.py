"""Pydantic models — the shared contract between sources, API, and frontend.

Every API request/response is typed here. No `Any`/`dict` leakage across the boundary.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Market = str  # "KR" | "US"


# ── search / universe ────────────────────────────────────────────────
class SearchHit(BaseModel):
    symbol: str
    name: str
    market: Market


# ── quote / overview ─────────────────────────────────────────────────
class Quote(BaseModel):
    symbol: str
    name: str
    market: Market
    currency: str
    price: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    per: float | None = None
    pbr: float | None = None
    eps: float | None = None
    div_yield: float | None = None
    w52_high: float | None = None
    w52_low: float | None = None
    updated: str | None = None


# ── OHLCV ────────────────────────────────────────────────────────────
class Bar(BaseModel):
    time: str  # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(BaseModel):
    symbol: str
    market: Market
    name: str
    currency: str
    bars: list[Bar]


# ── indicators ───────────────────────────────────────────────────────
class LinePoint(BaseModel):
    time: str
    value: float


class IndicatorLine(BaseModel):
    name: str  # e.g. "MA20", "BB_upper", "MACD", "RSI"
    pane: str  # "price" | "macd" | "rsi" | "volume"
    data: list[LinePoint]


class IndicatorsResponse(BaseModel):
    symbol: str
    lines: list[IndicatorLine]


# ── fundamentals / valuation ─────────────────────────────────────────
class FinancialRow(BaseModel):
    label: str
    values: list[float | None]  # most-recent-first, aligned with `periods`


class Fundamentals(BaseModel):
    symbol: str
    name: str
    market: Market
    currency: str
    periods: list[str] = Field(default_factory=list)  # e.g. ["2024", "2023", ...]
    income: list[FinancialRow] = Field(default_factory=list)
    balance: list[FinancialRow] = Field(default_factory=list)
    cashflow: list[FinancialRow] = Field(default_factory=list)
    multiples: dict[str, float | None] = Field(default_factory=dict)  # PER, PBR, ROE...
    note: str | None = None


class DCFRequest(BaseModel):
    symbol: str
    fcf: float  # base free cash flow (latest)
    growth: float = 0.08  # stage-1 annual growth
    years: int = 5
    terminal_growth: float = 0.025
    wacc: float = 0.09
    net_debt: float = 0.0
    shares: float = 1.0


class DCFResult(BaseModel):
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    pv_explicit: float
    pv_terminal: float


# ── screener ─────────────────────────────────────────────────────────
ScreenField = Literal[
    "per",
    "pbr",
    "roe",
    "div",
    "marketcap",
    "price",
    "change_pct",
    "above_ma200",
    "rsi",
    "ret_1y",
]
ScreenOp = Literal["lt", "lte", "gt", "gte", "between", "true"]


class ScreenFilter(BaseModel):
    field: ScreenField
    op: ScreenOp
    value: float | None = None
    value2: float | None = None
    weight: float = 1.0

    @model_validator(mode="after")
    def validate_operator_values(self) -> ScreenFilter:
        if self.op == "true":
            if self.field != "above_ma200":
                raise ValueError("true 연산자는 불리언 필드에만 사용할 수 있습니다.")
            if self.value is not None and self.value not in (0.0, 1.0):
                raise ValueError("true 연산자의 값은 0 또는 1이어야 합니다.")
            return self
        if self.value is None:
            raise ValueError("필터 값이 필요합니다.")
        if self.op == "between":
            if self.value2 is None:
                raise ValueError("between 연산자는 하한과 상한이 필요합니다.")
            if self.value > self.value2:
                raise ValueError("between 하한은 상한보다 클 수 없습니다.")
        return self


class ScreenSpec(BaseModel):
    market: Literal["KR", "US"] = "KR"
    mode: Literal["hard", "score"] = "hard"
    filters: list[ScreenFilter] = Field(default_factory=list)
    sector: str | None = None  # optional broad-sector filter (e.g. "반도체·전자")
    limit: int = Field(default=50, ge=1, le=100)


class NLScreenRequest(BaseModel):
    query: str
    market: Market = "KR"


class NLScreenResult(BaseModel):
    spec: ScreenSpec
    result: ScreenResult
    interpreted: str = ""  # human-readable back-translation of the query
    note: str | None = None


class ScreenRow(BaseModel):
    symbol: str
    name: str
    market: Market
    price: float | None = None
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    div: float | None = None
    score: float | None = None


class ScreenResult(BaseModel):
    rows: list[ScreenRow]
    scanned: int
    note: str | None = None


# ── watchlist / compare ──────────────────────────────────────────────
class WatchItem(BaseModel):
    symbol: str
    name: str
    market: Market


class CompareSeries(BaseModel):
    symbol: str
    name: str
    data: list[LinePoint]  # normalized to 100 at start


class CompareResult(BaseModel):
    series: list[CompareSeries]


# ── portfolio / backtest ─────────────────────────────────────────────
class Holding(BaseModel):
    symbol: str
    shares: float
    avg_price: float | None = None


class PortfolioRequest(BaseModel):
    holdings: list[Holding]
    period: str = "1y"


class PortfolioPosition(BaseModel):
    symbol: str
    name: str
    shares: float
    price: float | None = None
    value: float | None = None
    weight: float | None = None
    ret_pct: float | None = None


class PortfolioAnalysis(BaseModel):
    positions: list[PortfolioPosition]
    total_value: float
    currency: str
    equity_curve: list[LinePoint]
    cagr: float | None = None
    mdd: float | None = None
    sharpe: float | None = None
    vol: float | None = None
    note: str | None = None


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str = "ma_cross"  # "ma_cross" | "rsi_revert" | "buy_hold"
    fast: int = 20
    slow: int = 60
    rsi_buy: float = 30.0
    rsi_sell: float = 70.0
    period: str = "3y"
    cost_bps: float = 15.0  # round-trip cost in basis points


class BtTrade(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    ret_pct: float


class BacktestResult(BaseModel):
    symbol: str
    strategy: str
    equity_curve: list[LinePoint]
    benchmark_curve: list[LinePoint]
    cagr: float | None = None
    mdd: float | None = None
    sharpe: float | None = None
    trades: int = 0
    win_rate: float | None = None
    trades_list: list[BtTrade] = Field(default_factory=list)
    note: str | None = None


# ── alerts ───────────────────────────────────────────────────────────
class AlertRule(BaseModel):
    id: str
    symbol: str
    name: str
    metric: str  # "price" | "rsi" | "pct_change" | "ma_cross"
    op: str  # "gt" | "lt" | "cross_up" | "cross_down"
    value: float | None = None
    note: str | None = None


class AlertHit(BaseModel):
    id: str
    symbol: str
    name: str
    message: str
    current: float | None = None
    triggered: bool


class AlertCheckResult(BaseModel):
    hits: list[AlertHit]


# ── AI recommendation (rule-based multi-factor) ──────────────────────
class RecoPick(BaseModel):
    symbol: str
    name: str
    market: Market
    category: str
    sector: str = "기타"
    score: float  # 0–100 composite for the category
    price: float | None = None
    change_pct: float | None = None
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    ret_1y: float | None = None
    momentum: float | None = None  # sub-scores 0–100
    trend: float | None = None
    value: float | None = None
    quality: float | None = None
    financial: float | None = None
    rationale: str = ""
    fin_note: str = ""  # financial-statement highlight
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class RecoSectorGroup(BaseModel):
    sector: str
    picks: list[RecoPick]


class RecoCategory(BaseModel):
    key: str
    title: str
    subtitle: str
    picks: list[RecoPick]  # flat, score-sorted (kept for compatibility)
    sectors: list[RecoSectorGroup] = Field(default_factory=list)  # grouped by sector


class RecoResult(BaseModel):
    market: Market
    generated: str
    categories: list[RecoCategory]
    note: str


# ── whole-market turnaround scan (two-stage) ─────────────────────────
class TurnScanResult(BaseModel):
    picks: list[RecoPick]
    scanned: int
    pool: int
    generated: str
    note: str


# ── market regime (index breadth/trend) ──────────────────────────────
class RegimeItem(BaseModel):
    market: str
    index_name: str
    price: float | None
    change_pct: float | None
    above_ma200: bool | None
    ret_1m: float | None


class RegimeResult(BaseModel):
    items: list[RegimeItem]
    generated: str


# ── industry / economic cycle (sector rotation) ──────────────────────
class CyclePoint(BaseModel):
    time: str
    value: float


class CycleTheme(BaseModel):
    key: str
    name: str  # 산업 테마명 (반도체·조선·2차전지 …)
    phase: str  # 회복 | 확장 | 둔화 | 침체
    phase_emoji: str
    ret_1m: float | None = None
    ret_3m: float | None = None
    ret_6m: float | None = None
    ret_12m: float | None = None
    rs_3m: float | None = None  # 시장 대비 3개월 상대강도(%p)
    above_ma200: bool | None = None
    momentum_accel: float | None = None
    price_score: float | None = None  # 가격 모멘텀 축 (0~100)
    earnings_score: float | None = None  # 이익 모멘텀 축 (매출성장·영업이익률)
    valuation_score: float | None = None  # 밸류에이션 매력 축 (PER·PBR 낮을수록↑)
    avg_per: float | None = None
    avg_op_margin: float | None = None
    avg_rev_growth: float | None = None
    score: float  # 0~100 사이클 강도 (가격+이익+밸류 종합)
    leaders: list[str] = Field(default_factory=list)  # 테마 내 강세 종목
    index_curve: list[CyclePoint] = Field(default_factory=list)  # 정규화 테마 인덱스
    comment: str = ""
    fund_note: str = ""  # 이익·밸류 한 줄 요약
    members: list[str] = Field(default_factory=list)  # 구성 종목 심볼


class CycleResult(BaseModel):
    market: Market
    benchmark: str
    generated: str
    themes: list[CycleTheme]
    note: str


# ── investor flows (KR foreign/institution) ──────────────────────────
class FlowDay(BaseModel):
    time: str
    close: float | None = None
    inst: float | None = None  # 기관 순매매량(주)
    foreign: float | None = None  # 외국인 순매매량(주)
    foreign_hold_pct: float | None = None


class FlowResult(BaseModel):
    symbol: str
    name: str
    market: Market
    days: list[FlowDay] = Field(default_factory=list)
    inst_sum_5d: float | None = None
    foreign_sum_5d: float | None = None
    inst_sum_20d: float | None = None
    foreign_sum_20d: float | None = None
    note: str | None = None


# ── position sizing / risk calculator ────────────────────────────────
class PositionRequest(BaseModel):
    symbol: str | None = None
    account: float = 10_000_000.0  # 계좌 크기
    risk_pct: float = 1.0  # 1트레이드 리스크 (계좌 %)
    entry: float | None = None  # 진입가 (없으면 현재가)
    stop_mode: str = "atr"  # "atr" | "price" | "pct"
    atr_mult: float = 2.0
    stop_price: float | None = None
    stop_pct: float | None = None  # 진입가 대비 손절 %
    rr: float = 2.0  # 목표 R:R
    direction: str = "long"  # "long" | "short"


class PositionResult(BaseModel):
    symbol: str | None = None
    entry: float
    stop: float
    target: float
    risk_per_share: float
    shares: int
    position_value: float
    position_pct: float  # 투입금액 / 계좌
    risk_amount: float  # 감수 손실액 (1R)
    reward_amount: float
    rr: float
    atr: float | None = None
    currency: str = "KRW"
    note: str | None = None


# ── trade journal ────────────────────────────────────────────────────
class TradeEntry(BaseModel):
    id: str = ""
    symbol: str
    name: str = ""
    market: Market = "KR"
    direction: str = "long"  # long | short
    entry_date: str = ""
    entry_price: float
    exit_date: str | None = None
    exit_price: float | None = None
    shares: float = 0.0
    stop_price: float | None = None
    setup: str = ""  # 진입 근거/셋업
    note: str = ""
    # derived (filled by backend)
    status: str = "open"  # open | closed
    pnl: float | None = None
    pnl_pct: float | None = None
    r_multiple: float | None = None


class JournalStats(BaseModel):
    total: int = 0
    closed: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float | None = None
    avg_r: float | None = None
    expectancy_r: float | None = None
    total_pnl: float = 0.0
    avg_win: float | None = None
    avg_loss: float | None = None
    profit_factor: float | None = None


class JournalResult(BaseModel):
    trades: list[TradeEntry] = Field(default_factory=list)
    stats: JournalStats = Field(default_factory=JournalStats)


# ── chart / technical read (code-detected signals + optional LLM narrative) ──
class TechSignal(BaseModel):
    label: str
    state: str  # bullish | bearish | neutral
    detail: str = ""


class ChartRead(BaseModel):
    symbol: str
    name: str
    market: Market
    price: float | None = None
    signals: list[TechSignal] = Field(default_factory=list)
    support: float | None = None
    resistance: float | None = None
    bias: str = "중립"  # 매수우위 | 중립 | 매도우위 (code-derived)
    bias_score: int = 0  # net bullish-bearish signal count
    llm_read: str | None = None  # Gemini 차트 해석 (선택)
    generated: str = ""


# ── news summary (collected text + optional LLM summary/sentiment) ──
class NewsItem(BaseModel):
    title: str
    publisher: str = ""
    date: str = ""
    link: str = ""
    sentiment: str = ""  # 호재 | 악재 | 중립 (LLM)


class NewsSummary(BaseModel):
    symbol: str
    name: str
    market: Market
    items: list[NewsItem] = Field(default_factory=list)
    llm_summary: str | None = None  # Gemini 요약 (선택)
    overall_sentiment: str | None = None  # 종합 호재/악재/중립 (LLM)
    generated: str = ""
    note: str | None = None


# ── DART disclosure summary (KR) ─────────────────────────────────────
class DisclosureItem(BaseModel):
    date: str = ""
    report: str = ""
    rcept_no: str = ""
    tag: str = ""  # 실적 | 주주환원 | 자금조달 | 지분 | 기타 (LLM)
    link: str = ""


class DisclosureSummary(BaseModel):
    symbol: str
    name: str
    market: Market
    items: list[DisclosureItem] = Field(default_factory=list)
    llm_summary: str | None = None  # Gemini 핵심 요약 (선택)
    generated: str = ""
    note: str | None = None


# ── watchlist daily briefing ─────────────────────────────────────────
class BriefRow(BaseModel):
    symbol: str
    name: str
    market: Market
    price: float | None = None
    change_pct: float | None = None
    ret_1y: float | None = None
    signal: str = ""  # 코드 요약 태그 (정배열/과매도/급등 등)
    bias: str = ""  # 매수우위 | 중립 | 매도우위


class BriefResult(BaseModel):
    rows: list[BriefRow] = Field(default_factory=list)
    llm_brief: str | None = None  # Gemini 한 눈 브리핑 (선택)
    generated: str = ""
    note: str | None = None


# ── stock AI analysis (rule-based synthesis of all signals) ──────────
class AnalysisFactor(BaseModel):
    key: str  # momentum | trend | value | quality | financial | flow | cycle
    label: str
    score: float | None = None  # 0~100 (None = data unavailable)
    detail: str = ""


class StockAnalysis(BaseModel):
    symbol: str
    name: str
    market: Market
    sector: str = "기타"
    overall: float  # 0~100 종합 점수
    verdict: str  # 강한 매수후보 | 매수 관심 | 중립·관망 | 비중축소·회피
    headline: str  # 한 줄 요약
    summary: str  # 한 문단 종합 진단
    factors: list[AnalysisFactor] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    cycle_phase: str | None = None  # 소속 산업 사이클 국면
    llm_comment: str | None = (
        None  # (선택) Gemini 서술 코멘트 — 숫자는 코드, 서술만 LLM
    )
    generated: str = ""
    note: str = "점수·팩터는 규칙 기반(무료·결정적) 계산입니다. 투자 권유가 아니며 참고용입니다."
