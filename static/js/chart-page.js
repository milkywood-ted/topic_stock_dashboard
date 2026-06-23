// chart.html 페이지 글루 — 선택상태·fetch·사이드바·컨트롤 +
// 차트 팩토리(updateChart/drawMetricChart/drawCombinedChart)·플러그인·호버·Y축.
// 종목/그룹 데이터는 템플릿이 주입한 window.BOOT에서 읽는다. (ChartDrawer.js·toast.js 선행 로드)

const ALL_STOCKS = window.BOOT.stocks;
const ALL_GROUPS = window.BOOT.groups;

// ── 차트 호버 하이라이트 공통 함수 ──────────────────────────
const metricLabelPlugins = new WeakMap(); // chartInst → endLabelPlugin

function applyHoverToChart(chartInst, idx) {
  chartInst.data.datasets.forEach((ds, i) => {
    const base = ds._baseColor;
    if (!base) return;
    const origPr = ds._origPointRadius ?? 3;
    if (idx === -1) {
      ds.borderWidth        = 2;   ds.borderColor        = base;
      ds.backgroundColor    = base + '22';
      ds.pointRadius        = origPr; ds.pointHoverRadius   = 5;
      ds.pointBorderColor   = base;   ds.pointBackgroundColor = base;
    } else if (i === idx) {
      ds.borderWidth        = 3.5; ds.borderColor        = base;
      ds.backgroundColor    = base + '33';
      ds.pointRadius        = origPr; ds.pointHoverRadius   = 5;
      ds.pointBorderColor   = base;   ds.pointBackgroundColor = base;
    } else {
      ds.borderWidth        = 1;   ds.borderColor        = base + '50';
      ds.backgroundColor    = base + '0a';
      ds.pointRadius        = Math.min(1, origPr);
      ds.pointHoverRadius   = 0;
      ds.pointBorderColor   = base + '50'; ds.pointBackgroundColor = base + '50';
    }
  });
  const lp = metricLabelPlugins.get(chartInst);
  if (lp) lp._hoveredIdx = idx;
  chartInst.update('none');
}

