/* 配置図 印刷ページ ── ?dates=YYYY-MM-DD,... （最大3日）をA3横に並べる */
(function () {
  'use strict';

  const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土'];
  const sheet = document.getElementById('pp-sheet');

  function toMinutes(hhmm) {
    const m = /^(\d{1,2}):(\d{2})$/.exec((hhmm || '').trim());
    if (!m) return null;
    return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
  }

  /** 締め切り − 発売開始 = 発売時間（日跨ぎは +24h） */
  function duration(start, close) {
    const s = toMinutes(start);
    const c = toMinutes(close);
    if (s === null || c === null) return '';
    let diff = c - s;
    if (diff < 0) diff += 24 * 60;
    return String(Math.floor(diff / 60)).padStart(2, '0') + ':' +
           String(diff % 60).padStart(2, '0');
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function dateHeading(iso) {
    const d = new Date(iso + 'T00:00:00');
    if (isNaN(d.getTime())) return iso;
    const w = d.getDay();
    const label = (d.getMonth() + 1) + '/' + d.getDate() +
                  '（' + WEEKDAYS[w] + '）';
    const cls = w === 0 ? 'sun' : (w === 6 ? 'sat' : '');
    return { label, cls };
  }

  /** 1日分の配置図テーブルを組み立てる */
  function buildDay(data) {
    const box = el('div', 'pp-day');

    const h = dateHeading(data.date);
    const head = el('div', 'pp-day-head ' + (h.cls || ''), h.label);
    box.appendChild(head);

    const table = el('table', 'pp-table');

    // ヘッダー行
    const thead = document.createElement('thead');
    const htr = document.createElement('tr');
    htr.appendChild(el('th', 'pp-th-time', ''));
    htr.appendChild(el('th', 'pp-th-race', ''));
    const headers = (data.headers && data.headers.length ? data.headers : DEFAULT_HEADERS);
    for (let c = 0; c < COL_COUNT; c++) {
      htr.appendChild(el('th', 'pp-th-cell', headers[c] || ''));
    }
    thead.appendChild(htr);
    table.appendChild(thead);

    // レース時刻を引きやすい形に
    const races = {};
    (data.races || []).forEach(r => { races[r.race] = r; });

    const tbody = document.createElement('tbody');
    for (let r = 1; r <= RACE_COUNT; r++) {
      const info = races[r] || { start: '', close: '', highlight: false };

      // 1段目: 発売開始 ＋ レース番号(rowspan3) ＋ 配置セル(rowspan3)
      const tr1 = document.createElement('tr');
      tr1.appendChild(el('td', 'pp-time pp-start', info.start || ''));

      const tdRace = el('td', 'pp-race' + (info.highlight ? ' on' : ''), r + 'R');
      tdRace.rowSpan = 3;
      tr1.appendChild(tdRace);

      for (let c = 0; c < COL_COUNT; c++) {
        const key = r + '_' + c;
        const name  = (data.cells  || {})[key] || '';
        const color = (data.colors || {})[key] || '';
        const td = el('td', 'pp-cell' + (color ? ' tint-' + color : ''), name);
        td.rowSpan = 3;
        tr1.appendChild(td);
      }
      tbody.appendChild(tr1);

      // 2段目: 発売時間（自動計算）
      const tr2 = document.createElement('tr');
      tr2.appendChild(el('td', 'pp-time pp-dur', duration(info.start, info.close)));
      tbody.appendChild(tr2);

      // 3段目: 締め切り
      const tr3 = document.createElement('tr');
      tr3.appendChild(el('td', 'pp-time pp-close', info.close || ''));
      tbody.appendChild(tr3);
    }
    table.appendChild(tbody);
    box.appendChild(table);
    return box;
  }

  async function init() {
    const dates = DATES_PARAM.split(',').map(s => s.trim())
      .filter(s => /^\d{4}-\d{2}-\d{2}$/.test(s)).slice(0, 3);
    if (!dates.length) {
      sheet.textContent = '日付が指定されていません（?dates=YYYY-MM-DD,... を付けてください）';
      return;
    }

    try {
      const results = await Promise.all(dates.map(d =>
        fetch('/nitei/api/layout/?date=' + encodeURIComponent(d))
          .then(res => res.ok ? res.json() : Promise.reject(res.status))
      ));
      sheet.innerHTML = '';
      results.forEach(data => sheet.appendChild(buildDay(data)));
      document.title = '配置図 ' + dates.join(' ');
    } catch (e) {
      sheet.textContent = '読み込みに失敗しました。ログインし直してから開いてください。';
    }
  }

  document.getElementById('pp-print').addEventListener('click', () => window.print());
  document.getElementById('pp-close').addEventListener('click', () => window.close());

  init();
})();
