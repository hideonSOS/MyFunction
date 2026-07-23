/* 配置図（1日単位） */
(function () {
  'use strict';

  const API_GET   = '/nitei/api/layout/';
  const API_SAVE  = '/nitei/api/layout/save/';
  const API_CLEAR = '/nitei/api/layout/clear/';

  const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土'];

  const dateInput = document.getElementById('date-input');
  const statusEl  = document.getElementById('hc-status');
  const weekdayEl = document.getElementById('hc-weekday');
  const table     = document.getElementById('hc-table');

  // ── 状態 ───────────────────────────────────
  let state = {
    date:    dateInput.value,
    headers: DEFAULT_HEADERS.slice(),
    races:   {},   // race -> {start, close, highlight}
    cells:   {},   // "race_col" -> text
    colors:  {},   // "race_col" -> 'c1'〜'c10'
  };

  function blankRace() {
    return { start: '', close: '', highlight: false };
  }

  // ── ユーティリティ ─────────────────────────
  function setStatus(text, cls) {
    statusEl.textContent = text;
    statusEl.className = cls || '';
  }

  function toMinutes(hhmm) {
    const m = /^(\d{1,2}):(\d{2})$/.exec((hhmm || '').trim());
    if (!m) return null;
    const h = parseInt(m[1], 10);
    const mi = parseInt(m[2], 10);
    if (h > 23 || mi > 59) return null;
    return h * 60 + mi;
  }

  /** 締め切り − 発売開始 = 発売時間（日跨ぎは +24h） */
  function duration(start, close) {
    const s = toMinutes(start);
    const c = toMinutes(close);
    if (s === null || c === null) return '';
    let diff = c - s;
    if (diff < 0) diff += 24 * 60;
    const h = Math.floor(diff / 60);
    const mi = diff % 60;
    return String(h).padStart(2, '0') + ':' + String(mi).padStart(2, '0');
  }

  /** 入力された時刻を HH:MM に正規化（"1530" / "15:3" / "15時30" も許容） */
  function normalizeTime(raw) {
    const v = (raw || '').trim();
    if (!v) return '';
    const digits = v.replace(/[^\d]/g, '');
    let h, mi;
    if (/^\d{1,2}:\d{1,2}$/.test(v)) {
      const p = v.split(':');
      h = parseInt(p[0], 10);
      mi = parseInt(p[1], 10);
    } else if (digits.length === 3) {
      h = parseInt(digits.slice(0, 1), 10);
      mi = parseInt(digits.slice(1), 10);
    } else if (digits.length === 4) {
      h = parseInt(digits.slice(0, 2), 10);
      mi = parseInt(digits.slice(2), 10);
    } else {
      return '';
    }
    if (isNaN(h) || isNaN(mi) || h > 23 || mi > 59) return '';
    return String(h).padStart(2, '0') + ':' + String(mi).padStart(2, '0');
  }

  function shiftDate(isoDate, days) {
    const d = new Date(isoDate + 'T00:00:00');
    d.setDate(d.getDate() + days);
    return d.getFullYear() + '-' +
           String(d.getMonth() + 1).padStart(2, '0') + '-' +
           String(d.getDate()).padStart(2, '0');
  }

  function updateWeekday() {
    const d = new Date(state.date + 'T00:00:00');
    if (isNaN(d.getTime())) { weekdayEl.textContent = ''; return; }
    const w = d.getDay();
    weekdayEl.textContent = '（' + WEEKDAYS[w] + '）';
    weekdayEl.className = w === 0 ? 'sun' : (w === 6 ? 'sat' : '');
  }

  // ── 保存 ───────────────────────────────────
  let saveTimer = null;

  function scheduleSave() {
    setStatus('入力中...', 'saving');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 600);
  }

  /** 保留中の自動保存があれば即時に走らせる（日付切り替えで入力を捨てないため） */
  function flushSave() {
    if (saveTimer === null) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    save();
  }

  function save() {
    clearTimeout(saveTimer);
    saveTimer = null;
    setStatus('保存中...', 'saving');
    const races = [];
    for (let r = 1; r <= RACE_COUNT; r++) {
      const row = state.races[r];
      if (!row) continue;
      if (!row.start && !row.close && !row.highlight) continue;
      races.push({ race: r, start: row.start, close: row.close, highlight: row.highlight });
    }
    // 送信中に日付が変わっても、この保存は「送信時点の日付」に対して行う
    const payload = {
      date:    state.date,
      headers: state.headers.slice(),
      races:   races,
      cells:   Object.assign({}, state.cells),
      colors:  Object.assign({}, state.colors),
    };

    fetch(API_SAVE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(res => res.ok ? res.json() : Promise.reject(res.status))
      .then(() => setStatus('保存しました', 'saved'))
      .catch(() => setStatus('保存失敗', 'error'));
  }

  // ── 描画 ───────────────────────────────────
  function render() {
    table.innerHTML = '';

    // ヘッダー
    const thead = document.createElement('thead');
    const htr = document.createElement('tr');

    const thTime = document.createElement('th');
    thTime.className = 'hc-th-time';
    thTime.textContent = '';
    htr.appendChild(thTime);

    const thRace = document.createElement('th');
    thRace.className = 'hc-th-race';
    thRace.textContent = '';
    htr.appendChild(thRace);

    for (let c = 0; c < COL_COUNT; c++) {
      const th = document.createElement('th');
      th.className = 'hc-th-cell';
      const input = document.createElement('input');
      input.className = 'hc-head-input';
      input.value = state.headers[c] || '';
      input.placeholder = '（未設定）';
      input.addEventListener('input', () => {
        state.headers[c] = input.value;
        scheduleSave();
      });
      th.appendChild(input);
      htr.appendChild(th);
    }
    thead.appendChild(htr);
    table.appendChild(thead);

    // 本体
    const tbody = document.createElement('tbody');

    for (let r = 1; r <= RACE_COUNT; r++) {
      const row = state.races[r] || (state.races[r] = blankRace());

      // 1段目：発売開始
      const tr1 = document.createElement('tr');
      tr1.appendChild(timeCell(r, 'start', 'row-start'));

      const tdRace = document.createElement('td');
      tdRace.className = 'hc-race' + (row.highlight ? ' on' : '');
      tdRace.rowSpan = 3;
      tdRace.textContent = r + 'R';
      tdRace.title = 'クリックで着色切り替え';
      tdRace.addEventListener('click', () => {
        row.highlight = !row.highlight;
        tdRace.classList.toggle('on', row.highlight);
        scheduleSave();
      });
      tr1.appendChild(tdRace);

      for (let c = 0; c < COL_COUNT; c++) {
        const key = r + '_' + c;
        const td = document.createElement('td');
        td.rowSpan = 3;
        applyCellTint(td, key);

        // 左上のカラーチップ。入力欄のクリックを奪わないよう小さく置く
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'hc-chip';
        chip.title = '背景色を選ぶ';
        chip.setAttribute('aria-label', '背景色を選ぶ');
        chip.addEventListener('click', ev => {
          ev.preventDefault();
          ev.stopPropagation();
          openPalette(chip, key);
        });
        td.appendChild(chip);

        const input = document.createElement('input');
        input.className = 'hc-cell-input';
        input.value = state.cells[key] || '';
        input.maxLength = 200;
        input.addEventListener('input', () => {
          const v = input.value;
          if (v) state.cells[key] = v; else delete state.cells[key];
          scheduleSave();
        });
        td.appendChild(input);
        tr1.appendChild(td);
      }
      tbody.appendChild(tr1);

      // 2段目：発売時間（自動計算）
      const tr2 = document.createElement('tr');
      const tdDur = document.createElement('td');
      tdDur.className = 'hc-time-cell row-dur';
      const durDiv = document.createElement('div');
      durDiv.className = 'hc-dur';
      durDiv.dataset.race = r;
      durDiv.textContent = duration(row.start, row.close);
      tdDur.title = '発売時間（締め切り − 発売開始）';
      tdDur.appendChild(durDiv);
      tr2.appendChild(tdDur);
      tbody.appendChild(tr2);

      // 3段目：締め切り
      const tr3 = document.createElement('tr');
      tr3.className = 'race-close';
      tr3.appendChild(timeCell(r, 'close', 'row-close'));
      tbody.appendChild(tr3);
    }

    table.appendChild(tbody);
  }

  function timeCell(race, field, cls) {
    const td = document.createElement('td');
    td.className = 'hc-time-cell ' + cls;
    const input = document.createElement('input');
    input.className = 'hc-time-input';
    input.value = state.races[race][field] || '';
    input.placeholder = '--:--';
    input.title = field === 'start' ? '発売開始' : '締め切り時間';
    input.addEventListener('change', () => {
      const v = normalizeTime(input.value);
      input.value = v;
      state.races[race][field] = v;
      refreshDuration(race);
      scheduleSave();
    });
    td.appendChild(input);
    return td;
  }

  // ── セル背景色 ─────────────────────────────
  /** td に現在の色クラスを反映する */
  function applyCellTint(td, key) {
    const color = state.colors[key] || '';
    td.className = 'hc-cell' + (color ? ' tinted tint-' + color : '');
    td.dataset.key = key;
  }

  // パレット（1つを使い回す）
  let palette      = null;
  let paletteKey   = null;   // 編集中のセル
  let paletteChip  = null;

  function buildPalette() {
    palette = document.createElement('div');
    palette.id = 'hc-palette';

    const grid = document.createElement('div');
    grid.className = 'hc-pal-grid';
    COLOR_KEYS.forEach(ck => {
      const sw = document.createElement('button');
      sw.type = 'button';
      sw.className = 'hc-swatch tint-' + ck;
      sw.dataset.color = ck;
      sw.title = ck;
      sw.addEventListener('click', () => pickColor(ck));
      grid.appendChild(sw);
    });
    palette.appendChild(grid);

    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'hc-pal-clear';
    clearBtn.textContent = '色なし';
    clearBtn.addEventListener('click', () => pickColor(''));
    palette.appendChild(clearBtn);

    document.getElementById('haichi').appendChild(palette);
  }

  function openPalette(chip, key) {
    if (!palette) buildPalette();
    if (paletteKey === key && palette.classList.contains('open')) {
      closePalette();
      return;
    }
    paletteKey  = key;
    paletteChip = chip;

    // 現在の色を選択表示
    const current = state.colors[key] || '';
    palette.querySelectorAll('.hc-swatch').forEach(sw => {
      sw.classList.toggle('selected', sw.dataset.color === current);
    });

    palette.classList.add('open');

    // チップの真下へ。画面右端・下端からはみ出さないよう寄せる
    const host = document.getElementById('haichi').getBoundingClientRect();
    const rect = chip.getBoundingClientRect();
    const pw   = palette.offsetWidth;
    const ph   = palette.offsetHeight;

    let left = rect.left - host.left;
    let top  = rect.bottom - host.top + 4;
    const maxLeft = host.width - pw - 4;
    if (left > maxLeft) left = Math.max(0, maxLeft);
    if (rect.bottom + ph > window.innerHeight) {
      top = rect.top - host.top - ph - 4;
    }
    palette.style.left = left + 'px';
    palette.style.top  = top + 'px';
  }

  function closePalette() {
    if (palette) palette.classList.remove('open');
    paletteKey = null;
    paletteChip = null;
  }

  function pickColor(color) {
    if (paletteKey === null) return;
    const key = paletteKey;
    if (color) state.colors[key] = color; else delete state.colors[key];

    const td = table.querySelector('.hc-cell[data-key="' + key + '"]');
    if (td) applyCellTint(td, key);

    closePalette();
    scheduleSave();
  }

  // パレット外クリック / Esc で閉じる
  document.addEventListener('click', ev => {
    if (!palette || !palette.classList.contains('open')) return;
    if (palette.contains(ev.target) || ev.target === paletteChip) return;
    closePalette();
  });

  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape') closePalette();
  });

  function refreshDuration(race) {
    const el = table.querySelector('.hc-dur[data-race="' + race + '"]');
    if (el) el.textContent = duration(state.races[race].start, state.races[race].close);
  }

  // ── 読み込み ───────────────────────────────
  let loadSeq = 0;   // 連打時に古いレスポンスが後着しても上書きさせない

  function load(isoDate) {
    flushSave();   // 未保存の入力を捨てずに書き込んでから切り替える
    const seq = ++loadSeq;
    setStatus('読み込み中...', '');
    state.date = isoDate;
    dateInput.value = isoDate;
    updateWeekday();

    fetch(API_GET + '?date=' + encodeURIComponent(isoDate))
      .then(res => res.ok ? res.json() : Promise.reject(res.status))
      .then(data => {
        if (seq !== loadSeq) return;
        state.headers = (data.headers && data.headers.length)
          ? data.headers.slice() : DEFAULT_HEADERS.slice();
        state.races = {};
        for (let r = 1; r <= RACE_COUNT; r++) state.races[r] = blankRace();
        (data.races || []).forEach(item => {
          state.races[item.race] = {
            start:     item.start || '',
            close:     item.close || '',
            highlight: !!item.highlight,
          };
        });
        state.cells  = Object.assign({}, data.cells  || {});
        state.colors = Object.assign({}, data.colors || {});
        closePalette();
        render();
        setStatus(data.exists ? '読み込み完了' : '新規（未入力）', '');
      })
      .catch(() => { if (seq === loadSeq) setStatus('読み込み失敗', 'error'); });
  }

  // ── イベント ───────────────────────────────
  dateInput.addEventListener('change', () => {
    if (dateInput.value) load(dateInput.value);
  });

  document.getElementById('prev-day').addEventListener('click', () => load(shiftDate(state.date, -1)));
  document.getElementById('next-day').addEventListener('click', () => load(shiftDate(state.date, 1)));

  document.getElementById('today-btn').addEventListener('click', () => {
    const d = new Date();
    load(d.getFullYear() + '-' +
         String(d.getMonth() + 1).padStart(2, '0') + '-' +
         String(d.getDate()).padStart(2, '0'));
  });

  document.getElementById('clear-btn').addEventListener('click', () => {
    if (!confirm(state.date + ' の配置図をすべて消去します。よろしいですか？')) return;
    clearTimeout(saveTimer);
    saveTimer = null;   // 消去後に保留中の保存が復活しないように
    setStatus('消去中...', 'saving');
    fetch(API_CLEAR, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: state.date }),
    })
      .then(res => res.ok ? res.json() : Promise.reject(res.status))
      .then(() => load(state.date))
      .catch(() => setStatus('消去失敗', 'error'));
  });

  load(dateInput.value);
})();
