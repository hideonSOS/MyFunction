/* LINE予約通知 ── 登録・編集・削除・即時送信・送信先（グループ）管理 */
(function () {
  'use strict';

  const root = document.getElementById('linenotify');
  const CSRF = root.dataset.csrf;

  let items = [];
  let targets = [];
  let editingId = null;   // 編集中の通知ID（null=新規）

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  }

  function setStatus(text, cls) {
    const el = document.getElementById('ln-status');
    el.textContent = text;
    el.className = cls || '';
    if (text) setTimeout(() => { if (el.textContent === text) el.textContent = ''; }, 5000);
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // ── 送信先セレクト ────────────────────────
  function renderTargetSelect(selectedId) {
    const sel = document.getElementById('ln-target');
    sel.innerHTML = '';
    const opt0 = el('option', null, 'ブロードキャスト（友だち全員）');
    opt0.value = '';
    sel.appendChild(opt0);
    targets.forEach(t => {
      const o = el('option', null, `${t.name}（${t.kind_label}）`);
      o.value = t.id;
      sel.appendChild(o);
    });
    sel.value = selectedId != null ? String(selectedId) : '';
    if (sel.value !== String(selectedId ?? '')) sel.value = '';
  }

  // ── 予約一覧 ─────────────────────────────
  function render() {
    const box = document.getElementById('ln-list');
    box.innerHTML = '';
    if (!items.length) {
      box.appendChild(el('div', 'ln-empty', '予約はまだありません'));
      return;
    }
    items.forEach(n => {
      const row = el('div', 'ln-item' + (n.sent ? ' sent' : ''));

      const when = el('div', 'ln-when');
      when.appendChild(el('div', 'ln-when-date', n.date));
      when.appendChild(el('div', 'ln-when-time', n.time));
      row.appendChild(when);

      const body = el('div', 'ln-body');
      body.appendChild(el('div', 'ln-msg', n.message));
      const meta = el('div', 'ln-meta');
      meta.appendChild(el('span', 'ln-badge to', '→ ' + n.target_name));
      if (n.sent)       meta.appendChild(el('span', 'ln-badge ok', '送信済 ' + (n.sent_at || '')));
      else              meta.appendChild(el('span', 'ln-badge wait', '送信待ち'));
      if (n.error)      meta.appendChild(el('span', 'ln-badge err', 'エラー: ' + n.error));
      body.appendChild(meta);
      row.appendChild(body);

      const acts = el('div', 'ln-acts');
      if (!n.sent) {
        const bSend = el('button', 'ln-btn ln-mini', '今すぐ送信');
        bSend.addEventListener('click', () => sendNow(n));
        acts.appendChild(bSend);
        const bEdit = el('button', 'ln-btn ln-mini', '編集');
        bEdit.addEventListener('click', () => startEdit(n));
        acts.appendChild(bEdit);
      }
      const bDel = el('button', 'ln-btn ln-mini ln-danger', '削除');
      bDel.addEventListener('click', () => remove(n));
      acts.appendChild(bDel);
      row.appendChild(acts);

      box.appendChild(row);
    });
  }

  // ── 送信先一覧 ────────────────────────────
  function renderTargets() {
    const box = document.getElementById('ln-targets');
    box.innerHTML = '';
    if (!targets.length) {
      box.appendChild(el('div', 'ln-empty',
        '送信先はまだ登録されていません（未登録でもブロードキャスト送信は可能です）'));
      return;
    }
    targets.forEach(t => {
      const row = el('div', 'ln-target-item');
      row.appendChild(el('span', 'ln-target-kind', t.kind_label));
      row.appendChild(el('span', 'ln-target-name', t.name));
      const idSpan = el('span', 'ln-target-id', t.target_id);
      idSpan.title = t.target_id;
      row.appendChild(idSpan);

      const bRen = el('button', 'ln-btn ln-mini', '名前変更');
      bRen.addEventListener('click', async () => {
        const name = prompt('新しい表示名', t.name);
        if (!name || !name.trim()) return;
        try {
          await post('/line/api/target/save/', { id: t.id, name: name.trim() });
          await load();
        } catch (e) { setStatus(e.message, 'err'); }
      });
      row.appendChild(bRen);

      const bDel = el('button', 'ln-btn ln-mini ln-danger', '削除');
      bDel.addEventListener('click', async () => {
        if (!confirm(`送信先「${t.name}」を削除しますか？\nこの宛先の予約はブロードキャストに戻ります。`)) return;
        await post('/line/api/target/delete/', { id: t.id });
        await load();
      });
      row.appendChild(bDel);

      box.appendChild(row);
    });
  }

  async function addTarget() {
    const name = document.getElementById('ln-t-name').value.trim();
    const tid  = document.getElementById('ln-t-id').value.trim();
    if (!name || !tid) { setStatus('表示名とIDを入力してください', 'err'); return; }
    try {
      await post('/line/api/target/save/', { name, target_id: tid });
      document.getElementById('ln-t-name').value = '';
      document.getElementById('ln-t-id').value = '';
      setStatus('送信先を登録しました', 'ok');
      await load();
    } catch (e) { setStatus(e.message, 'err'); }
  }

  async function load() {
    const res = await fetch('/line/api/list/');
    const data = await res.json();
    items = data.items || [];
    targets = data.targets || [];
    renderTargetSelect(document.getElementById('ln-target').value || null);
    render();
    renderTargets();
  }

  // ── フォーム ─────────────────────────────
  function resetForm() {
    editingId = null;
    document.getElementById('ln-form-title').textContent = '新しい通知を予約';
    document.getElementById('ln-save').textContent = '予約する';
    document.getElementById('ln-cancel').hidden = true;
    document.getElementById('ln-message').value = '';
    renderTargetSelect(null);
    initDefaultDatetime();
  }

  function startEdit(n) {
    editingId = n.id;
    document.getElementById('ln-form-title').textContent = '通知を編集 (ID ' + n.id + ')';
    document.getElementById('ln-save').textContent = '更新する';
    document.getElementById('ln-cancel').hidden = false;
    document.getElementById('ln-date').value = n.date;
    document.getElementById('ln-time').value = n.time;
    document.getElementById('ln-message').value = n.message;
    renderTargetSelect(n.target);
    document.getElementById('ln-message').focus();
  }

  function initDefaultDatetime() {
    const now = new Date(Date.now() + 60 * 60000);   // 1時間後を初期値に
    const pad = v => String(v).padStart(2, '0');
    document.getElementById('ln-date').value =
      `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    document.getElementById('ln-time').value = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  }

  function selectedTarget() {
    const v = document.getElementById('ln-target').value;
    return v ? parseInt(v, 10) : null;
  }

  async function save() {
    const payload = {
      id:      editingId,
      date:    document.getElementById('ln-date').value,
      time:    document.getElementById('ln-time').value,
      message: document.getElementById('ln-message').value.trim(),
      target:  selectedTarget(),
    };
    if (!payload.date || !payload.time || !payload.message) {
      setStatus('日付・時刻・メッセージをすべて入力してください', 'err');
      return;
    }
    try {
      await post('/line/api/save/', payload);
      setStatus(editingId ? '更新しました' : '予約しました', 'ok');
      resetForm();
      await load();
    } catch (e) {
      setStatus(e.message, 'err');
    }
  }

  async function sendNow(n) {
    if (!confirm(`この通知を今すぐ「${n.target_name}」へ送信しますか？\n\n` + n.message.slice(0, 60))) return;
    try {
      await post('/line/api/sendnow/', { id: n.id });
      setStatus('送信しました', 'ok');
    } catch (e) {
      setStatus('送信失敗: ' + e.message, 'err');
    }
    await load();
  }

  async function remove(n) {
    if (!confirm('この通知を削除しますか？')) return;
    await post('/line/api/delete/', { id: n.id });
    if (editingId === n.id) resetForm();
    await load();
  }

  async function testSend() {
    const t = targets.find(x => x.id === selectedTarget());
    const name = t ? t.name : 'ブロードキャスト（友だち全員）';
    if (!confirm(`テストメッセージを「${name}」へ送信しますか？`)) return;
    try {
      const res = await post('/line/api/test/', { target: selectedTarget() });
      if (res.ok) setStatus('テスト送信しました。LINEを確認してください', 'ok');
      else setStatus('テスト失敗: ' + res.error, 'err');
    } catch (e) {
      setStatus('テスト失敗: ' + e.message, 'err');
    }
  }

  // ── 配線 ─────────────────────────────────
  document.getElementById('ln-save').addEventListener('click', save);
  document.getElementById('ln-cancel').addEventListener('click', resetForm);
  document.getElementById('ln-test').addEventListener('click', testSend);
  document.getElementById('ln-t-add').addEventListener('click', addTarget);

  // 1分ごとに一覧を更新（cron送信・Webhook自動登録の反映を拾う）
  setInterval(load, 60000);

  initDefaultDatetime();
  load();
})();
