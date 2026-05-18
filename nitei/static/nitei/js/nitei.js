// PERSON はテンプレート側で定義済み: const PERSON = "{{ person }}";
const START_DATE     = new Date(2026, 3, 15);  // 2026-04-15
const SCHEDULE_COUNT = 15;
const DAYS_PER_ROW   = window.innerWidth < 768 ? 7 : 14;
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

function applyWorkColor(cell) {
  const t = cell.textContent;
  if (['公休', '公出勤', '有給'].includes(t))   cell.style.color = '#ff9900';
  else if (['公開FM', '本社'].includes(t))       cell.style.color = '#ffffff';
  else                                           cell.style.color = '';
}

function generateDays(start) {
  const days = [];
  const d = new Date(start);
  for (let i = 0; i < 28; i++) { days.push(new Date(d)); d.setDate(d.getDate() + 1); }
  return days;
}

function createSection(dateList, workCells, eventCells, updateSum, sheetIndex, sectionIndex, dayOffset) {
  const table = document.createElement('table');
  const tr1 = document.createElement('tr');
  const tr2 = document.createElement('tr');
  const tr3 = document.createElement('tr');

  ['日付', '開催', '出勤'].forEach((text, i) => {
    const td = document.createElement('td');
    td.textContent = text;
    td.className = 'label';
    [tr1, tr2, tr3][i].appendChild(td);
  });

  const ORDER = ['', '公開FM', '有給', '公休', '本社', '公出勤'];

  dateList.forEach((date, localIndex) => {
    const dayIndex = localIndex + dayOffset;
    const m = date.getMonth() + 1;
    const d = date.getDate();
    const dow = date.getDay();

    // ── 日付行 ──
    const tdDay = document.createElement('td');
    tdDay.textContent = `${m}/${d}`;
    tdDay.className = 'day' + (dow === 6 ? ' sat' : dow === 0 ? ' sun' : '');
    tr1.appendChild(tdDay);

    // ── 開催行（色 + 時間入力） ──
    const tdEvent = document.createElement('td');
    const color = getEventColor(date);
    const eventKey = `e_${sheetIndex}_${sectionIndex}_${dayIndex}`;

    if (color) {
      tdEvent.classList.add(color);
      tdEvent.contentEditable = 'true';
      tdEvent.spellcheck = false;
      // 保存済み時間を表示
      if (eventData[eventKey]) {
        tdEvent.textContent = eventData[eventKey];
      }
      // Enter で確定（改行させない）
      tdEvent.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); tdEvent.blur(); }
      });
      // フォーカスを外したとき保存
      tdEvent.addEventListener('blur', () => {
        const val = tdEvent.textContent.trim();
        // 改行・余分な空白を除去して表示も更新
        tdEvent.textContent = val;
        saveEventTime(eventKey, val);
      });
    } else {
      tdEvent.style.cursor = 'default';
    }

    tr2.appendChild(tdEvent);
    eventCells.push(tdEvent);

    // ── 出勤行（クリックで循環） ──
    const workKey = `w_${sheetIndex}_${sectionIndex}_${dayIndex}`;
    const tdWork = document.createElement('td');

    if (savedData[workKey] !== undefined) {
      tdWork.textContent = savedData[workKey];
    }
    applyWorkColor(tdWork);

    tdWork.onclick = function () {
      const idx = ORDER.indexOf(tdWork.textContent);
      tdWork.textContent = ORDER[(idx + 1) % ORDER.length];
      saveCell(workKey, tdWork.textContent);
      applyWorkColor(tdWork);
      updateSum();
    };

    tr3.appendChild(tdWork);
    workCells.push(tdWork);
  });

  [tr1, tr2, tr3].forEach(tr => table.appendChild(tr));
  return table;
}

function buildSheets() {
  const container = document.getElementById('container');
  const currentStart = new Date(START_DATE);

  for (let i = 0; i < SCHEDULE_COUNT; i++) {
    const sheet = document.createElement('div');
    sheet.className = 'sheet';

    const title = document.createElement('h2');
    title.textContent = i === 0 ? '勤務表' : `勤務表${i + 1}`;
    sheet.appendChild(title);

    const workCells  = [];
    const eventCells = [];
    const days = generateDays(currentStart);

    const sumTable = document.createElement('table');
    sumTable.className = 'sumTable';
    const sumRow   = document.createElement('tr');
    sumRow.className = 'sumRow';
    const sumLabel = document.createElement('td');
    sumLabel.textContent = '合計';
    sumLabel.className = 'label';
    const sumCell = document.createElement('td');
    sumCell.colSpan = DAYS_PER_ROW;
    sumCell.textContent = '0';
    sumCell.className = 'sumValue';
    sumRow.appendChild(sumLabel);
    sumRow.appendChild(sumCell);
    sumTable.appendChild(sumRow);

    const updateSum = (cells => () => {
      sumCell.textContent = cells.filter(c => ['公休', '公出勤'].includes(c.textContent)).length;
    })(workCells);

    for (let sec = 0; sec < 2; sec++) {
      const secDays = days.slice(sec * 14, (sec + 1) * 14);
      for (let chunk = 0; chunk * DAYS_PER_ROW < secDays.length; chunk++) {
        const offset = chunk * DAYS_PER_ROW;
        const chunkDays = secDays.slice(offset, offset + DAYS_PER_ROW);
        sheet.appendChild(createSection(chunkDays, workCells, eventCells, updateSum, i, sec, offset));
      }
    }

    sheet.appendChild(sumTable);

    const resetBtn = document.createElement('button');
    resetBtn.textContent = 'リセット';
    resetBtn.style.marginTop = '4px';
    resetBtn.onclick = ((si, wc, ec, us) => () => clearSheet(si, wc, ec, us))(i, workCells, eventCells, updateSum);
    sheet.appendChild(resetBtn);

    updateSum();
    container.appendChild(sheet);
    currentStart.setDate(currentStart.getDate() + 28);
  }
}

init();
