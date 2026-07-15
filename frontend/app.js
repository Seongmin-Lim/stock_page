/* AI_stockScope frontend — vanilla JS. Talks to /api/* (see backend/schema.py). */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const LWC = window.LightweightCharts;

const state = {
  symbol: null,
  name: null,
  market: null,
  period: "1y",
  interval: "1d",
  indicators: new Set(["ma", "bb"]),
  loaded: { chart: false, fundamentals: false },
  watchSel: new Set(),
  levels: null, // {symbol, entry, stop, target} — chart price lines from position calc
};

// ── api / utils ──────────────────────────────────────────────────────
async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail || msg;
    } catch (e) {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}
const apiGet = (p) => api(p);
const apiPost = (p, body) =>
  api(p, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
const apiDel = (p) => api(p, { method: "DELETE" });

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}
const err = (e) => toast(String(e.message || e), "bad");

function num(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString(undefined, {
    maximumFractionDigits: d,
    minimumFractionDigits: 0,
  });
}
function cap(v, cur) {
  if (v === null || v === undefined) return "—";
  if (cur === "KRW") {
    if (v >= 1e12) return (v / 1e12).toFixed(1) + "조";
    if (v >= 1e8) return (v / 1e8).toFixed(0) + "억";
    return num(v);
  }
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + num(v);
}
const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
const sign = (v) => (v > 0 ? "+" : "");

// format a valuation-multiple value by its key (handles big KR amounts + percents)
const PCT_KEYS = [
  "ROE",
  "ROA",
  "Margin",
  "Yield",
  "DIV",
  "이익률",
  "성장률",
  "부채비율",
];
function fmtMultiple(k, v, cur) {
  if (v === null || v === undefined) return "—";
  if (k === "시가총액") return cap(v, cur);
  if (k === "현재가") return num(v) + " " + (cur || "");
  if (PCT_KEYS.some((p) => k.includes(p))) return num(v) + "%";
  return num(v);
}

// ── search ───────────────────────────────────────────────────────────
let searchTimer = null,
  activeIdx = -1,
  suggestions = [];
$("#search").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) {
    $("#suggest").innerHTML = "";
    return;
  }
  searchTimer = setTimeout(() => doSearch(q), 220);
});
$("#search").addEventListener("keydown", (e) => {
  const rows = $$("#suggest .suggest-row");
  if (e.key === "ArrowDown") {
    activeIdx = Math.min(activeIdx + 1, rows.length - 1);
    paintActive(rows);
    e.preventDefault();
  } else if (e.key === "ArrowUp") {
    activeIdx = Math.max(activeIdx - 1, 0);
    paintActive(rows);
    e.preventDefault();
  } else if (e.key === "Enter") {
    if (suggestions[activeIdx]) pick(suggestions[activeIdx]);
    else if (suggestions[0]) pick(suggestions[0]);
  } else if (e.key === "Escape") {
    $("#suggest").innerHTML = "";
  }
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-wrap")) $("#suggest").innerHTML = "";
});

function paintActive(rows) {
  rows.forEach((r, i) => r.classList.toggle("active", i === activeIdx));
}

async function doSearch(q) {
  try {
    suggestions = await apiGet(`/api/search?q=${encodeURIComponent(q)}`);
    activeIdx = -1;
    $("#suggest").innerHTML = suggestions
      .map(
        (s) =>
          `<div class="suggest-row" data-sym="${s.symbol}"><span class="sym">${s.symbol}</span>
       <span class="nm">${s.name}</span><span class="badge ${s.market.toLowerCase()}">${s.market}</span></div>`,
      )
      .join("");
    $$("#suggest .suggest-row").forEach((row, i) =>
      row.addEventListener("click", () => pick(suggestions[i])),
    );
  } catch (e) {
    // server unreachable/errored — tell the user instead of failing silently
    $("#suggest").innerHTML =
      `<div class="suggest-row" style="cursor:default;color:var(--down)">` +
      `⚠ 검색 실패 — 서버가 꺼져 있을 수 있습니다. start_stock.bat을 다시 실행하세요.</div>`;
  }
}

function pick(hit) {
  state.symbol = hit.symbol;
  state.name = hit.name;
  state.market = hit.market;
  state.loaded = { chart: false, fundamentals: false };
  $("#search").value = `${hit.name} (${hit.symbol})`;
  $("#suggest").innerHTML = "";
  renderOverview();
  const active = $(".tab.active").dataset.tab;
  if (active === "chart") renderChart();
  if (active === "fundamentals") renderFundamentals();
}

// ── tabs ─────────────────────────────────────────────────────────────
$$("#tabs .tab").forEach((t) =>
  t.addEventListener("click", () => activateTab(t.dataset.tab)),
);
function activateTab(name) {
  $$("#tabs .tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name),
  );
  $$(".panel").forEach((p) =>
    p.classList.toggle("active", p.id === `panel-${name}`),
  );
  if (name === "chart") renderChart();
  if (name === "fundamentals") renderFundamentals();
  if (name === "watch") renderWatchlist();
  if (name === "alerts") {
    clearTabBadge("alerts");
    renderAlerts();
  }
  if (name === "reco" && !recoLoaded) renderReco();
  if (name === "cycle" && !cycleLoaded) renderCycle();
  if (name === "trade") {
    if (state.symbol) $("#ps-symbol").value = state.symbol;
    renderJournal();
  }
}
const needSymbol = () => {
  if (!state.symbol) {
    toast("먼저 종목을 검색·선택하세요.");
    return false;
  }
  return true;
};

// ── overview ─────────────────────────────────────────────────────────
async function renderOverview() {
  const body = $("#overview-body");
  if (!state.symbol) return;
  body.innerHTML = `<div class="loading"><span class="spinner"></span> 불러오는 중…</div>`;
  try {
    const q = await apiGet(`/api/quote?symbol=${state.symbol}`);
    const c = q.currency;
    const chg = q.change_pct;
    body.innerHTML = `
      <div class="card">
        <div class="quote-head">
          <span class="qname">${q.name}</span>
          <span class="qsym">${q.symbol} · ${q.market}</span>
        </div>
        <div class="quote-price">${num(q.price)} <span style="font-size:16px;color:var(--secondary)">${c}</span></div>
        <div class="chg ${cls(chg)}" style="font-size:16px;font-weight:600">
          ${q.change != null ? sign(q.change) + num(q.change) : "—"} (${chg != null ? sign(chg) + num(chg) + "%" : "—"})
        </div>
        <div class="stat-grid">
          ${stat("시가총액", cap(q.market_cap, c))}
          ${stat("PER", num(q.per))}
          ${stat("PBR", num(q.pbr))}
          ${stat("EPS", num(q.eps))}
          ${stat("배당수익률", q.div_yield != null ? num(q.div_yield) + "%" : "—")}
          ${stat("52주 고가", num(q.w52_high))}
          ${stat("52주 저가", num(q.w52_low))}
          ${stat("거래량", num(q.volume, 0))}
        </div>
        <div class="row" style="margin-top:16px">
          <button class="btn" onclick="activateTab('chart')">차트 보기</button>
          <button class="btn sec" onclick="activateTab('fundamentals')">재무 보기</button>
          <button class="btn sec" id="ov-watch">관심 추가</button>
        </div>
        <div class="note">데이터: 무료 소스 기반 지연/EOD · 갱신 ${q.updated || ""}</div>
      </div>
      <div class="card" id="ai-card"><h2>AI 종합 분석</h2><div id="ai-body"><div class="loading"><span class="spinner"></span> 신호 종합 중… (최초는 산업사이클 계산으로 다소 걸릴 수 있습니다)</div></div></div>
      <div class="card" id="news-card"><h2>뉴스 — AI 요약·호재/악재</h2><div id="news-body"><div class="loading"><span class="spinner"></span> 뉴스 수집·요약 중…</div></div></div>
      ${q.market === "KR" ? `<div class="card"><h2>수급 — 외국인·기관 매매동향</h2><div id="flow-card"><div class="loading"><span class="spinner"></span> 수급 로딩…</div></div></div>` : ""}`;
    $("#ov-watch").addEventListener("click", addCurrentToWatch);
    renderAnalysis();
    renderNews();
    if (q.market === "KR") renderFlows();
  } catch (e) {
    body.innerHTML = `<div class="empty">조회 실패: ${e.message}</div>`;
  }
}

