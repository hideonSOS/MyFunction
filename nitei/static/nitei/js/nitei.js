// PERSON はテンプレート側で定義済み: const PERSON = "{{ person }}";
const START_DATE     = new Date(2026, 3, 15);  // 2026-04-15
const SCHEDULE_COUNT = 15;
const DAYS_PER_ROW   = window.innerWidth < 768 ? 7 : 14;
const TODAY          = new Date(); TODAY.setHours(0, 0, 0, 0);
let TITLES     = [];
let savedData  = {};
let eventData  = {};

// ── 保存キュー（DB lock 防止） ─────────────────────
const _queue  = [];
let   _saving = false;

async function _flush() {
  if (_saving || _queue.length === 0) return;
  _saving = true;
  const task = _queue.shift();
  try {
    await fetch(task.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task.body),
    });
  } finally {
    _saving = false;
    _flush();
  }
}

function enqueue(url, body) {
  _queue.push({ url, body });
  _flush();
}

// ─────────────────────────────────────────────────────

async function init() {
  const [titlesRes, scheduleRes, eventsRes] = await Promise.all([
    fetch('/nitei/api/titles/'),
    fetch(`/nitei/api/schedule/?person=${PERSON}`),
    fetch(`/nitei/api/events/?person=${PERSON}`),
  ]);
  TITLES    = await titlesRes.json();
  savedData = await scheduleRes.json();
  eventData = await eventsRes.json();
  document.getElementById('status').textContent = '✓ 読み込み完了';
  buildSheets();
  syncSumWidth();
  const todayCell = document.querySelector('td.today');
  if (todayCell) todayCell.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function getEventColor(date) {
  for (const t of TITLES) {
    const from = new Date(t.date_from.replace(/\//g, '-'));
    const to   = new Date(t.date_to.replace(/\//g, '-'));
    from.setHours(0, 0, 0, 0);
    to.setHours(0, 0, 0, 0);
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    if (d >= from && d <= to) return t.venue === '箕面' ? 'green' : 'blue';
  }
  return '';
}

function saveCell(key, value) {
  savedData[key] = value;
  enqueue('/nitei/api/schedule/save/', { key, status: value, person: PERSON });
}

function saveEventTime(key, value) {
  eventData[key] = value;
  enqueue('/nitei/api/events/save/', { key, time_text: value, person: PERSON });
}

async function clearSheet(sheetIndex, workCells, eventCells, updateSum) {
  const label = sheetIndex === 0 ? '勤務表' : `勤務表${sheetIndex + 1}`;
  if (!confirm(`${label}の入力をリセットしますか？`)) return;
  await fetch('/nitei/api/schedule/clear/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sheet_index: sheetIndex, person: PERSON }),
  });
  Object.keys(savedData)
    .filter(k => k.startsWith(`w_${sheetIndex}_`))
    .forEach(k => delete savedData[k]);
  workCells.forEach(c => { c.textContent = ''; c.style.color = ''; });
  updateSum();
}

function applyEventColor(cell) {
  const t = cell.textContent;
  if (['公開FM', '本社'].includes(t)) cell.style.color = '#ffffff';
  else if (t === '公休')              cell.style.color = '#ff9900';
  else                                cell.style.color = '';
}

function applyTimeColor(cell) {
  cell.style.color = cell.textContent ? '#ffe066' : '';
}

// ── タイムピッカー ────────────────────────────────
let _pickerTarget = null;
let _pickerSave   = null;

function createTimePicker() {
  const panel = document.createElement('div');
  panel.id = 'time-picker';

  // ヘッダー: time input + クリア + 閉じる
  const header = document.createElement('div');
  header.className = 'tp-header';

  const inp = document.createElement('input');
  inp.type = 'time';
  inp.id   = 'tp-input';
  inp.step = '900';  // 15分刻み

  const btnClear = document.createElement('button');
  btnClear.textContent = 'クリア';
  btnClear.className   = 'tp-btn-clear';
  btnClear.onclick = (e) => { e.stopPropagation(); selectTime(''); };

  const btnClose = document.createElement('button');
  btnClose.textContent = '×';
  btnClose.className   = 'tp-btn-close';
  btnClose.onclick = (e) => { e.stopPropagation(); closePicker(); };

  header.appendChild(inp);
  header.appendChild(btnClear);
  header.appendChild(btnClose);
  panel.appendChild(header);

  // 時間グリッド（06:00〜23:00、30分刻み）
  const grid = document.createElement('div');
  grid.className = 'tp-grid';

  for (let h = 6; h <= 23; h++) {
    for (const m of [0, 30]) {
      const btn = document.createElement('button');
      btn.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      btn.className   = 'tp-time-btn';
      btn.onclick = (e) => { e.stopPropagation(); selectTime(btn.textContent); };
      grid.appendChild(btn);
    }
  }

  panel.appendChild(grid);

  // inputのchangeで即時反映（モバイルネイティブピッカー確定時）
  inp.addEventListener('change', () => { if (inp.value) selectTime(inp.value); });

  document.body.appendChild(panel);

  // パネル外クリックで閉じる
  document.addEventListener('click', (e) => {
    if (_pickerTarget && !panel.contains(e.target) && e.target !== _pickerTarget) {
      closePicker();
    }
  }, true);

  return panel;
}

function openPicker(cell, saveCallback) {
  let panel = document.getElementById('time-picker');
  if (!panel) panel = createTimePicker();

  _pickerTarget = cell;
  _pickerSave   = saveCallback;

  panel.querySelector('#tp-input').value = cell.textContent || '';
  panel.style.display = 'block';

  if (window.innerWidth < 768) {
    // モバイル: ボトムシート
    Object.assign(panel.style, {
      left: '0', right: '0', bottom: '0', top: 'auto',
      width: '100%', borderRadius: '12px 12px 0 0', boxSizing: 'border-box',
    });
  } else {
    // デスクトップ: セルの直下に配置
    const rect = cell.getBoundingClientRect();
    const pw   = 264;
    let left   = rect.left + window.scrollX;
    let top    = rect.bottom + window.scrollY + 4;
    if (left + pw > window.innerWidth) left = Math.max(0, window.innerWidth - pw - 8);
    Object.assign(panel.style, {
      left: left + 'px', top: top + 'px', bottom: 'auto', right: 'auto',
      width: pw + 'px', borderRadius: '6px', boxSizing: 'content-box',
    });
  }
}

function selectTime(value) {
  if (_pickerTarget) {
    _pickerTarget.textContent = value;
    applyTimeColor(_pickerTarget);
    if (_pickerSave) _pickerSave(value);
  }
  closePicker();
}

function closePicker() {
  const panel = document.getElementById('time-picker');
  if (panel) panel.style.display = 'none';
  _pickerTarget = null;
  _pickerSave   = null;
}

// ─────────────────────────────────────────────────────

function syncSumWidth() {
  const dayCell = document.querySelector('td.day');
  if (!dayCell) return;
  const w = dayCell.getBoundingClientRect().width;
  document.querySelectorAll('td.sumValue').forEach(td => { td.style.width = w + 'px'; });
}

window.addEventListener('resize', syncSumWidth);

function generateDays(start) {
  const days = [];
  const d = new Date(start);
  for (let i = 0; i < 28; i++) { days.push(new Date(d)); d.setDate(d.getDate() + 1); }
  return days;
}

function createSection(dateList, workCells, sumCells, eventCells, updateSum, sheetIndex, sectionIndex, dayOffset) {
  const table = document.createElement('table');
  const tr1 = document.createElement('tr');
  const tr2 = document.createElement('tr');
  const tr3 = document.createElement('tr');
  const tr4 = document.createElement('tr');

  tr2.className = 'row-event';
  tr3.className = 'row-kami';
  tr4.className = 'row-shimo';

  ['日付', '開催', '上番', '下番'].forEach((text, i) => {
    const td = document.createElement('td');
    td.textContent = text;
    td.className = 'label';
    [tr1, tr2, tr3, tr4][i].appendChild(td);
  });

  const EVENT_ORDER = ['', '公開FM', '本社', '公休'];

  dateList.forEach((date, localIndex) => {
    const dayIndex = localIndex + dayOffset;
    const m   = date.getMonth() + 1;
    const d   = date.getDate();
    const dow = date.getDay();

    // ── 日付行 ──
    const tdDay    = document.createElement('td');
    const isToday  = date.getTime() === TODAY.getTime();
    tdDay.textContent = `${m}/${d}`;
    tdDay.className = 'day' + (dow === 6 ? ' sat' : dow === 0 ? ' sun' : '') + (isToday ? ' today' : '');
    tr1.appendChild(tdDay);

    // ── 開催行（クリックで循環） ──
    const tdEvent  = document.createElement('td');
    const color    = getEventColor(date);
    const eventKey = `e_${sheetIndex}_${sectionIndex}_${dayIndex}`;

    if (color) tdEvent.classList.add(color);
    if (isToday) tdEvent.classList.add('today-col');
    if (eventData[eventKey]) tdEvent.textContent = eventData[eventKey];
    applyEventColor(tdEvent);

    tdEvent.onclick = function () {
      const idx = EVENT_ORDER.indexOf(tdEvent.textContent);
      tdEvent.textContent = EVENT_ORDER[(idx + 1) % EVENT_ORDER.length];
      saveEventTime(eventKey, tdEvent.textContent);
      applyEventColor(tdEvent);
      updateSum();
    };

    tr2.appendChild(tdEvent);
    eventCells.push(tdEvent);

    // ── 上番行（タイムピッカー） ──
    const workKey0 = `w_${sheetIndex}_${sectionIndex}_${dayIndex}_0`;
    const tdWork0  = document.createElement('td');
    if (isToday) tdWork0.classList.add('today-col');
    if (savedData[workKey0]) tdWork0.textContent = savedData[workKey0];
    applyTimeColor(tdWork0);
    tdWork0.onclick = function (e) {
      e.stopPropagation();
      openPicker(tdWork0, (val) => { saveCell(workKey0, val); updateSum(); });
    };
    tr3.appendChild(tdWork0);
    workCells.push(tdWork0);
    sumCells.push(tdWork0);  // 上番を入力日数カウント対象に

    // ── 下番行（タイムピッカー） ──
    const workKey1 = `w_${sheetIndex}_${sectionIndex}_${dayIndex}_1`;
    const tdWork1  = document.createElement('td');
    if (isToday) tdWork1.classList.add('today-col');
    if (savedData[workKey1]) tdWork1.textContent = savedData[workKey1];
    applyTimeColor(tdWork1);
    tdWork1.onclick = function (e) {
      e.stopPropagation();
      openPicker(tdWork1, (val) => { saveCell(workKey1, val); updateSum(); });
    };
    tr4.appendChild(tdWork1);
    workCells.push(tdWork1);
  });

  [tr1, tr2, tr3, tr4].forEach(tr => table.appendChild(tr));
  return table;
}

function buildSheets() {
  const container    = document.getElementById('container');
  const currentStart = new Date(START_DATE);

  for (let i = 0; i < SCHEDULE_COUNT; i++) {
    const sheet = document.createElement('div');
    sheet.className = 'sheet';

    const title = document.createElement('h2');
    title.textContent = i === 0 ? '勤務表' : `勤務表${i + 1}`;
    sheet.appendChild(title);

    const workCells  = [];
    const sumCells   = [];
    const eventCells = [];
    const days = generateDays(currentStart);

    const sumTable = document.createElement('table');
    sumTable.className = 'sumTable';
    const sumRow   = document.createElement('tr');
    sumRow.className = 'sumRow';
    const sumLabel = document.createElement('td');
    sumLabel.textContent = '公休数';
    sumLabel.className   = 'label';
    const sumCell = document.createElement('td');
    sumCell.textContent = '0';
    sumCell.className  = 'sumValue';
    sumRow.appendChild(sumLabel);
    sumRow.appendChild(sumCell);
    sumTable.appendChild(sumRow);

    const updateSum = (ec => () => {
      sumCell.textContent = ec.filter(c => c.textContent === '公休').length;
    })(eventCells);

    for (let sec = 0; sec < 2; sec++) {
      const secDays = days.slice(sec * 14, (sec + 1) * 14);
      for (let chunk = 0; chunk * DAYS_PER_ROW < secDays.length; chunk++) {
        const offset    = chunk * DAYS_PER_ROW;
        const chunkDays = secDays.slice(offset, offset + DAYS_PER_ROW);
        sheet.appendChild(createSection(chunkDays, workCells, sumCells, eventCells, updateSum, i, sec, offset));
      }
    }

    sheet.appendChild(sumTable);

    const resetBtn = document.createElement('button');
    resetBtn.textContent    = 'リセット';
    resetBtn.style.marginTop = '4px';
    resetBtn.onclick = ((si, wc, ec, us) => () => clearSheet(si, wc, ec, us))(i, workCells, eventCells, updateSum);
    sheet.appendChild(resetBtn);

    updateSum();
    container.appendChild(sheet);
    currentStart.setDate(currentStart.getDate() + 28);
  }
}

init();

