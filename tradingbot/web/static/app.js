/* Trading Bot dashboard. Plain JS, no build step. */
"use strict";

const LC = window.LightweightCharts;
const $ = (sel, root = document) => root.querySelector(sel);
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const alpha = (hex, a) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

// Charts work in UTC seconds; shift so the axis shows local time.
const TZ_SHIFT = -new Date().getTimezoneOffset() * 60;
const chartTime = (ms) => Math.floor(ms / 1000) + TZ_SHIFT;

// ------------------------------------------------------------------ format

const nfCache = {};
const nf = (d) => (nfCache[d] ||= new Intl.NumberFormat("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d }));
const priceDigits = (v) => (v >= 1000 ? 2 : v >= 10 ? 3 : v >= 1 ? 4 : 6);
const fmtNum = (v, d = 2) => (v == null ? "—" : nf(d).format(v));
const fmtPrice = (v) => (v == null ? "—" : nf(priceDigits(Math.abs(v))).format(v));
const fmtQty = (v) => (v == null ? "—" : nf(v >= 100 ? 2 : 6).format(v));
const fmtPct = (v, sign = true) => (v == null ? "—" : `${sign && v > 0 ? "+" : ""}${nf(2).format(v)} %`);
const fmtTime = (ms) =>
  new Date(ms).toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const tone = (v) => (v == null || v === 0 ? "" : v > 0 ? "pos" : "neg");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
    throw new Error(detail || `Error ${res.status}`);
  }
  return data;
}

// ------------------------------------------------------------------ charts

function chartOptions() {
  return {
    autoSize: true,
    layout: {
      background: { type: "solid", color: cssVar("--surface") },
      textColor: cssVar("--muted"),
      fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    },
    grid: { vertLines: { color: cssVar("--grid") }, horzLines: { color: cssVar("--grid") } },
    rightPriceScale: { borderColor: cssVar("--border") },
    timeScale: { borderColor: cssVar("--border"), timeVisible: true, secondsVisible: false },
    crosshair: { mode: LC.CrosshairMode.Normal },
  };
}

/** Price chart (+ optional indicator pane) and equity chart, kept in sync. */
class ChartSet {
  constructor(priceEl, indEl, equityEl, { recentBars = 0 } = {}) {
    this.els = { priceEl, indEl, equityEl };
    this.recentBars = recentBars; // 0 = show everything
    this.charts = [];
    this.snapshot = null;
  }

  destroy() {
    this.charts.forEach((c) => c.remove());
    this.charts = [];
  }

