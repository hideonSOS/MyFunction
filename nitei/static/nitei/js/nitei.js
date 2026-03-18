const START_DATE     = new Date(2026, 3, 15);  // 2026-04-15
const SCHEDULE_COUNT = 15;
let TITLES    = [];
let savedData = {};

async function init() {
  const [titlesRes, scheduleRes] = await Promise.all([
    fetch('/nitei/api/titles/'),
    fetch('/nitei/api/schedule/'),
  ]);
  TITLES    = await titlesRes.json();
  savedData = await scheduleRes.json();
  document.getElementById('status').textContent = '✓ データ読み込み完了';
  buildSheets();
}

/* ----- TITLESから日付→色 ----- */
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

/* ----- サーバーに1セル保存 ----- */
async function saveCell(key, value) {
  savedData[key] = value;
  await fetch('/nitei/api/schedule/save/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, status: value }),
  });
}

/* ----- シートリセット ----- */
async function clearSheet(sheetIndex, workCells, updateSum) {
  const label = sheetIndex === 0 ? '勤務表' : `勤務表${sheetIndex + 1}`;
  if (!confirm(`${label}の入力をリセットしますか？`)) return;
  await fetch('/nitei/api/schedule/clear/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sheet_index: sheetIndex }),
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

function createSection(dateList, workCells, eventCells, updateSum, sheetIndex, sectionIndex) {
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

  dateList.forEach((date, dayIndex) => {
    const m = date.getMonth() + 1;
    const d = date.getDate();
    const dow = date.getDay();

    const tdDay = document.createElement('td');
    tdDay.textContent = `${m}/${d}`;
    tdDay.className = 'day' + (dow === 6 ? ' sat' : dow === 0 ? ' sun' : '');
    tr1.appendChild(tdDay);

    const tdEvent = document.createElement('td');
    tdEvent.style.cursor = 'default';
    const color = getEventColor(date);
    if (color) tdEvent.classList.add(color);
    tr2.appendChild(tdEvent);
    eventCells.push(tdEvent);

    const workKey = `w_${sheetIndex}_${sectionIndex}_${dayIndex}`;
    const tdWork = document.createElement('td');

    if (savedData[workKey] !== undefined) {
      tdWork.textContent = savedData[workKey];
    } else if (color) {
      tdWork.textContent = '公開FM';
      saveCell(workKey, '公開FM');
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
    const sumRow   = document.createElement('tr');
    sumRow.className = 'sumRow';
    const sumLabel = document.createElement('td');
    sumLabel.textContent = '合計';
    sumLabel.className = 'label';
    const sumCell = document.createElement('td');
    sumCell.colSpan = 14;
    sumCell.textContent = '0';
    sumCell.className = 'sumValue';
    sumRow.appendChild(sumLabel);
    sumRow.appendChild(sumCell);
    sumTable.appendChild(sumRow);

    const updateSum = (cells => () => {
      sumCell.textContent = cells.filter(c => ['公休', '公出勤'].includes(c.textContent)).length;
    })(workCells);

    sheet.appendChild(createSection(days.slice(0, 14),  workCells, eventCells, updateSum, i, 0));
    sheet.appendChild(createSection(days.slice(14, 28), workCells, eventCells, updateSum, i, 1));
    sheet.appendChild(sumTable);

    const resetBtn = document.createElement('button');
    resetBtn.textContent = 'リセット';
    resetBtn.style.marginTop = '4px';
    resetBtn.onclick = ((si, wc, us) => () => clearSheet(si, wc, us))(i, workCells, updateSum);
    sheet.appendChild(resetBtn);

    updateSum();
    container.appendChild(sheet);
    currentStart.setDate(currentStart.getDate() + 28);
  }
}

init();
