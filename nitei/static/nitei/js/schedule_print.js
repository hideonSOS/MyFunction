// 勤務表 印刷ページ ── ?person=X&sheet=N の勤務表1枚分（1人）を横長の用紙1枚に並べる
// 前提: PERSON / PERSON_NAME / SHEET_PARAM（テンプレート）, periods.js（NITEI_SHEETS）
(function () {
  'use strict';

  const DOW   = ['日', '月', '火', '水', '木', '金', '土'];
  const PAPER = {
    a4: '@page { size: A4 landscape; margin: 8mm; }',
    a3: '@page { size: A3 landscape; margin: 8mm; }',
  };
  // 公休数に数える区分（勤務表画面と同じ）と、灰色で示す休みの区分
  const HOLIDAY_CODES = ['公休', '指定公休'];
  const REST_CODES    = ['公休', '指定公休', '有給'];

  const page = document.getElementById('sp-page');

  let sheetIndex = 0;
  let paper      = 'a4';
  let titles = [], schedule = {}, events = {};

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function fitSpan(text) {
    return el('span', 'sp-fit', text);
  }

  /** 開催日なら 'blue'（都市）/ 'green'（箕面） */
  function eventColor(date) {
    const d = new Date(date); d.setHours(0, 0, 0, 0);
    for (const t of titles) {
      const from = new Date(t.date_from.replace(/\//g, '-')); from.setHours(0, 0, 0, 0);
      const to   = new Date(t.date_to.replace(/\//g, '-'));   to.setHours(0, 0, 0, 0);
      if (d >= from && d <= to) return t.venue === '箕面' ? 'green' : 'blue';
    }
    return '';
  }

  function initParams() {
    const n = parseInt(SHEET_PARAM, 10);
    sheetIndex = (n >= 0 && n < NITEI_SHEETS.length) ? n : niteiSheetIndexForDate(new Date());
    const p = new URLSearchParams(location.search).get('paper');
    if (PAPER[p]) paper = p;
  }

  function updateNav() {
    const def = NITEI_SHEETS[sheetIndex];
    document.getElementById('sp-sheet').textContent = `${def.label}  ${niteiRangeLabel(def)}`;
    document.getElementById('sp-prev').disabled = sheetIndex <= 0;
    document.getElementById('sp-next').disabled = sheetIndex >= NITEI_SHEETS.length - 1;
    history.replaceState(null, '', `?person=${PERSON}&sheet=${sheetIndex}` + (paper === 'a4' ? '' : `&paper=${paper}`));
    document.title = `${PERSON_NAME} ${def.label}`;   // PDF保存時の既定ファイル名になる
  }

  async function load() {
    const [t, s, e] = await Promise.all([
      fetch('/nitei/api/titles/').then(r => r.json()),
      fetch(`/nitei/api/schedule/?person=${PERSON}`).then(r => r.json()),
      fetch(`/nitei/api/events/?person=${PERSON}`).then(r => r.json()),
    ]);
    titles = t; schedule = s; events = e;
    render();
  }

  function render() {
    updateNav();
    const def = NITEI_SHEETS[sheetIndex];
    const si  = def.index;
    document.body.style.setProperty('--nsec', def.sections.length);
    document.body.style.setProperty('--maxdays', Math.max(...def.sections.map(s => s.length)));
    page.innerHTML = '';

    // 公休数（勤務表画面と同じ数え方）
    let holidays = 0;
    def.sections.forEach((sec, secIdx) => sec.forEach((d, day) => {
      if (HOLIDAY_CODES.includes(events[`e_${si}_${secIdx}_${day}`])) holidays++;
    }));

    // タイトル
    const head  = el('div', 'sp-head');
    const title = el('div', 'sp-head-title');
    title.appendChild(el('span', 'sp-name', PERSON_NAME));
    title.appendChild(document.createTextNode(
      `${def.label}　${niteiRangeLabel(def)}（${def.days.length}日）`));
    head.appendChild(title);
    const right = el('div', 'sp-head-right');
    const now = new Date();
    const legend = el('div', 'sp-legend');
    legend.innerHTML = `出力日 ${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}<br>`
      + '色付き＝開催日（青:都市 / 緑:箕面）　灰色＝休み';
    right.appendChild(legend);
    const sum = el('div', 'sp-sum', '公休数');
    sum.appendChild(el('b', null, String(holidays)));
    right.appendChild(sum);
    head.appendChild(right);
    page.appendChild(head);

    // 前半・後半（セクション）ごとに1つの表
    def.sections.forEach((secDays, secIdx) => {
      const table = el('table', 'sp-table');
      table.style.setProperty('--n', secDays.length);
      const cg = el('colgroup');
      cg.appendChild(el('col', 'sp-col-label'));
      secDays.forEach(() => cg.appendChild(el('col')));
      table.appendChild(cg);

      const rows = [
        el('tr', 'sp-row-date'), el('tr', 'sp-row-ev'),
        el('tr', 'sp-row-kami'), el('tr', 'sp-row-shimo'),
      ];
      ['日付', '開催', '上番', '下番'].forEach((t, i) => rows[i].appendChild(el('td', 'sp-label', t)));

      secDays.forEach((date, day) => {
        const dow   = date.getDay();
        const code  = events[`e_${si}_${secIdx}_${day}`] || '';
        const top   = schedule[`w_${si}_${secIdx}_${day}_0`] || '';
        const bot   = schedule[`w_${si}_${secIdx}_${day}_1`] || '';
        const rest  = REST_CODES.includes(code);
        const color = eventColor(date);

        const tdDate = el('td', 'sp-date' + (dow === 6 ? ' sat' : dow === 0 ? ' sun' : ''));
        tdDate.innerHTML = `<b>${date.getMonth() + 1}/${date.getDate()}</b><br>${DOW[dow]}`;
        rows[0].appendChild(tdDate);

        const tdEv = el('td', 'sp-ev sp-cell'
          + (color ? ' ' + color : '')
          + (rest ? ' kyu' : '')
          + (code === '指定公休' ? ' shitei' : ''));
        if (code) tdEv.appendChild(fitSpan(code));
        rows[1].appendChild(tdEv);

        [top, bot].forEach((v, i) => {
          const td = el('td', 'sp-cell' + (rest ? ' kyu' : ''));
          if (v) td.appendChild(el('span', 'sp-time', v));
          rows[2 + i].appendChild(td);
        });
      });

      rows.forEach(r => table.appendChild(r));
      page.appendChild(table);
    });
    fitAll();
  }

  /** セル幅からはみ出す文字を横方向に縮めて1行に収める */
  function fitAll() {
    page.querySelectorAll('.sp-fit').forEach(s => {
      s.style.transform = '';
      const avail = s.parentElement.clientWidth - 2;
      const w = s.scrollWidth;
      if (w > avail && avail > 0) s.style.transform = `scaleX(${(avail / w).toFixed(3)})`;
    });
  }

  function setPaper(p) {
    paper = p;
    document.getElementById('sp-page-size').textContent = PAPER[p];
    document.getElementById('sp-paper').value = p;
    document.body.className = 'paper-' + p;
    updateNav();
    fitAll();
  }

  document.getElementById('sp-prev').addEventListener('click', () => {
    if (sheetIndex > 0) { sheetIndex--; render(); }
  });
  document.getElementById('sp-next').addEventListener('click', () => {
    if (sheetIndex < NITEI_SHEETS.length - 1) { sheetIndex++; render(); }
  });
  document.getElementById('sp-paper').addEventListener('change', e => setPaper(e.target.value));
  document.getElementById('sp-print').addEventListener('click', () => window.print());
  document.getElementById('sp-close').addEventListener('click', () => window.close());

  initParams();
  setPaper(paper);
  load();
})();
