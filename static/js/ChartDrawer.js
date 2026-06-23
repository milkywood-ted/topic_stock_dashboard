// ChartDrawer — 차트 렌더 툴킷 (테마·색상·축·툴팁·robustY 범위).
// 차트로 보여주기 위한 변환·표시 설정을 담당. 데이터 적재·선택상태·Chart 인스턴스
// 오케스트레이션은 페이지(chart-page) 소관. init(stocks)로 종목 메타를 주입한다.
const ChartDrawer = (() => {
  const THEME = {
    tick:    "#8b8fa8",
    body:    "#e8eaf0",
    grid:    "rgba(255,255,255,.06)",
    gridX:   "rgba(255,255,255,.04)",
    surface: "#1a1d27",
    border:  "rgba(255,255,255,.12)",
  };

  const PALETTE = [
    "#5b8def","#f0a842","#4caf7d","#e05a5a","#a78bfa","#38bdf8",
    "#fb923c","#34d399","#f472b6","#facc15","#60a5fa","#c084fc",
  ];

  let stocks = [];

  return {
    THEME,
    PALETTE,

    // 종목 메타 주입 (색상·이름 도출용)
    init(stockList) { stocks = stockList || []; },

    // 티커 → 팔레트 색상 (목록에 없으면 글자코드 폴백)
    color(ticker) {
      const i = stocks.findIndex(s => s.ticker === ticker);
      return PALETTE[(i >= 0 ? i : ticker.charCodeAt(0)) % PALETTE.length];
    },

    // 티커 → 표시 이름
    name(ticker) {
      const s = stocks.find(s => s.ticker === ticker);
      return s ? s.name : ticker;
    },

    // 공용 툴팁 설정 (label 콜백만 주입)
    tooltip(labelFn) {
      return {
        backgroundColor: THEME.surface,
        borderColor:     THEME.border,
        borderWidth:     1,
        titleColor:      THEME.tick,
        bodyColor:       THEME.body,
        padding:         10,
        callbacks: { label: labelFn },
      };
    },

    // 공용 x축
    xScale(maxTicks = 8) {
      return {
        ticks: { color: THEME.tick, maxTicksLimit: maxTicks, maxRotation: 0 },
        grid:  { color: THEME.gridX },
      };
    },

    // 공용 y축 (tickFmt: 눈금 포맷, range: {min,max} 선택)
    yScale(tickFmt, range) {
      return {
        min: range?.min ?? undefined,
        max: range?.max ?? undefined,
        ticks: { color: THEME.tick, callback: tickFmt },
        grid:  { color: THEME.grid },
      };
    },

    // 이상치에 강건한 Y축 범위 — 백분위 기반, 극단값은 축 밖으로 클리핑
    robustYRange(values, padFrac = 0.08) {
      const clean = values.filter(v => v != null && isFinite(v)).sort((a, b) => a - b);
      if (clean.length < 5) return undefined;  // 표본 적으면 Chart.js 자동
      const q = p => {
        const idx = p * (clean.length - 1);
        const lo = Math.floor(idx), hi = Math.min(lo + 1, clean.length - 1);
        return clean[lo] + (clean[hi] - clean[lo]) * (idx - lo);
      };
      let lo = q(0.02), hi = q(0.98);
      if (lo === hi) { lo -= 1; hi += 1; }
      const pad = (hi - lo) * padFrac;
      return { min: lo - pad, max: hi + pad };
    },
  };
})();