// ── 통합 차트 플러그인 (십자가이드 + 라인 강조 + 끝 레이블) ─
const chartPlugin = {
  id: 'chartEnhancements',
  _x: null, _y: null, _hoveredIdx: -1, _labelBBoxes: [], _hoverSource: 'none',

  afterEvent(chart, args) {
    const e = args.event;
    const { chartArea: { top, bottom, left, right } } = chart;

    if (e.type === 'mousemove') {
      this._x = e.x; this._y = e.y;
      args.changed = true;

      let nearestIdx = -1, hoverSource = 'none';

      // 라인 근접 감지 (차트 영역 내)
      if (e.x >= left && e.x <= right && e.y >= top && e.y <= bottom) {
        let minDist = 25;
        chart.data.datasets.forEach((ds, i) => {
          const meta = chart.getDatasetMeta(i);
          if (!meta.visible) return;
          const pts = meta.data;
          for (let j = 0; j < pts.length - 1; j++) {
            const p1 = pts[j], p2 = pts[j + 1];
            if (isNaN(p1.y) || isNaN(p2.y)) continue;
            if (e.x >= p1.x && e.x <= p2.x) {
              const t = (p2.x - p1.x) === 0 ? 0 : (e.x - p1.x) / (p2.x - p1.x);
              const dist = Math.abs(e.y - (p1.y + t * (p2.y - p1.y)));
              if (dist < minDist) { minDist = dist; nearestIdx = i; }
              break;
            }
          }
        });
        if (nearestIdx !== -1) hoverSource = 'line';
      }

      // 레이블 bbox 감지 (오른쪽 여백, 라인보다 우선)
      const labelHit = this._labelBBoxes.find(
        b => e.x >= b.x && e.x <= b.x + b.w && e.y >= b.y && e.y <= b.y + b.h
      );
      if (labelHit) { nearestIdx = labelHit.idx; hoverSource = 'label'; }

      const changed = nearestIdx !== this._hoveredIdx || hoverSource !== this._hoverSource;
      if (changed) {
        this._hoveredIdx = nearestIdx;
        this._hoverSource = hoverSource;
        this._applyHover(chart, nearestIdx);

        if (hoverSource === 'label' && nearestIdx !== -1) {
          // 마지막 유효 데이터 포인트에 툴팁 고정
          const meta = chart.getDatasetMeta(nearestIdx);
          const ds   = chart.data.datasets[nearestIdx];
          let lastIdx = -1;
          for (let i = meta.data.length - 1; i >= 0; i--) {
            if (ds.data[i] !== null && !isNaN(ds.data[i])) { lastIdx = i; break; }
          }
          if (lastIdx !== -1) {
            const pt = meta.data[lastIdx];
            chart.tooltip.setActiveElements([{ datasetIndex: nearestIdx, index: lastIdx }], { x: pt.x, y: pt.y });
            chart.update();
          }
        } else if (hoverSource !== 'line') {
          // 레이블도 라인도 아니면 툴팁 초기화
          chart.tooltip.setActiveElements([], { x: 0, y: 0 });
          chart.update();
        }
      }
    } else if (e.type === 'mouseout') {
      this._x = null; this._y = null; this._hoverSource = 'none';
      if (this._hoveredIdx !== -1) {
        this._hoveredIdx = -1;
        this._applyHover(chart, -1);
        chart.tooltip.setActiveElements([], { x: 0, y: 0 });
        chart.update();
      }
    }
  },

  _applyHover(chart, idx) {
    applyHoverToChart(chart, idx);
    // 메트릭 차트: 캔버스 레벨 dimming (beforeDatasetDraw에서 처리)
    const hoveredTicker = idx !== -1 ? chart.data.datasets[idx]?.label : null;
    [metricInst.per, metricInst.pbr, metricInst.fcf].forEach(mc => {
      if (!mc) return;
      const mi = hoveredTicker
        ? mc.data.datasets.findIndex(ds => ds.label === hoveredTicker)
        : -1;
      const lp = metricLabelPlugins.get(mc);
      if (lp) lp._hoveredIdx = mi;
      mc.update('none');
    });
    // 복합 차트 — _ticker 기준으로 매칭
    if (combinedChartInst) {
      combinedChartInst.data.datasets.forEach(ds => {
        const base = ds._baseColor;
        if (!base) return;
        const match = !hoveredTicker || ds._ticker === hoveredTicker;
        if (ds.type === 'bar') {
          ds.backgroundColor = match ? base + '77' : base + '1a';
          ds.borderColor     = match ? base + 'cc' : base + '30';
        } else {
          ds.borderWidth        = match ? 3   : 1;
          ds.borderColor        = match ? base : base + '40';
          ds.pointRadius        = match ? 3   : 0;
          ds.pointHoverRadius   = match ? 5   : 0;
        }
      });
      combinedChartInst.update('none');
    }
  },

  afterDraw(chart) {
    const { ctx, chartArea: { top, bottom, left, right } } = chart;

    // 십자 가이드
    if (this._x !== null && this._x >= left && this._x <= right
        && this._y >= top && this._y <= bottom) {
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,.18)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(this._x, top);   ctx.lineTo(this._x, bottom); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left, this._y);  ctx.lineTo(right, this._y);  ctx.stroke();
      ctx.restore();
    }

    // 라인 끝 레이블
    const hasHover = this._hoveredIdx !== -1;
    this._labelBBoxes = [];
    chart.data.datasets.forEach((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      if (!meta.visible) return;
      const lastPt = [...meta.data].reverse().find(p => !p.skip && !isNaN(p.y) && p.y !== null);
      if (!lastPt) return;

      const isHovered = this._hoveredIdx === i;
      const alpha = hasHover && !isHovered ? 0.3 : 1;
      const base = ds._baseColor || ds.borderColor;
      const stock = ALL_STOCKS.find(s => s.ticker === ds.label);
      const label = stock ? stock.name : ds.label;
      const fs = isHovered ? 12 : 11;

      ctx.save();
      ctx.font = `${isHovered ? 'bold' : '600'} ${fs}px "SF Mono", monospace`;
      const tw = ctx.measureText(label).width;
      const px = right + 4, py = lastPt.y;
      const pad = 3;
      const bboxX = px - pad, bboxY = py - fs / 2 - pad;
      const bboxW = tw + pad * 3, bboxH = fs + pad * 2;

      // bbox 저장 (다음 mousemove에서 hit test용)
      this._labelBBoxes.push({ idx: i, x: bboxX, y: bboxY, w: bboxW, h: bboxH });

      // pill 배경
      ctx.globalAlpha = alpha * (isHovered ? 0.28 : 0.18);
      ctx.fillStyle = base;
      ctx.beginPath();
      ctx.roundRect(bboxX, bboxY, bboxW, bboxH, 3);
      ctx.fill();

      // 텍스트
      ctx.globalAlpha = alpha;
      ctx.fillStyle = base;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, px + pad / 2, py);
      ctx.restore();
    });
  }
};

// 차트 렌더 툴킷(테마·색상·축·툴팁·robustY)은 ChartDrawer.js로 분리됨.
ChartDrawer.init(ALL_STOCKS);

let selectedTickers = new Set();
let period = "3mo";
let mode = "price";
let chart = null;
let cache = {};
let yMin = null, yMax = null;
let sliderLo = 0, sliderHi = 100;