const VERDICT_CLASS = {
  "강한 매수후보": "v-strong",
  "매수 관심": "v-buy",
  "중립·관망": "v-neutral",
  "비중축소·회피": "v-avoid",
  "데이터 부족": "v-neutral",
};
async function renderAnalysis() {
  const sym = state.symbol;
  const host = document.getElementById("ai-body");
  if (!host || !sym) return;
  try {
    const a = await apiGet(`/api/analysis?symbol=${sym}`);
    if (state.symbol !== sym) return; // user moved on
    const vcls = VERDICT_CLASS[a.verdict] || "v-neutral";
    const facBars = a.factors
      .map((f) =>
        factorBar(f.label, f.score).replace(
          "</div>",
          `<span class="fdetail">${f.detail || ""}</span></div>`,
        ),
      )
      .join("");
    const tag = (t, k) => `<span class="tag ${k}">${t}</span>`;
    host.innerHTML = `
      <div class="ai-head">
        <div class="ai-gauge ${vcls}"><div class="ai-score">${num(a.overall, 0)}</div><div class="ai-of">/100</div></div>
        <div class="ai-headmeta">
          <div class="ai-verdict ${vcls}">${a.verdict}</div>
          <div class="ai-sector">${a.sector}${a.cycle_phase ? " · " + a.cycle_phase : ""}</div>
        </div>
      </div>
      <div class="ai-summary">${a.summary}</div>
      ${a.llm_comment ? `<div class="ai-llm"><span class="ai-llm-badge">✦ AI 코멘트</span><div class="ai-llm-text">${a.llm_comment.replace(/\n/g, "<br>")}</div></div>` : ""}
      <div class="ai-factors">${facBars}</div>
      <div class="ai-tags">
        ${a.strengths.map((s) => tag("+ " + s, "good")).join("")}
        ${a.weaknesses.map((s) => tag("− " + s, "bad")).join("")}
        ${a.cautions.map((s) => tag("⚠ " + s, "warn")).join("")}
      </div>
      <div class="note">${a.note}${a.llm_comment ? " · AI 코멘트는 위 지표를 Gemini가 서술한 것(숫자는 코드 계산)" : ""} · 생성 ${a.generated}</div>`;
  } catch (e) {
    if (state.symbol === sym)
      host.innerHTML = `<div class="empty">분석 실패: ${e.message}</div>`;
  }
}
const stat = (k, v) =>
  `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;

const SENT_CLASS = { 호재: "good", 악재: "bad", 중립: "neutral" };
async function renderNews() {
  const sym = state.symbol;
  const host = document.getElementById("news-body");
  if (!host || !sym) return;
  try {
    const n = await apiGet(`/api/news?symbol=${sym}`);
    if (state.symbol !== sym) return;
    if (!n.items.length) {
      host.innerHTML = `<div class="empty">${n.note || "뉴스가 없습니다."}</div>`;
      return;
    }
    const ov = n.overall_sentiment
      ? `<span class="sent-pill ${SENT_CLASS[n.overall_sentiment] || "neutral"}">종합 ${n.overall_sentiment}</span>`
      : "";
    const list = n.items
      .map((it) => {
        const sc = SENT_CLASS[it.sentiment] || "neutral";
        const badge = it.sentiment
          ? `<span class="sent-dot ${sc}">${it.sentiment}</span>`
          : "";
        const title = it.link
          ? `<a href="${it.link}" target="_blank" rel="noopener">${it.title}</a>`
          : it.title;
        return `<div class="news-row">${badge}<span class="news-title">${title}</span></div>`;
      })
      .join("");
    host.innerHTML = `
      <div class="news-head">${ov}</div>
      ${n.llm_summary ? `<div class="ai-llm"><span class="ai-llm-badge">✦ AI 뉴스 요약</span><div class="ai-llm-text">${n.llm_summary}</div></div>` : ""}
      <div class="news-list">${list}</div>
      <div class="note">뉴스 수집(${n.market === "KR" ? "네이버" : "yfinance"})${n.llm_summary ? " + Gemini 요약·분류" : ""} · 참고용 · ${n.generated}</div>`;
  } catch (e) {
    if (state.symbol === sym)
      host.innerHTML = `<div class="empty">뉴스 조회 실패: ${e.message}</div>`;
  }
}

// ── chart ────────────────────────────────────────────────────────────
const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"];
const INTERVALS = [
  ["1d", "일"],
  ["1wk", "주"],
  ["1mo", "월"],
];
const IND_PILLS = [
  ["ma", "이동평균"],
  ["bb", "볼린저"],
  ["ema", "EMA"],
  ["macd", "MACD"],
  ["rsi", "RSI"],
  ["atr", "ATR"],
];
const IND_COLORS = {
  MA20: "#0066cc",
  MA60: "#ff9500",
  MA120: "#af52de",
  EMA12: "#34c759",
  EMA26: "#ff3b30",
  BB_upper: "#8e8e93",
  BB_mid: "#c7c7cc",
  BB_lower: "#8e8e93",
};
let charts = { main: null, macd: null, rsi: null };

function buildChartToolbar() {
  $("#period-pills").innerHTML = PERIODS.map(
    (p) =>
      `<button class="pill ${p === state.period ? "active" : ""}" data-p="${p}">${p}</button>`,
  ).join("");
  $("#interval-pills").innerHTML = INTERVALS.map(
    ([v, l]) =>
      `<button class="pill ${v === state.interval ? "active" : ""}" data-i="${v}">${l}</button>`,
  ).join("");
  $("#indicator-pills").innerHTML = IND_PILLS.map(
    ([v, l]) =>
      `<button class="pill ${state.indicators.has(v) ? "active" : ""}" data-ind="${v}">${l}</button>`,
  ).join("");
  $$("#period-pills .pill").forEach(
    (b) =>
      (b.onclick = () => {
        state.period = b.dataset.p;
        renderChart();
      }),
  );
  $$("#interval-pills .pill").forEach(
    (b) =>
      (b.onclick = () => {
        state.interval = b.dataset.i;
        renderChart();
      }),
  );
  $$("#indicator-pills .pill").forEach(
    (b) =>
      (b.onclick = () => {
        const k = b.dataset.ind;
        state.indicators.has(k)
          ? state.indicators.delete(k)
          : state.indicators.add(k);
        renderChart();
      }),
  );
}

function disposeCharts() {
  for (const k of Object.keys(charts)) {
    if (charts[k]) {
      charts[k].remove();
      charts[k] = null;
    }
  }
  $("#chart-macd").style.display = "none";
  $("#chart-rsi").style.display = "none";
}

function renderLevelsPill() {
  const slot = $("#chart-levels-slot");
  if (!slot) return;
  if (state.levels && state.levels.symbol === state.symbol) {
    slot.innerHTML = `<button class="pill ghost" id="chart-levels-clear">레벨 지우기 ✕</button>`;
    $("#chart-levels-clear").addEventListener("click", () => {
      state.levels = null;
      renderChart();
    });
  } else {
    slot.innerHTML = "";
  }
}

async function renderChart() {
  if (!needSymbol()) return;
  buildChartToolbar();
  $("#chart-title").textContent = `${state.name} (${state.symbol})`;
  renderLevelsPill();
  const indNames = Array.from(state.indicators).join(",") || "ma";
  disposeCharts();
  $("#legend").innerHTML = `<span class="spinner"></span>`;
  try {
    const [ohlcv, ind] = await Promise.all([
      apiGet(
        `/api/ohlcv?symbol=${state.symbol}&period=${state.period}&interval=${state.interval}`,
      ),
      apiGet(
        `/api/indicators?symbol=${state.symbol}&period=${state.period}&interval=${state.interval}&names=${indNames}`,
      ),
    ]);
    if (!ohlcv.bars.length) {
      $("#legend").innerHTML = "";
      toast("가격 데이터가 없습니다.");
      return;
    }
    drawMain(ohlcv, ind);
    drawSub("macd", ind);
    drawSub("rsi", ind);
    renderChartRead();
  } catch (e) {
    $("#legend").innerHTML = "";
    err(e);
  }
}

const SIG_CLASS = { bullish: "good", bearish: "bad", neutral: "neutral" };
const SIG_MARK = { bullish: "▲", bearish: "▼", neutral: "▬" };
async function renderChartRead() {
  const sym = state.symbol;
  const host = document.getElementById("chartread-body");
  if (!host || !sym) return;
  host.innerHTML = `<div class="loading"><span class="spinner"></span> 기술적 신호 해석 중…</div>`;
  try {
    const c = await apiGet(`/api/chartread?symbol=${sym}`);
    if (state.symbol !== sym) return;
    const bcls =
      c.bias === "매수우위"
        ? "good"
        : c.bias === "매도우위"
          ? "bad"
          : "neutral";
    const sigs = c.signals
      .map(
        (s) =>
          `<span class="sig-chip ${SIG_CLASS[s.state]}">${SIG_MARK[s.state]} ${s.label}<span class="sig-d">${s.detail}</span></span>`,
      )
      .join("");
    const lv = [];
    if (c.support) lv.push(`지지 <b>${num(c.support)}</b>`);
    if (c.resistance) lv.push(`저항 <b>${num(c.resistance)}</b>`);
    host.innerHTML = `
      <div class="cr-head"><span class="cr-bias ${bcls}">${c.bias}</span>
        ${lv.length ? `<span class="cr-levels">${lv.join(" · ")}</span>` : ""}</div>
      <div class="sig-wrap">${sigs}</div>
      ${c.llm_read ? `<div class="ai-llm"><span class="ai-llm-badge">✦ AI 차트 해석</span><div class="ai-llm-text">${c.llm_read.replace(/\n/g, "<br>")}</div></div>` : ""}
      <div class="note">기술적 신호는 코드가 감지${c.llm_read ? ", 해석 서술은 Gemini" : ""} · 참고용 · ${c.generated}</div>`;
  } catch (e) {
    if (state.symbol === sym)
      host.innerHTML = `<div class="empty">해석 실패: ${e.message}</div>`;
  }
}

function mainOpts(el) {
  return {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { color: "#fff" },
      textColor: "#6e6e73",
      fontFamily: "-apple-system, sans-serif",
    },
    grid: { vertLines: { color: "#f0f0f2" }, horzLines: { color: "#f0f0f2" } },
    rightPriceScale: { borderColor: "#e0e0e0" },
    timeScale: { borderColor: "#e0e0e0" },
    crosshair: { mode: 1 },
  };
}

function drawMain(ohlcv, ind) {
  const el = $("#chart");
  const chart = LWC.createChart(el, mainOpts(el));
  charts.main = chart;
  const candle = chart.addCandlestickSeries({
    upColor: "#34c759",
    downColor: "#ff3b30",
    borderVisible: false,
    wickUpColor: "#34c759",
    wickDownColor: "#ff3b30",
  });
  candle.setData(
    ohlcv.bars.map((b) => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    })),
  );

  const vol = chart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "",
  });
  vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  vol.setData(
    ohlcv.bars.map((b) => ({
      time: b.time,
      value: b.volume,
      color: b.close >= b.open ? "rgba(52,199,89,.35)" : "rgba(255,59,48,.35)",
    })),
  );

  // position-calc price levels (진입/손절/목표) for the current symbol
  if (state.levels && state.levels.symbol === state.symbol) {
    const L = state.levels;
    if (L.entry != null)
      candle.createPriceLine({
        price: L.entry,
        color: "#0066cc",
        lineWidth: 1,
        lineStyle: LWC.LineStyle.Solid,
        title: "진입",
      });
    if (L.stop != null)
      candle.createPriceLine({
        price: L.stop,
        color: "#ff3b30",
        lineWidth: 1,
        lineStyle: LWC.LineStyle.Dashed,
        title: "손절",
      });
    if (L.target != null)
      candle.createPriceLine({
        price: L.target,
        color: "#34c759",
        lineWidth: 1,
        lineStyle: LWC.LineStyle.Dashed,
        title: "목표",
      });
  }

  const legend = [];
  for (const line of ind.lines.filter((l) => l.pane === "price")) {
    const color = IND_COLORS[line.name] || "#0066cc";
    const s = chart.addLineSeries({
      color,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    s.setData(line.data.map((p) => ({ time: p.time, value: p.value })));
    legend.push(`<span><i style="background:${color}"></i>${line.name}</span>`);
  }
  $("#legend").innerHTML =
    legend.join("") || `<span>${ohlcv.bars.length} bars</span>`;
  chart.timeScale().fitContent();
  observe(el, chart);
}

function drawSub(pane, ind) {
  const lines = ind.lines.filter((l) => l.pane === pane);
  const el = $(`#chart-${pane}`);
  if (!lines.length) {
    el.style.display = "none";
    return;
  }
  el.style.display = "block";
  const chart = LWC.createChart(el, {
    ...mainOpts(el),
    height: el.clientHeight,
  });
  charts[pane] = chart;
  if (pane === "rsi") {
    const s = chart.addLineSeries({ color: "#af52de", lineWidth: 1.5 });
    s.setData(lines[0].data.map((p) => ({ time: p.time, value: p.value })));
    [30, 70].forEach((lvl) =>
      s.createPriceLine({
        price: lvl,
        color: "#c7c7cc",
        lineStyle: 2,
        lineWidth: 1,
      }),
    );
  } else {
    // macd
    for (const l of lines) {
      if (l.name === "Hist") {
        const h = chart.addHistogramSeries({});
        h.setData(
          l.data.map((p) => ({
            time: p.time,
            value: p.value,
            color: p.value >= 0 ? "rgba(52,199,89,.5)" : "rgba(255,59,48,.5)",
          })),
        );
      } else {
        const s = chart.addLineSeries({
          color: l.name === "MACD" ? "#0066cc" : "#ff9500",
          lineWidth: 1.4,
        });
        s.setData(l.data.map((p) => ({ time: p.time, value: p.value })));
      }
    }
  }
  chart.timeScale().fitContent();
  observe(el, chart);
}

