// PERSONS はテンプレート側で定義済み
//
// 全員一覧は「カレンダー月」単位で表示する（勤務表ページの28日/14日/月サイクルとは別）。
// 月単位のデータ取得・範囲・開催判定は overview_data.js（印刷ページと共通）
const OV_DOW = ['日', '月', '火', '水', '木', '金', '土'];

let ovYear   = 0;   // 表示中の年
let ovMonth  = 0;   // 表示中の月（0始まり）
let ovTitles = [];

const TODAY = new Date(); TODAY.setHours(0, 0, 0, 0);

function ovSetMonthFromToday() {
  const c = ovClampToRange(TODAY.getFullYear(), TODAY.getMonth());
  ovYear = c.y; ovMonth = c.m;
}

function getEventInfo(date) {
  return ovEventInfo(date, ovTitles);
}

// ── データ取得＆描画 ──────────────────────────────

async function loadAndRender() {
  document.getElementById('ov-status').textContent = '読み込み中...';
  const month = await ovFetchMonth(ovYear, ovMonth);
  ovTitles = month.titles;
  render(month.data, month.days, month.positions);
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
document.getElementById('btn-print').onclick = () => {
  const ym = `${ovYear}-${String(ovMonth + 1).padStart(2, '0')}`;
  window.open(`/nitei/overview/print/?month=${ym}`, '_blank');
};

// ── 初期表示 ──────────────────────────────────────
ovSetMonthFromToday();
loadAndRender();