// ── 사이드바 렌더 ─────────────────────────────────────────
function renderSidebar() {
  const tiers = ["1차","2차","3차"];
  const listEl = document.getElementById("stockList");
  listEl.innerHTML = tiers.map(tier => {
    const stocks = ALL_STOCKS.filter(s => s.tier === tier);
    if (!stocks.length) return "";
    const tierClass = tier === "1차" ? "t1" : tier === "2차" ? "t2" : "t3";
    const items = stocks.map(s => {
      const colorIdx = ALL_STOCKS.indexOf(s) % ChartDrawer.PALETTE.length;
      return `
        <label class="stock-item">
          <input type="checkbox" class="ticker-checkbox" data-ticker="${s.ticker}" value="${s.ticker}" onchange="onToggle('${s.ticker}')">
          <div class="stock-item-info">
            <div class="stock-name">${s.name}</div>
            <div class="stock-ticker">${s.ticker}</div>
          </div>
          <div class="color-dot ticker-dot" data-ticker="${s.ticker}" style="background:${ChartDrawer.PALETTE[colorIdx]};opacity:.3"></div>
        </label>`;
    }).join("");
    return `<div class="tier-group">
      <div class="tier-label ${tierClass}" onclick="toggleTierGroup(this)">
        ${tier} 수혜 <span class="tier-chevron">▼</span>
      </div>
      <div class="tier-items">${items}</div>
    </div>`;
  }).join("");
}

// ── 체크박스·점 동기화 헬퍼 (같은 ticker가 여러 곳에 있을 수 있음) ──
function syncTickerUI(ticker, checked) {
  document.querySelectorAll(`.ticker-checkbox[data-ticker="${ticker}"]`).forEach(el => el.checked = checked);
  document.querySelectorAll(`.ticker-dot[data-ticker="${ticker}"]`).forEach(el => el.style.opacity = checked ? "1" : ".3");
}

// ── 토글 ─────────────────────────────────────────────────
async function onToggle(ticker) {
  const willCheck = !selectedTickers.has(ticker);
  syncTickerUI(ticker, willCheck);
  if (willCheck) {
    selectedTickers.add(ticker);
    if (!cache[ticker]) await fetchHistory(ticker);
  } else {
    selectedTickers.delete(ticker);
  }
  updateChart();
  updateTierBtnState();
  updateGroupBtnState();
}

// ── 히스토리 fetch ────────────────────────────────────────
async function fetchHistory(ticker) {
  try {
    const res = await fetch(`/api/history/${ticker}?period=${period}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cache[ticker] = await res.json();
  } catch(e) {
    showToast(`${ticker} 데이터 로드 실패: ${e.message}`, "err");
    cache[ticker] = [];
  }
}

// ── 기간 변경 시 캐시 초기화 후 재조회 ───────────────────
async function changePeriod(p) {
  period = p;
  cache = {};
  const tickers = [...selectedTickers];
  await Promise.all(tickers.map(t => fetchHistory(t)));
  updateChart();
}

// ── 차트 업데이트 ─────────────────────────────────────────
function updateChart() {
  const tickers = [...selectedTickers];
  const infoEl = document.getElementById("selectedInfo");
  const emptyEl = document.getElementById("emptyState");
  const wrapEl  = document.getElementById("canvasWrap");

  if (!tickers.length) {
    infoEl.textContent = "종목을 선택하세요";
    emptyEl.style.display = "flex";
    wrapEl.style.display  = "none";
    document.getElementById("yrangeRow").style.display = "none";
    if (chart) { chart.destroy(); chart = null; }
    document.getElementById("legend").innerHTML = "";
    updateMetricCharts();
    return;
  }

  infoEl.textContent = `${tickers.length}개 종목 선택됨`;
  emptyEl.style.display = "none";
  wrapEl.style.display  = "block";

  // 날짜 전체 합집합
  const dateSet = new Set();
  tickers.forEach(t => (cache[t] || []).forEach(r => dateSet.add(r.date)));
  const dates = [...dateSet].sort();

  const datasets = tickers.map((ticker, i) => {
    const color = ChartDrawer.color(ticker);
    const rows  = cache[ticker] || [];
    const priceMap = Object.fromEntries(rows.map(r => [r.date, r.price]));

    let values;
    if (mode === "norm") {
      // 첫 유효 가격 기준 100으로 정규화
      const prices = dates.map(d => priceMap[d] ?? null);
      const first  = prices.find(v => v !== null);
      values = prices.map(v => v !== null && first ? +((v / first * 100 - 100).toFixed(2)) : null);
    } else {
      values = dates.map(d => priceMap[d] ?? null);
    }

    const pr = dates.length <= 15 ? 3 : 0;
    return {
      label:            ticker,
      data:             values,
      _baseColor:       color,
      _origPointRadius: pr,
      borderColor:      color,
      backgroundColor:  color + "22",
      pointRadius:      pr,
      pointHoverRadius: 5,
      borderWidth:      2,
      tension:          0.3,
      fill:             false,
      spanGaps:         true,
    };
  });

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: { labels: dates, datasets },
    plugins: [chartPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 120 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: ChartDrawer.tooltip(ctx => {
          const v = ctx.parsed.y;
          if (v === null) return null;
          const name = `${ChartDrawer.name(ctx.dataset.label)} (${ctx.dataset.label})`;
          return mode === "norm"
            ? ` ${name}: ${v >= 0 ? "+" : ""}${v.toFixed(2)}%`
            : ` ${name}: ${v.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
        }),
      },
      scales: {
        x: ChartDrawer.xScale(10),
        y: ChartDrawer.yScale(
          v => mode === "norm" ? (v >= 0 ? "+" : "") + v.toFixed(1) + "%" : v.toLocaleString(),
          { min: yMin, max: yMax },
        ),
      },
    },
  });

  // 커스텀 레전드
  renderLegend(tickers);
  updateSliderRange();
  updateMetricCharts();
}

