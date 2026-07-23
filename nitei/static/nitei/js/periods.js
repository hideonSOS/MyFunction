/* 勤務表の期間定義（nitei.js / overview.js 共通）
 *
 * 会社のシステム変更にあわせ、途中で1枚あたりの日数が変わる:
 *   勤務表1〜5  : 28日固定   2026-04-15 〜 2026-09-01
 *   勤務表6     : 14日（移行期） 2026-09-02 〜 2026-09-15
 *   勤務表7〜   : 月単位      2026-09-16 〜 2026-10-15, 10-16 〜 11-15, ...
 *
 * ── 保存キーとの関係（重要） ──────────────────────────
 * WorkEntry / EventEntry のキーは日付ではなく位置:
 *     w_{sheet_index}_{section_index}_{day_index}_{row_type}
 * そのため、ここの定義を変えると既存データの指す日付がズレる。
 * 勤務表1〜5（sheet_index 0〜4）と勤務表6の前半14日は
 * 現行と完全に同じ並びになるよう組んであるので、その範囲の入力は影響を受けない。
 * 変更するときは必ず「既存 sheet_index の開始日と日数が変わっていないか」を確認すること。
 */

const NITEI_PERIODS = [
  // type 'fixed'   : length 日ぶんを count 枚
  // type 'cycle16' : 16日〜翌月15日 を count 枚
  { start: [2026, 4, 15], type: 'fixed',   length: 28, count: 5 },
  { start: [2026, 9,  2], type: 'fixed',   length: 14, count: 1 },
  { start: [2026, 9, 16], type: 'cycle16',             count: 12 },
];

/** 1セクション（＝1テーブル）の最大日数。fixed はこの単位で前後半に割る */
const NITEI_SECTION_SIZE = 14;

function _d(y, m, day) { return new Date(y, m - 1, day); }

function _addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function _daysBetween(from, to) {
  const a = new Date(from); a.setHours(0, 0, 0, 0);
  const b = new Date(to);   b.setHours(0, 0, 0, 0);
  return Math.round((b - a) / 86400000);
}

/** 開始日から length 日ぶんの Date 配列 */
function _dateRange(start, length) {
  const out = [];
  for (let i = 0; i < length; i++) out.push(_addDays(start, i));
  return out;
}

/**
 * 期間定義を展開して勤務表シートの一覧を作る。
 * 返り値: [{ index, label, start, end, days: [Date], sections: [[Date]] }]
 */
function buildNiteiSheets() {
  const sheets = [];

  NITEI_PERIODS.forEach(period => {
    let cursor = _d(period.start[0], period.start[1], period.start[2]);

    for (let n = 0; n < period.count; n++) {
      let days, sections;

      if (period.type === 'cycle16') {
        // 16日 〜 翌月15日。月によって 28〜31 日と長さが変わる
        const y = cursor.getFullYear();
        const m = cursor.getMonth();
        const endOfMonth = new Date(y, m + 1, 0).getDate();   // その月の末日
        const first  = _dateRange(cursor, endOfMonth - 15);   // 16日〜月末
        const second = _dateRange(new Date(y, m + 1, 1), 15); // 翌月1日〜15日
        days     = first.concat(second);
        sections = [first, second];
      } else {
        days = _dateRange(cursor, period.length);
        sections = [];
        for (let i = 0; i < days.length; i += NITEI_SECTION_SIZE) {
          sections.push(days.slice(i, i + NITEI_SECTION_SIZE));
        }
      }

      sheets.push({
        index:    sheets.length,
        label:    sheets.length === 0 ? '勤務表' : `勤務表${sheets.length + 1}`,
        start:    days[0],
        end:      days[days.length - 1],
        days:     days,
        sections: sections,
      });

      cursor = _addDays(days[days.length - 1], 1);
    }
  });

  return sheets;
}

const NITEI_SHEETS = buildNiteiSheets();

/** 期間ラベル（例: 9/2 〜 9/15） */
function niteiRangeLabel(sheet) {
  const f = d => `${d.getMonth() + 1}/${d.getDate()}`;
  return `${f(sheet.start)} 〜 ${f(sheet.end)}`;
}

/** Date → 'YYYY-MM-DD' */
function niteiDateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * 日付 → 保存位置（sheet_index / section_index / day_index）の逆引き表。
 *
 * WorkEntry / EventEntry は位置キーで保存されているため、勤務表の区切りと違う
 * 単位（全員一覧のカレンダー月など）で表示するにはこの変換が要る。
 */
const NITEI_DATE_INDEX = (() => {
  const map = {};
  NITEI_SHEETS.forEach(sheet => {
    sheet.sections.forEach((sec, sectionIndex) => {
      sec.forEach((d, dayIndex) => {
        map[niteiDateKey(d)] = { sheet: sheet.index, section: sectionIndex, day: dayIndex };
      });
    });
  });
  return map;
})();

/** その日の保存位置。勤務表の対象期間外なら null */
function niteiPositionForDate(date) {
  return NITEI_DATE_INDEX[niteiDateKey(date)] || null;
}

/** 勤務表がカバーしている全体の期間 */
const NITEI_RANGE = {
  start: NITEI_SHEETS[0].start,
  end:   NITEI_SHEETS[NITEI_SHEETS.length - 1].end,
};

/** 指定日を含むシート番号。範囲外なら最寄りに丸める */
function niteiSheetIndexForDate(date) {
  for (const s of NITEI_SHEETS) {
    if (_daysBetween(s.start, date) >= 0 && _daysBetween(date, s.end) >= 0) return s.index;
  }
  if (_daysBetween(date, NITEI_SHEETS[0].start) > 0) return 0;
  return NITEI_SHEETS.length - 1;
}
