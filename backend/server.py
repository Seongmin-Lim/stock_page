"""FastAPI app — serves the Apple-styled frontend and all /api/* endpoints.

Run:  python -m backend.server   (or double-click start_stock.bat)
Data is key-free (FinanceDataReader / yfinance / pykrx) and delayed/EOD.
"""

from __future__ import annotations

import logging
import socket
import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend import alerts as alerts_mod
from backend import analysis as analysis_mod
from backend import autotrade as autotrade_mod
from backend import briefing as briefing_mod
from backend import chartread as chartread_mod
from backend import cycles as cycles_mod
from backend import disclosure as disclosure_mod
from backend import flows as flows_mod
from backend import kis as kis_mod
from backend import kis_trade as kis_trade_mod
from backend import news as news_mod
from backend import nlscreen as nlscreen_mod
from backend import fundamentals as fund_mod
from backend import journal as journal_mod
from backend import portfolio as port_mod
from backend import recommend as reco_mod
from backend import regime as regime_mod
from backend import scanner as scanner_mod
from backend import screener as screen_mod
from backend import sources, trade, universe
from backend.config import has_dart, has_gemini, has_kis
from backend.indicators import compute_indicators
from backend.schema import (
    AlertCheckResult,
    AlertRule,
    AutotradeConfig,
    AutotradeConfigUpdate,
    BacktestRequest,
    BacktestResult,
    CompareResult,
    DCFRequest,
    DCFResult,
    Fundamentals,
    IndicatorsResponse,
    KisBalance,
    KisBuyingPower,
    KisCancelRequest,
    KisOrderRequest,
    KisOrderResult,
    OHLCVResponse,
    PortfolioAnalysis,
    PortfolioRequest,
    BriefResult,
    ChartRead,
    CycleResult,
    DisclosureSummary,
    FlowResult,
    NewsSummary,
    NLScreenRequest,
    NLScreenResult,
    StockAnalysis,
    JournalResult,
    PositionRequest,
    PositionResult,
    Quote,
    RecoResult,
    RegimeResult,
    ScreenResult,
    TradeEntry,
    TurnScanResult,
    ScreenSpec,
    SearchHit,
    WatchItem,
)
from backend.store import load_json, save_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stockscope")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
WATCHLIST_FILE = "watchlist.json"

app = FastAPI(title="AI_stockScope")

T = TypeVar("T")