function observe(el, chart) {
  const ro = new ResizeObserver(() =>
    chart.applyOptions({ width: el.clientWidth }),
  );
  ro.observe(el);
}

// ── fundamentals ─────────────────────────────────────────────────────
async function renderFundamentals() {
  if (!needSymbol()) {
    $("#fund-body").innerHTML =
      `<div class="empty">먼저 종목을 선택하세요.</div>`;
    return;
  }
  const body = $("#fund-body");
  body.innerHTML = `<div class="loading"><span class="spinner"></span> 재무 데이터 로딩…</div>`;
  try {
    const f = await apiGet(`/api/fundamentals?symbol=${state.symbol}`);
    const mult = Object.entries(f.multiples)
      .map(([k, v]) => stat(k, fmtMultiple(k, v, f.currency)))
      .join("");
    const stmt = (title, rows) =>
      !rows.length
        ? ""
        : `
      <div class="card"><h2>${title}</h2><table><thead><tr><th>항목</th>${f.periods.map((p) => `<th>${p}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${r.label}</td>${r.values.map((v) => `<td>${v == null ? "—" : cap(v, f.currency)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    body.innerHTML = `
      <div class="card"><h2>밸류에이션 멀티플 — ${f.name} (${f.symbol})</h2>
        <div class="stat-grid">${mult || '<div class="empty">멀티플 데이터 없음</div>'}</div>
        ${f.note ? `<div class="note">${f.note}</div>` : ""}
      </div>
      ${stmt("손익계산서", f.income)}
      ${stmt("재무상태표", f.balance)}
      ${stmt("현금흐름표", f.cashflow)}
      ${dcfCard(f)}
      ${f.market === "KR" ? `<div class="card" id="disc-card"><h2>공시 — AI 요약 (DART)</h2><div id="disc-body"><div class="loading"><span class="spinner"></span> 공시 수집·요약 중…</div></div></div>` : ""}`;
    wireDcf(f);
    if (f.market === "KR") renderDisclosures();
  } catch (e) {
    body.innerHTML = `<div class="empty">조회 실패: ${e.message}</div>`;
  }
}

const DISC_TAG = {
  실적: "good",
  주주환원: "good",
  자금조달: "warn",
  지분: "neutral",
  기타: "neutral",
};
async function renderDisclosures() {
  const sym = state.symbol;
  const host = document.getElementById("disc-body");
  if (!host || !sym) return;
  try {
    const d = await apiGet(`/api/disclosures?symbol=${sym}`);
    if (state.symbol !== sym) return;
    if (!d.items.length) {
      host.innerHTML = `<div class="empty">${d.note || "공시 없음"}</div>`;
      return;
    }
    const list = d.items
      .map((it) => {
        const tc = DISC_TAG[it.tag] || "neutral";
        const badge = it.tag
          ? `<span class="sent-dot ${tc}">${it.tag}</span>`
          : "";
        const title = it.link
          ? `<a href="${it.link}" target="_blank" rel="noopener">${it.report}</a>`
          : it.report;
        return `<div class="news-row">${badge}<span class="news-title">${title}</span><span class="disc-date">${it.date}</span></div>`;
      })
      .join("");
    host.innerHTML = `
      ${d.llm_summary ? `<div class="ai-llm"><span class="ai-llm-badge">✦ AI 공시 요약</span><div class="ai-llm-text">${d.llm_summary}</div></div>` : ""}
      <div class="news-list">${list}</div>
      <div class="note">DART 전자공시${d.llm_summary ? " + Gemini 요약·분류" : ""} · 참고용 · ${d.generated}</div>`;
  } catch (e) {
    if (state.symbol === sym)
      host.innerHTML = `<div class="empty">공시 조회 실패: ${e.message}</div>`;
  }
}

function dcfCard(f) {
  return `<div class="card"><h2>간이 DCF (2단계 FCFF)</h2>
    <div class="row mb">
      <label class="field">기준 FCF<input id="dcf-fcf" type="number" value="1000000000" style="width:160px"/></label>
      <label class="field">성장률(1단계)<input id="dcf-growth" type="number" step="0.01" value="0.08" style="width:90px"/></label>
      <label class="field">기간(년)<input id="dcf-years" type="number" value="5" style="width:70px"/></label>
      <label class="field">영구성장<input id="dcf-tg" type="number" step="0.005" value="0.025" style="width:90px"/></label>
      <label class="field">WACC<input id="dcf-wacc" type="number" step="0.005" value="0.09" style="width:90px"/></label>
      <label class="field">순부채<input id="dcf-nd" type="number" value="0" style="width:120px"/></label>
      <label class="field">주식수<input id="dcf-sh" type="number" value="1" style="width:120px"/></label>
      <button class="btn" id="dcf-run" style="align-self:flex-end">계산</button>
    </div>
    <div id="dcf-out"></div>
    <div class="note">FCF·순부채·주식수는 ${f.currency} 단위로 직접 입력하세요. 결과는 가정에 매우 민감합니다.</div>
  </div>`;
}
function wireDcf(f) {
  $("#dcf-run").addEventListener("click", async () => {
    try {
      const r = await apiPost("/api/dcf", {
        symbol: f.symbol,
        fcf: +$("#dcf-fcf").value,
        growth: +$("#dcf-growth").value,
        years: +$("#dcf-years").value,
        terminal_growth: +$("#dcf-tg").value,
        wacc: +$("#dcf-wacc").value,
        net_debt: +$("#dcf-nd").value,
        shares: +$("#dcf-sh").value,
      });
      $("#dcf-out").innerHTML = `<div class="stat-grid">
        ${stat("기업가치(EV)", cap(r.enterprise_value, f.currency))}
        ${stat("주주가치", cap(r.equity_value, f.currency))}
        ${stat("주당 내재가치", num(r.fair_value_per_share))}
        ${stat("PV(예측구간)", cap(r.pv_explicit, f.currency))}
        ${stat("PV(영구가치)", cap(r.pv_terminal, f.currency))}</div>`;
    } catch (e) {
      err(e);
    }
  });
}

// ── screener ─────────────────────────────────────────────────────────
const SCR_FIELDS = [
  ["per", "PER"],
  ["pbr", "PBR"],
  ["roe", "ROE(%)"],
  ["div", "배당수익률(%)"],
  ["marketcap", "시가총액"],
  ["price", "가격"],
  ["above_ma200", "200일선 상회"],
  ["rsi", "RSI"],
  ["ret_1y", "1년수익률(%)"],
];
const SCR_OPS = [
  ["lt", "<"],
  ["lte", "≤"],
  ["gt", ">"],
  ["gte", "≥"],
  ["between", "범위"],
  ["true", "참(boolean)"],
];

function addFilterRow(field = "per", op = "lt", value = "15", value2 = "") {
  const div = document.createElement("div");
  div.className = "row mb scr-row";
  div.innerHTML = `
    <select class="f-field">${SCR_FIELDS.map(([v, l]) => `<option value="${v}" ${v === field ? "selected" : ""}>${l}</option>`).join("")}</select>
    <select class="f-op">${SCR_OPS.map(([v, l]) => `<option value="${v}" ${v === op ? "selected" : ""}>${l}</option>`).join("")}</select>
    <input class="f-val" type="number" value="${value}" placeholder="값" style="width:110px"/>
    <input class="f-val2" type="number" value="${value2}" placeholder="상한" style="width:110px;display:none"/>
    <button class="pill ghost f-del">✕</button>`;
  div.querySelector(".f-op").addEventListener("change", (e) => {
    div.querySelector(".f-val2").style.display =
      e.target.value === "between" ? "inline-block" : "none";
    div.querySelector(".f-val").style.display =
      e.target.value === "true" ? "none" : "inline-block";
  });
  div.querySelector(".f-del").addEventListener("click", () => div.remove());
  $("#scr-filters").appendChild(div);
}
$("#scr-add").addEventListener("click", () => addFilterRow());
$("#scr-run").addEventListener("click", runScreen);

// render a ScreenResult into a host element (shared by 조건/자연어 스크리너)
function renderScreenRows(host, r, showScore) {
  if (!r.rows.length) {
    host.innerHTML = `<div class="empty">조건을 만족하는 종목이 없습니다.</div>${r.note ? `<div class="note">${r.note}</div>` : ""}`;
    return;
  }
  host.innerHTML = `
    <div class="note">스캔 ${num(r.scanned, 0)}종목 → ${r.rows.length}개 표시${r.note ? " · " + r.note : ""}</div>
    <table><thead><tr><th>종목</th><th>코드</th><th>가격</th><th>PER</th><th>PBR</th><th>ROE</th>${showScore ? "<th>점수</th>" : ""}</tr></thead>
    <tbody>${r.rows
      .map(
        (
          row,
        ) => `<tr class="clickable" data-sym="${row.symbol}" data-name="${row.name}" data-mkt="${row.market}">
      <td>${row.name}</td><td>${row.symbol}</td><td>${num(row.price)}</td><td>${num(row.per)}</td><td>${num(row.pbr)}</td><td>${num(row.roe)}</td>
      ${showScore ? `<td>${num(row.score, 1)}</td>` : ""}</tr>`,
      )
      .join("")}</tbody></table>`;
  $$("tr.clickable", host).forEach((tr) =>
    tr.addEventListener("click", () => {
      pick({
        symbol: tr.dataset.sym,
        name: tr.dataset.name,
        market: tr.dataset.mkt,
      });
      activateTab("overview");
    }),
  );
}

// ── natural-language screener ─────────────────────────────────────────
$("#nl-run").addEventListener("click", runNLScreen);
$("#nl-query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runNLScreen();
});
async function runNLScreen() {
  const query = $("#nl-query").value.trim();
  if (!query) {
    toast("찾고 싶은 조건을 말로 입력하세요.");
    return;
  }
  $("#nl-result").innerHTML =
    `<div class="loading"><span class="spinner"></span> AI가 조건으로 변환·검색 중…</div>`;
  try {
    const r = await apiPost("/api/nl-screen", {
      query,
      market: $("#nl-market").value,
    });
    const chips = `<div class="nl-interp"><span class="ai-llm-badge">✦ 해석</span> ${r.interpreted}${r.note ? ` <span style="color:var(--secondary)">· ${r.note}</span>` : ""}</div>`;
    const host = document.createElement("div");
    renderScreenRows(host, r.result, r.spec.mode === "score");
    $("#nl-result").innerHTML = chips;
    $("#nl-result").appendChild(host);
  } catch (e) {
    $("#nl-result").innerHTML =
      `<div class="empty">검색 실패: ${e.message}</div>`;
  }
}

async function runScreen() {
  const filters = $$(".scr-row").map((r) => ({
    field: r.querySelector(".f-field").value,
    op: r.querySelector(".f-op").value,
    value:
      +r.querySelector(".f-val").value ||
      (r.querySelector(".f-op").value === "true" ? 1 : 0),
    value2: +r.querySelector(".f-val2").value || null,
    weight: 1,
  }));
  const spec = {
    market: $("#scr-market").value,
    mode: $("#scr-mode").value,
    filters,
    limit: +$("#scr-limit").value || 50,
  };
  $("#scr-result").innerHTML =
    `<div class="loading"><span class="spinner"></span> 스크리닝 중… (최초 실행은 수십 초 걸릴 수 있습니다)</div>`;
  try {
    const r = await apiPost("/api/screener", spec);
    renderScreenRows($("#scr-result"), r, spec.mode === "score");
  } catch (e) {
    $("#scr-result").innerHTML =
      `<div class="empty">스크리닝 실패: ${e.message}</div>`;
  }
}

// ── watchlist / compare ──────────────────────────────────────────────
async function addCurrentToWatch() {
  if (!needSymbol()) return;
  try {
    await apiPost("/api/watchlist", {
      symbol: state.symbol,
      name: state.name,
      market: state.market,
    });
    toast("관심종목에 추가됨", "good");
    renderWatchlist();
  } catch (e) {
    err(e);
  }
}
$("#watch-add").addEventListener("click", addCurrentToWatch);
$("#watch-compare").addEventListener("click", runCompare);
$("#brief-run").addEventListener("click", renderBrief);

async function renderBrief() {
  const host = $("#brief-body");
  host.innerHTML = `<div class="loading"><span class="spinner"></span> 관심종목 신호 수집·브리핑 중…</div>`;
  try {
    const b = await apiGet("/api/briefing");
    if (!b.rows.length) {
      host.innerHTML = `<div class="empty">${b.note || "브리핑할 종목이 없습니다."}</div>`;
      return;
    }
    const bcls = (x) =>
      x === "매수우위" ? "good" : x === "매도우위" ? "bad" : "neutral";
    const rows = b.rows
      .map(
        (r) => `<div class="news-row">
      <span class="sent-dot ${bcls(r.bias)}">${r.bias || "-"}</span>
      <span class="news-title"><b>${r.name}</b> <span style="color:var(--secondary)">${r.symbol}</span> ${r.signal || ""}</span>
      <span class="num ${cls(r.change_pct)}" style="flex:none">${r.change_pct != null ? sign(r.change_pct) + num(r.change_pct) + "%" : "—"}</span></div>`,
      )
      .join("");
    host.innerHTML = `
      ${b.llm_brief ? `<div class="ai-llm"><span class="ai-llm-badge">✦ AI 브리핑</span><div class="ai-llm-text">${b.llm_brief.replace(/\n/g, "<br>")}</div></div>` : ""}
      <div class="news-list">${rows}</div>
      <div class="note">신호는 코드 계산${b.llm_brief ? ", 브리핑 서술은 Gemini" : ""} · 참고용 · ${b.generated}</div>`;
  } catch (e) {
    host.innerHTML = `<div class="empty">브리핑 실패: ${e.message}</div>`;
  }
}

async function renderWatchlist() {
  try {
    const items = await apiGet("/api/watchlist");
    if (!items.length) {
      $("#watch-list").innerHTML =
        `<div class="empty">관심종목이 없습니다. 개요/관심 탭에서 추가하세요.</div>`;
      return;
    }
    $("#watch-list").innerHTML = items
      .map(
        (w) => `
      <div class="row" style="justify-content:space-between;border-bottom:1px solid var(--hairline);padding:8px 0">
        <label class="row" style="gap:8px"><input type="checkbox" class="w-chk" data-sym="${w.symbol}" ${state.watchSel.has(w.symbol) ? "checked" : ""}/>
          <b>${w.name}</b> <span class="badge ${w.market.toLowerCase()}">${w.symbol}</span></label>
        <span class="row"><button class="pill ghost w-open" data-sym="${w.symbol}" data-name="${w.name}" data-mkt="${w.market}">열기</button>
          <button class="pill ghost w-del" data-sym="${w.symbol}">삭제</button></span>
      </div>`,
      )
      .join("");
    $$(".w-chk").forEach((c) =>
      c.addEventListener("change", () =>
        c.checked
          ? state.watchSel.add(c.dataset.sym)
          : state.watchSel.delete(c.dataset.sym),
      ),
    );
    $$(".w-open").forEach((b) =>
      b.addEventListener("click", () => {
        pick({
          symbol: b.dataset.sym,
          name: b.dataset.name,
          market: b.dataset.mkt,
        });
        activateTab("overview");
      }),
    );
    $$(".w-del").forEach((b) =>
      b.addEventListener("click", async () => {
        await apiDel(`/api/watchlist/${b.dataset.sym}`);
        state.watchSel.delete(b.dataset.sym);
        renderWatchlist();
      }),
    );
  } catch (e) {
    err(e);
  }
}

let compareChart = null;
async function runCompare() {
  const syms = Array.from(state.watchSel);
  if (syms.length < 1) {
    toast("비교할 종목을 체크하세요.");
    return;
  }
  $("#compare-legend").innerHTML = `<span class="spinner"></span>`;
  try {
    const r = await apiGet(`/api/compare?symbols=${syms.join(",")}&period=1y`);
    const el = $("#compare-chart");
    if (compareChart) {
      compareChart.remove();
      compareChart = null;
    }
    compareChart = LWC.createChart(el, mainOpts(el));
    const palette = [
      "#0066cc",
      "#ff9500",
      "#34c759",
      "#af52de",
      "#ff3b30",
      "#5ac8fa",
      "#ffcc00",
    ];
    const legend = [];
    r.series.forEach((s, i) => {
      const color = palette[i % palette.length];
      const ls = compareChart.addLineSeries({
        color,
        lineWidth: 1.8,
        lastValueVisible: false,
      });
      ls.setData(s.data.map((p) => ({ time: p.time, value: p.value })));
      legend.push(
        `<span><i style="background:${color}"></i>${s.name} (${s.symbol})</span>`,
      );
    });
    $("#compare-legend").innerHTML = legend.join("");
    compareChart.timeScale().fitContent();
    observe(el, compareChart);
  } catch (e) {
    $("#compare-legend").innerHTML = "";
    err(e);
  }
}

// ── portfolio / backtest ─────────────────────────────────────────────
function addHoldingRow(symbol = "", shares = "", avg = "") {
  const div = document.createElement("div");
  div.className = "row mb hold-row";
  div.innerHTML = `<input class="h-sym" placeholder="005930 / AAPL" value="${symbol}" style="width:140px"/>
    <input class="h-sh" type="number" placeholder="수량" value="${shares}" style="width:110px"/>
    <input class="h-avg" type="number" placeholder="평단(선택)" value="${avg}" style="width:130px"/>
    <button class="pill ghost h-del">✕</button>`;
  div.querySelector(".h-del").addEventListener("click", () => div.remove());
  $("#port-holdings").appendChild(div);
}
$("#port-add").addEventListener("click", () => addHoldingRow());
$("#port-run").addEventListener("click", runPortfolio);

let portChart = null;
async function runPortfolio() {
  const holdings = $$(".hold-row")
    .map((r) => ({
      symbol: r.querySelector(".h-sym").value.trim(),
      shares: +r.querySelector(".h-sh").value || 0,
      avg_price: +r.querySelector(".h-avg").value || null,
    }))
    .filter((h) => h.symbol && h.shares);
  if (!holdings.length) {
    toast("보유 종목을 입력하세요.");
    return;
  }
  $("#port-result").innerHTML =
    `<div class="loading"><span class="spinner"></span> 분석 중…</div>`;
  try {
    const r = await apiPost("/api/portfolio", { holdings, period: "1y" });
    const rows = r.positions
      .map(
        (
          p,
        ) => `<tr><td>${p.name}</td><td>${p.symbol}</td><td>${num(p.shares, 4)}</td>
      <td>${num(p.price)}</td><td>${cap(p.value, r.currency)}</td><td>${p.weight != null ? num(p.weight) + "%" : "—"}</td>
      <td class="num ${cls(p.ret_pct)}">${p.ret_pct != null ? sign(p.ret_pct) + num(p.ret_pct) + "%" : "—"}</td></tr>`,
      )
      .join("");
    $("#port-result").innerHTML = `
      <div class="stat-grid">
        ${stat("총 평가액", cap(r.total_value, r.currency))}
        ${stat("CAGR", r.cagr != null ? num(r.cagr) + "%" : "—")}
        ${stat("MDD", r.mdd != null ? num(r.mdd) + "%" : "—")}
        ${stat("Sharpe", num(r.sharpe))}
        ${stat("변동성", r.vol != null ? num(r.vol) + "%" : "—")}
      </div>
      <table style="margin-top:12px"><thead><tr><th>종목</th><th>코드</th><th>수량</th><th>현재가</th><th>평가액</th><th>비중</th><th>수익률</th></tr></thead><tbody>${rows}</tbody></table>
      <div id="port-chart" class="chart-box" style="height:280px;margin-top:14px"></div>
      ${r.note ? `<div class="note">${r.note}</div>` : ""}`;
    const el = $("#port-chart");
    if (portChart) {
      portChart.remove();
      portChart = null;
    }
    portChart = LWC.createChart(el, mainOpts(el));
    const s = portChart.addAreaSeries({
      lineColor: "#0066cc",
      topColor: "rgba(0,102,204,.25)",
      bottomColor: "rgba(0,102,204,.02)",
      lineWidth: 2,
    });
    s.setData(r.equity_curve.map((p) => ({ time: p.time, value: p.value })));
    portChart.timeScale().fitContent();
    observe(el, portChart);
  } catch (e) {
    $("#port-result").innerHTML =
      `<div class="empty">분석 실패: ${e.message}</div>`;
  }
}

function btTradesTable(list) {
  if (!list || !list.length) return "";
  const rows = list
    .slice(0, 30)
    .map(
      (t) => `<tr>
      <td>${t.entry_date || "—"}</td><td>${t.exit_date || "—"}</td>
      <td>${num(t.entry_price)}</td><td>${num(t.exit_price)}</td>
      <td class="num ${cls(t.ret_pct)}">${t.ret_pct == null ? "—" : sign(t.ret_pct) + num(t.ret_pct) + "%"}</td></tr>`,
    )
    .join("");
  return `<div class="bt-trades">
    <div class="note">거래내역 ${list.length}건${list.length > 30 ? " (최근 30건 표시)" : ""}</div>
    <table><thead><tr><th>진입일</th><th>청산일</th><th>진입가</th><th>청산가</th><th>수익률</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

let btChart = null;
$("#bt-run").addEventListener("click", async () => {
  const symbol = $("#bt-symbol").value.trim() || state.symbol;
  if (!symbol) {
    toast("백테스트할 종목을 입력하세요.");
    return;
  }
  $("#bt-result").innerHTML =
    `<div class="loading"><span class="spinner"></span> 백테스트 중…</div>`;
  try {
    const r = await apiPost("/api/backtest", {
      symbol,
      strategy: $("#bt-strategy").value,
      fast: +$("#bt-fast").value,
      slow: +$("#bt-slow").value,
      period: $("#bt-period").value,
      cost_bps: 15,
    });
    if (!r.equity_curve.length) {
      $("#bt-result").innerHTML =
        `<div class="empty">${r.note || "데이터 부족"}</div>`;
      return;
    }
    $("#bt-result").innerHTML = `
      <div class="stat-grid">
        ${stat("전략 CAGR", r.cagr != null ? num(r.cagr) + "%" : "—")}
        ${stat("MDD", r.mdd != null ? num(r.mdd) + "%" : "—")}
        ${stat("Sharpe", num(r.sharpe))}
        ${stat("매매횟수", num(r.trades, 0))}
        ${stat("승률", r.win_rate != null ? num(r.win_rate) + "%" : "—")}
      </div>
      <div class="legend"><span><i style="background:#0066cc"></i>전략</span><span><i style="background:#8e8e93"></i>바이앤홀드</span></div>
      <div id="bt-chart" class="chart-box" style="height:300px;margin-top:8px"></div>
      ${btTradesTable(r.trades_list)}`;
    const el = $("#bt-chart");
    if (btChart) {
      btChart.remove();
      btChart = null;
    }
    btChart = LWC.createChart(el, mainOpts(el));
    btChart
      .addLineSeries({ color: "#0066cc", lineWidth: 2 })
      .setData(r.equity_curve.map((p) => ({ time: p.time, value: p.value })));
    btChart
      .addLineSeries({ color: "#8e8e93", lineWidth: 1.4 })
      .setData(
        r.benchmark_curve.map((p) => ({ time: p.time, value: p.value })),
      );
    btChart.timeScale().fitContent();
    observe(el, btChart);
  } catch (e) {
    $("#bt-result").innerHTML =
      `<div class="empty">백테스트 실패: ${e.message}</div>`;
  }
});

// ── alerts ───────────────────────────────────────────────────────────
$("#al-add").addEventListener("click", async () => {
  const symbol = $("#al-symbol").value.trim();
  if (!symbol) {
    toast("종목을 입력하세요.");
    return;
  }
  try {
    await apiPost("/api/alerts", {
      id: "",
      symbol,
      name: symbol,
      metric: $("#al-metric").value,
      op: $("#al-op").value,
      value: +$("#al-value").value || null,
    });
    toast("알림 추가됨", "good");
    renderAlerts();
  } catch (e) {
    err(e);
  }
});
$("#al-check").addEventListener("click", checkAlerts);

async function renderAlerts() {
  try {
    const rules = await apiGet("/api/alerts");
    if (!rules.length) {
      $("#al-list").innerHTML =
        `<div class="empty">알림 규칙이 없습니다.</div>`;
      return;
    }
    $("#al-list").innerHTML = rules
      .map(
        (a) => `
      <div class="row" style="justify-content:space-between;border-bottom:1px solid var(--hairline);padding:8px 0">
        <span>${a.symbol} · ${metricLabel(a.metric)} ${opLabel(a.op)} ${a.value ?? ""}</span>
        <button class="pill ghost a-del" data-id="${a.id}">삭제</button></div>`,
      )
      .join("");
    $$(".a-del").forEach((b) =>
      b.addEventListener("click", async () => {
        await apiDel(`/api/alerts/${b.dataset.id}`);
        renderAlerts();
      }),
    );
  } catch (e) {
    err(e);
  }
}
async function checkAlerts() {
  $("#al-list").insertAdjacentHTML(
    "afterbegin",
    `<div class="note" id="al-checking"><span class="spinner"></span> 점검 중…</div>`,
  );
  try {
    const r = await apiGet("/api/alerts/check");
    $("#al-checking")?.remove();
    const fired = r.hits.filter((h) => h.triggered);
    if (!fired.length) {
      toast("충족된 알림이 없습니다.");
    }
    fired.forEach((h) => toast(`🔔 ${h.symbol}: ${h.message}`, "good"));
    $("#al-list")
      .querySelectorAll(".row")
      .forEach((row) => {
        /* keep list */
      });
  } catch (e) {
    $("#al-checking")?.remove();
    err(e);
  }
}
const metricLabel = (m) =>
  ({ price: "가격", rsi: "RSI", pct_change: "전일대비%", ma_cross: "MA교차" })[
    m
  ] || m;
const opLabel = (o) =>
  ({ gt: ">", lt: "<", cross_up: "골든크로스", cross_down: "데드크로스" })[o] ||
  o;

// ── AI recommendation ────────────────────────────────────────────────
let recoLoaded = false;
let recoMarket = "KR";
$$("#reco-market .pill").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#reco-market .pill").forEach((x) =>
      x.classList.toggle("active", x === b),
    );
    recoMarket = b.dataset.m;
    recoLoaded = false;
    scanView = false;
  }),
);
$("#reco-run").addEventListener("click", renderReco);

