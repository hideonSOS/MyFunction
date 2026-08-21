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
  const SPAN        = 7;   // 表示日数（週・当日±3）
  const DAYS_BEFORE = 3;   // 当日より前
  const START_HOUR  = 0;   // 時間軸の開始（0:00）
  const END_HOUR    = 24;  // 時間軸の終了（24:00）
  const HOURS       = END_HOUR - START_HOUR;
  // Google カレンダー風：1時間の高さは固定し、全時間帯はスクロールで見る
  const HOUR_H = 44;                 // 1時間の高さ(px)
  const ITEM_H = 22;                 // ブロックの高さ(px)
  const GRID_H = HOURS * HOUR_H;     // グリッド全高(px)
  const SNAP_MIN = 15;               // ドロップ時刻のスナップ（分）
  const DEFAULT_SCROLL_HOUR = 7;     // 初期表示で上端に来る時刻

  // 状態
  let notes = [];
  let tasks = [];
  let dismissedReminders = new Set();
  let winStart = null;       // 表示ウィンドウの左端の日付
  let timelineScroll = null; // タイムラインの縦スクロール位置（再描画で維持）

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

  // 時刻ユーティリティ（分-of-day）
  function taskMinutes(t) {
    if (!t.due_at) return null;
    const hm = t.due_at.slice(11, 16);   // 'HH:MM'
    return parseInt(hm.slice(0, 2), 10) * 60 + parseInt(hm.slice(3), 10);
  }
  function noteMinutes(n) {
    if (!n.time) return null;
    return parseInt(n.time.slice(0, 2), 10) * 60 + parseInt(n.time.slice(3), 10);
  }
  function topForMinutes(m) {
    let top = (m - START_HOUR * 60) / 60 * HOUR_H;
    return Math.max(0, Math.min(GRID_H - ITEM_H, top));
  }

  function renderWindow() {
    const cal = document.getElementById('fs-calendar');
    cal.innerHTML = '';
    cal.className = 'fs-timeline';

    const todayKey = dateKey(localMidnight(new Date()));
    const days = [];
    for (let i = 0; i < SPAN; i++) days.push(addDays(winStart, i));

    // 期間ラベル
    const fmt = d => `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
    document.getElementById('fs-range').textContent = `${fmt(days[0])} 〜 ${fmt(days[SPAN - 1])}`;

    // バケツ分け: inbox / 各日の終日 / 各日の時間指定
    const allday = {}, timed = {}, inboxT = [], inboxN = [];
    days.forEach(d => { const k = dateKey(d); allday[k] = []; timed[k] = []; });

    tasks.forEach(t => {
      const k = taskDay(t);
      if (!k) { inboxT.push(t); return; }
      if (!(k in allday)) return;   // 表示範囲外
      if (t.all_day || taskMinutes(t) === null) allday[k].push({ kind: 'task', item: t });
      else timed[k].push({ kind: 'task', item: t, minutes: taskMinutes(t) });
    });
    notes.forEach(n => {
      const k = noteDay(n);
      if (!k) { inboxN.push(n); return; }
      if (!(k in allday)) return;
      if (noteMinutes(n) === null) allday[k].push({ kind: 'note', item: n });
      else timed[k].push({ kind: 'note', item: n, minutes: noteMinutes(n) });
    });

    renderInbox(inboxT, inboxN);

    // ── 上部固定ブロック（ヘッダー＋終日帯。スクロール時も残る） ──
    const stickyTop = el('div', 'fs-tl-stickytop');

    // ── ヘッダー行（左隅 + 各日見出し） ──
    const headRow = document.createElement('div');
    headRow.className = 'fs-tl-row fs-tl-headrow';
    headRow.appendChild(el('div', 'fs-tl-gutter-cell'));
    days.forEach(d => {
      const key = dateKey(d), dow = d.getDay();
      const cell = el('div', 'fs-tl-dayhead'
        + (key === todayKey ? ' today' : '')
        + (dow === 0 ? ' sun' : dow === 6 ? ' sat' : ''));
      const label = el('div', 'fs-tl-dayhead-label');
      label.innerHTML = `<b>${d.getMonth() + 1}/${d.getDate()}</b> <span>${DOW[dow]}</span>`;
      cell.appendChild(label);
      const add = el('div', 'fs-tl-dayadd');
      const bT = el('button', null, '＋タスク'); bT.addEventListener('click', () => openTaskModal(null, key));
      const bN = el('button', null, '＋付箋');  bN.addEventListener('click', () => addNote(key));
      add.appendChild(bT); add.appendChild(bN);
      cell.appendChild(add);
      headRow.appendChild(cell);
    });
    stickyTop.appendChild(headRow);

    // ── 終日帯 ──
    const adRow = el('div', 'fs-tl-row fs-tl-alldayrow');
    const adLabel = el('div', 'fs-tl-gutter-cell fs-tl-allday-label', '終日');
    adRow.appendChild(adLabel);
    days.forEach(d => {
      const key = dateKey(d);
      const cell = el('div', 'fs-tl-allday-cell' + (key === todayKey ? ' today' : ''));
      cell.dataset.day = key;
      allday[key].forEach(x => cell.appendChild(x.kind === 'task' ? taskCard(x.item) : noteCard(x.item)));
      setDropTarget(cell, { date: key, allDay: true });
      adRow.appendChild(cell);
    });
    stickyTop.appendChild(adRow);
    cal.appendChild(stickyTop);

    // ── 時間軸グリッド ──
    const grid = el('div', 'fs-tl-grid');

    // 左の時刻ガター（ラベルは絶対配置。高さを日カラムと揃える）
    const gutter = el('div', 'fs-tl-gutter');
    gutter.style.height = GRID_H + 'px';
    for (let h = START_HOUR; h <= END_HOUR; h++) {
      const hr = el('div', 'fs-tl-hourlabel', `${pad(h)}:00`);
      hr.style.top = ((h - START_HOUR) * HOUR_H) + 'px';
      gutter.appendChild(hr);
    }
    grid.appendChild(gutter);

    // 各日カラム
    days.forEach(d => {
      const key = dateKey(d);
      const col = el('div', 'fs-tl-daycol' + (key === todayKey ? ' today' : ''));
      col.dataset.day = key;
      col.style.height = GRID_H + 'px';
      // 時間線
      for (let h = START_HOUR; h <= END_HOUR; h++) {
        const line = el('div', 'fs-tl-hourline');
        line.style.top = ((h - START_HOUR) * HOUR_H) + 'px';
        col.appendChild(line);
      }
      // 現在時刻ライン
      if (key === todayKey) {
        const now = new Date();
        const nowMin = now.getHours() * 60 + now.getMinutes();
        if (nowMin >= START_HOUR * 60 && nowMin <= END_HOUR * 60) {
          const nl = el('div', 'fs-tl-nowline');
          nl.style.top = ((nowMin - START_HOUR * 60) / 60 * HOUR_H) + 'px';
          col.appendChild(nl);
        }
      }
      // 時間指定アイテム（レーン割り）
      layoutLanes(timed[key]);
      timed[key].forEach(x => {
        const card = x.kind === 'task' ? taskCard(x.item) : noteCard(x.item);
        card.classList.add('fs-tl-block');
        card.style.top    = x._top + 'px';
        card.style.height = ITEM_H + 'px';
        card.style.left   = `calc(${(x._lane * 100 / x._laneCount).toFixed(3)}% + 2px)`;
        card.style.width  = `calc(${(100 / x._laneCount).toFixed(3)}% - 4px)`;
        col.appendChild(card);
      });
      setDropTarget(col, { date: key, grid: true });
      grid.appendChild(col);
    });

    cal.appendChild(grid);

    // タイムラインをスクロール領域にして高さを画面に合わせる。
    // 全時間帯(0-24h)はスクロールで見られるようにし、既定は 7:00 を上端に。
    const calTop = cal.getBoundingClientRect().top;
    cal.style.maxHeight = Math.max(300, window.innerHeight - calTop - 16) + 'px';
    cal.scrollTop = (timelineScroll != null)
      ? timelineScroll
      : DEFAULT_SCROLL_HOUR * HOUR_H;
  }

  // 時間指定アイテムをレーンに割り付け（重なり回避）
  function layoutLanes(list) {
    list.sort((a, b) => a.minutes - b.minutes);
    const laneEnd = [];
    list.forEach(x => {
      const top = topForMinutes(x.minutes);
      let lane = laneEnd.findIndex(end => end <= top);
      if (lane === -1) { lane = laneEnd.length; laneEnd.push(0); }
      laneEnd[lane] = top + ITEM_H;
      x._lane = lane; x._top = top;
    });
    const laneCount = Math.max(1, laneEnd.length);
    list.forEach(x => { x._laneCount = laneCount; });
  }

  // 小さなDOM生成ヘルパー
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function renderInbox(untasked, unnoted) {
    const box = document.getElementById('fs-inbox-body');
    box.innerHTML = '';
    untasked.forEach(t => box.appendChild(taskCard(t)));
    unnoted.forEach(n => box.appendChild(noteCard(n)));
    const total = untasked.length + unnoted.length;
    document.getElementById('fs-inbox-count').textContent = total ? `(${total})` : '';
    if (total === 0) {
      const hint = el('div', 'fs-inbox-hint',
        '日付のないタスク・付箋がここに入ります（ここへドラッグで日付・時刻を外す）');
      box.appendChild(hint);
    }
    setDropTarget(document.getElementById('fs-inbox'), { date: '' });
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

  // HTML → 表示用テキスト（タグ除去。見出し抽出に使う）
  function htmlToText(html) {
    if (!html) return '';
    const tmp = document.createElement('div');
    tmp.innerHTML = html.replace(/<(br|div|p|li|h2|blockquote)[^>]*>/gi, '\n');
    return (tmp.textContent || '').replace(/ /g, ' ');
  }

  // ── 付箋カード（見出しのみ。クリックで閲覧モーダル） ──
  function noteHeading(n) {
    if (n.title && n.title.trim()) return n.title.trim();
    const first = htmlToText(n.body).split('\n').find(l => l.trim()) || '';
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

    if (n.attachments && n.attachments.length) {
      const clip = document.createElement('span');
      clip.className = 'fs-note-clip';
      clip.textContent = '📎' + n.attachments.length;
      clip.title = `添付 ${n.attachments.length} 件`;
      card.appendChild(clip);
    }

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
    // 掴んだ位置（カード上端からのオフセット）を記録し、精密に落とせるようにする
    let offsetY = 0;
    const src = ev.currentTarget;
    if (src && src.getBoundingClientRect) {
      offsetY = ev.clientY - src.getBoundingClientRect().top;
    }
    dragData = { kind, id, offsetY };
    ev.dataTransfer.effectAllowed = 'move';
    ev.dataTransfer.setData('text/plain', JSON.stringify({ kind, id }));
    document.body.classList.add('fs-dragging');
  }

  function onDragEnd() {
    dragData = null;
    document.body.classList.remove('fs-dragging');
    document.querySelectorAll('.fs-drop-over').forEach(e => e.classList.remove('fs-drop-over'));
    hideDropIndicator();
  }

  // グリッド列内の Y から「カード上端が来る時刻(分)」を掴み位置補正＋15分スナップで返す
  function gridSnappedMinutes(col, ev) {
    const rect = col.getBoundingClientRect();
    const grab = (dragData && dragData.offsetY) || 0;
    const yTop = ev.clientY - rect.top - grab;
    const min = Math.round((yTop / HOUR_H) * 60 / SNAP_MIN) * SNAP_MIN;
    return Math.max(0, Math.min(24 * 60 - SNAP_MIN, min));   // 0:00〜23:45
  }

  // ドロップ位置のガイド線（Google カレンダー風の吸着表示）
  let dropIndicator = null;
  function showDropIndicator(col, min) {
    if (!dropIndicator) {
      dropIndicator = el('div', 'fs-tl-dropline');
      dropIndicator.appendChild(el('span', 'fs-tl-dropline-label'));
    }
    dropIndicator.style.top = ((min / 60) * HOUR_H) + 'px';
    dropIndicator.firstChild.textContent = pad(Math.floor(min / 60)) + ':' + pad(min % 60);
    if (dropIndicator.parentNode !== col) col.appendChild(dropIndicator);
  }
  function hideDropIndicator() {
    if (dropIndicator && dropIndicator.parentNode) {
      dropIndicator.parentNode.removeChild(dropIndicator);
    }
  }

  // target: { date, allDay?, grid?, date:'' で未分類 }。cell はドロップ先 DOM
  function setDropTarget(cell, target) {
    cell.addEventListener('dragover', ev => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      cell.classList.add('fs-drop-over');
      if (target.grid) showDropIndicator(cell, gridSnappedMinutes(cell, ev));
    });
    cell.addEventListener('dragleave', ev => {
      if (ev.target === cell) cell.classList.remove('fs-drop-over');
      if (target.grid && !cell.contains(ev.relatedTarget)) hideDropIndicator();
    });
    cell.addEventListener('drop', async ev => {
      ev.preventDefault();
      cell.classList.remove('fs-drop-over');
      hideDropIndicator();
      let payload = dragData;
      if (!payload) {
        try { payload = JSON.parse(ev.dataTransfer.getData('text/plain')); } catch (e) { return; }
      }
      if (!payload) return;
      // グリッドへのドロップは Y 位置から時刻を算出（掴み位置補正＋15分スナップ）
      let time = null;
      if (target.grid) {
        const min = gridSnappedMinutes(cell, ev);
        time = pad(Math.floor(min / 60)) + ':' + pad(min % 60);
      }
      await moveItem(payload, target, time);
    });
  }

  async function moveItem(payload, target, time) {
    const date = target.date;
    if (payload.kind === 'task') {
      const updated = await post('/fusen/api/task/move/', {
        id: payload.id, date, time, all_day: !!target.allDay,
      });
      replaceTask(updated);
      dismissedReminders.delete(updated.id);
      render();
    } else {
      // 付箋: 未分類=date&time空 / 終日=date のみ / グリッド=date+time
      await saveNote({ id: payload.id, date, time: time || '' });
      // saveNote 内で render 済み
    }
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
      const when = t.all_day ? (t.due_at.slice(0, 10) + ' 終日') : fmtWhen(t.due_at);
      add('due' + (t.is_overdue ? ' over' : t.is_due_soon ? ' soon' : ''), '期限 ' + when);
    }
    if (t.remind_at) add('remind', '🔔 ' + fmtWhen(t.remind_at));

    const detail = document.getElementById('fs-tm-vdetail');
    if (t.detail) {
      detail.innerHTML = bodyToHtml(t.detail);
      detail.classList.remove('empty');
      // 閲覧でもチェックはトグル＆保存できる
      bindChecklist(detail, async html => { await persistTaskDetail(html); });
    } else {
      detail.textContent = '(詳細なし)';
      detail.classList.add('empty');
    }
  }

  // 閲覧時のチェックリスト・トグルで詳細だけ保存する
  async function persistTaskDetail(html) {
    if (!currentTask) return;
    const t = currentTask;
    const saved = await post('/fusen/api/task/save/', {
      id: t.id, title: t.title, detail: html,
      due_at: t.due_at || '', remind_at: t.remind_at || '',
      priority: t.priority, status: t.status, all_day: t.all_day, tone: t.tone,
    });
    replaceTask(saved);
    currentTask = saved;
    render();
  }

  // 編集フォームに値を流し込む
  function fillTaskEdit(t, presetDay) {
    document.getElementById('fs-f-title').value    = t ? t.title : '';
    const detEd = document.getElementById('fs-f-detail');
    detEd.innerHTML = bodyToHtml(t ? t.detail : '');
    bindChecklist(detEd);
    let due = t && t.due_at ? t.due_at : '';
    if (!t && presetDay) due = presetDay + 'T09:00';   // 新規で日付指定なら 09:00
    document.getElementById('fs-f-due').value      = due;
    document.getElementById('fs-f-remind').value   = t && t.remind_at ? t.remind_at : '';
    document.getElementById('fs-f-priority').value = t ? String(t.priority) : '1';
    document.getElementById('fs-f-status').value   = t ? t.status : 'todo';
    document.getElementById('fs-f-allday').checked = !!(t && t.all_day);
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
      detail:    editorGetHtml(document.getElementById('fs-f-detail')),
      due_at:    document.getElementById('fs-f-due').value,
      remind_at: document.getElementById('fs-f-remind').value,
      priority:  parseInt(document.getElementById('fs-f-priority').value, 10),
      status:    document.getElementById('fs-f-status').value,
      all_day:   document.getElementById('fs-f-allday').checked,
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

  // 保存された本文をエディタ用HTMLに。旧データ（プレーンテキスト）は改行を <br> に
  function bodyToHtml(body) {
    if (!body) return '';
    if (/<[a-z][\s\S]*>/i.test(body)) return body;   // すでにHTML
    const esc = body.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc.replace(/\n/g, '<br>');
  }

  // 閲覧モードの表示を組み立てる
  function fillNoteView(n) {
    const vt = document.getElementById('fs-nm-vtitle');
    const vb = document.getElementById('fs-nm-vbody');
    const title = (n.title || '').trim();
    vt.textContent = title || '(無題)';
    vt.classList.toggle('empty', !title);
    const body = n.body || '';
    if (body) {
      vb.innerHTML = bodyToHtml(body);
      vb.classList.remove('empty');
      // 閲覧でもチェックはトグル＆保存できる
      bindChecklist(vb, async html => {
        currentNote.body = html;
        await saveNote({ id: currentNote.id, body: html });
      });
    } else {
      vb.textContent = '(中身なし)';
      vb.classList.add('empty');
    }
    const meta = [];
    if (n.date)   meta.push('日付 ' + n.date + (n.time ? ' ' + n.time : ' 終日'));
    if (n.pinned) meta.push('📌 ピン留め');
    document.getElementById('fs-nm-vmeta').textContent = meta.join('　');
    renderNoteFiles();
  }

  // 編集フォームに値を流し込む
  function fillNoteEdit(n) {
    document.getElementById('fs-nm-title').value   = n.title || '';
    const ed = document.getElementById('fs-nm-body');
    ed.innerHTML = bodyToHtml(n.body || '');
    bindChecklist(ed);
    document.getElementById('fs-nm-date').value    = n.date || '';
    document.getElementById('fs-nm-time').value    = n.time || '';
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

  // 保存用に内部属性を除去
  function cleanHtml(html) {
    return (html || '').replace(/\sdata-bound="1"/g, '');
  }

  // エディタの内容を取り出す（実質空なら空文字）
  function editorGetHtml(ed) {
    const text = (ed.textContent || '').replace(/​/g, '').trim();
    const hasMedia = ed.querySelector('img, .fs-ckbox, li');
    if (!text && !hasMedia) return '';
    return cleanHtml(ed.innerHTML);
  }

  async function saveNoteModal() {
    if (!currentNote) return;
    const saved = await saveNote({
      id:     currentNote.id,
      title:  document.getElementById('fs-nm-title').value,
      body:   editorGetHtml(document.getElementById('fs-nm-body')),
      date:   document.getElementById('fs-nm-date').value,
      time:   document.getElementById('fs-nm-time').value,
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

  // ── 添付ファイル（画像・PDF） ─────────────────
  function fmtSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  // 1つの添付をタイル表示。editable=true で操作バー（順序・削除）付き。
  // 画像はフォーム全幅で表示し、クリックで原寸ライトボックス。
  function attachmentTile(a, editable) {
    const tile = el('div', 'fs-file' + (a.is_image ? ' is-image' : ' is-doc'));

    if (editable) {
      const bar = el('div', 'fs-file-bar');
      const up = el('button', 'fs-file-move', '▲');
      up.type = 'button'; up.title = '上へ';
      up.addEventListener('click', ev => { ev.stopPropagation(); moveAttachment(a.id, -1); });
      const down = el('button', 'fs-file-move', '▼');
      down.type = 'button'; down.title = '下へ';
      down.addEventListener('click', ev => { ev.stopPropagation(); moveAttachment(a.id, 1); });
      const cap = el('span', 'fs-file-cap', a.is_image ? a.name : `${a.name}（${fmtSize(a.size)}）`);
      cap.title = a.name;
      const del = el('button', 'fs-file-del', '×');
      del.type = 'button'; del.title = '削除';
      del.addEventListener('click', async ev => {
        ev.stopPropagation();
        if (!confirm('この添付を削除しますか？')) return;
        await post('/fusen/api/note/attach/delete/', { id: a.id });
        if (currentNote) {
          currentNote.attachments = (currentNote.attachments || []).filter(x => x.id !== a.id);
          syncNoteInList();
          renderNoteFiles();
        }
      });
      bar.appendChild(up); bar.appendChild(down); bar.appendChild(cap); bar.appendChild(del);
      tile.appendChild(bar);
    }

    if (a.is_image) {
      const img = document.createElement('img');
      img.className = 'fs-file-img';
      img.src = a.url; img.alt = a.name; img.loading = 'lazy';
      // 閲覧・編集どちらでも画像を掴んで並べ替え可（ドラッグ時は click が
      // 発火しないので「クリックで拡大」と両立する）
      img.draggable = true;
      img.classList.add('fs-file-img-drag');
      img.addEventListener('click', () => openLightbox(a.url));
      tile.appendChild(img);
    } else {
      const doc = el('a', 'fs-file-doc');
      doc.href = a.url; doc.target = '_blank'; doc.rel = 'noopener';
      doc.draggable = false;   // リンクの既定ドラッグを止め、タイルの並べ替えを優先
      doc.appendChild(el('span', 'fs-file-ico', '📄'));
      doc.appendChild(el('span', 'fs-file-docname', a.name));
      tile.appendChild(doc);
    }

    makeTileDraggable(tile, a);
    return tile;
  }

  // ── 添付の並べ替え ──────────────────────────
  // ▲▼ ボタン用（1つ上/下へ入れ替え）
  function moveAttachment(id, dir) {
    if (!currentNote) return;
    const atts = currentNote.attachments || [];
    const i = atts.findIndex(x => x.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= atts.length) return;
    [atts[i], atts[j]] = [atts[j], atts[i]];
    syncNoteInList();
    renderNoteFiles();
    persistAttachOrder();
  }

  // ドラッグ&ドロップ用
  let fileDragId = null;
  function clearDropMarks() {
    document.querySelectorAll('.fs-drop-before, .fs-drop-after')
      .forEach(e => e.classList.remove('fs-drop-before', 'fs-drop-after'));
  }
  function makeTileDraggable(tile, a) {
    tile.draggable = true;
    tile.addEventListener('dragstart', ev => {
      fileDragId = a.id;
      ev.dataTransfer.effectAllowed = 'move';
      ev.dataTransfer.setData('text/plain', String(a.id));
      tile.classList.add('fs-file-dragging');
    });
    tile.addEventListener('dragend', () => {
      fileDragId = null;
      tile.classList.remove('fs-file-dragging');
      clearDropMarks();
    });
    tile.addEventListener('dragover', ev => {
      if (fileDragId == null || fileDragId === a.id) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';   // ＋(コピー)ではなく移動カーソルにする
      // 挿入位置（上半分=前 / 下半分=後）をガイド線で示す
      const rect = tile.getBoundingClientRect();
      const after = ev.clientY > rect.top + rect.height / 2;
      tile.classList.toggle('fs-drop-after', after);
      tile.classList.toggle('fs-drop-before', !after);
    });
    tile.addEventListener('dragleave', ev => {
      if (!tile.contains(ev.relatedTarget)) {
        tile.classList.remove('fs-drop-before', 'fs-drop-after');
      }
    });
    tile.addEventListener('drop', ev => {
      if (fileDragId == null || fileDragId === a.id) return;
      ev.preventDefault();
      const rect = tile.getBoundingClientRect();
      const after = ev.clientY > rect.top + rect.height / 2;
      clearDropMarks();
      dropAttachment(fileDragId, a.id, after);
      fileDragId = null;
    });
  }

  function dropAttachment(dragId, targetId, after) {
    if (!currentNote) return;
    const atts = currentNote.attachments || [];
    const from = atts.findIndex(x => x.id === dragId);
    if (from < 0) return;
    const [moved] = atts.splice(from, 1);
    let to = atts.findIndex(x => x.id === targetId);
    if (to < 0) to = atts.length;
    atts.splice(after ? to + 1 : to, 0, moved);
    syncNoteInList();
    renderNoteFiles();
    persistAttachOrder();
  }

  async function persistAttachOrder() {
    if (!currentNote) return;
    try {
      await post('/fusen/api/note/attach/reorder/', {
        note_id: currentNote.id,
        ids: (currentNote.attachments || []).map(a => a.id),
      });
    } catch (e) { /* 並び順の保存失敗は次回読込で復帰 */ }
  }

  // 閲覧・編集それぞれの添付一覧を描画（currentNote を元に）
  function renderNoteFiles() {
    const atts = (currentNote && currentNote.attachments) || [];
    const vbox = document.getElementById('fs-nm-vfiles');
    const ebox = document.getElementById('fs-nm-efiles');
    vbox.innerHTML = ''; ebox.innerHTML = '';
    atts.forEach(a => {
      vbox.appendChild(attachmentTile(a, false));
      ebox.appendChild(attachmentTile(a, true));
    });
    vbox.hidden = atts.length === 0;
    if (atts.length === 0) ebox.appendChild(el('div', 'fs-files-empty', 'まだ添付はありません'));
  }

  // 一覧データ(notes)側の付箋にも添付を反映（カード再描画用）
  function syncNoteInList() {
    if (!currentNote) return;
    const i = notes.findIndex(x => x.id === currentNote.id);
    if (i >= 0) notes[i] = currentNote;
  }

  async function uploadFiles(fileList) {
    if (!currentNote || !fileList || !fileList.length) return;
    for (const f of fileList) {
      const fd = new FormData();
      fd.append('note_id', currentNote.id);
      fd.append('file', f);
      try {
        const res = await fetch('/fusen/api/note/upload/', {
          method: 'POST', headers: { 'X-CSRFToken': CSRF }, body: fd,
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || 'アップロードに失敗しました'); continue; }
        currentNote.attachments = currentNote.attachments || [];
        currentNote.attachments.push(data);
        renderNoteFiles();
      } catch (e) {
        alert('アップロードに失敗しました');
      }
    }
    syncNoteInList();
  }

  // 画像ライトボックス
  const lightbox = document.getElementById('fs-lightbox');
  function openLightbox(url) {
    document.getElementById('fs-lb-img').src = url;
    lightbox.hidden = false;
  }
  function closeLightbox() {
    lightbox.hidden = true;
    document.getElementById('fs-lb-img').src = '';
  }
  document.getElementById('fs-lb-close').addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', ev => { if (ev.target === lightbox) closeLightbox(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !lightbox.hidden) closeLightbox(); });

  // アップロードUI配線
  document.getElementById('fs-nm-upload-btn').addEventListener('click', () => {
    document.getElementById('fs-nm-file-input').click();
  });
  document.getElementById('fs-nm-file-input').addEventListener('change', ev => {
    uploadFiles(ev.target.files);
    ev.target.value = '';   // 同じファイルを続けて選べるように
  });
  // src（data: / blob: / http）から画像を取り込んで添付にする
  async function uploadFromSrc(src) {
    if (!currentNote || !src) return;
    try {
      const res = await fetch(src);
      const blob = await res.blob();
      if (!blob.type.startsWith('image/')) { alert('画像として取り込めませんでした'); return; }
      const ext = (blob.type.split('/')[1] || 'png').split('+')[0];
      const file = new File([blob], 'paste.' + ext, { type: blob.type });
      uploadFiles([file]);
    } catch (e) {
      alert('画像の取り込みに失敗しました（コピー元によっては取り込めないことがあります）');
    }
  }

  // エディタ内に埋め込まれた <img> を添付へ移し、本文から取り除く。
  // skip に含まれる要素（貼り付け前から在った img）は対象外にする。
  async function migrateEmbeddedImages(editor, skip) {
    const targets = [];
    editor.querySelectorAll('img').forEach(img => {
      if (!skip || !skip.has(img)) targets.push(img);
    });
    for (const img of targets) {
      const src = img.getAttribute('src');
      img.remove();
      if (src) await uploadFromSrc(src);
    }
  }

  // 本文エディタへ画像を貼り付け → 本文に埋め込まず添付として取り込む
  const noteEditor = document.getElementById('fs-nm-body');
  noteEditor.addEventListener('paste', ev => {
    const dt = ev.clipboardData;

    // 1) 画像がファイルとして来る場合（スクリーンショット等：Chrome など）
    const imgs = [];
    if (dt) {
      if (dt.files && dt.files.length) {
        for (const f of dt.files) if (f.type.startsWith('image/')) imgs.push(f);
      }
      if (!imgs.length && dt.items) {
        for (const it of dt.items) {
          if (it.kind === 'file' && it.type.startsWith('image/')) {
            const f = it.getAsFile();
            if (f) imgs.push(f);
          }
        }
      }
    }
    if (imgs.length) { ev.preventDefault(); uploadFiles(imgs); return; }

    // 2) HTML内に <img>（他アプリ/ブラウザからのコピー）が含まれる場合は
    //    本文への埋め込みを止めて、その画像を添付として取り込む
    const html = dt && dt.getData && dt.getData('text/html');
    if (html && /<img\b/i.test(html)) {
      ev.preventDefault();
      const m = html.match(/<img[^>]+src\s*=\s*["']([^"']+)["']/i);
      if (m) uploadFromSrc(m[1]);
      else alert('画像を取り込めませんでした');
      return;
    }

    // 3) フォールバック（Firefox など）：上記で捕捉できず、ブラウザが
    //    paste 後に <img> を直接挿入するケース。挿入直後に検出して添付へ移す。
    const before = new Set(noteEditor.querySelectorAll('img'));
    setTimeout(() => migrateEmbeddedImages(noteEditor, before), 0);
  });

  // 添付の並べ替え中に画像を本文へ落としても埋め込まない（誤ドロップ防止）
  noteEditor.addEventListener('dragover', ev => { if (fileDragId != null) ev.preventDefault(); });
  noteEditor.addEventListener('drop',     ev => { if (fileDragId != null) ev.preventDefault(); });

  // ── リッチテキスト エディタ（付箋・タスク共通） ──
  const FORE_COLORS = [
    ['標準', '#b0c8e0'], ['白', '#ffffff'], ['シアン', '#00f5ff'], ['緑', '#00ff88'],
    ['黄', '#ffe600'], ['橙', '#ff9900'], ['桃', '#ff006e'], ['赤', '#ff5555'],
    ['紫', '#b98bff'], ['空', '#7fd0ff'],
  ];
  const HL_COLORS = [
    ['黄', 'rgba(255,230,0,0.28)'], ['緑', 'rgba(0,255,136,0.25)'],
    ['青', 'rgba(0,180,255,0.30)'], ['桃', 'rgba(255,0,110,0.25)'],
    ['紫', 'rgba(185,139,255,0.30)'],
  ];

  // チェックボックスのトグル。onToggle(html) があれば保存に使う（閲覧時）
  // 属性で印を付けると保存HTMLに残るので WeakSet で管理する
  const boundBoxes = new WeakSet();
  function bindChecklist(root, onToggle) {
    root.querySelectorAll('.fs-ckbox').forEach(box => {
      if (boundBoxes.has(box)) return;
      boundBoxes.add(box);
      box.addEventListener('click', async () => {
        const line = box.closest('.fs-ck');
        const done = box.textContent.trim() === '☑';
        box.textContent = done ? '☐' : '☑';
        if (line) line.classList.toggle('done', !done);
        if (onToggle) await onToggle(cleanHtml(root.innerHTML));
      });
    });
  }

  // 1つのエディタ（ツールバー＋contenteditable）を初期化する
  function initEditor(toolbar, editor) {
    function exec(cmd, value) {
      editor.focus();
      try { document.execCommand('styleWithCSS', false, true); } catch (e) {}
      document.execCommand(cmd, false, value);
      refreshState();
    }

    toolbar.addEventListener('mousedown', ev => {
      const btn = ev.target.closest('.fs-rte-btn');
      if (!btn || btn.dataset.pop) return;   // ポップは click で扱う
      ev.preventDefault();
      if (btn.dataset.cmd) {
        exec(btn.dataset.cmd);
        if (btn.dataset.clearblock) exec('formatBlock', 'div');
      } else if (btn.dataset.block) {
        const cur = document.queryCommandValue('formatBlock');
        exec('formatBlock', (cur || '').toLowerCase() === btn.dataset.block ? 'div' : btn.dataset.block);
      } else if (btn.dataset.checklist) {
        editor.focus();
        document.execCommand('insertHTML', false,
          '<div class="fs-ck"><span class="fs-ckbox" contenteditable="false">☐</span>&nbsp;</div>');
        bindChecklist(editor);
      }
    });

    // このツールバー内の色ポップオーバーを組み立て
    toolbar.querySelectorAll('.fs-rte-pop-wrap').forEach(wrap => {
      const kind = wrap.querySelector('[data-pop]').dataset.pop;   // 'fore' | 'hl'
      const pop  = wrap.querySelector('.fs-rte-pop');
      const list = kind === 'fore' ? FORE_COLORS : HL_COLORS;
      const apply = c => kind === 'fore'
        ? exec('foreColor', c || '#b0c8e0')
        : exec('hiliteColor', c || 'transparent');
      list.forEach(([label, color]) => {
        const sw = el('button', 'fs-rte-swatch'); sw.type = 'button';
        sw.style.background = color; sw.title = label;
        sw.addEventListener('mousedown', ev => { ev.preventDefault(); apply(color); pop.classList.remove('open'); });
        pop.appendChild(sw);
      });
      const none = el('button', 'fs-rte-swatch none', 'なし'); none.type = 'button';
      none.addEventListener('mousedown', ev => { ev.preventDefault(); apply(null); pop.classList.remove('open'); });
      pop.appendChild(none);
    });

    toolbar.addEventListener('click', ev => {
      const btn = ev.target.closest('.fs-rte-btn[data-pop]');
      if (!btn) return;
      ev.preventDefault();
      const pop = btn.closest('.fs-rte-pop-wrap').querySelector('.fs-rte-pop');
      const wasOpen = pop.classList.contains('open');
      document.querySelectorAll('.fs-rte-pop').forEach(p => p.classList.remove('open'));
      if (!wasOpen) pop.classList.add('open');
    });

    function refreshState() {
      toolbar.querySelectorAll('.fs-rte-btn[data-cmd]').forEach(btn => {
        let on = false;
        try { on = document.queryCommandState(btn.dataset.cmd); } catch (e) {}
        btn.classList.toggle('active', on);
      });
    }
    editor.addEventListener('keyup', refreshState);
    editor.addEventListener('mouseup', refreshState);
  }

  // ポップオーバーは外側クリックで閉じる（全エディタ共通）
  document.addEventListener('click', ev => {
    if (!ev.target.closest('.fs-rte-pop-wrap')) {
      document.querySelectorAll('.fs-rte-pop').forEach(p => p.classList.remove('open'));
    }
  });

  initEditor(document.getElementById('fs-rte-toolbar'),      document.getElementById('fs-nm-body'));
  initEditor(document.getElementById('fs-rte-toolbar-task'), document.getElementById('fs-f-detail'));

  // ── 週ナビゲーション ───────────────────────
  function recenterToday() {
    winStart = addDays(localMidnight(new Date()), -DAYS_BEFORE);
  }

  document.getElementById('fs-prev').addEventListener('click', () => { winStart = addDays(winStart, -SPAN); renderWindow(); });
  document.getElementById('fs-next').addEventListener('click', () => { winStart = addDays(winStart, SPAN); renderWindow(); });
  document.getElementById('fs-today').addEventListener('click', () => { recenterToday(); renderWindow(); });

  // ── イベント配線 ───────────────────────────
  document.getElementById('fs-add-task').addEventListener('click', () => openTaskModal(null, null));
  document.getElementById('fs-add-note').addEventListener('click', () => addNote(dateKey(localMidnight(new Date()))));
  document.getElementById('fs-modal-save').addEventListener('click', saveModal);
  document.getElementById('fs-modal-close').addEventListener('click', closeModal);
  document.getElementById('fs-modal-delete').addEventListener('click', deleteTask);
  modal.addEventListener('click', ev => { if (ev.target === modal) closeModal(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !modal.hidden) closeModal(); });

  // タイムラインの縦スクロール位置を保持（再描画で維持するため）
  document.getElementById('fs-calendar').addEventListener('scroll', ev => {
    timelineScroll = ev.target.scrollTop;
  });

  // 画面サイズ変更で表示高さを再計算
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderWindow, 150);
  });

  // 1分ごとに再取得（リマインド時刻の跨ぎに対応）
  setInterval(loadState, 60000);

  // 初期化
  recenterToday();
  loadState();
})();
