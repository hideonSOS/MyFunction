// 勤務表の「区分の編集」パネル（追加・改名・色・種類・並び替え・削除）。
// 前提: event_codes.js（EVENT_CODES 等）, nitei.js（eventData / applyEventColor / SUM_UPDATERS）
(function () {
  'use strict';

  const panel = document.getElementById('code-panel');
  const list  = document.getElementById('code-list');

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  }

  function colorSelect(value) {
    const sel = el('select', 'cd-color');
    Object.keys(CODE_PALETTE).forEach(k => {
      const o = el('option', null, CODE_PALETTE[k].label);
      o.value = k;
      o.style.color = CODE_PALETTE[k].screen;
      sel.appendChild(o);
    });
    sel.value = value || 'white';
    sel.style.color = CODE_PALETTE[sel.value].screen;
    sel.title = '文字色';
    return sel;
  }

  function kindSelect(value) {
    const sel = el('select', 'cd-kind');
    Object.keys(CODE_KIND_LABELS).forEach(k => {
      const o = el('option', null, CODE_KIND_LABELS[k]);
      o.value = k;
      sel.appendChild(o);
    });
    sel.value = value || 'work';
    sel.title = '種類';
    return sel;
  }

  /** サーバー応答の区分一覧を反映し、パネル・勤務表の色・公休数を描き直す */
  function updated(data, rename) {
    EVENT_CODES = data.codes || [];
    if (rename) {
      // 改名はサーバー側で入力済みデータも置き換え済み。画面上の表示と手元のデータも合わせる
      Object.keys(eventData).forEach(k => {
        if (eventData[k] === rename.from) eventData[k] = rename.to;
      });
      document.querySelectorAll('tr.row-event td:not(.label)').forEach(td => {
        if (td.textContent === rename.from) td.textContent = rename.to;
      });
    }
    document.querySelectorAll('tr.row-event td:not(.label)').forEach(applyEventColor);
    SUM_UPDATERS.forEach(fn => fn());
    renderPanel();
  }

  async function save(body, rename) {
    try { updated(await post('/nitei/api/codes/save/', body), rename); }
    catch (e) { alert(e.message); renderPanel(); }
  }

  function renderPanel() {
    list.innerHTML = '';
    EVENT_CODES.forEach((c, i) => {
      const row = el('div', 'cd-row');

      const up = el('button', 'cd-move', '▲');
      up.type = 'button'; up.title = '上へ'; up.disabled = (i === 0);
      up.addEventListener('click', () => move(i, -1));
      const down = el('button', 'cd-move', '▼');
      down.type = 'button'; down.title = '下へ'; down.disabled = (i === EVENT_CODES.length - 1);
      down.addEventListener('click', () => move(i, 1));
      row.appendChild(up);
      row.appendChild(down);

      const name = el('input', 'cd-name');
      name.type = 'text';
      name.maxLength = 10;
      name.value = c.name;
      name.style.color = codeColor(c.name);
      name.title = '区分名（変更すると入力済みの勤務表も置き換わります）';
      name.addEventListener('change', () => {
        const v = name.value.trim();
        if (!v || v === c.name) { name.value = c.name; return; }
        if (!confirm('「' + c.name + '」を「' + v + '」に変更します。\n入力済みの勤務表（全員・全期間）の「' + c.name + '」も置き換わります。よろしいですか？')) {
          name.value = c.name;
          return;
        }
        save({ id: c.id, name: v }, { from: c.name, to: v });
      });
      row.appendChild(name);

      const color = colorSelect(c.color);
      color.addEventListener('change', () => save({ id: c.id, color: color.value }));
      row.appendChild(color);

      const kind = kindSelect(c.kind);
      kind.addEventListener('change', () => save({ id: c.id, kind: kind.value }));
      row.appendChild(kind);

      const del = el('button', 'cd-del', '削除');
      del.type = 'button';
      del.addEventListener('click', async () => {
        if (!confirm('「' + c.name + '」を区分から削除しますか？\n（入力済みの勤務表の文字は残りますが、色・公休数の集計・切り替え候補から外れます）')) return;
        try { updated(await post('/nitei/api/codes/delete/', { id: c.id })); }
        catch (e) { alert(e.message); }
      });
      row.appendChild(del);

      list.appendChild(row);
    });
    if (!EVENT_CODES.length) list.appendChild(el('div', 'cd-note', '区分がありません。下から追加してください'));
  }

  async function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= EVENT_CODES.length) return;
    const ids = EVENT_CODES.map(c => c.id);
    [ids[i], ids[j]] = [ids[j], ids[i]];
    try { updated(await post('/nitei/api/codes/reorder/', { ids })); }
    catch (e) { alert(e.message); }
  }

  // 追加フォーム
  const addRow   = document.getElementById('code-add-row');
  const newName  = el('input', 'cd-name');
  newName.type = 'text';
  newName.maxLength = 10;
  newName.placeholder = '区分名（例：出張）';
  const newColor = colorSelect('white');
  const newKind  = kindSelect('work');
  const addBtn   = el('button', 'cd-add', '＋ 追加');
  addBtn.type = 'button';
  [newName, newColor, newKind, addBtn].forEach(e => addRow.appendChild(e));
  newColor.addEventListener('change', () => { newColor.style.color = CODE_PALETTE[newColor.value].screen; });

  async function add() {
    const v = newName.value.trim();
    if (!v) { newName.focus(); return; }
    try {
      updated(await post('/nitei/api/codes/save/', { name: v, color: newColor.value, kind: newKind.value }));
      newName.value = '';
      newName.focus();
    } catch (e) { alert(e.message); }
  }
  addBtn.addEventListener('click', add);
  newName.addEventListener('keydown', e => { if (e.key === 'Enter') add(); });

  document.getElementById('code-btn').addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) renderPanel();
  });
  document.getElementById('code-close').addEventListener('click', () => { panel.hidden = true; });
})();