function factorBar(label, v) {
  const w = v == null ? 0 : Math.max(0, Math.min(100, v));
  const color =
    w >= 70 ? "var(--up)" : w <= 35 ? "var(--down)" : "var(--primary)";
  return `<div class="factor-row"><span class="flabel">${label}</span>
    <span class="factor-bar"><i style="width:${w}%;background:${color}"></i></span>
    <span class="fval">${v == null ? "—" : Math.round(v)}</span></div>`;
}

let recoData = null;
let recoCat = "bluechip";
let recoSector = "all";
let scanData = null; // cached whole-market turnaround scan result
let scanView = false; // showing scan results instead of curated list

function recoCard(p) {
  const tags = [
    ...p.strengths.map((s) => `<span class="tag good">+ ${s}</span>`),
    ...p.weaknesses.map((s) => `<span class="tag bad">− ${s}</span>`),
  ].join("");
  return `
    <div class="reco-card" data-sym="${p.symbol}" data-name="${p.name}" data-mkt="${p.market}">
      <div class="top">
        <span class="rname" title="${p.name}">${p.name}</span>
        <span class="rscore">${num(p.score, 0)}</span>
      </div>
      <div class="rsym">${p.symbol} · <span class="sector-chip">${p.sector}</span>${p.ret_1y != null ? ` · 1Y <span class="${cls(p.ret_1y)}">${sign(p.ret_1y)}${num(p.ret_1y, 0)}%</span>` : ""}</div>
      <div class="rprice">${num(p.price)}${p.per != null ? ` · PER ${num(p.per, 0)}` : ""}${p.pbr != null ? ` · PBR ${num(p.pbr, 1)}` : ""}${p.roe != null ? ` · ROE ${num(p.roe, 0)}%` : ""}</div>
      <div class="rwhy">${p.rationale || ""}</div>
      <div class="rfin">📑 ${p.fin_note || "재무 데이터 제한"}</div>
      <div class="tags">${tags}</div>
      ${factorBar("모멘텀", p.momentum)}${factorBar("추세", p.trend)}${factorBar("가치", p.value)}${factorBar("퀄리티", p.quality)}${factorBar("재무", p.financial)}
    </div>`;
}

