/* ── ハンバーガーメニュー ────────── */
// PC: 既定で開き、タップで閉じる（sidebar-closed）
// スマホ: 既定で閉じ、タップで本文の上に開く（sidebar-open）。外側・メニュー項目のタップで閉じる
(function () {
  const btn = document.getElementById('hamburger');
  if (!btn) return;
  const mobile = window.matchMedia('(max-width: 767px)');
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    document.body.classList.toggle(mobile.matches ? 'sidebar-open' : 'sidebar-closed');
  });
  document.addEventListener('click', function (e) {
    if (!document.body.classList.contains('sidebar-open')) return;
    const sb = document.getElementById('sidebar');
    if (!sb.contains(e.target) || e.target.closest('.sb-item')) {
      document.body.classList.remove('sidebar-open');
    }
  });
  // 画面幅が変わったら（回転など）スマホ用の開状態は解除
  mobile.addEventListener('change', function () {
    document.body.classList.remove('sidebar-open');
  });
})();

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
