/* ── サイドバー アクティブ状態 ─── */
(function () {
  const path = window.location.pathname;
  document.querySelectorAll('.sb-item[data-path]').forEach(el => {
    const p = el.dataset.path;
    if (p === '/' ? path === '/' : path.startsWith(p)) {
      el.classList.add('active');
    }
  });
})();

/* ── 時計 ────────────────────────── */
(function () {
  const el = document.getElementById('sb-clock');
  if (!el) return;
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleString('ja-JP', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    });
  }
  tick();
  setInterval(tick, 1000);
})();
