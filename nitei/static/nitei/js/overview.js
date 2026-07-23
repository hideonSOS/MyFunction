// PERSONS はテンプレート側で定義済み
//
// 全員一覧は「カレンダー月」単位で表示する（勤務表ページの28日/14日/月サイクルとは別）。
// 保存データは位置キー（sheet/section/day）なので、periods.js の
// niteiPositionForDate() で日付から保存位置を逆引きして拾う。
const OV_DOW = ['日', '月', '火', '水', '木', '金', '土'];

let ovYear   = 0;   // 表示中の年
let ovMonth  = 0;   // 表示中の月（0始まり）
let ovTitles = [];

const TODAY = new Date(); TODAY.setHours(0, 0, 0, 0);

// 勤務表がカバーしている範囲の月（ここより外へはナビゲートさせない）
const OV_FIRST = { y: NITEI_RANGE.start.getFullYear(), m: NITEI_RANGE.start.getMonth() };
const OV_LAST  = { y: NITEI_RANGE.end.getFullYear(),   m: NITEI_RANGE.end.getMonth()   };

// ── ユーティリティ ────────────────────────────────

/** 年月を通し番号にして比較しやすくする */
function ovSerial(y, m) { return y * 12 + m; }

function ovClampToRange(y, m) {
  const s   = ovSerial(y, m);
  const min = ovSerial(OV_FIRST.y, OV_FIRST.m);
  const max = ovSerial(OV_LAST.y,  OV_LAST.m);
  const v   = Math.max(min, Math.min(max, s));
  return { y: Math.floor(v / 12), m: v % 12 };
}

function ovSetMonthFromToday() {
  const c = ovClampToRange(TODAY.getFullYear(), TODAY.getMonth());
  ovYear = c.y; ovMonth = c.m;
}

/** 表示中の月の日付一覧 */
function ovMonthDays() {
  const last = new Date(ovYear, ovMonth + 1, 0).getDate();
  const days = [];
  for (let i = 1; i <= last; i++) days.push(new Date(ovYear, ovMonth, i));
  return days;
}