function renderLegend(tickers) {
  const legEl = document.getElementById("legend");
  legEl.innerHTML = tickers.map(ticker => {
    const color = ChartDrawer.color(ticker);
    const rows  = cache[ticker] || [];
    const last  = rows.length ? rows[rows.length - 1] : null;
    const stock = ALL_STOCKS.find(s => s.ticker === ticker);
    const priceStr = last && last.price != null ? last.price.toLocaleString(undefined, {maximumFractionDigits: 2}) : "—";
    return `<div class="legend-item">
      <div class="legend-line" style="background:${color}"></div>
      <span style="color:${color};font-weight:600;font-family:'SF Mono',monospace;font-size:12px">${ticker}</span>
      <span class="legend-name">${stock?.name || ""}</span>
      <span class="legend-price">${priceStr}</span>
    </div>`;
  }).join("");
}

// ── 전체 선택 / 해제 ─────────────────────────────────────
async function selectTickers(tickers) {
  const newOnes = tickers.filter(t => !selectedTickers.has(t));
  newOnes.forEach(t => { selectedTickers.add(t); syncTickerUI(t, true); });
  await Promise.all(newOnes.filter(t => !cache[t]).map(t => fetchHistory(t)));
  updateChart();
  updateTierBtnState();
  updateGroupBtnState();
}

function deselectTickers(tickers) {
  tickers.forEach(t => { selectedTickers.delete(t); syncTickerUI(t, false); });
  updateChart();
  updateTierBtnState();
  updateGroupBtnState();
}

async function selectAll() {
  await selectTickers(ALL_STOCKS.map(s => s.ticker));
}

async function selectTier(tier) {
  const tierTickers = ALL_STOCKS.filter(s => s.tier === tier).map(s => s.ticker);
  const allSelected = tierTickers.every(t => selectedTickers.has(t));
  if (allSelected) deselectTickers(tierTickers);
  else await selectTickers(tierTickers);
}

function clearAll() {
  selectedTickers.clear();
  document.querySelectorAll(".ticker-checkbox").forEach(c => c.checked = false);
  document.querySelectorAll(".ticker-dot").forEach(d => d.style.opacity = ".3");
  updateChart();
  updateTierBtnState();
  updateGroupBtnState();
}

function updateTierBtnState() {
  ["1차","2차","3차"].forEach(tier => {
    const tierTickers = ALL_STOCKS.filter(s => s.tier === tier).map(s => s.ticker);
    const allSelected = tierTickers.length > 0 && tierTickers.every(t => selectedTickers.has(t));
    const cls = tier === "1차" ? "t1" : tier === "2차" ? "t2" : "t3";
    const btn = document.querySelector(`.tier-btn.${cls}`);
    if (btn) btn.classList.toggle("active", allSelected);
  });
}

// ── 버튼 이벤트 ──────────────────────────────────────────
document.querySelectorAll(".period-groups button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".period-groups button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    changePeriod(btn.dataset.period);
  });
});

document.querySelectorAll("#modeGroup button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#modeGroup button").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    mode = btn.dataset.mode;
    resetYRange();
    updateChart();
  });
});

// ── Y축 수동 범위 ─────────────────────────────────────────
function updateSliderRange() {
  if (!chart || !chart.data.datasets.length) return;
  let lo = Infinity, hi = -Infinity;
  chart.data.datasets.forEach(ds => {
    (ds.data || []).forEach(v => {
      if (v !== null && v !== undefined && !isNaN(v)) {
        if (v < lo) lo = v; if (v > hi) hi = v;
      }
    });
  });
  if (!isFinite(lo)) return;

  const pad = (hi - lo) * 0.12 || Math.abs(hi) * 0.1 || 1;
  sliderLo = lo - pad; sliderHi = hi + pad;
  const step = (sliderHi - sliderLo) / 800;

  const minEl = document.getElementById("yRangeMin");
  const maxEl = document.getElementById("yRangeMax");
  [minEl, maxEl].forEach(el => { el.min = sliderLo; el.max = sliderHi; el.step = step; });
  minEl.value = yMin ?? sliderLo;
  maxEl.value = yMax ?? sliderHi;

  const fmt = v => Math.abs(v) >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(v % 1 === 0 ? 0 : 1);
  document.getElementById("rangeLo").textContent = fmt(sliderLo);
  document.getElementById("rangeHi").textContent = fmt(sliderHi);
  document.getElementById("yrangeRow").style.display = "flex";
  updateRangeFill();
}

