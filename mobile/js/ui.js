// 화면 공통 UI 도우미

const SVG_NS = 'http://www.w3.org/2000/svg';

const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9v11h14V9"/>',
  scan: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
  plus: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 8v8M8 12h8"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
  grid: '<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 9.33h16M4 14.67h16M9.33 4v16M14.67 4v16"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  share: '<path d="M12 15V4M8 8l4-4 4 4"/><path d="M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7"/>',
  play: '<path d="M8 5v14l11-7z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  robot: '<rect x="5" y="8" width="14" height="10" rx="2"/><path d="M12 4v4M9 13h.01M15 13h.01"/><path d="M3 12v3M21 12v3"/>',
  trash: '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"/><path d="M9 7V4h6v3"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  db: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.66 3.13 3 7 3s7-1.34 7-3V6"/><path d="M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  spinner: '<path d="M21 12a9 9 0 1 1-6.22-8.56"/>',
};

export function icon(name, size = 20, strokeWidth = 1.9) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', strokeWidth);
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = ICONS[name] || '';
  if (name === 'spinner') svg.classList.add('spin');
  return svg;
}

// ---------- SIDA 캐릭터 (디자인 캔버스의 돔 카트 로봇) ----------
// 몸통·얼굴은 이동 중과 대기 모습에서 공유한다
const SIDA_BODY =
  '<rect x="36" y="80" width="64" height="36" rx="12" fill="#FFFFFF" stroke="#22292E" stroke-width="3"/>' +
  '<path d="M30 84A38 38 0 0 1 106 84Z" fill="#FFFFFF" stroke="#22292E" stroke-width="3"/>' +
  '<rect x="42" y="56" width="52" height="24" rx="12" fill="#D7F0EF" stroke="#22292E" stroke-width="2.5"/>' +
  '<circle cx="57" cy="68" r="6" fill="#22292E"/><circle cx="79" cy="68" r="6" fill="#22292E"/>' +
  '<circle cx="59" cy="65.5" r="2" fill="#FFFFFF"/><circle cx="81" cy="65.5" r="2" fill="#FFFFFF"/>' +
  '<path d="M68 42V34" stroke="#22292E" stroke-width="3"/>' +
  '<circle cx="68" cy="30" r="4.5" fill="LAMP" stroke="#22292E" stroke-width="2.5"/>' +
  '<rect x="56" y="92" width="24" height="8" rx="4" fill="#7FB9BC"/>';

// 상태별 머리 위 표시등 색
const SIDA_LAMP = { moving: '#7FD4D6', idle: '#7FD4D6', stopped: '#F2C14E', obstacle_detected: '#F08A7A', error: '#F08A7A' };

// state: 'moving'이면 카트에 탄 모습, 그 밖에는 카트에서 내린 모습
export function sida(state, size = 200) {
  const moving = state === 'moving';
  const lamp = SIDA_LAMP[state] || '#A7B4B8';
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', moving ? '카트를 타고 이동 중인 SIDA' : 'SIDA');
  const body = SIDA_BODY.replace('LAMP', lamp);
  if (moving) {
    svg.setAttribute('viewBox', '0 18 160 140');
    svg.setAttribute('width', size);
    svg.setAttribute('height', Math.round(size * 140 / 160));
    svg.innerHTML =
      '<ellipse cx="80" cy="152" rx="54" ry="5" fill="#22393C"/>' +
      '<path d="M2 104H13M4 116H15M2 128H11" stroke="#7FB8DE" stroke-width="3.5"/>' +
      '<g class="bob">' +
      '<circle cx="44" cy="140" r="10" fill="#3A474B"/><circle cx="116" cy="140" r="10" fill="#3A474B"/>' +
      '<circle cx="44" cy="140" r="3.5" fill="#A7B4B8"/><circle cx="116" cy="140" r="3.5" fill="#A7B4B8"/>' +
      '<rect x="22" y="112" width="116" height="26" rx="12" fill="#BFE3E1" stroke="#22292E" stroke-width="3"/>' +
      '<path d="M34 125H126" stroke="#7FB9BC" stroke-width="3"/>' +
      '<rect x="104" y="92" width="26" height="22" rx="3" fill="#E6D6B8" stroke="#22292E" stroke-width="2.5"/>' +
      '<path d="M117 92V114" stroke="#D2BC96" stroke-width="4"/>' + body + '</g>';
  } else {
    svg.setAttribute('viewBox', '10 14 140 124');
    svg.setAttribute('width', Math.round(size * 0.82));
    svg.setAttribute('height', Math.round(size * 0.82 * 124 / 140));
    svg.innerHTML = '<ellipse cx="80" cy="129" rx="40" ry="5" fill="#22393C"/><g transform="translate(12 8)">' + body + '</g>';
  }
  return svg;
}