function getEventInfo(date) {
  const d = new Date(date); d.setHours(0, 0, 0, 0);
  for (const t of ovTitles) {
    const from = new Date(t.date_from.replace(/\//g, '-')); from.setHours(0, 0, 0, 0);
    const to   = new Date(t.date_to.replace(/\//g, '-'));   to.setHours(0, 0, 0, 0);
    if (d >= from && d <= to) return { color: t.venue === '箕面' ? 'green' : 'blue', venue: t.venue };
  }
  return null;
}

function getEventColor(date) {
  const info = getEventInfo(date);
  return info ? info.color : '';
}

// ── データ取得＆描画 ──────────────────────────────

async function loadAndRender() {
  document.getElementById('ov-status').textContent = '読み込み中...';

  const days      = ovMonthDays();
  const positions = days.map(d => niteiPositionForDate(d));

  // この月が触れる (sheet, section) の組み合わせだけを取得する。
  // 月は勤務表の区切りをまたぐので、1〜3 組になることが多い。
  const needed = [];
  const seen   = {};
  positions.forEach(p => {
    if (!p) return;
    const id = `${p.sheet}_${p.section}`;
    if (!seen[id]) { seen[id] = true; needed.push(p); }
  });

  const results = await Promise.all(
    needed.map(p =>
      fetch(`/nitei/api/overview/?sheet_index=${p.sheet}&section_index=${p.section}`)
        .then(r => r.json())
        .then(json => ({ id: `${p.sheet}_${p.section}`, json }))
    )
  );

  const bySection = {};
  results.forEach(r => { bySection[r.id] = r.json.data; });
  if (results.length) ovTitles = results[0].json.titles;

  // 日付ごとに、その日の保存位置から値を引いて日付インデックスへ詰め替える
  const data = {};
  Object.keys(PERSONS).forEach(person => {
    const pdata = {};
    positions.forEach((p, i) => {
      if (!p) return;
      const src = (bySection[`${p.sheet}_${p.section}`] || {})[person] || {};
      const ev  = src[`e_${p.day}`];
      const w0  = src[`w_${p.day}_0`];
      const w1  = src[`w_${p.day}_1`];
      if (ev !== undefined) pdata[`e_${i}`]   = ev;
      if (w0 !== undefined) pdata[`w_${i}_0`] = w0;
      if (w1 !== undefined) pdata[`w_${i}_1`] = w1;
    });
    data[person] = pdata;
  });

  render(data, days, positions);
  document.getElementById('ov-status').textContent = '✓';
}

function render(data, days, positions) {
  // 期間ラベルは「2026年9月」
  document.getElementById('period-label').textContent = `${ovYear}年${ovMonth + 1}月`;

  // ── thead ──
  const thead = document.getElementById('ov-thead');
  thead.innerHTML = '';
  const trHead = document.createElement('tr');

  const thCorner = document.createElement('th');
  thCorner.className = 'ov-corner';
  thCorner.textContent = '氏名';
  trHead.appendChild(thCorner);

  days.forEach((date) => {
    const dow     = date.getDay();
    const info    = getEventInfo(date);
    const isToday = date.getTime() === TODAY.getTime();
    const th      = document.createElement('th');
    th.className  = 'ov-date'
      + (dow === 6 ? ' ov-sat' : dow === 0 ? ' ov-sun' : '')
      + (info ? ` ov-ev-${info.color}` : '')
      + (isToday ? ' ov-today' : '');
    th.innerHTML  = `${date.getMonth()+1}/<b>${date.getDate()}</b><br><span class="ov-dow">${OV_DOW[dow]}</span>`;
    trHead.appendChild(th);
  });

  thead.appendChild(trHead);

  // ── 開催インジケーター行 ──
  const trEvent = document.createElement('tr');
  const thEvLabel = document.createElement('th');
  thEvLabel.className = 'ov-ev-label';
  thEvLabel.textContent = '開催';
  trEvent.appendChild(thEvLabel);

  days.forEach((date) => {
    const info    = getEventInfo(date);
    const isToday = date.getTime() === TODAY.getTime();
    const th      = document.createElement('th');
    th.className  = 'ov-ev-row'
      + (info ? ` ov-ev-${info.color}` : '')
      + (isToday ? ' ov-today' : '');
    th.textContent = info ? info.venue : '';
    trEvent.appendChild(th);
  });

  thead.appendChild(trEvent);

  // ── tbody ──
  const tbody = document.getElementById('ov-tbody');
  tbody.innerHTML = '';

  // 今日列までスクロール（今日が表示範囲内の場合のみ）
  setTimeout(() => {
    const todayTh = document.querySelector('.ov-date.ov-today');
    if (todayTh) todayTh.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }, 0);

  Object.entries(PERSONS).forEach(([key, name]) => {
    const tr = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.className  = 'ov-name';
    tdName.textContent = name;
    tr.appendChild(tdName);

    const pdata = data[key] || {};

    days.forEach((date, i) => {
      const dow       = date.getDay();
      const info      = getEventInfo(date);
      const color     = info ? info.color : '';
      const isToday   = date.getTime() === TODAY.getTime();
      const eventCode = pdata[`e_${i}`] || '';
      const timeTop   = pdata[`w_${i}_0`] || '';
      const timeBot   = pdata[`w_${i}_1`] || '';
      const isKyu     = eventCode === '公休';

      const td = document.createElement('td');
      td.className = 'ov-cell'
        + (dow === 6 ? ' ov-sat' : dow === 0 ? ' ov-sun' : '')
        + (color && !isKyu ? ` ov-ev-${color}` : '')
        + (isKyu ? ' ov-kyu' : '')
        + (isToday ? ' ov-today' : '')
        + (positions[i] ? '' : ' ov-nodata');   // 勤務表の対象期間外

      let html = '';
      if (eventCode) html += `<div class="ov-code ${isKyu ? 'c-kyu' : 'c-ev'}">${eventCode}</div>`;
      if (timeTop)   html += `<div class="ov-time ov-top">↑&thinsp;${timeTop}</div>`;
      if (timeBot)   html += `<div class="ov-time ov-bot">↓&thinsp;${timeBot}</div>`;

      td.innerHTML = html;
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
}

// ── ナビゲーション ────────────────────────────────

function ovShiftMonth(delta) {
  const c = ovClampToRange(ovYear, ovMonth + delta);
  if (c.y === ovYear && c.m === ovMonth) return;   // 範囲端では動かさない
  ovYear = c.y; ovMonth = c.m;
  loadAndRender();
}

document.getElementById('btn-prev').onclick  = () => ovShiftMonth(-1);
document.getElementById('btn-next').onclick  = () => ovShiftMonth(1);
document.getElementById('btn-today').onclick = () => { ovSetMonthFromToday(); loadAndRender(); };

// ── 初期表示 ──────────────────────────────────────
ovSetMonthFromToday();
loadAndRender();

