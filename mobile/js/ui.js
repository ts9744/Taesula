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