// 앱 상단 로고용 SIDA 얼굴
export function sidaFace(size = 30) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('viewBox', '0 0 120 120');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML =
    '<path d="M60 44V36" stroke="#22292E" stroke-width="5" stroke-linecap="round"/>' +
    '<circle cx="60" cy="30" r="7" fill="#7FD4D6" stroke="#22292E" stroke-width="4"/>' +
    '<rect x="28" y="88" width="64" height="24" rx="9" fill="#FFFFFF" stroke="#22292E" stroke-width="5"/>' +
    '<path d="M14 92A46 46 0 0 1 106 92Z" fill="#FFFFFF" stroke="#22292E" stroke-width="5" stroke-linejoin="round"/>' +
    '<rect x="30" y="60" width="60" height="28" rx="14" fill="#D7F0EF" stroke="#22292E" stroke-width="4"/>' +
    '<circle cx="49" cy="74" r="7" fill="#22292E"/><circle cx="71" cy="74" r="7" fill="#22292E"/>' +
    '<circle cx="51.5" cy="71.5" r="2.4" fill="#FFFFFF"/><circle cx="73.5" cy="71.5" r="2.4" fill="#FFFFFF"/>';
  return svg;
}

// 작은 DOM 생성기: h('div', { class: 'card', onClick }, child1, 'text', ...)
export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k in el && k !== 'list' && k !== 'form') el[k] = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children.flat()) {
    if (c === undefined || c === null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function btn(label, { kind = 'secondary', icon: ic, block, lg, onClick, type = 'button', disabled } = {}) {
  const cls = ['btn', `btn-${kind}`, block && 'btn-block', lg && 'btn-lg'].filter(Boolean).join(' ');
  return h('button', { type, class: cls, onClick, disabled }, ic ? icon(ic, 18) : null, label);
}

// 버튼을 누르는 동안 비활성화하고 스피너를 보여 준다
export async function busy(button, task) {
  const original = [...button.childNodes];
  button.disabled = true;
  button.replaceChildren(icon('spinner', 18), original.filter((n) => n.nodeType === 3).map((n) => n.textContent).join(''));
  try { return await task(); }
  finally { button.disabled = false; button.replaceChildren(...original); }
}

// ---------- 상태 표시 ----------
const ITEM_STATUS = {
  waiting: ['대기', ''],
  moving: ['이동 중', 'move'],
  delivering: ['이동 중', 'move'],
  done: ['완료', 'done'],
  completed: ['완료', 'done'],
  arrived: ['완료', 'done'],
};
export function itemBadge(status) {
  const [label, cls] = ITEM_STATUS[status] || [status || '알 수 없음', ''];
  return h('span', { class: `badge ${cls}` }, label);
}

const ROBOT_STATUS = {
  idle: ['대기', ''],
  moving: ['이동 중', 'move'],
  stopped: ['정지', 'warn'],
  obstacle_detected: ['장애물 감지', 'warn'],
  error: ['오류', 'error'],
  not_initialized: ['초기화 안 됨', 'warn'],
};
export function robotStatusLabel(status) {
  return (ROBOT_STATUS[status] || [status || '—'])[0];
}
export function robotBadge(status) {
  const [label, cls] = ROBOT_STATUS[status] || [status || '—', ''];
  return h('span', { class: `badge ${cls}` }, label);
}

export function commandChips(commands) {
  return h('div', { class: 'chips' }, (commands || []).map((c) =>
    h('span', { class: `chip ${c === 'left' || c === 'right' ? 'turn' : c === 'stop' ? 'stop' : ''}` }, c)));
}

export function kv(pairs) {
  return h('dl', { class: 'kv' }, pairs.map(([k, v, mono]) =>
    h('div', null, h('dt', null, k), h('dd', { class: mono ? 'mono' : '' }, v))));
}

// ---------- 격자 그리기 ----------
// raw: 서버 raw_grid (0 이동 가능, 1 장애물, 2 시작점, 3 목적지), 인덱스는 [row][col]
// path: [[x, y], ...] (0부터, x=col), robot: {x, y} (0부터)
export function gridView(raw, { path = [], robot = null, dark = false, labels = null } = {}) {
  const rows = raw.length;
  const cols = rows ? raw[0].length : 0;
  const onPath = new Set(path.slice(1, -1).map(([x, y]) => `${y},${x}`));
  const el = h('div', { class: `grid-map${dark ? ' dark' : ''}`, role: 'img', 'aria-label': `${cols}×${rows} 격자 지도` });
  el.style.setProperty('--cols', cols);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = raw[r][c];
      const cls = ['cell', v ? `v${v}` : '', !v && onPath.has(`${r},${c}`) ? 'path' : '',
        robot && robot.x === c && robot.y === r ? 'robot' : ''].filter(Boolean).join(' ');
      el.append(h('div', { class: cls }, labels ? labels[`${r},${c}`] || '' : ''));
    }
  }
  return el;
}