function wireRecoCards() {
  $$("#reco-body .reco-card").forEach((c) =>
    c.addEventListener("click", () => {
      pick({
        symbol: c.dataset.sym,
        name: c.dataset.name,
        market: c.dataset.mkt,
      });
      activateTab("overview");
    }),
  );
}

function paintReco() {
  if (!recoData) return;
  const cat =
    recoData.categories.find((c) => c.key === recoCat) ||
    recoData.categories[0];
  const isTurn = recoCat === "turnaround";

  // sector filter chips (from this category's sectors); hidden in scan view
  const sectors = cat.sectors.map((s) => s.sector);
  $("#reco-sectorbar").innerHTML =
    isTurn && scanView
      ? ""
      : `<button class="pill ${recoSector === "all" ? "active" : ""}" data-s="all">전체</button>` +
        sectors
          .map(
            (s) =>
              `<button class="pill ${recoSector === s ? "active" : ""}" data-s="${s}">${s}</button>`,
          )
          .join("");
  $$("#reco-sectorbar .pill").forEach((b) =>
    b.addEventListener("click", () => {
      recoSector = b.dataset.s;
      paintReco();
    }),
  );

  if (isTurn && scanView) {
    paintScan();
    return;
  }

  // scan toolbar (turnaround category only)
  const scanBar = isTurn
    ? `<div class="scan-toolbar">
        <button class="btn" id="scan-run">🔍 전시장 스캔 — 전 종목에서 턴어라운드 발굴</button>
        <span class="note" style="margin-top:0;flex:1;min-width:220px">큐레이션 목록이 아닌 시장 전체(KR: 시총 1000억↑ / US: S&P500)에서 스캔합니다. 최초 실행은 수 분 소요.</span>
      </div>`
    : "";

  // body: sector groups (filtered)
  const groups = cat.sectors.filter(
    (g) => recoSector === "all" || g.sector === recoSector,
  );
  $("#reco-body").innerHTML =
    `<div class="reco-cat-sub">${cat.subtitle}</div>` +
    scanBar +
    (groups.length
      ? groups
          .map(
            (g) => `<div class="sector-block">
        <div class="sector-head"><span class="sector-name">${g.sector}</span><span class="sector-count">${g.picks.length}종목</span></div>
        <div class="reco-grid">${g.picks.map(recoCard).join("")}</div>
      </div>`,
          )
          .join("")
      : `<div class="empty">해당 섹터 종목이 없습니다.</div>`) +
    `<div class="note">생성 ${recoData.generated} · ${recoData.note}</div>`;
  if (isTurn) $("#scan-run").addEventListener("click", runScan);
  wireRecoCards();
}

