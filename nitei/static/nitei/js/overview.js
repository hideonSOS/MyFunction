// PERSONS はテンプレート側で定義済み
const OV_START_DATE     = new Date(2026, 3, 15);  // 2026-04-15
const OV_DAYS           = 28;                      // 1シート = 28日
const OV_TOTAL_SECTIONS = 15;                      // 15シート
const OV_DOW            = ['日', '月', '火', '水', '木', '金', '土'];

let ovSection = 0;
let ovTitles  = [];

const TODAY = new Date(); TODAY.setHours(0, 0, 0, 0);

// ── ユーティリティ ────────────────────────────────

function sectionStartDate(s) {
  const d = new Date(OV_START_DATE);
  d.setDate(d.getDate() + s * OV_DAYS);
  return d;
}

function currentSectionFromToday() {
  const diff = Math.floor((TODAY - OV_START_DATE) / 86400000);
  return Math.max(0, Math.min(OV_TOTAL_SECTIONS - 1, Math.floor(diff / OV_DAYS)));
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
  const si = ovSection;

  // 両セクション（前半14日・後半14日）を並行取得
  const [res0, res1] = await Promise.all([
    fetch(`/nitei/api/overview/?sheet_index=${si}&section_index=0`),
    fetch(`/nitei/api/overview/?sheet_index=${si}&section_index=1`),
  ]);
  const [json0, json1] = await Promise.all([res0.json(), res1.json()]);
  ovTitles = json0.titles;

  // セクション1のキーを14オフセットしてマージ
  const data = {};
  for (const person of Object.keys(json0.data)) {
    const pdata = { ...json0.data[person] };
    for (const [key, val] of Object.entries(json1.data[person] || {})) {
      const m = key.match(/^([ew])_(\d+)(.*)$/);
      if (m) pdata[`${m[1]}_${parseInt(m[2]) + 14}${m[3]}`] = val;
    }
    data[person] = pdata;
  }

  render(data);
  document.getElementById('ov-status').textContent = '✓';
}

function render(data) {
  const start = sectionStartDate(ovSection);
  const days  = [];
  for (let i = 0; i < OV_DAYS; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    days.push(d);
  }

  // 期間ラベル更新
  const fmt = d => `${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`;
  document.getElementById('period-label').textContent = `${fmt(days[0])}  〜  ${fmt(days[OV_DAYS-1])}`;

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
        + (isToday ? ' ov-today' : '');

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

document.getElementById('btn-prev').onclick = () => {
  if (ovSection > 0) { ovSection--; loadAndRender(); }
};
document.getElementById('btn-next').onclick = () => {
  if (ovSection < OV_TOTAL_SECTIONS - 1) { ovSection++; loadAndRender(); }
};
document.getElementById('btn-today').onclick = () => {
  ovSection = currentSectionFromToday();
  loadAndRender();
};

// ── 初期表示 ──────────────────────────────────────
ovSection = currentSectionFromToday();
loadAndRender();

