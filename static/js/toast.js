// 공용 토스트 — 모든 페이지 공유 (이전: 4개 템플릿에 중복 정의).
// cls: "ok" | "err". 토스트 요소(#toast)가 없으면 무시.
function showToast(msg, cls = "ok") {
  const t = document.getElementById("toast");
  if (!t) return;
  t.className = `toast ${cls} show`;
  t.textContent = msg;
  setTimeout(() => t.classList.remove("show"), 3000);
}