function paintScan() {
  const back = `<div class="scan-toolbar">
      <button class="pill ghost" id="scan-back">← 큐레이션 추천으로</button>
    </div>`;
  if (!scanData) {
    $("#reco-body").innerHTML =
      back + `<div class="empty">스캔 결과가 없습니다.</div>`;
  } else {
    const d = scanData;
    $("#reco-body").innerHTML =
      back +
      `<div class="scan-head">스캔 ${num(d.scanned, 0)}종목 → 후보군 ${num(d.pool, 0)} → 상위 ${d.picks.length}</div>` +
      `<div class="note">${d.note || ""}</div>` +
      (d.picks.length
        ? `<div class="reco-grid">${d.picks.map(recoCard).join("")}</div>`
        : `<div class="empty">턴어라운드 후보가 없습니다.</div>`) +
      `<div class="note">생성 ${d.generated}</div>`;
    wireRecoCards();
  }
  $("#scan-back").addEventListener("click", () => {
    scanView = false;
    paintReco();
  });
}

async function runScan() {
  scanView = true;
  $("#reco-sectorbar").innerHTML = "";
  $("#reco-body").innerHTML =
    `<div class="loading"><span class="spinner"></span> 전시장 스캔 중… KR은 ~350종목 히스토리+재무를 훑으므로 최초 실행은 수 분 걸릴 수 있습니다.</div>`;
  // reuse cached result if it matches the current market
  if (scanData && scanData.market === recoMarket) {
    paintScan();
    return;
  }
  try {
    const r = await apiGet(
      `/api/turnaround-scan?market=${recoMarket}&limit=24`,
    );
    r.market = recoMarket; // remember which market this scan was for
    scanData = r;
    paintScan();
  } catch (e) {
    $("#reco-body").innerHTML =
      `<div class="scan-toolbar"><button class="pill ghost" id="scan-back">← 큐레이션 추천으로</button></div><div class="empty">스캔 실패: ${e.message}</div>`;
    $("#scan-back").addEventListener("click", () => {
      scanView = false;
      paintReco();
    });
  }
}

