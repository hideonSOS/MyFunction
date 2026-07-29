/* 付箋・タスク（fusen） ── 週カレンダー表示 */
(function () {
  'use strict';

  const root = document.getElementById('fusen');
  const CSRF = root.dataset.csrf;

  // トーン → 実際の色（CSS の .tone-* と一致させる）
  const TONE_COLOR = {
    yellow: '#f5e17a', pink: '#f5a3c7', green: '#a3e6b0',
    blue:   '#a3c7f5', purple: '#cbb3f0', gray: '#cfd6de',
  };
  const TONE_KEYS = Object.keys(TONE_COLOR);
  const DOW = ['日', '月', '火', '水', '木', '金', '土'];
  const DAYS_BEFORE = 5;   // 当日より前
  const DAYS_AFTER  = 5;   // 当日より後（合計 11 日）
  const SPAN = DAYS_BEFORE + DAYS_AFTER + 1;

  // 状態
  let notes = [];
  let tasks = [];
  let dismissedReminders = new Set();
  let winStart = null;   // 表示ウィンドウの左端の日付

  // ── 通信 ───────────────────────────────────
  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error('request failed: ' + res.status);
    return res.json();
  }

  async function loadState() {
    const res = await fetch('/fusen/api/state/');
    const data = await res.json();
    notes = data.notes || [];
    tasks = data.tasks || [];
    render();
  }

  // ── 日付ユーティリティ ─────────────────────
  function pad(n) { return String(n).padStart(2, '0'); }

  function dateKey(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function localMidnight(d) {
    const x = new Date(d); x.setHours(0, 0, 0, 0); return x;
  }

  function addDays(d, n) {
    const x = new Date(d); x.setDate(x.getDate() + n); return x;
  }

  function parseLocal(s) {
    if (!s) return null;
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function toLocalInput(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function hhmm(s) {
    const d = parseLocal(s);
    if (!d) return '';
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fmtWhen(s) {
    const d = parseLocal(s);
    if (!d) return '';
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const isTmr = d.toDateString() === addDays(now, 1).toDateString();
    const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    if (sameDay) return `今日 ${hm}`;
    if (isTmr)   return `明日 ${hm}`;
    return `${d.getMonth() + 1}/${d.getDate()} ${hm}`;
  }

  function relWhen(s) {
    const d = parseLocal(s);
    if (!d) return '';
    const diffMin = Math.round((d - new Date()) / 60000);
    const abs = Math.abs(diffMin);
    let txt;
    if (abs < 60)        txt = `${abs}分`;
    else if (abs < 1440) txt = `${Math.round(abs / 60)}時間`;
    else                 txt = `${Math.round(abs / 1440)}日`;
    return diffMin >= 0 ? `あと${txt}` : `${txt}前`;
  }

  // タスク/付箋が属する日付キー（無ければ null=未分類）
  function taskDay(t) { return t.due_at ? t.due_at.slice(0, 10) : null; }
  function noteDay(n) { return n.date || null; }

  // ── 描画: 全体 ─────────────────────────────
  function render() {
    renderReminders();
    renderWindow();
  }

  function renderWindow() {
    const cal = document.getElementById('fs-calendar');
    cal.innerHTML = '';

    const today = localMidnight(new Date());
    const todayKey = dateKey(today);

    // 期間ラベル
    const last = addDays(winStart, SPAN - 1);
    const fmt = d => `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
    document.getElementById('fs-range').textContent = `${fmt(winStart)} 〜 ${fmt(last)}`;

    // バケツ分け
    const tasksByDay = {};
    const untasked = [];
    tasks.forEach(t => {
      const k = taskDay(t);
      if (k) (tasksByDay[k] = tasksByDay[k] || []).push(t);
      else untasked.push(t);
    });
    const notesByDay = {};
    const unnoted = [];
    notes.forEach(n => {
      const k = noteDay(n);
      if (k) (notesByDay[k] = notesByDay[k] || []).push(n);
      else unnoted.push(n);
    });

    // 未分類
    renderInbox(untasked, unnoted);

    // 各日カラム
    let todayCol = null;
    for (let i = 0; i < SPAN; i++) {
      const d = addDays(winStart, i);
      const key = dateKey(d);
      const col = dayColumn(d, key, key === todayKey,
        tasksByDay[key] || [], notesByDay[key] || []);
      cal.appendChild(col);
      if (key === todayKey) todayCol = col;
    }

    // 今日の列を中央にスクロール
    if (todayCol) {
      requestAnimationFrame(() => {
        todayCol.scrollIntoView({ behavior: 'auto', inline: 'center', block: 'nearest' });
      });
    }
  }

  function dayColumn(d, key, isToday, dayTasks, dayNotes) {
    const dow = d.getDay();
    const col = document.createElement('div');
    col.className = 'fs-col'
      + (isToday ? ' today' : '')
      + (dow === 0 ? ' sun' : dow === 6 ? ' sat' : '');
    col.dataset.day = key;

    // ヘッダー
    const head = document.createElement('div');
    head.className = 'fs-col-head';
    const label = document.createElement('div');
    label.className = 'fs-col-date';
    label.innerHTML = `<b>${d.getMonth() + 1}/${d.getDate()}</b> <span class="fs-col-dow">${DOW[dow]}</span>`;
    head.appendChild(label);

    const add = document.createElement('div');
    add.className = 'fs-col-add';
    const addT = document.createElement('button');
    addT.textContent = '＋タスク';
    addT.title = 'この日にタスクを追加';
    addT.addEventListener('click', () => openTaskModal(null, key));
    const addN = document.createElement('button');
    addN.textContent = '＋付箋';
    addN.title = 'この日に付箋を追加';
    addN.addEventListener('click', () => addNote(key));
    add.appendChild(addT);
    add.appendChild(addN);
    head.appendChild(add);
    col.appendChild(head);

    // 本文
    const body = document.createElement('div');
    body.className = 'fs-col-body';
    dayTasks.forEach(t => body.appendChild(taskCard(t)));
    dayNotes.forEach(n => body.appendChild(noteCard(n)));
    col.appendChild(body);

    setDropTarget(col, key);
    return col;
  }

  function renderInbox(untasked, unnoted) {
    const box = document.getElementById('fs-inbox-body');
    box.innerHTML = '';
    untasked.forEach(t => box.appendChild(taskCard(t)));
    unnoted.forEach(n => box.appendChild(noteCard(n)));
    const total = untasked.length + unnoted.length;
    document.getElementById('fs-inbox-count').textContent = total ? `(${total})` : '';
    const empty = total === 0;
    if (empty) {
      const hint = document.createElement('div');
      hint.className = 'fs-inbox-hint';
      hint.textContent = '日付のないタスク・付箋がここに入ります（ここへドラッグで日付を外す）';
      box.appendChild(hint);
    }
    setDropTarget(document.getElementById('fs-inbox'), '');
  }

  // ── タスクカード ───────────────────────────
  function taskCard(t) {
    const card = document.createElement('div');
    card.className = 'fs-task' + (t.is_done ? ' done' : '') + (t.is_overdue ? ' overdue' : '');
    card.style.setProperty('--tone-c', TONE_COLOR[t.tone] || TONE_COLOR.blue);
    card.draggable = true;
    card.addEventListener('dragstart', ev => onDragStart(ev, 'task', t.id));
    card.addEventListener('dragend', onDragEnd);

    const top = document.createElement('div');
    top.className = 'fs-task-top';

    const check = document.createElement('button');
    check.className = 'fs-check' + (t.is_done ? ' checked' : t.status === 'doing' ? ' doing' : '');
    check.title = '状態を切り替え';
    check.addEventListener('click', ev => {
      ev.stopPropagation();
      const next = { todo: 'doing', doing: 'done', done: 'todo' }[t.status] || 'todo';
      updateStatus(t, next);
    });
    top.appendChild(check);

    const title = document.createElement('div');
    title.className = 'fs-task-title';
    title.textContent = t.title;
    title.addEventListener('click', () => openTaskModal(t));
    top.appendChild(title);
    card.appendChild(top);

    const meta = document.createElement('div');
    meta.className = 'fs-task-meta';
    const prio = document.createElement('span');
    prio.className = 'fs-badge prio-' + t.priority;
    prio.textContent = ['低', '中', '高'][t.priority] || '中';
    meta.appendChild(prio);
    if (t.due_at) {
      const due = document.createElement('span');
      due.className = 'fs-badge due' + (t.is_overdue ? ' over' : t.is_due_soon ? ' soon' : '');
      due.textContent = hhmm(t.due_at);
      meta.appendChild(due);
    }
    if (t.remind_at && !t.is_done) {
      const rm = document.createElement('span');
      rm.className = 'fs-badge remind';
      rm.textContent = '🔔' + hhmm(t.remind_at);
      meta.appendChild(rm);
    }
    card.appendChild(meta);
    return card;
  }

  async function updateStatus(t, status) {
    const updated = await post('/fusen/api/task/status/', { id: t.id, status });
    replaceTask(updated);
    render();
  }

  function replaceTask(u) {
    const i = tasks.findIndex(x => x.id === u.id);
    if (i >= 0) tasks[i] = u; else tasks.push(u);
  }

  // ── 付箋カード ─────────────────────────────
  function noteCard(n) {
    const card = document.createElement('div');
    card.className = 'fs-note' + (n.pinned ? ' pinned' : '');
    card.style.setProperty('--note-bg', TONE_COLOR[n.tone] || TONE_COLOR.yellow);

    const grip = document.createElement('div');
    grip.className = 'fs-note-grip';
    grip.textContent = '⠿';
    grip.title = 'ドラッグで移動';
    grip.draggable = true;
    grip.addEventListener('dragstart', ev => onDragStart(ev, 'note', n.id));
    grip.addEventListener('dragend', onDragEnd);
    card.appendChild(grip);

    const body = document.createElement('textarea');
    body.className = 'fs-note-body';
    body.value = n.body;
    body.placeholder = 'メモ...';
    body.dataset.noteFocus = n.id;
    let saveTimer = null;
    body.addEventListener('input', () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => saveNote({ id: n.id, body: body.value }), 500);
    });
    card.appendChild(body);

    const bar = document.createElement('div');
    bar.className = 'fs-note-bar';

    const pin = document.createElement('button');
    pin.className = 'fs-note-pin' + (n.pinned ? ' on' : '');
    pin.textContent = '📌';
    pin.title = 'ピン留め';
    pin.addEventListener('click', () => saveNote({ id: n.id, pinned: !n.pinned }));
    bar.appendChild(pin);

    const toneBtn = document.createElement('button');
    toneBtn.className = 'fs-note-tone';
    toneBtn.textContent = '🎨';
    toneBtn.title = '色を変える';
    const tones = document.createElement('div');
    tones.className = 'fs-note-tones';
    TONE_KEYS.forEach(k => {
      const sw = document.createElement('button');
      sw.className = 'fs-tone tone-' + k;
      sw.addEventListener('click', () => saveNote({ id: n.id, tone: k }));
      tones.appendChild(sw);
    });
    toneBtn.addEventListener('click', () => tones.classList.toggle('open'));
    bar.appendChild(toneBtn);
    bar.appendChild(tones);

    const del = document.createElement('button');
    del.className = 'fs-note-del';
    del.textContent = '🗑';
    del.title = '削除';
    del.style.marginLeft = 'auto';
    del.addEventListener('click', () => {
      if (confirm('この付箋を削除しますか？')) deleteNote(n);
    });
    bar.appendChild(del);
    card.appendChild(bar);
    return card;
  }

  async function saveNote(patch) {
    const saved = await post('/fusen/api/note/save/', patch);
    const i = notes.findIndex(x => x.id === saved.id);
    if (i >= 0) notes[i] = saved; else notes.push(saved);
    render();
  }

  async function deleteNote(n) {
    await post('/fusen/api/note/delete/', { id: n.id });
    notes = notes.filter(x => x.id !== n.id);
    render();
  }

  async function addNote(day) {
    const saved = await post('/fusen/api/note/save/', { body: '', tone: 'yellow', date: day || '' });
    notes.push(saved);
    render();
    // 追加した付箋にフォーカス
    requestAnimationFrame(() => {
      const sel = `[data-note-focus="${saved.id}"]`;
      const el = document.querySelector(sel);
      if (el) el.focus();
    });
  }

  // ── ドラッグ&ドロップ ─────────────────────
  let dragData = null;

  function onDragStart(ev, kind, id) {
    dragData = { kind, id };
    ev.dataTransfer.effectAllowed = 'move';
    ev.dataTransfer.setData('text/plain', JSON.stringify(dragData));
    document.body.classList.add('fs-dragging');
  }

  function onDragEnd() {
    dragData = null;
    document.body.classList.remove('fs-dragging');
    document.querySelectorAll('.fs-drop-over').forEach(e => e.classList.remove('fs-drop-over'));
  }

  function setDropTarget(el, dayKey) {
    el.addEventListener('dragover', ev => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      el.classList.add('fs-drop-over');
    });
    el.addEventListener('dragleave', ev => {
      if (ev.target === el) el.classList.remove('fs-drop-over');
    });
    el.addEventListener('drop', async ev => {
      ev.preventDefault();
      el.classList.remove('fs-drop-over');
      let payload = dragData;
      if (!payload) {
        try { payload = JSON.parse(ev.dataTransfer.getData('text/plain')); } catch (e) { return; }
      }
      if (!payload) return;
      await moveItem(payload, dayKey);
    });
  }

  async function moveItem(payload, dayKey) {
    if (payload.kind === 'task') {
      const cur = tasks.find(t => t.id === payload.id);
      if (cur && taskDay(cur) === (dayKey || null)) return;   // 同じ日なら無視
      const updated = await post('/fusen/api/task/move/', { id: payload.id, date: dayKey });
      replaceTask(updated);
      dismissedReminders.delete(updated.id);
    } else {
      const cur = notes.find(n => n.id === payload.id);
      if (cur && noteDay(cur) === (dayKey || null)) return;
      await saveNote({ id: payload.id, date: dayKey });
      return;   // saveNote 内で render 済み
    }
    render();
  }

  // ── 思い出しバナー ─────────────────────────
  function renderReminders() {
    const box = document.getElementById('fs-reminders');
    const due = tasks.filter(t => t.should_remind && !dismissedReminders.has(t.id));
    if (due.length === 0) { box.hidden = true; box.innerHTML = ''; return; }

    box.hidden = false;
    box.innerHTML = '';
    const title = document.createElement('div');
    title.className = 'fs-reminders-title';
    title.textContent = `🔔 思い出し（${due.length}件）`;
    box.appendChild(title);

    due.forEach(t => {
      const item = document.createElement('div');
      item.className = 'fs-remind-item';
      const ttl = document.createElement('span');
      ttl.className = 'fs-rm-title';
      ttl.textContent = t.title;
      item.appendChild(ttl);
      const when = document.createElement('span');
      when.className = 'fs-rm-when';
      when.textContent = t.due_at ? '期限 ' + fmtWhen(t.due_at) : relWhen(t.remind_at);
      item.appendChild(when);

      const actions = document.createElement('div');
      actions.className = 'fs-rm-actions';
      const doneBtn = document.createElement('button');
      doneBtn.className = 'fs-rm-done';
      doneBtn.textContent = '完了';
      doneBtn.addEventListener('click', () => updateStatus(t, 'done'));
      actions.appendChild(doneBtn);
      const snooze = document.createElement('button');
      snooze.textContent = '30分後';
      snooze.addEventListener('click', () => snoozeTask(t, 30));
      actions.appendChild(snooze);
      const later = document.createElement('button');
      later.textContent = 'あとで';
      later.addEventListener('click', () => { dismissedReminders.add(t.id); renderReminders(); });
      actions.appendChild(later);
      item.appendChild(actions);
      box.appendChild(item);
    });
  }

  async function snoozeTask(t, minutes) {
    const updated = await post('/fusen/api/task/reminded/', { id: t.id, snooze_minutes: minutes });
    replaceTask(updated);
    render();
  }

  // ── タスクモーダル ─────────────────────────
  const modal = document.getElementById('fs-modal');
  let editingId = null;
  let modalTone = 'blue';

  function setModalTone(tone) {
    modalTone = tone;
    document.querySelectorAll('#fs-f-tone .fs-tone').forEach(el => {
      el.classList.toggle('selected', el.dataset.tone === tone);
    });
  }

  function openTaskModal(t, presetDay) {
    editingId = t ? t.id : null;
    document.getElementById('fs-modal-title').textContent = t ? 'タスクを編集' : '新しいタスク';
    document.getElementById('fs-f-title').value    = t ? t.title : '';
    document.getElementById('fs-f-detail').value   = t ? t.detail : '';
    // 新規で日付指定があれば、その日の 09:00 を期限の初期値にする
    let due = t && t.due_at ? t.due_at : '';
    if (!t && presetDay) due = presetDay + 'T09:00';
    document.getElementById('fs-f-due').value      = due;
    document.getElementById('fs-f-remind').value   = t && t.remind_at ? t.remind_at : '';
    document.getElementById('fs-f-priority').value = t ? String(t.priority) : '1';
    document.getElementById('fs-f-status').value   = t ? t.status : 'todo';
    setModalTone(t ? t.tone : 'blue');
    document.getElementById('fs-modal-delete').hidden = !t;
    modal.hidden = false;
    document.getElementById('fs-f-title').focus();
  }

  function closeModal() { modal.hidden = true; editingId = null; }

  async function saveModal() {
    const title = document.getElementById('fs-f-title').value.trim();
    if (!title) { document.getElementById('fs-f-title').focus(); return; }
    const payload = {
      id:        editingId,
      title,
      detail:    document.getElementById('fs-f-detail').value,
      due_at:    document.getElementById('fs-f-due').value,
      remind_at: document.getElementById('fs-f-remind').value,
      priority:  parseInt(document.getElementById('fs-f-priority').value, 10),
      status:    document.getElementById('fs-f-status').value,
      tone:      modalTone,
    };
    const saved = await post('/fusen/api/task/save/', payload);
    replaceTask(saved);
    dismissedReminders.delete(saved.id);
    closeModal();
    render();
  }

  async function deleteTask() {
    if (editingId == null) return;
    if (!confirm('このタスクを削除しますか？')) return;
    await post('/fusen/api/task/delete/', { id: editingId });
    tasks = tasks.filter(x => x.id !== editingId);
    closeModal();
    render();
  }

  document.getElementById('fs-remind-quick').addEventListener('click', ev => {
    const b = ev.target.closest('button');
    if (!b) return;
    const remindInput = document.getElementById('fs-f-remind');
    if (b.dataset.min) {
      remindInput.value = toLocalInput(new Date(Date.now() + parseInt(b.dataset.min, 10) * 60000));
    } else if (b.dataset.at === 'tomorrow9') {
      const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0);
      remindInput.value = toLocalInput(d);
    } else if (b.dataset.due) {
      const dueVal = document.getElementById('fs-f-due').value;
      if (dueVal) remindInput.value = dueVal;
    }
  });

  document.querySelectorAll('#fs-f-tone .fs-tone').forEach(el => {
    el.addEventListener('click', () => setModalTone(el.dataset.tone));
  });

  // ── 週ナビゲーション ───────────────────────
  function recenterToday() {
    winStart = addDays(localMidnight(new Date()), -DAYS_BEFORE);
  }

  document.getElementById('fs-prev').addEventListener('click', () => { winStart = addDays(winStart, -7); renderWindow(); });
  document.getElementById('fs-next').addEventListener('click', () => { winStart = addDays(winStart, 7); renderWindow(); });
  document.getElementById('fs-today').addEventListener('click', () => { recenterToday(); renderWindow(); });

  // ── イベント配線 ───────────────────────────
  document.getElementById('fs-add-task').addEventListener('click', () => openTaskModal(null, null));
  document.getElementById('fs-add-note').addEventListener('click', () => addNote(dateKey(localMidnight(new Date()))));
  document.getElementById('fs-modal-save').addEventListener('click', saveModal);
  document.getElementById('fs-modal-cancel').addEventListener('click', closeModal);
  document.getElementById('fs-modal-close').addEventListener('click', closeModal);
  document.getElementById('fs-modal-delete').addEventListener('click', deleteTask);
  modal.addEventListener('click', ev => { if (ev.target === modal) closeModal(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !modal.hidden) closeModal(); });

  // 1分ごとに再取得（リマインド時刻の跨ぎに対応）
  setInterval(loadState, 60000);

  // 初期化
  recenterToday();
  loadState();
})();
