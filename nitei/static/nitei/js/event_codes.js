// 勤務表の「開催」行の区分（公開FM・公休など）。勤務表・全員一覧・印刷ページ共通。
// テンプレート側で定義済み: let EVENT_CODES = [{id, name, color, kind, order}, ...]（並び順）
//   kind: work=勤務 / holiday=休み（公休数に数える）/ rest=休み（公休数に数えない）
// 区分は「区分」パネルで編集でき、入力済みのデータは区分名の文字列で保存されている。
// 一覧に無い名前（削除された区分の過去データ）は、色なし・勤務扱いで表示する

// 文字色。キーはサーバー側の EVENT_CODE_COLORS と一致させる。印刷（白い紙）用は濃いめ
const CODE_PALETTE = {
  white:  { screen: '#ffffff', print: '#000000', label: '白' },
  orange: { screen: '#ff9900', print: '#b35900', label: '橙' },
  red:    { screen: '#ff3b3b', print: '#d00000', label: '赤' },
  yellow: { screen: '#ffe066', print: '#8a6d00', label: '黄' },
  cyan:   { screen: '#00e5ff', print: '#00707a', label: '水色' },
  green:  { screen: '#39ff14', print: '#1d7a1d', label: '緑' },
  pink:   { screen: '#ff6ec7', print: '#b0307a', label: '桃' },
  purple: { screen: '#b36bff', print: '#6a2fb3', label: '紫' },
};

const CODE_KIND_LABELS = {
  work:    '勤務',
  holiday: '休み（公休数に数える）',
  rest:    '休み（数えない）',
};

function codeInfo(name) {
  return EVENT_CODES.find(c => c.name === name) || null;
}

/** 区分名の文字色。media は 'screen'（画面）か 'print'（印刷）。一覧に無い区分は '' */
function codeColor(name, media) {
  const c = codeInfo(name);
  if (!c) return '';
  return (CODE_PALETTE[c.color] || CODE_PALETTE.white)[media || 'screen'];
}

/** 公休数に数える区分か */
function isHolidayCode(name) {
  const c = codeInfo(name);
  return !!c && c.kind === 'holiday';
}

/** 休みの区分か（全員一覧・印刷で灰色にする。公休数に数えるかは問わない） */
function isRestCode(name) {
  const c = codeInfo(name);
  return !!c && c.kind !== 'work';
}

/** セルのクリックで切り替わる順序（先頭の '' は空欄） */
function eventCodeOrder() {
  return [''].concat(EVENT_CODES.map(c => c.name));
}
