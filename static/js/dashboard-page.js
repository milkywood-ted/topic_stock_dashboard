// index.html 페이지 글루 — 종목 테이블(필터·정렬)·요약(updateSummary)·
// 요약차트(tierChart/distChart, ChartDrawer.THEME 공유)·수집/백필 등 액션 트리거.
// 데이터는 템플릿 주입 window.BOOT에서 읽음. (ChartDrawer.js·toast.js 선행 로드)

const RAW_DATA = window.BOOT.stocks;
const SUMMARY  = window.BOOT.summary;   // 백엔드 DataView 통계 (티어 집계·분포)
let sortKey = "tier";
let sortAsc  = true;
let filterF  = "all";
let searchQ  = "";

// ── 렌더 ──────────────────────────────────────────────────
function renderTable(data) {
  const tbody = document.getElementById("tableBody");
  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="no-data">수집된 데이터가 없습니다. "지금 수집" 버튼을 눌러주세요.</td></tr>`;
    document.getElementById("rowCount").textContent = "";
    return;
  }
  tbody.innerHTML = data.map(d => {
    const chgCls = d.change_pct > 0 ? "up" : d.change_pct < 0 ? "dn" : "neu";
    const chgTxt = d.change_pct != null ? `${d.change_pct > 0 ? "+" : ""}${d.change_pct.toFixed(2)}%` : "—";
    const barW   = Math.min(100, Math.abs(d.week52_ret || 0));
    const barClr = d.tier === "1차" ? "#5b8def" : d.tier === "2차" ? "#f0a842" : "#e05a5a";
    return `
    <tr>
      <td class="ticker-cell">
        <div class="nm">${d.name}</div>
        <div class="sym">${d.ticker}</div>
      </td>
      <td><span class="tier-badge tier-${d.tier.charAt(0)}">${d.tier} 수혜</span></td>
      <td class="sector-txt">${d.sector || "—"}</td>
      <td><span class="market-tag">${d.market}</span></td>
      <td class="r"><span class="price-val">${d.price != null ? d.price.toLocaleString(undefined,{maximumFractionDigits:2}) : "—"}</span></td>
      <td class="r"><span class="chg ${chgCls}">${chgTxt}</span></td>
      <td class="r"><span class="mcap">${d.mkt_cap_b != null ? d.mkt_cap_b.toLocaleString() + "B" : "—"}</span></td>
      <td class="r"><span class="pe">${d.pe_ratio != null ? d.pe_ratio.toFixed(1) + "x" : "—"}</span></td>
      <td class="r">
        <div class="bar-wrap">
          <span class="price-val" style="font-size:12px;color:var(--up)">${d.week52_ret != null ? "+" + d.week52_ret.toFixed(0) + "%" : "—"}</span>
          <div class="mini-bar"><div class="mini-fill" style="width:${barW}%;background:${barClr}"></div></div>
        </div>
      </td>
    </tr>`;
  }).join("");
  document.getElementById("rowCount").textContent = `${data.length}개 표시 중`;
}

function getFiltered() {
  return RAW_DATA
    .filter(d => filterF === "all" || d.tier === filterF || d.market === filterF)
    .filter(d => !searchQ || d.ticker.toLowerCase().includes(searchQ) || d.name.toLowerCase().includes(searchQ));
}

function getSorted(data) {
  return [...data].sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });
}

function refresh() {
  const filtered = getSorted(getFiltered());
  renderTable(filtered);
  drawCharts();
  updateSummary();
}

window.sortTable = (key) => {
  if (sortKey === key) sortAsc = !sortAsc; else { sortKey = key; sortAsc = true; }
  refresh();
};

document.querySelectorAll(".filter-btn").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    filterF = b.dataset.f;
    refresh();
  });
});

document.getElementById("searchInput").addEventListener("input", e => {
  searchQ = e.target.value.toLowerCase().trim();
  refresh();
});

// ── 요약 (백엔드 DataView 통계 사용) ──────────────────────
function updateSummary() {
  ["1차","2차"].forEach((t,i) => {
    const ts  = SUMMARY.tiers[t];
    const avg = ts && ts.count > 0 ? ts.avg_change : null;
    const el  = document.getElementById(`avg${i+1}`);
    if (avg != null) {
      el.textContent = `${avg>=0?"+":""}${avg.toFixed(2)}%`;
      el.style.color = avg >= 0 ? "var(--up)" : "var(--dn)";
    }
  });
}

// ── 차트 (백엔드 DataView 통계 사용) ──────────────────────
let chartTier, chartDist;
function drawCharts() {
  // 티어별 평균
  const tiers = ["1차","2차","3차"];
  const avgs  = tiers.map(t => SUMMARY.tiers[t] ? SUMMARY.tiers[t].avg_change : 0);

  if (chartTier) chartTier.destroy();
  chartTier = new Chart(document.getElementById("tierChart"), {
    type: "bar",
    data: {
      labels: ["1차 수혜","2차 수혜","3차 수혜"],
      datasets: [{
        label: "평균 등락률 (%)",
        data: avgs,
        backgroundColor: avgs.map(v => v >= 0 ? "rgba(76,175,125,.7)" : "rgba(224,90,90,.7)"),
        borderColor:     avgs.map(v => v >= 0 ? "#4caf7d" : "#e05a5a"),
        borderWidth: 1,
        borderRadius: 5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: ChartDrawer.THEME.tick }, grid: { color: ChartDrawer.THEME.gridX } },
        y: { ticks: { color: ChartDrawer.THEME.tick, callback: v => v + "%" }, grid: { color: ChartDrawer.THEME.grid } },
      },
    },
  });

  // 등락률 분포 (백엔드 집계)
  const buckets = SUMMARY.distribution;
  const colors = ["#e05a5a","#e07a5a","rgba(140,140,160,.6)","rgba(76,175,125,.5)","rgba(76,175,125,.7)","#4caf7d"];

  if (chartDist) chartDist.destroy();
  chartDist = new Chart(document.getElementById("distChart"), {
    type: "bar",
    data: {
      labels: Object.keys(buckets),
      datasets: [{
        label: "종목 수",
        data:  Object.values(buckets),
        backgroundColor: colors,
        borderRadius: 5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: ChartDrawer.THEME.tick }, grid: { color: ChartDrawer.THEME.gridX } },
        y: { ticks: { color: ChartDrawer.THEME.tick, stepSize: 1 }, grid: { color: ChartDrawer.THEME.grid } },
      },
    },
  });
}

// ── 과거 데이터 백필 ──────────────────────────────────────
async function triggerBackfill() {
  const btn    = document.getElementById("backfillBtn");
  const sel    = document.getElementById("backfillPeriod");
  const period = sel.value;
  const label  = sel.options[sel.selectedIndex].text;
  btn.disabled = true;
  btn.textContent = "수집 중...";
  try {
    const res  = await fetch(`/backfill?period=${period}`, { method: "POST" });
    const json = await res.json();
    if (json.error) throw new Error(json.error);
    showToast(`✓ 과거 ${label}: ${json.inserted}개 삽입, ${json.skipped}개 중복 스킵`, "ok");
  } catch(e) {
    showToast("백필 실패: " + e.message, "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "📥 과거 데이터";
  }
}

// ── 수동 수집 ─────────────────────────────────────────────
async function triggerCollect() {
  const btn = document.getElementById("collectBtn");
  btn.disabled = true;
  btn.textContent = "수집 중...";
  try {
    const res  = await fetch("/collect", { method: "POST" });
    const json = await res.json();
    showToast(`✓ 수집 완료: ${json.success}/${json.total} 성공`, "ok");
    setTimeout(() => location.reload(), 1500);
  } catch(e) {
    showToast("수집 실패: " + e.message, "err");
    btn.disabled = false;
    btn.textContent = "▶ 지금 수집";
  }
}

async function triggerReset() {
  if (!confirm("스냅샷과 수집 로그를 전부 삭제합니다.\n종목 목록은 유지됩니다.\n계속하시겠습니까?")) return;
  const btn = document.getElementById("resetBtn");
  btn.disabled = true; btn.textContent = "초기화 중...";
  try {
    const res  = await fetch("/reset-snapshots", { method: "POST" });
    const json = await res.json();
    showToast("✓ 초기화 완료 — 과거 데이터 버튼으로 재수집하세요", "ok");
    setTimeout(() => location.reload(), 2000);
  } catch(e) {
    showToast("초기화 실패: " + e.message, "err");
    btn.disabled = false; btn.textContent = "⚠ 데이터 초기화";
  }
}

async function triggerCleanup() {
  const btn = document.getElementById("cleanupBtn");
  btn.disabled = true; btn.textContent = "정리 중...";
  try {
    const res  = await fetch("/cleanup-duplicates", { method: "POST" });
    const json = await res.json();
    showToast(`✓ 중복 정리 완료: ${json.deleted}개 삭제`, "ok");
  } catch(e) {
    showToast("정리 실패: " + e.message, "err");
  } finally {
    btn.disabled = false; btn.textContent = "🧹 중복 정리";
  }
}

async function triggerFillMetrics() {
  const btn = document.getElementById("metricsBtn");
  btn.disabled = true;
  btn.textContent = "계산 중...";
  try {
    const res  = await fetch("/fill-metrics", { method: "POST" });
    const json = await res.json();
    if (json.error) throw new Error(json.error);
    showToast(`✓ PER/PBR 소급 완료: ${json.updated}개 스냅샷 처리`, "ok");
  } catch(e) {
    showToast("소급 실패: " + e.message, "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "📊 PER/PBR 소급";
  }
}

// 초기 렌더
refresh();
