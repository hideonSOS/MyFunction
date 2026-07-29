/* 付箋・タスク（fusen） */
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

  // 状態
  let notes  = [];
  let tasks  = [];
  let filter = 'active';
  let dismissedReminders = new Set();   // このセッションで閉じた思い出し

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
    renderAll();
  }

  // ── 日時ユーティリティ ─────────────────────
  function parseLocal(s) {
    if (!s) return null;
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtWhen(s) {
    const d = parseLocal(s);
    if (!d) return '';
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const tmr = new Date(now); tmr.setDate(tmr.getDate() + 1);
    const isTmr = d.toDateString() === tmr.toDateString();
    const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
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
    if (abs < 60)       txt = `${abs}分`;
    else if (abs < 1440) txt = `${Math.round(abs / 60)}時間`;
    else                 txt = `${Math.round(abs / 1440)}日`;
    return diffMin >= 0 ? `あと${txt}` : `${txt}前`;
  }

  // ── 描画: 全体 ─────────────────────────────
  function renderAll() {
    renderTasks();
    renderNotes();
    renderReminders();
  }

  // ── 描画: タスク ───────────────────────────
  function taskMatchesFilter(t) {
    switch (filter) {
      case 'active':  return !t.is_done;
      case 'today':   return !t.is_done && t.is_due_soon;
      case 'overdue': return t.is_overdue;
      case 'done':    return t.is_done;
      case 'all':     return true;
      default:        return true;
    }
  }

  function renderTasks() {
    const list = document.getElementById('fs-task-list');
    const empty = document.getElementById('fs-task-empty');
    list.innerHTML = '';

    const shown = tasks.filter(taskMatchesFilter);
    empty.hidden = shown.length > 0;

    shown.forEach(t => list.appendChild(taskRow(t)));
  }

  function taskRow(t) {
    const row = document.createElement('div');
    row.className = 'fs-task' + (t.is_done ? ' done' : '') + (t.is_overdue ? ' overdue' : '');
    row.style.setProperty('--tone-c', TONE_COLOR[t.tone] || TONE_COLOR.blue);

    // チェックボックス（未着手→進行中→完了→未着手）
    const check = document.createElement('button');
    check.className = 'fs-check' + (t.is_done ? ' checked' : t.status === 'doing' ? ' doing' : '');
    check.title = '状態を切り替え';
    check.addEventListener('click', ev => {
      ev.stopPropagation();
      const next = { todo: 'doing', doing: 'done', done: 'todo' }[t.status] || 'todo';
      updateStatus(t, next);
    });
    row.appendChild(check);

    // 本文
    const main = document.createElement('div');
    main.className = 'fs-task-main';
    main.addEventListener('click', () => openTaskModal(t));

    const title = document.createElement('div');
    title.className = 'fs-task-title';
    title.textContent = t.title;
    main.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'fs-task-meta';

    const prio = document.createElement('span');
    prio.className = 'fs-badge prio-' + t.priority;
    prio.textContent = ['低', '中', '高'][t.priority] || '中';
    meta.appendChild(prio);

    if (t.due_at) {
      const due = document.createElement('span');
      due.className = 'fs-badge due' + (t.is_overdue ? ' over' : t.is_due_soon ? ' soon' : '');
      due.textContent = '期限 ' + fmtWhen(t.due_at);
      meta.appendChild(due);
    }
    if (t.remind_at && !t.is_done) {
      const rm = document.createElement('span');
      rm.className = 'fs-badge remind';
      rm.textContent = '🔔 ' + fmtWhen(t.remind_at);
      meta.appendChild(rm);
    }
    main.appendChild(meta);

    if (t.detail) {
      const det = document.createElement('div');
      det.className = 'fs-task-detail';
      det.textContent = t.detail;
      main.appendChild(det);
    }

    row.appendChild(main);
    return row;
  }

  async function updateStatus(t, status) {
    const updated = await post('/fusen/api/task/status/', { id: t.id, status });
    replaceTask(updated);
    renderAll();
  }

  function replaceTask(updated) {
    const i = tasks.findIndex(x => x.id === updated.id);
    if (i >= 0) tasks[i] = updated; else tasks.push(updated);
  }

  // ── 描画: 付箋 ─────────────────────────────
  function renderNotes() {
    const board = document.getElementById('fs-note-board');
    const empty = document.getElementById('fs-note-empty');
    board.innerHTML = '';
    empty.hidden = notes.length > 0;
    notes.forEach(n => board.appendChild(noteCard(n)));
  }

  function noteCard(n) {
    const card = document.createElement('div');
    card.className = 'fs-note' + (n.pinned ? ' pinned' : '');
    card.style.setProperty('--note-bg', TONE_COLOR[n.tone] || TONE_COLOR.yellow);

    const body = document.createElement('textarea');
    body.className = 'fs-note-body';
    body.value = n.body;
    body.placeholder = 'メモを入力...';
    let saveTimer = null;
    body.addEventListener('input', () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => saveNote({ ...n, body: body.value }), 500);
    });
    card.appendChild(body);

    const bar = document.createElement('div');
    bar.className = 'fs-note-bar';

    const pin = document.createElement('button');
    pin.className = 'fs-note-pin' + (n.pinned ? ' on' : '');
    pin.textContent = '📌';
    pin.title = 'ピン留め';
    pin.addEventListener('click', () => saveNote({ ...n, body: body.value, pinned: !n.pinned }));
    bar.appendChild(pin);

    // 色切り替え
    const toneBtn = document.createElement('button');
    toneBtn.className = 'fs-note-tone';
    toneBtn.textContent = '🎨';
    toneBtn.title = '色を変える';
    const tones = document.createElement('div');
    tones.className = 'fs-note-tones';
    TONE_KEYS.forEach(k => {
      const sw = document.createElement('button');
      sw.className = 'fs-tone tone-' + k;
      sw.addEventListener('click', () => saveNote({ ...n, body: body.value, tone: k }));
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
    const saved = await post('/fusen/api/note/save/', {
      id: patch.id, body: patch.body, tone: patch.tone, pinned: patch.pinned,
    });
    const i = notes.findIndex(x => x.id === saved.id);
    if (i >= 0) notes[i] = saved; else notes.push(saved);
    renderNotes();
  }

  async function deleteNote(n) {
    await post('/fusen/api/note/delete/', { id: n.id });
    notes = notes.filter(x => x.id !== n.id);
    renderNotes();
  }

  async function addNote() {
    const saved = await post('/fusen/api/note/save/', { body: '', tone: 'yellow' });
    notes.unshift(saved);
    renderNotes();
    // 追加直後は先頭カードにフォーカス
    const first = document.querySelector('.fs-note .fs-note-body');
    if (first) first.focus();
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
    renderAll();
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

  function openTaskModal(t) {
    editingId = t ? t.id : null;
    document.getElementById('fs-modal-title').textContent = t ? 'タスクを編集' : '新しいタスク';
    document.getElementById('fs-f-title').value    = t ? t.title : '';
    document.getElementById('fs-f-detail').value   = t ? t.detail : '';
    document.getElementById('fs-f-due').value      = t && t.due_at ? t.due_at : '';
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
    renderAll();
  }

  async function deleteTask() {
    if (editingId == null) return;
    if (!confirm('このタスクを削除しますか？')) return;
    await post('/fusen/api/task/delete/', { id: editingId });
    tasks = tasks.filter(x => x.id !== editingId);
    closeModal();
    renderAll();
  }

  // リマインドのクイック指定
  function pad(n) { return String(n).padStart(2, '0'); }
  function toLocalInput(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  document.getElementById('fs-remind-quick').addEventListener('click', ev => {
    const b = ev.target.closest('button');
    if (!b) return;
    const remindInput = document.getElementById('fs-f-remind');
    if (b.dataset.min) {
      const d = new Date(Date.now() + parseInt(b.dataset.min, 10) * 60000);
      remindInput.value = toLocalInput(d);
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

  // ── イベント配線 ───────────────────────────
  document.getElementById('fs-add-task').addEventListener('click', () => openTaskModal(null));
  document.getElementById('fs-add-note').addEventListener('click', addNote);
  document.getElementById('fs-modal-save').addEventListener('click', saveModal);
  document.getElementById('fs-modal-cancel').addEventListener('click', closeModal);
  document.getElementById('fs-modal-close').addEventListener('click', closeModal);
  document.getElementById('fs-modal-delete').addEventListener('click', deleteTask);
  modal.addEventListener('click', ev => { if (ev.target === modal) closeModal(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !modal.hidden) closeModal(); });

  document.getElementById('fs-filters').addEventListener('click', ev => {
    const chip = ev.target.closest('.fs-chip');
    if (!chip) return;
    document.querySelectorAll('#fs-filters .fs-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    filter = chip.dataset.filter;
    renderTasks();
  });

  // ── リマインド監視 ─────────────────────────
  // 表示中でもリマインド時刻を跨ぐことがあるので、1分ごとに再取得する
  setInterval(loadState, 60000);

  // 初期ロード
  loadState();
})();