function updateRangeFill() {
  const minEl = document.getElementById("yRangeMin");
  const maxEl = document.getElementById("yRangeMax");
  const fill  = document.getElementById("dualFill");
  const range = sliderHi - sliderLo;
  if (!range) return;
  fill.style.left  = ((minEl.value - sliderLo) / range * 100) + "%";
  fill.style.width = (Math.max(0, (maxEl.value - minEl.value) / range * 100)) + "%";
}

function applyYRange() {
  const isAuto = yMin === null && yMax === null;
  document.getElementById("yAutoBtn").classList.toggle("active", isAuto);
  const minEl = document.getElementById("yRangeMin");
  const maxEl = document.getElementById("yRangeMax");
  minEl.value = isAuto ? sliderLo : (yMin ?? sliderLo);
  maxEl.value = isAuto ? sliderHi : (yMax ?? sliderHi);
  updateRangeFill();
  if (chart) {
    chart.options.scales.y.min = yMin ?? undefined;
    chart.options.scales.y.max = yMax ?? undefined;
    chart.update();
  }
}

function resetYRange() {
  yMin = null; yMax = null;
  document.getElementById("yMin").value = "";
  document.getElementById("yMax").value = "";
  applyYRange();
}

document.getElementById("yMin").addEventListener("change", e => {
  yMin = e.target.value !== "" ? +e.target.value : null;
  applyYRange();
});
document.getElementById("yMax").addEventListener("change", e => {
  yMax = e.target.value !== "" ? +e.target.value : null;
  applyYRange();
});

document.getElementById("yRangeMin").addEventListener("input", e => {
  const maxEl = document.getElementById("yRangeMax");
  if (+e.target.value >= +maxEl.value) e.target.value = +maxEl.value - +e.target.step;
  yMin = +e.target.value;
  document.getElementById("yMin").value = yMin.toFixed(2);
  updateRangeFill();
  if (chart) { chart.options.scales.y.min = yMin; chart.update('none'); }
  document.getElementById("yAutoBtn").classList.remove("active");
});

document.getElementById("yRangeMax").addEventListener("input", e => {
  const minEl = document.getElementById("yRangeMin");
  if (+e.target.value <= +minEl.value) e.target.value = +minEl.value + +e.target.step;
  yMax = +e.target.value;
  document.getElementById("yMax").value = yMax.toFixed(2);
  updateRangeFill();
  if (chart) { chart.options.scales.y.max = yMax; chart.update('none'); }
  document.getElementById("yAutoBtn").classList.remove("active");
});

// ── Y축 휠 스크롤 (pan) ───────────────────────────────────
document.getElementById("priceChart").addEventListener("wheel", e => {
  if (!chart) return;
  const { chartArea: { top, bottom, left, right } } = chart;
  const rect = e.target.getBoundingClientRect();
  const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
  if (cx < left || cx > right || cy < top || cy > bottom) return;

  e.preventDefault();

  // 현재 범위가 자동이면 실제 스케일값으로 초기화
  if (yMin === null || yMax === null) {
    yMin = chart.scales.y.min;
    yMax = chart.scales.y.max;
  }

  const range = yMax - yMin;
  const delta = (e.deltaY > 0 ? 1 : -1) * range * 0.05;
  yMin += delta; yMax += delta;

  // 슬라이더 트랙이 벗어나면 확장
  if (yMin < sliderLo) { sliderLo = yMin - range * 0.1; }
  if (yMax > sliderHi) { sliderHi = yMax + range * 0.1; }
  const minEl = document.getElementById("yRangeMin");
  const maxEl = document.getElementById("yRangeMax");
  [minEl, maxEl].forEach(el => { el.min = sliderLo; el.max = sliderHi; });
  const fmt = v => Math.abs(v) >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(1);
  document.getElementById("rangeLo").textContent = fmt(sliderLo);
  document.getElementById("rangeHi").textContent = fmt(sliderHi);
  minEl.value = yMin; maxEl.value = yMax;
  updateRangeFill();

  document.getElementById("yMin").value = yMin.toFixed(2);
  document.getElementById("yMax").value = yMax.toFixed(2);
  document.getElementById("yAutoBtn").classList.remove("active");

  chart.options.scales.y.min = yMin;
  chart.options.scales.y.max = yMax;
  chart.update('none');
}, { passive: false });

