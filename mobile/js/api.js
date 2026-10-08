// Taesula 서버(FastAPI) API 클라이언트
// 앱을 서버의 /app 경로에서 열면 같은 주소로 요청하므로 따로 설정할 것이 없습니다.
// 다른 주소에서 앱을 열었다면 홈 화면의 설정에서 서버 주소를 입력합니다.

const KEY = 'taesula.serverUrl';

function readStore(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function writeStore(key, value) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch { /* 저장소를 쓸 수 없는 환경(사생활 보호 모드 등)에서는 무시 */ }
}

let serverUrl = (readStore(KEY) || '').trim().replace(/\/+$/, '');

export function getServerUrl() { return serverUrl; }
export function setServerUrl(url) {
  serverUrl = (url || '').trim().replace(/\/+$/, '');
  writeStore(KEY, serverUrl);
}

function buildUrl(path, params) {
  const base = serverUrl || window.location.origin;
  const url = new URL(base + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, path, { params, json, timeout = 8000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let res;
  try {
    res = await fetch(buildUrl(path, params), {
      method,
      headers: json ? { 'Content-Type': 'application/json' } : undefined,
      body: json ? JSON.stringify(json) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    throw new ApiError(
      e.name === 'AbortError' ? '서버 응답이 없습니다. (시간 초과)' : '서버에 연결할 수 없습니다. 같은 Wi-Fi에 있는지 확인하세요.',
      0,
    );
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try { data = await res.json(); } catch { /* 본문이 JSON이 아님 */ }

  if (!res.ok) {
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : (d ? JSON.stringify(d) : `서버 오류 (HTTP ${res.status})`);
    throw new ApiError(msg, res.status);
  }
  return data;
}

const enc = encodeURIComponent;

export const api = {
  // 로봇
  status: () => request('GET', '/status', { timeout: 4000 }),
  setRobotStatus: (current_x, current_y, status) =>
    request('PUT', '/robot/status', { params: { current_x, current_y, status } }),
  setPath: (path) => request('POST', '/path', { json: { path } }),

  // 물품
  items: () => request('GET', '/items'),
  createItem: (name, qr_code, destination_id) =>
    request('POST', '/items', { params: { name, qr_code, destination_id } }),
  updateItem: (qr_code, name, destination_id) =>
    request('PUT', `/items/${enc(qr_code)}`, { params: { name, destination_id } }),
  deleteItem: (qr_code) => request('DELETE', `/items/${enc(qr_code)}`),

  // 경로 (호출 시 서버가 command_path를 로봇 대기열에 넣음)
  route: (qr_code) => request('GET', `/route/${enc(qr_code)}`),

  // 목적지 · 격자
  locations: () => request('GET', '/locations'),
  createLocation: (zone_name, x, y) => request('POST', '/locations', { params: { zone_name, x, y } }),
  gridMap: () => request('GET', '/grid-map'),
  saveGridMap: (payload) => request('POST', '/grid-map', { json: payload }),

  // 카메라
  cameraQr: () => request('GET', '/camera/qr', { timeout: 5000 }),
  streamUrl: () => buildUrl('/camera/stream', { t: Date.now() }),
  qrImageUrl: (text) => buildUrl('/mobile-api/qr.png', { text }),
};