def _guard(fn: Callable[[], T]) -> T:
    """Run a data call; convert library/network failures into a clean 502 for the UI."""
    try:
        return fn()
    except HTTPException:
        raise
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"데이터 라이브러리 미설치: {exc}. start_stock.bat로 설치하세요.",
        )
    except Exception as exc:  # noqa: BLE001 - surface a readable message
        log.warning("data call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"데이터 조회 실패: {exc}")


# ── market data ──────────────────────────────────────────────────────
@app.get("/api/search", response_model=list[SearchHit])
def api_search(q: str = Query(""), limit: int = 15) -> list[SearchHit]:
    return _guard(lambda: universe.search(q, limit))


@app.get("/api/quote", response_model=Quote)
def api_quote(symbol: str) -> Quote:
    return _guard(lambda: sources.get_quote(symbol))


@app.get("/api/ohlcv", response_model=OHLCVResponse)
def api_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> OHLCVResponse:
    return _guard(lambda: sources.get_ohlcv(symbol, period, interval))


@app.get("/api/indicators", response_model=IndicatorsResponse)
def api_indicators(
    symbol: str, period: str = "1y", interval: str = "1d", names: str = "ma,bb,macd,rsi"
) -> IndicatorsResponse:
    wanted = tuple(n.strip() for n in names.split(",") if n.strip())
    return _guard(lambda: compute_indicators(symbol, period, interval, wanted))


# ── AI synthesis (rule-based) ────────────────────────────────────────
@app.get("/api/analysis", response_model=StockAnalysis)
def api_analysis(symbol: str) -> StockAnalysis:
    return _guard(lambda: analysis_mod.analyze(symbol))


@app.get("/api/chartread", response_model=ChartRead)
def api_chartread(symbol: str) -> ChartRead:
    return _guard(lambda: chartread_mod.read_chart(symbol))


@app.get("/api/news", response_model=NewsSummary)
def api_news(symbol: str) -> NewsSummary:
    return _guard(lambda: news_mod.get_news(symbol))


@app.get("/api/disclosures", response_model=DisclosureSummary)
def api_disclosures(symbol: str) -> DisclosureSummary:
    return _guard(lambda: disclosure_mod.get_disclosures(symbol))


# ── fundamentals / valuation ─────────────────────────────────────────
@app.get("/api/fundamentals", response_model=Fundamentals)
def api_fundamentals(symbol: str) -> Fundamentals:
    return _guard(lambda: sources.get_fundamentals(symbol))


@app.post("/api/dcf", response_model=DCFResult)
def api_dcf(req: DCFRequest) -> DCFResult:
    return _guard(lambda: fund_mod.run_dcf(req))


# ── screener ─────────────────────────────────────────────────────────
@app.post("/api/screener", response_model=ScreenResult)
def api_screener(spec: ScreenSpec) -> ScreenResult:
    return _guard(lambda: screen_mod.run_screen(spec))


@app.post("/api/nl-screen", response_model=NLScreenResult)
def api_nl_screen(req: NLScreenRequest) -> NLScreenResult:
    return _guard(lambda: nlscreen_mod.nl_screen(req.query, req.market))


# ── watchlist / compare ──────────────────────────────────────────────
@app.get("/api/watchlist", response_model=list[WatchItem])
def api_watchlist_get() -> list[WatchItem]:
    return [WatchItem(**w) for w in load_json(WATCHLIST_FILE, [])]


@app.post("/api/watchlist", response_model=list[WatchItem])
def api_watchlist_add(item: WatchItem) -> list[WatchItem]:
    items = load_json(WATCHLIST_FILE, [])
    if not any(w["symbol"] == item.symbol for w in items):
        items.append(item.model_dump())
        save_json(WATCHLIST_FILE, items)
    return [WatchItem(**w) for w in items]


@app.delete("/api/watchlist/{symbol}", response_model=list[WatchItem])
def api_watchlist_del(symbol: str) -> list[WatchItem]:
    items = [w for w in load_json(WATCHLIST_FILE, []) if w["symbol"] != symbol]
    save_json(WATCHLIST_FILE, items)
    return [WatchItem(**w) for w in items]


@app.get("/api/compare", response_model=CompareResult)
def api_compare(symbols: str, period: str = "1y") -> CompareResult:
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    return _guard(lambda: port_mod.compare(syms, period))


@app.get("/api/briefing", response_model=BriefResult)
def api_briefing() -> BriefResult:
    return _guard(briefing_mod.daily_brief)


# ── portfolio / backtest ─────────────────────────────────────────────
@app.post("/api/portfolio", response_model=PortfolioAnalysis)
def api_portfolio(req: PortfolioRequest) -> PortfolioAnalysis:
    return _guard(lambda: port_mod.analyze_portfolio(req))


@app.post("/api/backtest", response_model=BacktestResult)
def api_backtest(req: BacktestRequest) -> BacktestResult:
    return _guard(lambda: port_mod.backtest(req))


# ── alerts ───────────────────────────────────────────────────────────
@app.get("/api/alerts", response_model=list[AlertRule])
def api_alerts_get() -> list[AlertRule]:
    return alerts_mod.list_alerts()


@app.post("/api/alerts", response_model=list[AlertRule])
def api_alerts_add(rule: AlertRule) -> list[AlertRule]:
    return alerts_mod.add_alert(rule)


@app.delete("/api/alerts/{alert_id}", response_model=list[AlertRule])
def api_alerts_del(alert_id: str) -> list[AlertRule]:
    return alerts_mod.delete_alert(alert_id)


@app.get("/api/alerts/check", response_model=AlertCheckResult)
def api_alerts_check() -> AlertCheckResult:
    return _guard(alerts_mod.check_alerts)


# ── AI recommendation ────────────────────────────────────────────────
@app.get("/api/recommend", response_model=RecoResult)
def api_recommend(market: str = "KR") -> RecoResult:
    return _guard(lambda: reco_mod.recommend(market))


# ── whole-market turnaround scanner ──────────────────────────────────
@app.get("/api/turnaround-scan", response_model=TurnScanResult)
def api_turnaround_scan(market: str = "KR", limit: int = 24) -> TurnScanResult:
    return _guard(lambda: scanner_mod.scan_turnaround(market, limit))


# ── market regime (index weather) ────────────────────────────────────
@app.get("/api/regime", response_model=RegimeResult)
def api_regime() -> RegimeResult:
    return _guard(regime_mod.regime)


# ── industry / economic cycle ────────────────────────────────────────
@app.get("/api/cycles", response_model=CycleResult)
def api_cycles(market: str = "KR") -> CycleResult:
    return _guard(lambda: cycles_mod.cycles(market))


# ── investor flows (KR) ──────────────────────────────────────────────
@app.get("/api/flows", response_model=FlowResult)
def api_flows(symbol: str) -> FlowResult:
    return _guard(lambda: flows_mod.get_flows(symbol))


# ── KIS connection status ────────────────────────────────────────────
@app.get("/api/kis/status")
def api_kis_status() -> dict[str, object]:
    return kis_mod.status()


@app.get("/api/kis/balance", response_model=KisBalance)
def api_kis_balance() -> KisBalance:
    return _guard(lambda: KisBalance(**kis_trade_mod.account()))


@app.post("/api/kis/order", response_model=KisOrderResult)
def api_kis_order(req: KisOrderRequest) -> KisOrderResult:
    result = _guard(
        lambda: kis_trade_mod.order_cash(
            req.symbol, req.qty, req.price, req.order_type, req.side
        )
    )
    return KisOrderResult(**result)


@app.post("/api/kis/order/cancel", response_model=KisOrderResult)
def api_kis_order_cancel(req: KisCancelRequest) -> KisOrderResult:
    result = _guard(
        lambda: kis_trade_mod.modify_cancel(
            req.order_no, req.org_no, req.qty, req.price, cancel=True
        )
    )
    return KisOrderResult(**result)


@app.get("/api/kis/psbl", response_model=KisBuyingPower)
def api_kis_psbl(symbol: str, price: float | None = None) -> KisBuyingPower:
    return _guard(lambda: KisBuyingPower(**kis_trade_mod.psbl(symbol, price)))


# ── paper-trading automation ─────────────────────────────────────────
@app.get("/api/autotrade/status")
def api_autotrade_status() -> dict[str, object]:
    return autotrade_mod.status()


@app.post("/api/autotrade/config", response_model=AutotradeConfig)
def api_autotrade_config(req: AutotradeConfigUpdate) -> AutotradeConfig:
    try:
        return autotrade_mod.update_config(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/autotrade/start")
async def api_autotrade_start() -> dict[str, object]:
    return await autotrade_mod.start()


@app.post("/api/autotrade/stop")
async def api_autotrade_stop() -> dict[str, object]:
    return await autotrade_mod.stop()


# ── position sizing ──────────────────────────────────────────────────
@app.post("/api/position", response_model=PositionResult)
def api_position(req: PositionRequest) -> PositionResult:
    return _guard(lambda: trade.size_position(req))


# ── trade journal ────────────────────────────────────────────────────
@app.get("/api/journal", response_model=JournalResult)
def api_journal_get() -> JournalResult:
    return journal_mod.result()


@app.post("/api/journal", response_model=JournalResult)
def api_journal_add(entry: TradeEntry) -> JournalResult:
    return journal_mod.add_trade(entry)


@app.delete("/api/journal/{trade_id}", response_model=JournalResult)
def api_journal_del(trade_id: str) -> JournalResult:
    return journal_mod.delete_trade(trade_id)


# ── health / feature flags ───────────────────────────────────────────
@app.get("/api/health")
def api_health() -> dict[str, object]:
    return {
        "ok": True,
        "features": {
            "dart": has_dart(),
            "gemini": has_gemini(),
            "kis": has_kis(),
        },
    }


# ── startup cache warmup ─────────────────────────────────────────────
def _warmup() -> None:
    """Pre-warm the heaviest caches so the first user search is instant.

    Never raises — any failure is swallowed so the server always stays up.
    """
    try:
        universe.search("삼성")
    except Exception as exc:  # noqa: BLE001 - warmup is best-effort
        log.warning("warmup search failed: %s", exc)
    try:
        sources.kr_listing_snapshot()
    except Exception as exc:  # noqa: BLE001
        log.warning("warmup snapshot failed: %s", exc)


@app.on_event("startup")
async def _on_startup() -> None:
    threading.Thread(target=_warmup, daemon=True).start()
    await autotrade_mod.start_on_startup()


# ── frontend ─────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def _free_port(host: str, start: int, tries: int = 11) -> int:
    """Return the first bindable port in [start, start+tries); fall back to start.

    Fixes the stale-server trap: if 8000 is held by an old uvicorn, roll forward.
    """
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                if port == start:
                    log.warning("포트 %d 사용 중 → %d 로 실행", start, port + 1)
                continue
    return start


def main(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    port = _free_port(host, port)
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    log.info("AI_stockScope → http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
