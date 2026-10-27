// 알림: 서버 상태를 주기적으로 보고, 바뀐 점을 알림으로 쌓아 상단 종(🔔)에 보여준다
// 서버에 알림 API가 따로 없으므로 /status 의 로봇 상태가 바뀌는 순간을 잡아서 만든다.
import { api } from './api.js';
import { h, icon, toast, openSheet } from './ui.js';

const KEY = 'taesula.notifications';
const MAX = 40;

// kind: info(일반) · ok(완료) · warn(주의) · error(오류)
let list = load();
const listeners = new Set();

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* 저장 불가 환경은 무시 */ }
  listeners.forEach((fn) => fn());
}

export function unreadCount() { return list.filter((n) => !n.read).length; }

// 다른 화면에서도 알림을 남길 수 있다. 예: notify('warn', '경로 없음', 'boxA 목적지까지 길이 막혔습니다.')
// popup: true 이면 화면 아래에 토스트도 잠깐 띄운다
export function notify(kind, title, body = '', { popup = kind !== 'info' } = {}) {
  list.unshift({ id: Date.now() + Math.random(), kind, title, body, at: Date.now(), read: false });
  if (list.length > MAX) list.length = MAX;
  save();
  if (popup) toast(body ? `${title}\n${body}` : title, kind === 'ok' ? 'ok' : kind === 'info' ? '' : 'error');
}

function markAllRead() {
  if (!list.some((n) => !n.read)) return;
  list = list.map((n) => ({ ...n, read: true }));
  save();
}
function clearAll() { list = []; save(); }

// ---------- 상태 감시 ----------
// 꼭 필요한 것만 알린다: 출발(배송 시작) · 도착 · 장애물 감지 · 오류 · 서버 연결 끊김
const ITEM_MOVING = new Set(['moving', 'delivering']);

let lastRobot;          // 직전 로봇 상태 (undefined = 아직 모름)
let cargo = null;       // 지금 싣고 가는 물품 { name, where }
let zones = {};         // 목적지 id → 구역 이름
let failures = 0;
let offline = false;
let started = false;

// 지금 이동 중인 물품을 찾는다 (없으면 null)
async function findCargo() {
  try {
    const it = (await api.items()).find((i) => ITEM_MOVING.has(i.status));
    return it ? { name: it.name, where: zones[it.destination_id] || `목적지 ${it.destination_id}` } : null;
  } catch { return null; }
}

async function onRobotChange(prev, st) {
  if (st === 'moving' && prev !== 'obstacle_detected' && prev !== 'stopped') {
    // 장애물로 잠깐 멈췄다 다시 가는 것은 새 출발로 치지 않는다
    cargo = await findCargo();
    notify('info', 'SIDA 출발', cargo ? `${cargo.name}을(를) ${cargo.where}(으)로 옮기기 시작했습니다.` : '목적지로 이동을 시작했습니다.');
  } else if (st === 'idle' && (prev === 'moving' || prev === 'obstacle_detected')) {
    notify('ok', 'SIDA 도착', cargo ? `${cargo.name}을(를) ${cargo.where}에 옮겼습니다.` : '이동을 마치고 대기 중입니다.');
    cargo = null;
  } else if (st === 'obstacle_detected') {
    notify('warn', '장애물 감지', 'SIDA 앞에 장애물이 있습니다. 경로를 확인하세요.');
  } else if (st === 'error') {
    notify('error', 'SIDA 오류', '로봇에서 오류가 발생했습니다.');
  }
}

async function checkStatus() {
  try {
    const s = await api.status();
    failures = 0;
    offline = false;
    const st = (s.robot_status || {}).status;
    const prev = lastRobot;
    lastRobot = st;
    if (prev !== undefined && st !== prev) await onRobotChange(prev, st);
  } catch {
    failures += 1;
    // 잠깐 끊긴 것은 무시하고, 세 번 연속(약 9초) 실패하면 한 번만 알린다
    if (failures === 3 && !offline) {
      offline = true;
      notify('error', '서버 연결 끊김', '같은 Wi-Fi에 있는지, 서버가 켜져 있는지 확인하세요.');
    }
  }
}

async function loadZones() {
  try {
    const locs = await api.locations();
    zones = Object.fromEntries(locs.map((l) => [l.id, l.zone_name]));
  } catch { /* 없어도 동작 */ }
}

export function startWatching() {
  if (started) return;
  started = true;
  loadZones().then(checkStatus);
  setInterval(checkStatus, 3000);
  setInterval(loadZones, 60000);
}

// ---------- 상단 종 버튼 ----------
export function bellButton() {
  const dot = h('span', { class: 'bell-dot' });
  const button = h('button', { type: 'button', class: 'icon-btn bell', onClick: openPanel }, icon('bell', 22), dot);
  function refresh() {
    const n = unreadCount();
    dot.textContent = n > 9 ? '9+' : String(n);
    dot.hidden = n === 0;
    button.setAttribute('aria-label', n ? `알림 ${n}개 읽지 않음` : '알림');
  }
  refresh();
  listeners.add(refresh);
  // 화면이 바뀌어 버튼이 사라지면 감시 목록에서 뺀다
  const gc = setInterval(() => { if (!button.isConnected) { listeners.delete(refresh); clearInterval(gc); } }, 5000);
  return button;
}

const KIND_ICON = { info: 'robot', ok: 'check', warn: 'alert', error: 'alert' };

function timeAgo(t) {
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) return '방금';
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return new Date(t).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' });
}

function openPanel() {
  const body = h('div', { class: 'noti-list' });
  function render() {
    if (!list.length) {
      body.replaceChildren(h('div', { class: 'empty' }, '새 알림이 없습니다.\nSIDA가 출발하거나 배송을 마치면 여기에 표시됩니다.'));
      return;
    }
    body.replaceChildren(...list.map((n) =>
      h('div', { class: `noti ${n.kind}${n.read ? '' : ' unread'}` },
        h('div', { class: 'noti-ico' }, icon(KIND_ICON[n.kind] || 'robot', 18, 2)),
        h('div', { class: 'noti-t' },
          h('div', { class: 'noti-head' }, h('span', { class: 'noti-title' }, n.title), h('span', { class: 'noti-time' }, timeAgo(n.at))),
          n.body ? h('p', null, n.body) : null))));
  }
  render();
  const clear = h('button', { type: 'button', class: 'text-btn', onClick: () => { clearAll(); render(); clear.remove(); } }, '모두 지우기');
  openSheet({ title: '알림', body: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } }, body, list.length ? clear : null), onClose: markAllRead });
}
