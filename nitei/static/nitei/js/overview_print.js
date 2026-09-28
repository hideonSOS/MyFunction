// 全員一覧 印刷ページ ── ?month=YYYY-MM の1か月分を横長の用紙1枚に並べる
// 前提: PERSONS / MONTH_PARAM（テンプレート）, periods.js, overview_data.js
(function () {
  'use strict';

  const DOW   = ['日', '月', '火', '水', '木', '金', '土'];
  const PAPER = {
    a3: '@page { size: A3 landscape; margin: 8mm; }',
    a4: '@page { size: A4 landscape; margin: 8mm; }',
  };
  const page = document.getElementById('op-page');

  let year = 0, month = 0;   // month は0始まり
  let paper = 'a3';

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  /** 1行ぶんの文字。セル幅に収まらなければ横だけ縮める（fitAll） */
  function line(cls, text) {
    const d = el('div', 'op-l ' + cls);
    d.appendChild(el('span', 'op-fit', text));
    return d;
  }

  function initMonth() {
    const m = /^(\d{4})-(\d{1,2})$/.exec(MONTH_PARAM || '');
    const today = new Date();
    const c = m ? ovClampToRange(+m[1], +m[2] - 1)
                : ovClampToRange(today.getFullYear(), today.getMonth());
    year = c.y; month = c.m;
    const p = new URLSearchParams(location.search).get('paper');
    if (PAPER[p]) paper = p;
  }

  function updateNav() {
    document.getElementById('op-month').textContent = `${year}年${month + 1}月`;
    const s = ovSerial(year, month);
    document.getElementById('op-prev').disabled = s <= ovSerial(OV_FIRST.y, OV_FIRST.m);
    document.getElementById('op-next').disabled = s >= ovSerial(OV_LAST.y, OV_LAST.m);
    const ym = `${year}-${String(month + 1).padStart(2, '0')}`;
    history.replaceState(null, '', `?month=${ym}` + (paper === 'a3' ? '' : `&paper=${paper}`));
    document.title = `全員一覧 ${year}年${month + 1}月`;   // PDF保存時の既定ファイル名になる
  }

  async function load() {
    updateNav();
    page.textContent = '読み込み中...';
    const m = await ovFetchMonth(year, month);
    render(m);
  }

  function render(m) {
    const { days, positions, titles, data } = m;
    const persons = Object.entries(PERSONS);
    document.body.style.setProperty('--rows', persons.length);
    page.innerHTML = '';

    // タイトル
    const head = el('div', 'op-head');
    head.appendChild(el('div', 'op-head-title', `全員一覧　${year}年${month + 1}月`));
    const now = new Date();
    head.appendChild(el('div', 'op-head-sub',
      `出力日 ${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}　` +
      '↑=上段の時刻　↓=下段の時刻　色付き=開催日（青:都市 / 緑:箕面）'));
    page.appendChild(head);

    const table = el('table', 'op-table');
    const cg = el('colgroup');
    cg.appendChild(el('col', 'op-col-name'));
    days.forEach(() => cg.appendChild(el('col')));
    table.appendChild(cg);

    // 日付行・開催行
    const thead = el('thead');
    const trDate = el('tr');
    trDate.appendChild(el('th', 'op-corner', '氏名'));
    const trEv = el('tr');
    trEv.appendChild(el('th', 'op-ev-label op-ev', '開催'));
    const info = days.map(d => ovEventInfo(d, titles));
    days.forEach((d, i) => {
      const dow = d.getDay();
      const th = el('th', 'op-date' + (dow === 6 ? ' sat' : dow === 0 ? ' sun' : ''));
      th.innerHTML = `<b>${d.getDate()}</b><br>${DOW[dow]}`;
      trDate.appendChild(th);
      const ev = el('th', 'op-ev' + (info[i] ? ' ' + info[i].color : ''));
      if (info[i]) ev.appendChild(el('span', 'op-fit', info[i].venue));
      trEv.appendChild(ev);
    });
    thead.appendChild(trDate);
    thead.appendChild(trEv);
    table.appendChild(thead);

    // 1人1行
    const tbody = el('tbody');
    persons.forEach(([key, name]) => {
      const tr = el('tr');
      tr.appendChild(el('td', 'op-name', name));
      const pdata = data[key] || {};
      days.forEach((d, i) => {
        const dow  = d.getDay();
        const code = pdata[`e_${i}`] || '';
        const top  = pdata[`w_${i}_0`] || '';
        const bot  = pdata[`w_${i}_1`] || '';
        const kyu  = code === '公休' || code === '有給';   // 休み（同じ色で表示）
        const td = el('td', 'op-cell'
          + (!positions[i] ? ' nodata'
             : kyu ? ' kyu'
             : info[i] ? ' ' + info[i].color
             : dow === 6 ? ' sat' : dow === 0 ? ' sun' : ''));
        if (code) td.appendChild(line('op-code' + (kyu ? ' kyu' : ''), code));
        if (top)  td.appendChild(line('op-time top', '↑' + top));
        if (bot)  td.appendChild(line('op-time bot', '↓' + bot));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    page.appendChild(table);
    fitAll();
  }

  /** セル幅からはみ出す文字を横方向に縮めて1行に収める */
  function fitAll() {
    page.querySelectorAll('.op-fit').forEach(s => {
      s.style.transform = '';
      const box = s.parentElement;
      const avail = box.clientWidth - 2;
      const w = s.scrollWidth;
      if (w > avail && avail > 0) s.style.transform = `scaleX(${(avail / w).toFixed(3)})`;
    });
  }

  function setPaper(p) {
    paper = p;
    document.getElementById('op-page-size').textContent = PAPER[p];
    document.getElementById('op-paper').value = p;
    document.body.className = 'paper-' + p;
    updateNav();
    fitAll();
  }

  document.getElementById('op-prev').addEventListener('click', () => {
    const c = ovClampToRange(year, month - 1); year = c.y; month = c.m; load();
  });
  document.getElementById('op-next').addEventListener('click', () => {
    const c = ovClampToRange(year, month + 1); year = c.y; month = c.m; load();
  });
  document.getElementById('op-paper').addEventListener('change', e => setPaper(e.target.value));
  document.getElementById('op-print').addEventListener('click', () => window.print());
  document.getElementById('op-close').addEventListener('click', () => window.close());

  initMonth();
  setPaper(paper);
  load();
})();
