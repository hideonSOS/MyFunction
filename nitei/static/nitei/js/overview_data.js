// 全員一覧の「カレンダー月」単位のデータ取得（一覧画面・印刷ページ共通）
// 前提: テンプレート側の PERSONS と periods.js（NITEI_RANGE / niteiPositionForDate）
//
// 保存データは位置キー（sheet/section/day）なので、日付から保存位置を逆引きして拾う。

// 勤務表がカバーしている範囲の月（ここより外へはナビゲートさせない）
const OV_FIRST = { y: NITEI_RANGE.start.getFullYear(), m: NITEI_RANGE.start.getMonth() };
const OV_LAST  = { y: NITEI_RANGE.end.getFullYear(),   m: NITEI_RANGE.end.getMonth()   };

/** 年月を通し番号にして比較しやすくする */
function ovSerial(y, m) { return y * 12 + m; }

function ovClampToRange(y, m) {
  const s   = ovSerial(y, m);
  const min = ovSerial(OV_FIRST.y, OV_FIRST.m);
  const max = ovSerial(OV_LAST.y,  OV_LAST.m);
  const v   = Math.max(min, Math.min(max, s));
  return { y: Math.floor(v / 12), m: v % 12 };
}

/** 指定月（m は0始まり）の日付一覧 */
function ovMonthDaysOf(y, m) {
  const last = new Date(y, m + 1, 0).getDate();
  const days = [];
  for (let i = 1; i <= last; i++) days.push(new Date(y, m, i));
  return days;
}

/** その日が開催期間なら { color: 'blue'|'green', venue } */
function ovEventInfo(date, titles) {
  const d = new Date(date); d.setHours(0, 0, 0, 0);
  for (const t of titles) {
    const from = new Date(t.date_from.replace(/\//g, '-')); from.setHours(0, 0, 0, 0);
    const to   = new Date(t.date_to.replace(/\//g, '-'));   to.setHours(0, 0, 0, 0);
    if (d >= from && d <= to) return { color: t.venue === '箕面' ? 'green' : 'blue', venue: t.venue };
  }
  return null;
}

/**
 * 指定月の全員分のデータを取得する。
 * 返り値: { days, positions, titles, data: { person: { e_{i}, w_{i}_0, w_{i}_1 } } }
 * （i は月内の日付インデックス。positions[i] が null の日は勤務表の対象期間外）
 */
async function ovFetchMonth(y, m) {
  const days      = ovMonthDaysOf(y, m);
  const positions = days.map(d => niteiPositionForDate(d));

  // この月が触れる (sheet, section) の組み合わせだけを取得する。
  // 月は勤務表の区切りをまたぐので、1〜3 組になることが多い。
  const needed = [];
  const seen   = {};
  positions.forEach(p => {
    if (!p) return;
    const id = `${p.sheet}_${p.section}`;
    if (!seen[id]) { seen[id] = true; needed.push(p); }
  });

  const results = await Promise.all(
    needed.map(p =>
      fetch(`/nitei/api/overview/?sheet_index=${p.sheet}&section_index=${p.section}`)
        .then(r => r.json())
        .then(json => ({ id: `${p.sheet}_${p.section}`, json }))
    )
  );

  const bySection = {};
  results.forEach(r => { bySection[r.id] = r.json.data; });
  const titles = results.length ? results[0].json.titles : [];

  // 日付ごとに、その日の保存位置から値を引いて日付インデックスへ詰め替える
  const data = {};
  Object.keys(PERSONS).forEach(person => {
    const pdata = {};
    positions.forEach((p, i) => {
      if (!p) return;
      const src = (bySection[`${p.sheet}_${p.section}`] || {})[person] || {};
      const ev  = src[`e_${p.day}`];
      const w0  = src[`w_${p.day}_0`];
      const w1  = src[`w_${p.day}_1`];
      if (ev !== undefined) pdata[`e_${i}`]   = ev;
      if (w0 !== undefined) pdata[`w_${i}_0`] = w0;
      if (w1 !== undefined) pdata[`w_${i}_1`] = w1;
    });
    data[person] = pdata;
  });

  return { days, positions, titles, data };
}