async function renderReco() {
  $("#reco-body").innerHTML =
    `<div class="loading"><span class="spinner"></span> 멀티팩터 분석 중… 재무제표까지 반영하므로 최초 생성은 1~2분 걸릴 수 있습니다.</div>`;
  $("#reco-catbar").innerHTML = "";
  $("#reco-sectorbar").innerHTML = "";
  try {
    const r = await apiGet(`/api/recommend?market=${recoMarket}`);
    recoData = r;
    recoLoaded = true;
    recoSector = "all";
    scanView = false;
    if (!r.categories.some((c) => c.key === recoCat))
      recoCat = r.categories[0].key;
    // category segmented control
    $("#reco-catbar").innerHTML = r.categories
      .map(
        (c) =>
          `<button class="pill ${c.key === recoCat ? "active" : ""}" data-c="${c.key}">${c.title}</button>`,
      )
      .join("");
    $$("#reco-catbar .pill").forEach((b) =>
      b.addEventListener("click", () => {
        recoCat = b.dataset.c;
        recoSector = "all";
        scanView = false;
        paintReco();
        $$("#reco-catbar .pill").forEach((x) =>
          x.classList.toggle("active", x === b),
        );
      }),
    );
    paintReco();
  } catch (e) {
    $("#reco-body").innerHTML =
      `<div class="empty">추천 생성 실패: ${e.message}</div>`;
  }
}

// ── industry cycle ───────────────────────────────────────────────────
let cycleLoaded = false;
let cycleMarket = "KR";
const PHASE_CLASS = {
  확장: "expansion",
  회복: "recovery",
  둔화: "slowdown",
  침체: "contraction",
};
$$("#cycle-market .pill").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#cycle-market .pill").forEach((x) =>
      x.classList.toggle("active", x === b),
    );
    cycleMarket = b.dataset.m;
    cycleLoaded = false;
  }),
);
$("#cycle-run").addEventListener("click", renderCycle);

function retCell(label, v) {
  const c = v == null ? "" : cls(v);
  return `<div class="rcell"><div class="rk">${label}</div><div class="rv ${c}">${v == null ? "—" : sign(v) + num(v, 0) + "%"}</div></div>`;
}
function axisChip(label, v) {
  const col =
    v == null
      ? "var(--secondary)"
      : v >= 65
        ? "var(--up)"
        : v <= 35
          ? "var(--down)"
          : "var(--ink)";
  return `<span class="axis-chip"><b>${label}</b> <span style="color:${col}">${v == null ? "—" : num(v, 0)}</span></span>`;
}

function sparkline(el, curve, up) {
  if (!curve || !curve.length) return;
  const chart = LWC.createChart(el, {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: { background: { color: "transparent" }, textColor: "transparent" },
    grid: { vertLines: { visible: false }, horzLines: { visible: false } },
    rightPriceScale: { visible: false },
    leftPriceScale: { visible: false },
    timeScale: { visible: false },
    crosshair: { mode: 0 },
    handleScroll: false,
    handleScale: false,
  });
  const s = chart.addAreaSeries({
    lineColor: up ? "#34c759" : "#ff3b30",
    lineWidth: 2,
    topColor: up ? "rgba(52,199,89,.20)" : "rgba(255,59,48,.18)",
    bottomColor: "rgba(0,0,0,0)",
    priceLineVisible: false,
    lastValueVisible: false,
  });
  s.setData(curve.map((p) => ({ time: p.time, value: p.value })));
  chart.timeScale().fitContent();
}

async function renderCycle() {
  $("#cycle-body").innerHTML =
    `<div class="loading"><span class="spinner"></span> 산업 사이클 분석 중… 여러 테마의 가격지수를 계산하므로 최초 생성은 1~2분 걸릴 수 있습니다.</div>`;
  try {
    const r = await apiGet(`/api/cycles?market=${cycleMarket}`);
    cycleLoaded = true;
    const cards = r.themes
      .map(
        (t) => `
      <div class="cycle-card" data-members="${t.members.join(",")}" data-name="${t.name}">
        <div class="ctop"><span class="cname">${t.phase_emoji} ${t.name}</span><span class="cscore">${num(t.score, 0)}</span></div>
        <span class="phase-pill phase-${PHASE_CLASS[t.phase] || "recovery"}">${t.phase} 국면</span>
        <span style="font-size:11.5px;color:var(--secondary)"> · 시장 대비 RS ${t.rs_3m == null ? "—" : (t.rs_3m > 0 ? "+" : "") + num(t.rs_3m, 0) + "%p"}</span>
        <div class="cycle-rets">
          ${retCell("1M", t.ret_1m)}${retCell("3M", t.ret_3m)}${retCell("6M", t.ret_6m)}${retCell("12M", t.ret_12m)}
        </div>
        <div class="cycle-axes">
          ${axisChip("가격", t.price_score)}${axisChip("이익", t.earnings_score)}${axisChip("밸류", t.valuation_score)}
        </div>
        <div class="cycle-spark" id="spark-${t.key}"></div>
        <div class="ccomment">${t.comment}</div>
        <div class="cfund">📑 ${t.fund_note || ""}</div>
        <div class="cleaders"><b>주도주</b> ${t.leaders.join(" · ") || "—"}</div>
      </div>`,
      )
      .join("");
    $("#cycle-body").innerHTML = `
      <div class="card">
        <div class="cycle-legend">
          <span>🔵 회복: 바닥에서 반등 시작</span><span>🟢 확장: 추세·모멘텀 강세(주도)</span>
          <span>🟡 둔화: 고점권 모멘텀 약화</span><span>🔴 침체: 추세·모멘텀 약세</span>
        </div>
        <div class="cycle-grid">${cards}</div>
        <div class="note">벤치마크 ${r.benchmark} · 생성 ${r.generated} · ${r.note}</div>
      </div>`;
    r.themes.forEach((t) => {
      const el = document.getElementById(`spark-${t.key}`);
      if (el) sparkline(el, t.index_curve, (t.ret_3m || 0) >= 0);
    });
    $$("#cycle-body .cycle-card").forEach((c) =>
      c.addEventListener("click", () => {
        const first = (c.dataset.members || "").split(",")[0];
        if (first) {
          pick({ symbol: first, name: c.dataset.name, market: cycleMarket });
          activateTab("overview");
        }
      }),
    );
  } catch (e) {
    $("#cycle-body").innerHTML =
      `<div class="empty">사이클 분석 실패: ${e.message}</div>`;
  }
}

// ── trade: position sizing ───────────────────────────────────────────
function syncStopMode() {
  const m = $("#ps-mode").value;
  $("#ps-atr-wrap").style.display = m === "atr" ? "flex" : "none";
  $("#ps-pct-wrap").style.display = m === "pct" ? "flex" : "none";
  $("#ps-price-wrap").style.display = m === "price" ? "flex" : "none";
}
$("#ps-mode").addEventListener("change", syncStopMode);
$("#ps-run").addEventListener("click", async () => {
  const psSymbol = $("#ps-symbol").value.trim() || null;
  const body = {
    symbol: psSymbol,
    account: +$("#ps-account").value || 0,
    risk_pct: +$("#ps-risk").value || 1,
    entry: +$("#ps-entry").value || null,
    stop_mode: $("#ps-mode").value,
    atr_mult: +$("#ps-atr").value || 2,
    stop_pct: +$("#ps-pct").value || null,
    stop_price: +$("#ps-stop").value || null,
    rr: +$("#ps-rr").value || 2,
    direction: $("#ps-dir").value,
  };
  $("#ps-result").innerHTML =
    `<div class="loading"><span class="spinner"></span> 계산 중…</div>`;
  try {
    const r = await apiPost("/api/position", body);
    const cur = r.currency;
    $("#ps-result").innerHTML = `
      <div class="ps-levels">
        <div class="lvl stop"><div class="lk">손절</div><div class="lv">${num(r.stop)}</div></div>
        <div class="lvl entry"><div class="lk">진입</div><div class="lv">${num(r.entry)}</div></div>
        <div class="lvl target"><div class="lk">목표 (R:R ${r.rr})</div><div class="lv">${num(r.target)}</div></div>
      </div>
      <div class="ps-out">
        <div><div class="k">매수 수량</div><div class="v">${num(r.shares, 0)}주</div></div>
        <div><div class="k">투입 금액</div><div class="v">${cap(r.position_value, cur)} <span style="font-size:12px;color:var(--secondary)">(${num(r.position_pct)}%)</span></div></div>
        <div><div class="k">감수 손실 (1R)</div><div class="v" style="color:var(--down)">${cap(r.risk_amount, cur)}</div></div>
        <div><div class="k">목표 수익</div><div class="v" style="color:#1f9e4a">${cap(r.reward_amount, cur)}</div></div>
        <div><div class="k">주당 리스크</div><div class="v">${num(r.risk_per_share)}</div></div>
        ${r.atr != null ? `<div><div class="k">ATR(14)</div><div class="v">${num(r.atr)}</div></div>` : ""}
      </div>
      <div class="row" style="margin-top:12px">
        <button class="btn sec" id="ps-tochart">📈 차트에 레벨 표시</button>
      </div>
      ${r.note ? `<div class="note" style="color:var(--down)">${r.note}</div>` : ""}`;
    $("#ps-tochart").addEventListener("click", () => {
      // if a symbol was typed use it, else fall back to the selected symbol
      const lvlSym = psSymbol || state.symbol || null;
      state.levels = {
        symbol: lvlSym,
        entry: r.entry,
        stop: r.stop,
        target: r.target,
      };
      toast("차트 탭에서 진입/손절/목표 라인이 표시됩니다");
    });
  } catch (e) {
    $("#ps-result").innerHTML =
      `<div class="empty">계산 실패: ${e.message}</div>`;
  }
});