// ── 라인 끝 레이블 플러그인 (메트릭 차트용) ──────────────
function makeEndLabelPlugin() {
  return {
    id: 'endLabels',
    _labelBBoxes: [],
    _hoveredIdx: -1,

    afterEvent(chart, args) {
      const e = args.event;
      if (e.type === 'mousemove') {
        const hit    = this._labelBBoxes.find(b => e.x >= b.x && e.x <= b.x + b.w && e.y >= b.y && e.y <= b.y + b.h);
        const newIdx = hit ? hit.idx : -1;
        if (newIdx !== this._hoveredIdx) {
          this._hoveredIdx = newIdx;
          if (newIdx !== -1) {
            const meta = chart.getDatasetMeta(newIdx);
            const ds   = chart.data.datasets[newIdx];
            let lastIdx = -1;
            for (let i = meta.data.length - 1; i >= 0; i--) {
              if (ds.data[i] !== null && !isNaN(ds.data[i])) { lastIdx = i; break; }
            }
            if (lastIdx !== -1) {
              const pt = meta.data[lastIdx];
              chart.tooltip.setActiveElements([{ datasetIndex: newIdx, index: lastIdx }], { x: pt.x, y: pt.y });
              chart.update();
            }
          } else {
            chart.tooltip.setActiveElements([], { x: 0, y: 0 });
            chart.update();
          }
          args.changed = true;
        }
      } else if (e.type === 'mouseout') {
        if (this._hoveredIdx !== -1) {
          this._hoveredIdx = -1;
          chart.tooltip.setActiveElements([], { x: 0, y: 0 });
          chart.update();
          args.changed = true;
        }
      }
    },

    beforeDatasetDraw(chart, args) {
      if (this._hoveredIdx === -1) return;
      if (args.index === this._hoveredIdx) return;
      chart.ctx.save();
      chart.ctx.globalAlpha = 0.2;
    },

    afterDatasetDraw(chart, args) {
      if (this._hoveredIdx === -1) return;
      if (args.index === this._hoveredIdx) return;
      chart.ctx.restore();
    },

    afterDraw(chart) {
      const { ctx, chartArea: { right } } = chart;
      this._labelBBoxes = [];
      chart.data.datasets.forEach((ds, i) => {
        const meta = chart.getDatasetMeta(i);
        if (!meta.visible) return;
        const lastPt = [...meta.data].reverse().find(p => !p.skip && !isNaN(p.y) && p.y !== null);
        if (!lastPt) return;
        const base      = ds._baseColor || ds.borderColor;
        const stock     = ALL_STOCKS.find(s => s.ticker === ds.label);
        const label     = stock ? stock.name : ds.label;
        const isHovered = this._hoveredIdx === i;
        const hasHover  = this._hoveredIdx !== -1;
        const alpha     = hasHover && !isHovered ? 0.3 : 1;
        const fs = isHovered ? 12 : 11, pad = 3;
        ctx.save();
        ctx.font = `${isHovered ? 'bold' : '600'} ${fs}px "SF Mono", monospace`;
        const tw = ctx.measureText(label).width;
        const px = right + 4, py = lastPt.y;
        const bboxX = px - pad, bboxY = py - fs / 2 - pad;
        const bboxW = tw + pad * 3, bboxH = fs + pad * 2;
        this._labelBBoxes.push({ idx: i, x: bboxX, y: bboxY, w: bboxW, h: bboxH });
        ctx.globalAlpha = alpha * (isHovered ? 0.28 : 0.18);
        ctx.fillStyle = base;
        ctx.beginPath();
        ctx.roundRect(bboxX, bboxY, bboxW, bboxH, 3);
        ctx.fill();
        ctx.globalAlpha = alpha;
        ctx.fillStyle = base;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, px + pad / 2, py);
        ctx.restore();
      });
    }
  };
}

// ── PER / PBR 메트릭 차트 ────────────────────────────────
const metricInst = { per: null, pbr: null, fcf: null };
let combinedChartInst = null;

// 메트릭별 표시 설정 (라벨·단위 포맷, floorZero: 음수→0 처리)
const METRIC_CFG = {
  per: { label: "PER", floorZero: true,  tickFmt: v => v.toFixed(1) + "x",   tipFmt: v => v === 0 ? "0 (적자)" : v.toFixed(2) },
  pbr: { label: "PBR", floorZero: false, tickFmt: v => v.toFixed(1) + "x",   tipFmt: v => v.toFixed(2) },
  fcf: { label: "FCF", floorZero: false, tickFmt: v => (v/1e8).toFixed(1)+"억$", tipFmt: v => (v/1e8).toFixed(2)+"억 달러" },
};

function destroyMetric(metric) {
  if (metricInst[metric]) { metricInst[metric].destroy(); metricInst[metric] = null; }
}