  load(snapshot) {
    this.snapshot = snapshot;
    this.destroy();
    const { priceEl, indEl, equityEl } = this.els;
    const plots = snapshot.strategy.plots || [];
    const overlays = plots.filter((p) => p.overlay);
    const panes = plots.filter((p) => !p.overlay);
    const palette = [cssVar("--line-1"), cssVar("--line-2"), cssVar("--line-3")];
    const up = cssVar("--up"), down = cssVar("--down");

    const lastClose = snapshot.candles.at(-1)?.close ?? 1;
    const precision = priceDigits(lastClose);

    this.price = LC.createChart(priceEl, chartOptions());
    this.candles = this.price.addCandlestickSeries({
      upColor: up, downColor: down, borderUpColor: up, borderDownColor: down, wickUpColor: up, wickDownColor: down,
      priceFormat: { type: "price", precision, minMove: 1 / 10 ** precision },
    });
    this.lines = {};
    overlays.forEach((p, i) => {
      this.lines[p.name] = this.price.addLineSeries({
        color: palette[i % palette.length], lineWidth: 1.5, title: p.name,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
    });
    this.charts = [this.price];

    indEl.hidden = panes.length === 0;
    if (panes.length) {
      this.ind = LC.createChart(indEl, chartOptions());
      panes.forEach((p, i) => {
        const s = this.ind.addLineSeries({
          color: palette[i % palette.length], lineWidth: 1.5, title: p.name, priceLineVisible: false,
        });
        p.levels.forEach((level) =>
          s.createPriceLine({ price: level, color: cssVar("--muted"), lineWidth: 1, lineStyle: LC.LineStyle.Dashed, axisLabelVisible: true })
        );
        this.lines[p.name] = s;
      });
      this.charts.push(this.ind);
    }

    this.equityChart = LC.createChart(equityEl, chartOptions());
    this.equity = this.equityChart.addBaselineSeries({
      baseValue: { type: "price", price: snapshot.account.initial_cash },
      topLineColor: up, bottomLineColor: down,
      topFillColor1: alpha(up, 0.25), topFillColor2: alpha(up, 0),
      bottomFillColor1: alpha(down, 0), bottomFillColor2: alpha(down, 0.25),
      lineWidth: 2, priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    this.charts.push(this.equityChart);

    this._setData(snapshot);
    this._sync();
  }

  _setData(snap) {
    const times = snap.candles.map((c) => chartTime(c.time));
    this.candles.setData(snap.candles.map((c) => ({ time: chartTime(c.time), open: c.open, high: c.high, low: c.low, close: c.close })));

    // Every chart gets one point per candle (blank where there is no value),
    // so scrolling and zooming stay aligned across charts.
    const padded = (pairs) => {
      const byTime = new Map(pairs.map(([t, v]) => [chartTime(t), v]));
      return times.map((time) => (byTime.has(time) ? { time, value: byTime.get(time) } : { time }));
    };
    for (const [name, series] of Object.entries(this.lines)) series.setData(padded(snap.indicators[name] || []));
    this.equity.setData(padded(snap.equity));

    this.fills = [...snap.fills];
    this._markers();
    this.price.timeScale().fitContent();
    if (this.recentBars && times.length > this.recentBars) {
      this.price.timeScale().setVisibleLogicalRange({ from: times.length - this.recentBars, to: times.length + 2 });
    }
  }

  _markers() {
    const up = cssVar("--up"), down = cssVar("--down");
    this.candles.setMarkers(
      this.fills.map((f) => ({
        time: chartTime(f.time),
        position: f.side === "BUY" ? "belowBar" : "aboveBar",
        color: f.side === "BUY" ? up : down,
        shape: f.side === "BUY" ? "arrowUp" : "arrowDown",
      }))
    );
  }

  _sync() {
    let busy = false;
    for (const src of this.charts) {
      src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || busy) return;
        busy = true;
        for (const dst of this.charts) if (dst !== src) dst.timeScale().setVisibleLogicalRange(range);
        busy = false;
      });
    }
  }

  updateCandle(c) {
    if (!this.candles) return;
    const time = chartTime(c.time);
    this.candles.update({ time, open: c.open, high: c.high, low: c.low, close: c.close });
    for (const s of Object.values(this.lines)) s.update({ time });
    this.equity.update({ time });
  }

  addBar(ev) {
    if (!this.candles) return;
    this.updateCandle(ev.candle);
    const time = chartTime(ev.candle.time);
    for (const [name, series] of Object.entries(this.lines)) {
      if (ev.indicators[name] != null) series.update({ time, value: ev.indicators[name] });
    }
    if (ev.equity) this.equity.update({ time, value: ev.equity[1] });
    if (ev.fills.length) {
      this.fills.push(...ev.fills);
      this._markers();
    }
  }
}

// --------------------------------------------------------------- KPIs etc.

function renderKpis(el, m, { sharpe = false } = {}) {
  const items = [
    ["Capital", fmtNum(m.final_equity), `inicial ${fmtNum(m.initial_equity, 0)}`, ""],
    ["Rentabilidad", fmtPct(m.return_pct), "", tone(m.return_pct)],
    ["Comprar y mantener", fmtPct(m.buy_hold_pct), "referencia", tone(m.buy_hold_pct)],
    ["Máx. drawdown", m.max_drawdown_pct ? fmtPct(-m.max_drawdown_pct, false) : "0,00 %", "", m.max_drawdown_pct ? "neg" : ""],
    ["Operaciones", String(m.trades), m.win_rate_pct == null ? "sin cerrar" : `${fmtNum(m.win_rate_pct, 0)} % aciertos`, ""],
    ["Profit factor", fmtNum(m.profit_factor), m.avg_trade_pct == null ? "" : `media ${fmtPct(m.avg_trade_pct)}`, ""],
  ];
  if (sharpe) items.push(["Sharpe", fmtNum(m.sharpe), "anualizado", tone(m.sharpe)]);
  el.innerHTML = items
    .map(([label, value, sub, cls]) =>
      `<div class="kpi"><div class="label">${label}</div><div class="value ${cls}">${value}</div><div class="sub">${sub || "&nbsp;"}</div></div>`)
    .join("");
}

function renderFills(table, fills) {
  const rows = fills.slice(-300).reverse();
  table.innerHTML =
    `<thead><tr><th>Fecha</th><th class="left">Tipo</th><th>Precio</th><th>Cantidad</th><th>Comisión</th><th class="left">Motivo</th></tr></thead><tbody>` +
    (rows.length
      ? rows.map((f) => `<tr>
          <td>${fmtTime(f.time)}</td>
          <td class="left side-${f.side.toLowerCase()}">${f.side === "BUY" ? "Compra" : "Venta"}</td>
          <td>${fmtPrice(f.price)}</td><td>${fmtQty(f.quantity)}</td><td>${fmtNum(f.fee, 4)}</td>
          <td class="left">${esc(f.reason)}</td></tr>`).join("")
      : `<tr><td colspan="6" class="empty-row">Aún no hay órdenes. La estrategia espera su señal.</td></tr>`) +
    "</tbody>";
}

function renderTrades(table, trades) {
  const rows = trades.slice().reverse();
  table.innerHTML =
    `<thead><tr><th>Entrada</th><th>Salida</th><th>Precio entrada</th><th>Precio salida</th><th>Resultado</th><th>P&amp;L</th></tr></thead><tbody>` +
    (rows.length
      ? rows.map((t) => `<tr>
          <td>${fmtTime(t.entry_time)}</td><td>${fmtTime(t.exit_time)}</td>
          <td>${fmtPrice(t.entry_price)}</td><td>${fmtPrice(t.exit_price)}</td>
          <td class="${tone(t.return_pct)}">${fmtPct(t.return_pct)}</td>
          <td class="${tone(t.pnl)}">${fmtNum(t.pnl)}</td></tr>`).join("")
      : `<tr><td colspan="6" class="empty-row">La estrategia no cerró ninguna operación en este periodo.</td></tr>`) +
    "</tbody>";
}

function renderPosition(el, account, price) {
  const open = account.quantity > 0;
  const pnl = open ? account.quantity * (price - account.entry_price) : null;
  const pnlPct = open ? (price / account.entry_price - 1) * 100 : null;
  const rows = [
    ["Estado", open ? `<span class="side-buy">Comprado</span>` : "Sin posición"],
    ["Cantidad", open ? fmtQty(account.quantity) : "—"],
    ["Precio de entrada", open ? fmtPrice(account.entry_price) : "—"],
    ["P&amp;L abierto", open ? `<span class="${tone(pnl)}">${fmtNum(pnl)} (${fmtPct(pnlPct)})</span>` : "—"],
    ["Efectivo", fmtNum(account.cash)],
    ["Capital total", fmtNum(account.equity)],
  ];
  el.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

// --------------------------------------------------------- strategy forms

let SCHEMAS = [];

function setupStrategyForm(form, { name, params = {}, risk } = {}) {
  const select = $(".strategy-select", form);
  select.innerHTML = SCHEMAS.map((s) => `<option value="${s.name}">${esc(s.title)}</option>`).join("");
  const render = (values) => {
    const schema = SCHEMAS.find((s) => s.name === select.value);
    $(".strategy-desc", form).textContent = schema.description;
    $(".params", form).innerHTML = Object.entries(schema.params)
      .map(([key, p]) => {
        const value = values[key] ?? p.default;
        const isFlag = p.type === "int" && p.min === 0 && p.max === 1;
        const input = isFlag
          ? `<select name="param:${key}"><option value="1"${value ? " selected" : ""}>Sí</option><option value="0"${value ? "" : " selected"}>No</option></select>`
          : `<input type="number" name="param:${key}" value="${value}" step="${p.type === "int" ? 1 : "any"}"` +
            `${p.min != null ? ` min="${p.min}"` : ""}${p.max != null ? ` max="${p.max}"` : ""} required>`;
        return `<label title="${esc(p.description)}">${esc(p.description || key)}${input}</label>`;
      })
      .join("");
  };
  select.onchange = () => render({});
  if (name && SCHEMAS.some((s) => s.name === name)) select.value = name;
  render(params);
  if (risk) {
    form.elements.position_size.value = Math.round(risk.position_size * 100);
    form.elements.stop_loss_pct.value = risk.stop_loss_pct;
    form.elements.take_profit_pct.value = risk.take_profit_pct;
  }
}

function readStrategyForm(form) {
  const params = {};
  for (const el of form.elements) {
    if (el.name?.startsWith("param:")) params[el.name.slice(6)] = Number(el.value);
  }
  return {
    strategy: form.elements.strategy.value,
    params,
    risk: {
      position_size: Number(form.elements.position_size.value) / 100,
      stop_loss_pct: Number(form.elements.stop_loss_pct.value) || 0,
      take_profit_pct: Number(form.elements.take_profit_pct.value) || 0,
    },
  };
}

async function submitting(form, fn) {
  const btn = $("button[type=submit]", form);
  const err = $(".form-error", form);
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Procesando…";
  err.hidden = true;
  try {
    await fn();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

// ------------------------------------------------------------------- live

const STATUS = {
  running: "En marcha",
  starting: "Conectando…",
  error: "Error",
  stopped: "Detenido",
};
const SOURCES = { binance: "Binance", synthetic: "Datos sintéticos" };

const live = {
  charts: new ChartSet($("#live-price-chart"), $("#live-ind-chart"), $("#live-equity-chart"), { recentBars: 180 }),
  state: null,
  formReady: false,
  ws: null,
  loading: null, // in-flight reload; events that arrive meanwhile are queued
  pending: [],
};

function setStatus(session) {
  const el = $("#live-status");
  el.textContent = STATUS[session.status] || session.status;
  el.className = `status status-${session.status}`;
  $("#live-source").textContent = SOURCES[session.source] || session.source;
  const err = $("#live-error");
  err.hidden = !session.error;
  err.textContent = session.error ? `Sin conexión con el mercado (${session.error}). Reintentando… Si persiste, revisa la red o cambia rest_url/ws_url en la configuración.` : "";
}

function setPrice(price) {
  if (price == null || !live.state) return;
  $("#live-price").textContent = fmtPrice(price);
  document.title = `${fmtPrice(price)} ${live.state.symbol} · Trading Bot`;
}

function renderLiveSummary() {
  const s = live.state;
  renderKpis($("#live-kpis"), s.metrics);
  renderPosition($("#live-position"), s.account, s.price);
  renderFills($("#live-fills"), s.fills);
  $("#live-fill-count").textContent = s.fills.length ? `${s.fills.length}` : "";
}

function loadLive() {
  // After a restart the old charts are stale: queue live events until the
  // new snapshot is drawn, then replay the ones it does not include yet.
  if (!live.loading) {
    live.loading = fetchLive().finally(() => {
      live.loading = null;
      const queued = live.pending.splice(0);
      const candles = live.state?.candles ?? [];
      const last = candles.at(-1)?.time ?? Infinity;
      const lastClosed = candles.findLast((c) => c.closed)?.time ?? -Infinity;
      for (const ev of queued) {
        if (ev.type === "bar" && ev.candle.time <= lastClosed) continue; // already in the snapshot
        if (ev.type === "candle" && ev.candle.time < last) continue;
        handleLiveEvent(ev);
      }
    });
  }
  return live.loading;
}

async function fetchLive() {
  const { session, state } = await api("/api/live");
  setStatus(session);
  if (!state) return;
  state.price = state.candles.at(-1)?.close;
  live.state = state;
  $("#live-symbol").textContent = state.symbol;
  $("#live-interval").textContent = state.interval;
  const params = Object.entries(state.strategy.params).map(([k, v]) => `${k} ${v}`).join(" · ");
  $("#live-strategy-label").textContent = `${state.strategy.title} · ${params}`;
  setPrice(state.price);
  renderLiveSummary();
  if (state.candles.length) live.charts.load(state);
  if (!live.formReady) {
    setupStrategyForm($("#live-form"), { ...state.strategy, risk: state.risk });
    live.formReady = true;
  }
}

function connectLive() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  live.ws = ws;
  ws.onmessage = (msg) => {
    const ev = JSON.parse(msg.data);
    if (ev.type === "reset" || ev.type === "status") {
      live.state = null;
      return void loadLive().catch(console.error);
    }
    if (live.loading) return void live.pending.push(ev);
    handleLiveEvent(ev);
  };
  ws.onclose = () => setTimeout(() => { connectLive(); loadLive().catch(console.error); }, 2000);
}

function handleLiveEvent(ev) {
  if (!live.state) return;
  try {
    applyLiveEvent(ev);
  } catch (e) {
    // Out-of-order data: redraw from a fresh snapshot instead of breaking.
    console.warn(e);
    loadLive().catch(console.error);
  }
}

function applyLiveEvent(ev) {
    if (ev.type === "candle") {
      live.charts.updateCandle(ev.candle);
      live.state.price = ev.candle.close;
      setPrice(ev.candle.close);
      renderPosition($("#live-position"), { ...live.state.account, equity: live.state.account.cash + live.state.account.quantity * ev.candle.close }, ev.candle.close);
    } else if (ev.type === "bar") {
      live.charts.addBar(ev);
      Object.assign(live.state, { account: ev.account, metrics: ev.metrics, price: ev.candle.close });
      live.state.fills.push(...ev.fills);
      setPrice(ev.candle.close);
      renderLiveSummary();
    }
}

$("#live-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  if (!confirm("Se reiniciará la cuenta virtual con la nueva estrategia. ¿Continuar?")) return;
  submitting(form, async () => {
    await api("/api/live/start", readStrategyForm(form));
    await loadLive();
  });
});

// --------------------------------------------------------------- backtest

const bt = { charts: new ChartSet($("#bt-price-chart"), $("#bt-ind-chart"), $("#bt-equity-chart")), result: null };

$("#bt-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  submitting(form, async () => {
    const body = {
      ...readStrategyForm(form),
      symbol: form.elements.symbol.value.trim(),
      interval: form.elements.interval.value,
      days: Number(form.elements.days.value),
      initial_cash: Number(form.elements.initial_cash.value),
    };
    const result = await api("/api/backtest", body);
    bt.result = result;
    $("#bt-empty").hidden = true;
    $("#bt-results").hidden = false;
    const c = result.candles;
    $("#bt-summary").textContent =
      `${result.symbol} ${result.interval} · ${result.strategy.title} · ${c.length} velas ` +
      `(${fmtTime(c[0].time)} – ${fmtTime(c.at(-1).time)}) · ${fmtNum(result.elapsed_s, 2)} s`;
    renderKpis($("#bt-kpis"), result.metrics, { sharpe: true });
    renderTrades($("#bt-trades"), result.trades);
    $("#bt-trade-count").textContent = result.trades.length ? `${result.trades.length}` : "";
    bt.charts.load(result);
  });
});

// ------------------------------------------------------------------- tabs

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t === tab);
      t.setAttribute("aria-selected", t === tab);
    });
    document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${tab.dataset.tab}`));
  })
);

// Redraw charts with the new colors when the system theme changes.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (live.charts.snapshot) live.charts.load(live.state);
  if (bt.result) bt.charts.load(bt.result);
});

// ------------------------------------------------------------------- boot

(async function boot() {
  try {
    const [schemas, config] = await Promise.all([api("/api/strategies"), api("/api/config")]);
    SCHEMAS = schemas;
    const btForm = $("#bt-form");
    setupStrategyForm(btForm, { ...config.strategy, risk: config.risk });
    btForm.elements.symbol.value = config.market.symbol;
    btForm.elements.initial_cash.value = config.paper.initial_cash;
    await loadLive();
  } catch (e) {
    console.error(e);
    const err = $("#live-error");
    err.textContent = `No se pudo cargar el estado: ${e.message}`;
    err.hidden = false;
  }
  connectLive();
})();