// ── trade: journal ───────────────────────────────────────────────────
$("#tj-add").addEventListener("click", async () => {
  const symbol = $("#tj-symbol").value.trim();
  if (!symbol) {
    toast("종목을 입력하세요.");
    return;
  }
  const eprice = +$("#tj-eprice").value;
  if (!eprice) {
    toast("진입가를 입력하세요.");
    return;
  }
  try {
    await apiPost("/api/journal", {
      symbol,
      name: symbol,
      market: symbol.match(/^\d{6}$/) ? "KR" : "US",
      direction: $("#tj-dir").value,
      entry_date: $("#tj-edate").value,
      entry_price: eprice,
      shares: +$("#tj-shares").value || 0,
      stop_price: +$("#tj-stop").value || null,
      exit_date: $("#tj-xdate").value || null,
      exit_price: +$("#tj-xprice").value || null,
      setup: $("#tj-setup").value,
    });
    [
      "tj-symbol",
      "tj-eprice",
      "tj-shares",
      "tj-stop",
      "tj-xprice",
      "tj-setup",
    ].forEach((id) => ($("#" + id).value = ""));
    toast("매매 기록 추가됨", "good");
    renderJournal();
  } catch (e) {
    err(e);
  }
});

async function renderJournal() {
  try {
    const r = await apiGet("/api/journal");
    const s = r.stats;
    const rcls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
    $("#journal-stats").innerHTML = `<div class="jstats">
      <div><div class="k">전체/청산</div><div class="v">${s.total}/${s.closed}</div></div>
      <div><div class="k">승률</div><div class="v">${s.win_rate == null ? "—" : s.win_rate + "%"}</div></div>
      <div><div class="k">평균 R</div><div class="v ${rcls(s.avg_r)}">${s.avg_r == null ? "—" : s.avg_r + "R"}</div></div>
      <div><div class="k">기대값</div><div class="v ${rcls(s.expectancy_r)}">${s.expectancy_r == null ? "—" : s.expectancy_r + "R"}</div></div>
      <div><div class="k">누적 손익</div><div class="v ${rcls(s.total_pnl)}">${num(s.total_pnl, 0)}</div></div>
      <div><div class="k">손익비(PF)</div><div class="v">${s.profit_factor == null ? "—" : s.profit_factor}</div></div>
    </div>`;
    if (!r.trades.length) {
      $("#journal-list").innerHTML =
        `<div class="empty" style="margin-top:12px">기록이 없습니다. 위에서 매매를 추가하세요.</div>`;
      return;
    }
    $("#journal-list").innerHTML = `<table style="margin-top:14px"><thead><tr>
      <th>종목</th><th>방향</th><th>진입일</th><th>진입가</th><th>청산가</th><th>수량</th><th>손익</th><th>수익률</th><th>R</th><th>셋업</th><th></th></tr></thead><tbody>
      ${r.trades
        .map(
          (t) => `<tr>
        <td>${t.symbol}</td><td>${t.direction === "long" ? "매수" : "매도"}</td>
        <td>${t.entry_date || "—"}</td><td>${num(t.entry_price)}</td>
        <td>${t.exit_price == null ? `<span class="j-open">보유중</span>` : num(t.exit_price)}</td>
        <td>${num(t.shares, 0)}</td>
        <td class="num ${cls(t.pnl)}">${t.pnl == null ? "—" : num(t.pnl, 0)}</td>
        <td class="num ${cls(t.pnl_pct)}">${t.pnl_pct == null ? "—" : sign(t.pnl_pct) + num(t.pnl_pct) + "%"}</td>
        <td class="num ${cls(t.r_multiple)}">${t.r_multiple == null ? "—" : t.r_multiple + "R"}</td>
        <td style="text-align:left;max-width:160px;overflow:hidden;text-overflow:ellipsis">${t.setup || ""}</td>
        <td><button class="pill ghost tj-del" data-id="${t.id}">✕</button></td></tr>`,
        )
        .join("")}
      </tbody></table>`;
    $$("#journal-list .tj-del").forEach((b) =>
      b.addEventListener("click", async () => {
        await apiDel(`/api/journal/${b.dataset.id}`);
        renderJournal();
      }),
    );
  } catch (e) {
    err(e);
  }
}

// ── overview: KR investor flows card ──────────────────────────────────
async function renderFlows() {
  if (!state.symbol || state.market !== "KR") return;
  const host = document.getElementById("flow-card");
  if (!host) return;
  try {
    const f = await apiGet(`/api/flows?symbol=${state.symbol}`);
    if (!f.days || !f.days.length) {
      host.innerHTML = `<div class="empty">${f.note || "수급 데이터 없음"}</div>`;
      return;
    }
    const fmtK = (v) =>
      v == null
        ? "—"
        : (v >= 0 ? "+" : "") + Math.round(v / 1000).toLocaleString() + "K주";
    host.innerHTML = `
      <div class="flow-bars">
        <div class="flow-row"><span class="fl-k">외국인 5일</span><span class="fl-v ${cls(f.foreign_sum_5d)}">${fmtK(f.foreign_sum_5d)}</span>
          <span class="fl-k" style="margin-left:14px">20일</span><span class="fl-v ${cls(f.foreign_sum_20d)}">${fmtK(f.foreign_sum_20d)}</span></div>
        <div class="flow-row"><span class="fl-k">기관 5일</span><span class="fl-v ${cls(f.inst_sum_5d)}">${fmtK(f.inst_sum_5d)}</span>
          <span class="fl-k" style="margin-left:14px">20일</span><span class="fl-v ${cls(f.inst_sum_20d)}">${fmtK(f.inst_sum_20d)}</span></div>
        <div class="flow-row"><span class="fl-k">외국인 보유율</span><span class="fl-v">${f.days[f.days.length - 1].foreign_hold_pct ?? "—"}%</span></div>
      </div>
      <div class="note">최근 20거래일 누적 순매매. 외국인·기관 동반 매수는 강세 신호로 해석됩니다.</div>`;
  } catch (e) {
    host.innerHTML = `<div class="empty">수급 조회 실패</div>`;
  }
}

// ── tab badges (triggered alerts) ─────────────────────────────────────
function setTabBadge(tab, count) {
  const btn = $(`#tabs .tab[data-tab="${tab}"]`);
  if (!btn) return;
  let badge = btn.querySelector(".tab-badge");
  if (!count) {
    if (badge) badge.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "tab-badge";
    btn.appendChild(badge);
  }
  badge.textContent = String(count);
}
function clearTabBadge(tab) {
  setTabBadge(tab, 0);
}

// ── market regime banner (header) ─────────────────────────────────────
async function loadRegime() {
  try {
    const r = await apiGet("/api/regime");
    const bar = $("#regime-bar");
    if (!bar || !r.items || !r.items.length) return;
    bar.innerHTML = r.items
      .map((it) => {
        const dot = it.above_ma200 ? "🟢" : "🔴";
        const chg =
          it.change_pct == null
            ? "—"
            : sign(it.change_pct) + num(it.change_pct) + "%";
        const tip =
          it.ret_1m == null
            ? ""
            : `1개월 수익률 ${sign(it.ret_1m)}${num(it.ret_1m)}%`;
        return `<span class="regime-chip" title="${tip}">${dot}
          <span class="rg-name">${it.index_name}</span>
          <span class="rg-chg ${cls(it.change_pct)}">${chg}</span></span>`;
      })
      .join("");
  } catch (e) {
    /* fail silent — keep the old hint text (title attr) */
  }
}

// ── alerts auto-check on load + tab badge ─────────────────────────────
async function autoCheckAlerts() {
  try {
    const rules = await apiGet("/api/alerts");
    if (!rules.length) return;
    const r = await apiGet("/api/alerts/check");
    const fired = r.hits.filter((h) => h.triggered);
    if (!fired.length) return;
    fired
      .slice(0, 3)
      .forEach((h) => toast(`🔔 ${h.symbol}: ${h.message}`, "good"));
    setTabBadge("alerts", fired.length);
  } catch (e) {
    /* fail silent */
  }
}

// ── feature footprint (health) ────────────────────────────────────────
async function checkHealth() {
  try {
    const h = await apiGet("/api/health");
    if (h.features && h.features.gemini === false) {
      toast(
        "Gemini 키가 없어 AI 서술 기능이 비활성화됩니다 (숫자 분석은 정상)",
      );
    }
  } catch (e) {
    /* fail silent */
  }
}

// ── init ─────────────────────────────────────────────────────────────
syncStopMode();
addFilterRow("per", "lt", "15");
addFilterRow("roe", "gt", "10");
addHoldingRow();
window.activateTab = activateTab; // for inline onclick

document.addEventListener("DOMContentLoaded", () => {
  loadRegime();
  autoCheckAlerts(); // non-blocking, runs after regime kicks off
  checkHealth();
});