async function onMetricToggle(metric, enabled) {
  document.getElementById(metric + "Card").style.display = enabled ? "block" : "none";
  if (!enabled) { destroyMetric(metric); return; }
  // 지표 소급 결과가 반영되도록 최신 데이터 재조회
  cache = {};
  await Promise.all([...selectedTickers].map(fetchHistory));
  updateChart();
  drawMetricChart(metric);
}

function drawMetricChart(metric) {
  const tickers = [...selectedTickers];
  const cfg = METRIC_CFG[metric];

  // 해당 지표가 있는 날짜들의 합집합
  const dateSet = new Set();
  tickers.forEach(t => (cache[t] || []).forEach(r => { if (r[metric] != null) dateSet.add(r.date); }));
  const dates = [...dateSet].sort();

  // 음수→0 처리 (PER: 적자는 0으로 표시해 축 폭발 방지)
  const xform = cfg.floorZero ? (v => Math.max(0, v)) : (v => v);
  const datasets = tickers.map(ticker => {
    const color  = ChartDrawer.color(ticker);
    const valMap = Object.fromEntries((cache[ticker] || [])
      .filter(r => r[metric] != null).map(r => [r.date, xform(r[metric])]));
    return {
      label:            ticker,
      data:             dates.map(d => valMap[d] ?? null),
      _baseColor:       color,
      _origPointRadius: 3,
      borderColor:      color,
      backgroundColor:  color + "22",
      pointRadius:      3,
      pointHoverRadius: 5,
      borderWidth:      2,
      tension:          0.3,
      spanGaps:         false,
    };
  }).filter(ds => ds.data.some(v => v !== null));

  destroyMetric(metric);
  if (!datasets.length) return;

  // 이상치가 축을 폭발시키지 않도록 강건한 Y 범위 계산
  const allVals = datasets.flatMap(ds => ds.data);
  const yRange  = ChartDrawer.robustYRange(allVals);

  const endLabelPlugin = makeEndLabelPlugin();
  const inst = new Chart(document.getElementById(metric + "Chart"), {
    type: "line",
    data: { labels: dates, datasets },
    plugins: [endLabelPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 120 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: ChartDrawer.tooltip(ctx => {
          const v = ctx.parsed.y;
          if (v === null) return null;
          return ` ${ChartDrawer.name(ctx.dataset.label)} (${ctx.dataset.label}): ${cfg.tipFmt(v)}`;
        }),
      },
      scales: {
        x: ChartDrawer.xScale(8),
        y: ChartDrawer.yScale(cfg.tickFmt, yRange),
      },
    },
  });

  metricInst[metric] = inst;
  metricLabelPlugins.set(inst, endLabelPlugin);
}

function updateMetricCharts() {
  ["per","pbr","fcf"].forEach(m => {
    if (document.getElementById(m + "Toggle").checked) drawMetricChart(m);
  });
  if (document.getElementById("combinedToggle").checked) drawCombinedChart();
}

// ── CAPEX + 주주환원율 복합 차트 ──────────────────────────
async function onCombinedToggle(enabled) {
  const card = document.getElementById("combinedCard");
  card.style.display = enabled ? "block" : "none";
  if (!enabled) {
    if (combinedChartInst) { combinedChartInst.destroy(); combinedChartInst = null; }
    return;
  }
  const tickers = [...selectedTickers];
  cache = {};
  await Promise.all(tickers.map(t => fetchHistory(t)));
  updateChart();
  drawCombinedChart();
}

function drawCombinedChart() {
  const tickers = [...selectedTickers];
  const dateSet = new Set();
  tickers.forEach(t => (cache[t] || []).forEach(r => {
    if (r.capex != null || r.payout_ratio != null) dateSet.add(r.date);
  }));
  const dates = [...dateSet].sort();

  if (combinedChartInst) { combinedChartInst.destroy(); combinedChartInst = null; }
  if (!dates.length || !tickers.length) return;

  const datasets = [];
  tickers.forEach(ticker => {
    const color = ChartDrawer.color(ticker);
    const byDate = Object.fromEntries((cache[ticker] || []).map(r => [r.date, r]));

    datasets.push({
      type: 'bar', label: ticker + '__capex', _ticker: ticker, _baseColor: color,
      data: dates.map(d => byDate[d]?.capex ?? null),
      backgroundColor: color + '55', borderColor: color + 'aa',
      borderWidth: 1, borderRadius: 3, yAxisID: 'yLeft',
    });
    datasets.push({
      type: 'line', label: ticker + '__payout', _ticker: ticker, _baseColor: color,
      _origPointRadius: 3,
      data: dates.map(d => byDate[d]?.payout_ratio ?? null),
      borderColor: color, backgroundColor: 'transparent',
      borderWidth: 2, pointRadius: 3, pointHoverRadius: 5,
      tension: 0.3, spanGaps: false, yAxisID: 'yRight',
    });
  });

  combinedChartInst = new Chart(document.getElementById('combinedChart'), {
    type: 'bar',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 10 } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: ChartDrawer.tooltip(ctx => {
          const v = ctx.parsed.y;
          if (v == null || isNaN(v)) return null;
          const isCapex = ctx.dataset.label.endsWith('__capex');
          return ` ${ChartDrawer.name(ctx.dataset._ticker)} ${isCapex ? 'CAPEX' : '주주환원율'}: ${isCapex ? (v/1e8).toFixed(1)+'억$' : v.toFixed(1)+'%'}`;
        }),
      },
      scales: {
        x: ChartDrawer.xScale(8),
        yLeft: {
          position: 'left',
          ...ChartDrawer.yScale(v => (v/1e8).toFixed(0)+'억$'),
          title: { display: true, text: 'CAPEX (억$)', color: ChartDrawer.THEME.tick, font: { size: 10 } },
        },
        yRight: {
          position: 'right',
          ticks: { color: ChartDrawer.THEME.tick, callback: v => v.toFixed(0)+'%' },
          grid:  { drawOnChartArea: false },
          title: { display: true, text: '주주환원율 (%)', color: ChartDrawer.THEME.tick, font: { size: 10 } },
        },
      },
    },
  });
}