// 서버 격자와 목적지 목록(1부터 시작하는 좌표)을 합쳐 화면용 격자를 만든다
export function mergeLocations(raw, locations) {
  const grid = raw.map((row) => row.slice());
  const labels = {};
  for (const loc of locations || []) {
    const r = loc.y - 1, c = loc.x - 1;
    if (grid[r] && c >= 0 && c < grid[r].length) {
      if (grid[r][c] !== 1 && grid[r][c] !== 2) grid[r][c] = 3;
      labels[`${r},${c}`] = loc.zone_name;
    }
  }
  return { grid, labels };
}

// ---------- 토스트 ----------
export function toast(message, kind = '') {
  const wrap = document.getElementById('toasts');
  const t = h('div', { class: `toast ${kind}` }, message);
  wrap.append(t);
  setTimeout(() => t.remove(), kind === 'error' ? 5000 : 3000);
}

// ---------- 바텀 시트 ----------
export function openSheet({ title, sub, body, label, onClose }) {
  const prevFocus = document.activeElement;
  const scrim = h('div', { class: 'scrim' });
  const sheet = h('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true', 'aria-label': label || title },
    h('div', { class: 'grab' }),
    h('div', { class: 'card-head' }, h('h2', null, title), sub ? h('span', { class: 'sub' }, sub) : null),
    body);
  const close = () => {
    if (!sheet.isConnected) return;
    scrim.remove(); sheet.remove();
    document.removeEventListener('keydown', onKey);
    if (onClose) onClose();
    if (prevFocus && prevFocus.focus) prevFocus.focus();
  };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  scrim.addEventListener('click', close);
  document.addEventListener('keydown', onKey);
  document.body.append(scrim, sheet);
  const first = sheet.querySelector('input, select, button');
  if (first) setTimeout(() => first.focus(), 50);
  return close;
}

// ---------- 예/아니오 확인 창 ----------
// 사용: if (await confirmDialog({ title: '정말 삭제하시겠습니까?' })) { ... }
export function confirmDialog({ title, message, yes = '예', no = '아니오', danger = true }) {
  return new Promise((resolve) => {
    const prevFocus = document.activeElement;
    const scrim = h('div', { class: 'scrim', style: { zIndex: 22 } }); // 수정 시트 위에도 뜨도록
    const noBtn = btn(no, { kind: 'secondary' });
    const yesBtn = btn(yes, { kind: danger ? 'danger-fill' : 'primary' });
    const box = h('div', { class: 'dialog', role: 'alertdialog', 'aria-modal': 'true', 'aria-label': title },
      h('h2', null, title),
      message ? h('p', null, message) : null,
      h('div', { class: 'row' }, noBtn, yesBtn));
    const done = (answer) => {
      scrim.remove(); box.remove();
      document.removeEventListener('keydown', onKey);
      if (prevFocus && prevFocus.focus) prevFocus.focus();
      resolve(answer);
    };
    const onKey = (e) => { if (e.key === 'Escape') done(false); };
    noBtn.addEventListener('click', () => done(false));
    yesBtn.addEventListener('click', () => done(true));
    scrim.addEventListener('click', () => done(false));
    document.addEventListener('keydown', onKey);
    document.body.append(scrim, box);
    setTimeout(() => noBtn.focus(), 30); // 실수로 Enter를 눌러도 삭제되지 않게 '아니오'에 초점
  });
}

export function field(labelText, control) {
  if (!control.id) control.id = `f-${Math.random().toString(36).slice(2, 8)}`;
  return h('div', { class: 'field' }, h('label', { for: control.id }, labelText), control);
}

export function locationSelect(locations, selectedId) {
  const sel = h('select', { class: 'select' });
  if (!locations.length) sel.append(h('option', { value: '' }, '등록된 목적지가 없습니다'));
  for (const loc of locations) {
    const opt = h('option', { value: loc.id }, `${loc.zone_name} · (${loc.x}, ${loc.y})`);
    if (String(loc.id) === String(selectedId)) opt.selected = true;
    sel.append(opt);
  }
  return sel;
}
