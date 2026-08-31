/* 進捗確認ToDo ── 重要度降順リスト＋詳細モーダル（付箋と同じリッチメモ・添付） */
(function () {
  'use strict';

  const root = document.getElementById('todo');
  const CSRF = root.dataset.csrf;

  let items = [];
  let currentItem = null;   // モーダル表示中のToDo

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
    const el = document.getElementById('td-status');
    el.textContent = text;
    el.className = cls || '';
    if (text) setTimeout(() => { if (el.textContent === text) el.textContent = ''; }, 3000);
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function replaceItem(u) {
    const i = items.findIndex(x => x.id === u.id);
    if (i >= 0) items[i] = u; else items.push(u);
  }

  async function saveItem(patch) {
    try {
      const saved = await post('/todo/api/save/', patch);
      replaceItem(saved);
      setStatus('保存しました', 'ok');
      return saved;
    } catch (e) {
      setStatus(e.message, 'err');
      return null;
    }
  }

  // ── HTMLユーティリティ（付箋と共通の考え方） ──
  function bodyToHtml(body) {
    if (!body) return '';
    if (/<[a-z][\s\S]*>/i.test(body)) return body;   // すでにHTML
    const esc = body.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc.replace(/\n/g, '<br>');
  }

  function htmlToText(html) {
    if (!html) return '';
    const tmp = document.createElement('div');
    tmp.innerHTML = html.replace(/<(br|div|p|li|h2|blockquote)[^>]*>/gi, '\n');
    return (tmp.textContent || '').replace(/ /g, ' ');
  }

  function cleanHtml(html) {
    return (html || '').replace(/\sdata-bound="1"/g, '');
  }

  function editorGetHtml(ed) {
    const text = (ed.textContent || '').replace(/​/g, '').trim();
    const hasMedia = ed.querySelector('img, .fs-ckbox, li');
    if (!text && !hasMedia) return '';
    return cleanHtml(ed.innerHTML);
  }

  // ── 一覧の1行 ────────────────────────────
  function row(t) {
    const r = el('div', 'td-item' + (t.done ? ' done' : '') + ' imp-' + t.importance);

    // 完了チェック
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.className = 'td-done';
    chk.checked = t.done;
    chk.title = '完了';
    chk.addEventListener('click', ev => ev.stopPropagation());
    chk.addEventListener('change', async () => {
      await saveItem({ id: t.id, done: chk.checked });
      render();
    });
    r.appendChild(chk);

    // 重要度（★セレクト）
    const imp = document.createElement('select');
    imp.className = 'td-imp';
    for (let v = 5; v >= 1; v--) {
      const o = el('option', null, '★' + v);
      o.value = v;
      imp.appendChild(o);
    }
    imp.value = String(t.importance);
    imp.title = '重要度（5=最重要）';
    imp.addEventListener('click', ev => ev.stopPropagation());
    imp.addEventListener('change', async () => {
      await saveItem({ id: t.id, importance: parseInt(imp.value, 10) });
      render();
    });
    r.appendChild(imp);

    // タイトル＋プレビュー（クリックで詳細モーダル）
    const mid = el('div', 'td-mid');
    const titleRow = el('div', 'td-title-line');
    titleRow.appendChild(el('span', 'td-title-text', t.title));
    if (t.attachments && t.attachments.length) {
      const clip = el('span', 'td-clip', '📎' + t.attachments.length);
      clip.title = `添付 ${t.attachments.length} 件`;
      titleRow.appendChild(clip);
    }
    mid.appendChild(titleRow);
    const first = htmlToText(t.memo).split('\n').find(l => l.trim()) || '';
    if (first.trim()) mid.appendChild(el('div', 'td-preview', first.trim()));
    r.appendChild(mid);

    // 進捗（スライダー＋%）
    const prog = el('div', 'td-prog');
    const bar = document.createElement('input');
    bar.type = 'range';
    bar.min = 0; bar.max = 100; bar.step = 10;
    bar.value = t.progress;
    bar.className = 'td-range';
    const pct = el('span', 'td-pct', t.progress + '%');
    bar.addEventListener('click', ev => ev.stopPropagation());
    bar.addEventListener('input', () => {
      pct.textContent = bar.value + '%';
      r.style.setProperty('--p', bar.value);
    });
    bar.addEventListener('change', () => saveItem({ id: t.id, progress: parseInt(bar.value, 10) }));
    prog.appendChild(bar);
    prog.appendChild(pct);
    r.appendChild(prog);

    // 更新日時
    const meta = el('div', 'td-meta');
    meta.appendChild(el('span', 'td-updated', t.updated));
    r.appendChild(meta);

    r.style.setProperty('--p', t.progress);
    r.addEventListener('click', () => openModal(t));
    return r;
  }

  function render() {
    const showDone = document.getElementById('td-show-done').checked;
    const box = document.getElementById('td-list');
    box.innerHTML = '';
    const visible = items.filter(t => showDone || !t.done);
    if (!visible.length) {
      box.appendChild(el('div', 'td-empty',
        items.length ? '（未完了はありません。「完了も表示」で確認できます）'
                     : 'まだ何もありません。上のフォームから追加してください'));
      return;
    }
    visible.forEach(t => box.appendChild(row(t)));
  }

  async function load() {
    const res = await fetch('/todo/api/list/');
    const data = await res.json();
    items = data.items || [];
    render();
  }

  // ── 追加 ─────────────────────────────────
  async function addItem() {
    const titleEl = document.getElementById('td-new-title');
    const title = titleEl.value.trim();
    if (!title) { titleEl.focus(); return; }
    const importance = parseInt(document.getElementById('td-new-imp').value, 10);
    const saved = await saveItem({ title, importance });
    if (saved) {
      titleEl.value = '';
      titleEl.focus();
      await load();
    }
  }

  document.getElementById('td-add-btn').addEventListener('click', addItem);
  document.getElementById('td-new-title').addEventListener('keydown', ev => {
    if (ev.key === 'Enter') addItem();
  });
  document.getElementById('td-show-done').addEventListener('change', render);

  // ── 詳細モーダル（閲覧 / 編集） ─────────────
  const modal = document.getElementById('td-modal');
  const mbox  = document.getElementById('td-mbox');

  function setMode(mode) {
    mbox.classList.toggle('mode-view', mode === 'view');
    mbox.classList.toggle('mode-edit', mode === 'edit');
  }

  function fillView(t) {
    document.getElementById('td-m-vtitle').textContent = t.title;

    const badges = document.getElementById('td-m-vbadges');
    badges.innerHTML = '';
    const add = (cls, text) => {
      const s = el('span', 'td-badge ' + cls, text);
      badges.appendChild(s);
    };
    add('imp-' + t.importance, '重要度 ★' + t.importance);
    add('prog', '進捗 ' + t.progress + '%');
    add(t.done ? 'ok' : 'wait', t.done ? '完了' : '進行中');
    add('', '更新 ' + t.updated);

    const body = document.getElementById('td-m-vbody');
    if (t.memo) {
      body.innerHTML = bodyToHtml(t.memo);
      body.classList.remove('empty');
      // 閲覧でもチェックリストはトグル＆保存できる
      bindChecklist(body, async html => {
        const saved = await saveItem({ id: t.id, memo: html });
        if (saved) currentItem = saved;
        render();
      });
    } else {
      body.textContent = '(詳細メモなし)';
      body.classList.add('empty');
    }
    renderModalFiles();
  }

  function fillEdit(t) {
    document.getElementById('td-m-title').value = t.title;
    const ed = document.getElementById('td-m-body');
    ed.innerHTML = bodyToHtml(t.memo || '');
    bindChecklist(ed);
    document.getElementById('td-m-imp').value  = String(t.importance);
    document.getElementById('td-m-prog').value = String(t.progress);
    document.getElementById('td-m-done').value = t.done ? '1' : '0';
    renderModalFiles();
  }

  function openModal(t, edit) {
    currentItem = t;
    fillView(t);
    fillEdit(t);
    setMode(edit ? 'edit' : 'view');
    modal.hidden = false;
  }

  function closeModal() {
    modal.hidden = true;
    currentItem = null;
    render();   // モーダル中の変更（添付・チェック）を一覧に反映
  }

  async function saveModal() {
    if (!currentItem) return;
    const title = document.getElementById('td-m-title').value.trim();
    if (!title) { document.getElementById('td-m-title').focus(); return; }
    const saved = await saveItem({
      id:         currentItem.id,
      title,
      memo:       editorGetHtml(document.getElementById('td-m-body')),
      importance: parseInt(document.getElementById('td-m-imp').value, 10),
      progress:   parseInt(document.getElementById('td-m-prog').value, 10),
      done:       document.getElementById('td-m-done').value === '1',
    });
    if (saved) {
      currentItem = saved;
      fillView(saved);
      setMode('view');
      render();
    }
  }

  async function deleteModal() {
    if (!currentItem) return;
    if (!confirm('「' + currentItem.title + '」を削除しますか？（添付も消えます）')) return;
    const id = currentItem.id;
    modal.hidden = true;
    currentItem = null;
    await post('/todo/api/delete/', { id });
    items = items.filter(x => x.id !== id);
    render();
  }

  document.getElementById('td-m-edit').addEventListener('click', () => {
    if (!currentItem) return;
    fillEdit(currentItem);
    setMode('edit');
    document.getElementById('td-m-title').focus();
  });
  document.getElementById('td-m-cancel').addEventListener('click', () => {
    if (currentItem) { fillView(currentItem); setMode('view'); }
  });
  document.getElementById('td-m-save').addEventListener('click', saveModal);
  document.getElementById('td-m-close').addEventListener('click', closeModal);
  document.getElementById('td-m-close2').addEventListener('click', closeModal);
  document.getElementById('td-m-delete').addEventListener('click', deleteModal);
  modal.addEventListener('click', ev => { if (ev.target === modal) closeModal(); });
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && !modal.hidden && lightbox.hidden) closeModal();
  });

  // ── 添付ファイル（付箋と同方式） ─────────────
  function fmtSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

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
        await post('/todo/api/attach/delete/', { id: a.id });
        if (currentItem) {
          currentItem.attachments = (currentItem.attachments || []).filter(x => x.id !== a.id);
          replaceItem(currentItem);
          renderModalFiles();
        }
      });
      bar.appendChild(up); bar.appendChild(down); bar.appendChild(cap); bar.appendChild(del);
      tile.appendChild(bar);
    }

    if (a.is_image) {
      const img = document.createElement('img');
      img.className = 'fs-file-img';
      img.src = a.url; img.alt = a.name; img.loading = 'lazy';
      img.draggable = true;
      img.classList.add('fs-file-img-drag');
      img.addEventListener('click', () => openLightbox(a.url));
      tile.appendChild(img);
    } else {
      const doc = el('a', 'fs-file-doc');
      doc.href = a.url; doc.target = '_blank'; doc.rel = 'noopener';
      doc.draggable = false;
      doc.appendChild(el('span', 'fs-file-ico', '📄'));
      doc.appendChild(el('span', 'fs-file-docname', a.name));
      tile.appendChild(doc);
    }

    makeTileDraggable(tile, a);
    return tile;
  }

  function renderModalFiles() {
    const atts = (currentItem && currentItem.attachments) || [];
    const vbox = document.getElementById('td-m-vfiles');
    const ebox = document.getElementById('td-m-efiles');
    vbox.innerHTML = ''; ebox.innerHTML = '';
    atts.forEach(a => {
      vbox.appendChild(attachmentTile(a, false));
      ebox.appendChild(attachmentTile(a, true));
    });
    vbox.hidden = atts.length === 0;
    if (atts.length === 0) ebox.appendChild(el('div', 'fs-files-empty', 'まだ添付はありません'));
  }

  // 並べ替え（▲▼）
  function moveAttachment(id, dir) {
    if (!currentItem) return;
    const atts = currentItem.attachments || [];
    const i = atts.findIndex(x => x.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= atts.length) return;
    [atts[i], atts[j]] = [atts[j], atts[i]];
    replaceItem(currentItem);
    renderModalFiles();
    persistAttachOrder();
  }

  // 並べ替え（ドラッグ&ドロップ）
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
      ev.dataTransfer.dropEffect = 'move';
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
    if (!currentItem) return;
    const atts = currentItem.attachments || [];
    const from = atts.findIndex(x => x.id === dragId);
    if (from < 0) return;
    const [moved] = atts.splice(from, 1);
    let to = atts.findIndex(x => x.id === targetId);
    if (to < 0) to = atts.length;
    atts.splice(after ? to + 1 : to, 0, moved);
    replaceItem(currentItem);
    renderModalFiles();
    persistAttachOrder();
  }
  async function persistAttachOrder() {
    if (!currentItem) return;
    try {
      await post('/todo/api/attach/reorder/', {
        item_id: currentItem.id,
        ids: (currentItem.attachments || []).map(a => a.id),
      });
    } catch (e) { /* 並び順の保存失敗は次回読込で復帰 */ }
  }

  // アップロード
  async function uploadFiles(fileList) {
    if (!currentItem || !fileList || !fileList.length) return;
    for (const f of fileList) {
      const fd = new FormData();
      fd.append('item_id', currentItem.id);
      fd.append('file', f);
      try {
        const res = await fetch('/todo/api/upload/', {
          method: 'POST', headers: { 'X-CSRFToken': CSRF }, body: fd,
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || 'アップロードに失敗しました'); continue; }
        currentItem.attachments = currentItem.attachments || [];
        currentItem.attachments.push(data);
        renderModalFiles();
      } catch (e) {
        alert('アップロードに失敗しました');
      }
    }
    replaceItem(currentItem);
  }

  async function uploadFromSrc(src) {
    if (!currentItem || !src) return;
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

  document.getElementById('td-m-upload-btn').addEventListener('click', () => {
    document.getElementById('td-m-file-input').click();
  });
  document.getElementById('td-m-file-input').addEventListener('change', ev => {
    uploadFiles(ev.target.files);
    ev.target.value = '';
  });

  // 本文への画像貼り付け → 埋め込まず添付として取り込む（付箋と同じ3段構え）
  const noteEditor = document.getElementById('td-m-body');
  noteEditor.addEventListener('paste', ev => {
    const dt = ev.clipboardData;
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

    const html = dt && dt.getData && dt.getData('text/html');
    if (html && /<img\b/i.test(html)) {
      ev.preventDefault();
      const m = html.match(/<img[^>]+src\s*=\s*["']([^"']+)["']/i);
      if (m) uploadFromSrc(m[1]);
      else alert('画像を取り込めませんでした');
      return;
    }

    // Firefox 等: paste 後に挿入された <img> を検出して添付へ移す
    const before = new Set(noteEditor.querySelectorAll('img'));
    setTimeout(() => migrateEmbeddedImages(noteEditor, before), 0);
  });
  noteEditor.addEventListener('dragover', ev => { if (fileDragId != null) ev.preventDefault(); });
  noteEditor.addEventListener('drop',     ev => { if (fileDragId != null) ev.preventDefault(); });

  // ── 画像ライトボックス ───────────────────────
  const lightbox = document.getElementById('td-lightbox');
  function openLightbox(url) {
    document.getElementById('td-lb-img').src = url;
    lightbox.hidden = false;
  }
  function closeLightbox() {
    lightbox.hidden = true;
    document.getElementById('td-lb-img').src = '';
  }
  document.getElementById('td-lb-close').addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', ev => { if (ev.target === lightbox) closeLightbox(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !lightbox.hidden) closeLightbox(); });

  // ── リッチテキスト エディタ（付箋と同実装） ──
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

  const boundBoxes = new WeakSet();
  function bindChecklist(boxRoot, onToggle) {
    boxRoot.querySelectorAll('.fs-ckbox').forEach(box => {
      if (boundBoxes.has(box)) return;
      boundBoxes.add(box);
      box.addEventListener('click', async () => {
        const line = box.closest('.fs-ck');
        const done = box.textContent.trim() === '☑';
        box.textContent = done ? '☐' : '☑';
        if (line) line.classList.toggle('done', !done);
        if (onToggle) await onToggle(cleanHtml(boxRoot.innerHTML));
      });
    });
  }

  function initEditor(toolbar, editor) {
    function exec(cmd, value) {
      editor.focus();
      try { document.execCommand('styleWithCSS', false, true); } catch (e) {}
      document.execCommand(cmd, false, value);
      refreshState();
    }

    toolbar.addEventListener('mousedown', ev => {
      const btn = ev.target.closest('.fs-rte-btn');
      if (!btn || btn.dataset.pop) return;
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

    toolbar.querySelectorAll('.fs-rte-pop-wrap').forEach(wrap => {
      const kind = wrap.querySelector('[data-pop]').dataset.pop;
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

  document.addEventListener('click', ev => {
    if (!ev.target.closest('.fs-rte-pop-wrap')) {
      document.querySelectorAll('.fs-rte-pop').forEach(p => p.classList.remove('open'));
    }
  });

  initEditor(document.getElementById('td-rte-toolbar'), noteEditor);

  load();
})();