// ── 툴팁 토글 ────────────────────────────────────────────
function onTooltipToggle(enabled) {
  if (!chart) return;
  chart.options.plugins.tooltip.enabled = enabled;
  chart.update();
}

// ── 내 그룹 렌더·토글 ────────────────────────────────────
function renderGroupButtons() {
  const section = document.getElementById("groupSection");
  const btnList = document.getElementById("groupBtnList");
  if (!ALL_GROUPS.length) { section.style.display = "none"; return; }

  section.style.display = "block";
  btnList.innerHTML = ALL_GROUPS.map(g => {
    const items = g.tickers.map(ticker => {
      const s = ALL_STOCKS.find(x => x.ticker === ticker);
      if (!s) return "";
      const color    = ChartDrawer.color(ticker);
      const checked  = selectedTickers.has(ticker);
      return `
        <label class="stock-item">
          <input type="checkbox" class="ticker-checkbox" data-ticker="${ticker}"
                 value="${ticker}" ${checked ? "checked" : ""} onchange="onToggle('${ticker}')">
          <div class="stock-item-info">
            <div class="stock-name">${s.name}</div>
            <div class="stock-ticker">${ticker}</div>
          </div>
          <div class="color-dot ticker-dot" data-ticker="${ticker}"
               style="background:${color};opacity:${checked ? '1' : '.3'}"></div>
        </label>`;
    }).filter(Boolean).join("");

    return `<div class="tier-group">
      <div class="tier-label" id="gbtn_${g.id}" style="color:var(--muted)">
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer"
              onclick="toggleGroup(${g.id})" title="전체 선택/해제">${g.name}</span>
        <span class="group-btn-count">${g.tickers.length}</span>
        <span class="tier-chevron" style="cursor:pointer;padding-left:6px"
              onclick="toggleTierGroup(document.getElementById('gbtn_${g.id}'))">▼</span>
      </div>
      <div class="tier-items">${items}</div>
    </div>`;
  }).join("");
}

async function toggleGroup(groupId) {
  const g = ALL_GROUPS.find(x => x.id === groupId);
  if (!g || !g.tickers.length) return;
  const allSelected = g.tickers.every(t => selectedTickers.has(t));
  if (allSelected) deselectTickers(g.tickers);
  else await selectTickers(g.tickers);
  updateGroupBtnState();
}

function updateGroupBtnState() {
  ALL_GROUPS.forEach(g => {
    const lbl = document.getElementById(`gbtn_${g.id}`);
    if (!lbl) return;
    const allSelected = g.tickers.length > 0 && g.tickers.every(t => selectedTickers.has(t));
    lbl.style.color = allSelected ? "var(--text)" : "var(--muted)";
    lbl.style.fontWeight = allSelected ? "700" : "";
  });
}

// ── 사이드바 접기/펼치기 ──────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const btn     = document.getElementById("sidebarToggle");
  const collapsed = sidebar.classList.toggle("collapsed");
  btn.textContent = collapsed ? "▶" : "◀";
  btn.title       = collapsed ? "펼치기" : "접기";
  localStorage.setItem("sidebarCollapsed", collapsed);
}

function toggleTierGroup(labelEl) {
  labelEl.classList.toggle("collapsed");
  const items = labelEl.nextElementSibling;
  items.classList.toggle("hidden");
}

// 초기화
renderSidebar();
renderGroupButtons();

// 이전 접힘 상태 복원
if (localStorage.getItem("sidebarCollapsed") === "true") toggleSidebar();

