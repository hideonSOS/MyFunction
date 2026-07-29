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

  // ── タスクカード（見出しのみ。クリックで編集モーダル） ──
  function taskCard(t) {
    const card = document.createElement('div');
    card.className = 'fs-task' + (t.is_done ? ' done' : '') + (t.is_overdue ? ' overdue' : '');
    card.style.setProperty('--tone-c', TONE_COLOR[t.tone] || TONE_COLOR.blue);
    card.draggable = true;
    card.addEventListener('dragstart', ev => onDragStart(ev, 'task', t.id));
    card.addEventListener('dragend', onDragEnd);

    const check = document.createElement('button');
    check.className = 'fs-check' + (t.is_done ? ' checked' : t.status === 'doing' ? ' doing' : '');
    check.title = '状態を切り替え';
    check.addEventListener('click', ev => {
      ev.stopPropagation();
      const next = { todo: 'doing', doing: 'done', done: 'todo' }[t.status] || 'todo';
      updateStatus(t, next);
    });
    card.appendChild(check);

    const title = document.createElement('div');
    title.className = 'fs-task-title';
    title.textContent = t.title;
    // 期限時刻・リマインドは見出しに影響しないよう tooltip に集約
    const tip = [t.title];
    if (t.due_at)    tip.push('期限 ' + fmtWhen(t.due_at));
    if (t.remind_at) tip.push('🔔 ' + fmtWhen(t.remind_at));
    title.title = tip.join('\n');
    if (t.remind_at && !t.is_done) card.classList.add('has-remind');
    card.appendChild(title);

    // カード全体クリックで編集モーダル（チェックボックスは stopPropagation 済み）
    card.addEventListener('click', () => openTaskModal(t));
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

  // ── 付箋カード（見出しのみ。クリックで閲覧モーダル） ──
  function noteHeading(n) {
    if (n.title && n.title.trim()) return n.title.trim();
    const first = (n.body || '').split('\n').find(l => l.trim()) || '';
    return first.trim() || '(無題)';
  }

  function noteCard(n) {
    const card = document.createElement('div');
    card.className = 'fs-note' + (n.pinned ? ' pinned' : '');
    card.style.setProperty('--note-bg', TONE_COLOR[n.tone] || TONE_COLOR.yellow);
    card.draggable = true;
    card.addEventListener('dragstart', ev => onDragStart(ev, 'note', n.id));
    card.addEventListener('dragend', onDragEnd);

    if (n.pinned) {
      const pin = document.createElement('span');
      pin.className = 'fs-note-pinmark';
      pin.textContent = '📌';
      card.appendChild(pin);
    }

    const head = document.createElement('div');
    head.className = 'fs-note-head';
    head.textContent = noteHeading(n);
    head.title = n.title || noteHeading(n);
    card.appendChild(head);

    card.addEventListener('click', () => openNoteModal(n));
    return card;
  }

  async function saveNote(patch) {
    const saved = await post('/fusen/api/note/save/', patch);
    const i = notes.findIndex(x => x.id === saved.id);
    if (i >= 0) notes[i] = saved; else notes.push(saved);
    render();
    return saved;
  }

  async function deleteNote(id) {
    await post('/fusen/api/note/delete/', { id });
    notes = notes.filter(x => x.id !== id);
    render();
  }

  // 新規付箋: 空で作成し、そのまま編集モードでモーダルを開く
  async function addNote(day) {
    const saved = await post('/fusen/api/note/save/', { title: '', body: '', tone: 'yellow', date: day || '' });
    notes.push(saved);
    render();
    openNoteModal(saved, true);   // 新規は最初から編集モード
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

  // ── タスクモーダル（閲覧 / 編集） ───────────
  const modal    = document.getElementById('fs-modal');
  const taskBox  = document.getElementById('fs-tm-box');
  let currentTask = null;    // 表示中のタスク（新規は null）
  let modalTone = 'blue';

  const STATUS_LABEL   = { todo: '未着手', doing: '進行中', done: '完了' };
  const PRIORITY_LABEL = ['低', '中', '高'];

  function setModalTone(tone) {
    modalTone = tone;
    document.querySelectorAll('#fs-f-tone .fs-tone').forEach(el => {
      el.classList.toggle('selected', el.dataset.tone === tone);
    });
  }

  function setTaskMode(mode) {
    taskBox.classList.toggle('mode-view', mode === 'view');
    taskBox.classList.toggle('mode-edit', mode === 'edit');
  }

  // 閲覧モードの表示を組み立てる
  function fillTaskView(t) {
    document.getElementById('fs-modal-title').textContent = 'タスク';
    document.getElementById('fs-tm-vtitle').textContent = t.title;

    const badges = document.getElementById('fs-tm-vbadges');
    badges.innerHTML = '';
    const add = (cls, text) => {
      const s = document.createElement('span');
      s.className = 'fs-badge ' + cls;
      s.textContent = text;
      badges.appendChild(s);
    };
    add('prio-' + t.priority, '優先度: ' + (PRIORITY_LABEL[t.priority] || '中'));
    add('', '状態: ' + (STATUS_LABEL[t.status] || '未着手'));
    if (t.due_at) {
      add('due' + (t.is_overdue ? ' over' : t.is_due_soon ? ' soon' : ''), '期限 ' + fmtWhen(t.due_at));
    }
    if (t.remind_at) add('remind', '🔔 ' + fmtWhen(t.remind_at));

    const detail = document.getElementById('fs-tm-vdetail');
    detail.textContent = t.detail || '(詳細なし)';
    detail.classList.toggle('empty', !t.detail);
  }

  // 編集フォームに値を流し込む
  function fillTaskEdit(t, presetDay) {
    document.getElementById('fs-f-title').value    = t ? t.title : '';
    document.getElementById('fs-f-detail').value   = t ? t.detail : '';
    let due = t && t.due_at ? t.due_at : '';
    if (!t && presetDay) due = presetDay + 'T09:00';   // 新規で日付指定なら 09:00
    document.getElementById('fs-f-due').value      = due;
    document.getElementById('fs-f-remind').value   = t && t.remind_at ? t.remind_at : '';
    document.getElementById('fs-f-priority').value = t ? String(t.priority) : '1';
    document.getElementById('fs-f-status').value   = t ? t.status : 'todo';
    setModalTone(t ? t.tone : 'blue');
  }

  // t あり＝閲覧モードで開く / t なし＝新規（編集モード）
  function openTaskModal(t, presetDay) {
    currentTask = t || null;
    document.getElementById('fs-modal-delete').hidden = !t;
    fillTaskEdit(t, presetDay);
    if (t) {
      fillTaskView(t);
      document.getElementById('fs-modal-title').textContent = 'タスク';
      setTaskMode('view');
    } else {
      document.getElementById('fs-modal-title').textContent = '新しいタスク';
      setTaskMode('edit');
      document.getElementById('fs-f-title').focus();
    }
    modal.hidden = false;
  }

  function enterTaskEdit() {
    if (!currentTask) return;
    fillTaskEdit(currentTask);
    document.getElementById('fs-modal-title').textContent = 'タスクを編集';
    setTaskMode('edit');
    document.getElementById('fs-f-title').focus();
  }

  function closeModal() { modal.hidden = true; currentTask = null; }

  async function saveModal() {
    const title = document.getElementById('fs-f-title').value.trim();
    if (!title) { document.getElementById('fs-f-title').focus(); return; }
    const payload = {
      id:        currentTask ? currentTask.id : null,
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
    render();
    // 保存後は閲覧モードに戻す（続けて確認できる）
    currentTask = saved;
    document.getElementById('fs-modal-delete').hidden = false;
    fillTaskView(saved);
    setTaskMode('view');
  }

  async function deleteTask() {
    if (!currentTask) return;
    if (!confirm('このタスクを削除しますか？')) return;
    const id = currentTask.id;
    closeModal();
    await post('/fusen/api/task/delete/', { id });
    tasks = tasks.filter(x => x.id !== id);
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

  document.getElementById('fs-tm-edit').addEventListener('click', enterTaskEdit);
  document.getElementById('fs-tm-close2').addEventListener('click', closeModal);
  document.getElementById('fs-modal-cancel').addEventListener('click', () => {
    // 既存タスクの編集を破棄して閲覧へ。新規なら閉じる
    if (currentTask) { fillTaskView(currentTask); setTaskMode('view'); }
    else closeModal();
  });

  // ── 付箋モーダル（閲覧 / 編集） ─────────────
  const noteModal = document.getElementById('fs-note-modal');
  const noteBox   = document.getElementById('fs-nm-box');
  let currentNote = null;         // 表示中の付箋
  let noteModalTone = 'yellow';

  function setNoteTone(tone) {
    noteModalTone = tone;
    document.querySelectorAll('#fs-nm-tone .fs-tone').forEach(el => {
      el.classList.toggle('selected', el.dataset.tone === tone);
    });
  }

  // 閲覧モードの表示を組み立てる
  function fillNoteView(n) {
    const vt = document.getElementById('fs-nm-vtitle');
    const vb = document.getElementById('fs-nm-vbody');
    const title = (n.title || '').trim();
    vt.textContent = title || '(無題)';
    vt.classList.toggle('empty', !title);
    const body = n.body || '';
    vb.textContent = body || '(中身なし)';
    vb.classList.toggle('empty', !body);
    const meta = [];
    if (n.date)   meta.push('日付 ' + n.date);
    if (n.pinned) meta.push('📌 ピン留め');
    document.getElementById('fs-nm-vmeta').textContent = meta.join('　');
  }

  // 編集フォームに値を流し込む
  function fillNoteEdit(n) {
    document.getElementById('fs-nm-title').value   = n.title || '';
    document.getElementById('fs-nm-body').value    = n.body || '';
    document.getElementById('fs-nm-date').value    = n.date || '';
    document.getElementById('fs-nm-pinned').checked = !!n.pinned;
    setNoteTone(n.tone || 'yellow');
  }

  function setNoteMode(mode) {
    noteBox.classList.toggle('mode-view', mode === 'view');
    noteBox.classList.toggle('mode-edit', mode === 'edit');
  }

  // edit=true で最初から編集モード（新規付箋）。既定は閲覧モード
  function openNoteModal(n, edit) {
    currentNote = n;
    fillNoteView(n);
    fillNoteEdit(n);
    setNoteMode(edit ? 'edit' : 'view');
    noteModal.hidden = false;
    if (edit) {
      const ti = document.getElementById('fs-nm-title');
      ti.focus();
    }
  }

  function enterEditMode() {
    if (!currentNote) return;
    fillNoteEdit(currentNote);
    setNoteMode('edit');
    document.getElementById('fs-nm-title').focus();
  }

  function closeNoteModal() { noteModal.hidden = true; currentNote = null; }

  async function saveNoteModal() {
    if (!currentNote) return;
    const saved = await saveNote({
      id:     currentNote.id,
      title:  document.getElementById('fs-nm-title').value,
      body:   document.getElementById('fs-nm-body').value,
      date:   document.getElementById('fs-nm-date').value,
      pinned: document.getElementById('fs-nm-pinned').checked,
      tone:   noteModalTone,
    });
    // 保存後は閲覧モードに戻す（続けて確認できる）
    currentNote = saved;
    fillNoteView(saved);
    setNoteMode('view');
  }

  async function deleteNoteModal() {
    if (!currentNote) return;
    if (!confirm('この付箋を削除しますか？')) return;
    const id = currentNote.id;
    closeNoteModal();
    await deleteNote(id);
  }

  document.querySelectorAll('#fs-nm-tone .fs-tone').forEach(el => {
    el.addEventListener('click', () => setNoteTone(el.dataset.tone));
  });
  document.getElementById('fs-nm-edit').addEventListener('click', enterEditMode);
  document.getElementById('fs-nm-save').addEventListener('click', saveNoteModal);
  document.getElementById('fs-nm-cancel').addEventListener('click', () => {
    // 編集を破棄して閲覧へ（新規で空のままキャンセルしたら閉じる）
    if (currentNote) { fillNoteView(currentNote); setNoteMode('view'); }
  });
  document.getElementById('fs-nm-close').addEventListener('click', closeNoteModal);
  document.getElementById('fs-nm-close2').addEventListener('click', closeNoteModal);
  document.getElementById('fs-nm-delete').addEventListener('click', deleteNoteModal);
  noteModal.addEventListener('click', ev => { if (ev.target === noteModal) closeNoteModal(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !noteModal.hidden) closeNoteModal(); });

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
