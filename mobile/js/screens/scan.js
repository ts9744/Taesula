// 물품 인식: 라즈베리파이 카메라로 QR을 읽고 경로를 계산해 SIDA에 전송
import { api } from '../api.js';
import { h, icon, btn, busy, toast, kv, commandChips, gridView, mergeLocations, itemBadge } from '../ui.js';

const ROUTE_ERRORS = {
  'item not found': '등록되지 않은 QR 코드입니다. 물품 등록 탭에서 먼저 등록하세요.',
  'robot status not found': '로봇 위치 정보가 없습니다. 격자 탭에서 시작점을 저장하세요.',
  'grid map not found': '격자 지도가 없습니다. 격자 탭에서 지도를 저장하세요.',
  'start position is out of grid range': '로봇 시작 위치가 격자 밖에 있습니다.',
  'goal position is out of grid range': '목적지가 격자 밖에 있습니다.',
  'start position is obstacle': '로봇 시작 위치가 장애물 칸입니다.',
  'goal position is obstacle': '목적지가 장애물 칸입니다.',
  'path not found': '목적지까지 갈 수 있는 경로가 없습니다. 장애물 배치를 확인하세요.',
};

export default {
  title: '물품 인식',

  render(root) {
    let alive = true;
    let scanning = false;
    let pollTimer = null;
    let failures = 0;
    let lastQr = null;
    let raw = null;

    api.gridMap().then(async (gm) => {
      if (!gm || !gm.raw_grid) return;
      const locs = await api.locations().catch(() => []);
      raw = mergeLocations(gm.raw_grid, locs).grid;
    }).catch(() => {});

    // --- 카메라 영역
    const placeholder = h('div', { class: 'placeholder' }, icon('scan', 36, 1.6),
      h('span', null, '인식 시작을 누르면 라즈베리파이 카메라 영상이 여기에 나옵니다.'));
    const live = h('span', { class: 'live', hidden: true }, 'LIVE');
    const frame = h('div', { class: 'frame', hidden: true }, h('i'), h('i'), h('i'), h('i'), h('b'));
    const found = h('div', { class: 'found', hidden: true });
    const camera = h('div', { class: 'camera' }, placeholder, live, frame, found);
    let img = null;

    const startBtn = btn('인식 시작', { kind: 'primary', icon: 'play', onClick: start });
    const stopBtn = btn('중지', { icon: 'stop', onClick: () => stop('인식을 멈췄습니다.'), disabled: true });

    // --- 직접 입력 (카메라 없이 테스트할 때)
    const manualInput = h('input', { class: 'input', placeholder: 'QR 값 입력 (예: 부품 박스 01)', autocomplete: 'off', enterKeyHint: 'search' });
    const manualBtn = btn('조회', { kind: 'dark' });
    const manualForm = h('form', { class: 'row', onSubmit: (e) => {
      e.preventDefault();
      const v = manualInput.value.trim();
      if (!v) { manualInput.focus(); return; }
      busy(manualBtn, () => handleQr(v));
    } }, h('label', { class: 'sr-only', for: 'manual-qr' }, 'QR 값'), manualInput, manualBtn);
    manualInput.id = 'manual-qr';
    manualBtn.type = 'submit';
    manualBtn.style.flex = '0 0 auto';
    const manual = h('details', { class: 'manual' }, h('summary', null, 'QR 값을 직접 입력하기'), manualForm);

    // --- 결과
    const result = h('section', { class: 'card', 'aria-live': 'polite' },
      h('div', { class: 'card-head' }, h('h2', null, '인식 결과')),
      h('div', { class: 'empty' }, '아직 인식한 QR 코드가 없습니다.'));

    root.append(camera, h('div', { class: 'row' }, startBtn, stopBtn), manual, result);

    function start() {
      if (scanning) return;
      scanning = true; failures = 0; lastQr = null;
      startBtn.disabled = true; stopBtn.disabled = false;
      found.hidden = true;
      placeholder.hidden = true; live.hidden = false; frame.hidden = false;

      img = h('img', { alt: '라즈베리파이 카메라 실시간 영상', src: api.streamUrl() });
      img.addEventListener('error', () => {
        if (!scanning) return;
        live.hidden = true;
        placeholder.hidden = false;
        placeholder.lastChild.textContent = '카메라 영상을 불러오지 못했습니다. QR 인식은 계속 시도합니다.';
      });
      camera.prepend(img);
      poll();
    }

    function stop(message) {
      scanning = false;
      clearTimeout(pollTimer);
      startBtn.disabled = false; stopBtn.disabled = true;
      frame.hidden = true; live.hidden = true;
      if (img) { img.src = ''; img.remove(); img = null; } // MJPEG 연결 끊기
      placeholder.hidden = !found.hidden;
      placeholder.lastChild.textContent = '인식 시작을 누르면 라즈베리파이 카메라 영상이 여기에 나옵니다.';
      if (message && alive) toast(message);
    }

    async function poll() {
      if (!scanning || !alive) return;
      try {
        const r = await api.cameraQr();
        failures = 0;
        if (scanning && r.detected && r.qr_code && r.qr_code !== lastQr) {
          lastQr = r.qr_code;
          stop();
          found.replaceChildren(h('span', null, `QR 인식됨 · ${r.qr_code}`),
            h('span', { class: 'mono', style: { fontSize: '11px', fontWeight: 500 } }, new Date().toLocaleTimeString('ko-KR', { hour12: false })));
          found.hidden = false;
          placeholder.hidden = true;
          if (navigator.vibrate) navigator.vibrate(60);
          await handleQr(r.qr_code);
          return;
        }
      } catch (e) {
        failures += 1;
        if (failures >= 3) { stop(); toast(`QR 인식을 할 수 없습니다.\n${e.message}`, 'error'); return; }
      }
      if (scanning) pollTimer = setTimeout(poll, 1200);
    }

    async function handleQr(qr) {
      renderLoading(qr);
      try {
        const route = await api.route(qr);
        if (!alive) return;
        renderRoute(qr, route);
      } catch (e) {
        if (!alive) return;
        renderError(qr, e.message);
      }
    }

    function head(extra) {
      return h('div', { class: 'card-head' }, h('h2', null, '인식 결과'), extra || null);
    }

    function renderLoading(qr) {
      result.replaceChildren(head(h('span', { class: 'badge move' }, '경로 계산 중')),
        kv([['QR 코드', qr, true]]));
    }

    function renderError(qr, message) {
      result.replaceChildren(head(h('span', { class: 'badge error' }, '실패')),
        kv([['QR 코드', qr, true]]),
        h('p', { style: { margin: 0, fontSize: '14px', lineHeight: 1.6 } }, message),
        btn('다시 인식', { kind: 'secondary', icon: 'scan', block: true, onClick: start }));
    }

    function renderRoute(qr, route) {
      if (route.message !== 'route found') {
        renderError(qr, ROUTE_ERRORS[route.message] || route.detail || route.message || '경로를 만들지 못했습니다.');
        return;
      }
      const dest = route.destination;
      const cmds = route.command_path || [];
      const steps = Math.max((route.path || []).length - 1, 0);
      const resend = btn('경로 다시 전송', { kind: 'dark', icon: 'robot', block: true });
      resend.addEventListener('click', () => busy(resend, async () => {
        try { await api.setPath(cmds); toast('SIDA에 경로를 다시 보냈습니다.', 'ok'); }
        catch (e) { toast(e.message, 'error'); }
      }));

      const nodes = [
        head(h('span', { class: 'badge done' }, 'SIDA로 전송됨')),
        kv([
          ['물품명', route.item.name],
          ['QR 코드', route.qr_code, true],
          ['목적지', `${dest.zone_name} · (${dest.x + 1}, ${dest.y + 1})`, true],
          ['경로 길이', `${steps}칸`, true],
          ['물품 상태', itemBadge(route.item.status)],
        ]),
      ];
      if (raw) {
        const [sx, sy] = route.start;
        nodes.push(h('div', { style: { display: 'flex', gap: '14px', alignItems: 'flex-start' } },
          h('div', { style: { flex: 1 } }, gridView(raw, { path: route.path, robot: { x: sx, y: sy } })),
          h('div', { class: 'legend', style: { flexDirection: 'column', width: '76px' } },
            h('span', null, h('i', { style: { background: 'var(--accent)' } }), '로봇'),
            h('span', null, h('i', { style: { background: 'var(--path)' } }), 'A* 경로'),
            h('span', null, h('i', { style: { background: 'var(--green)' } }), '목적지'),
            h('span', null, h('i', { style: { background: 'var(--ink)' } }), '장애물'))));
      }
      nodes.push(
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
          h('span', { class: 'label-sm' }, `command_path · ${cmds.length}개 명령`), commandChips(cmds)),
        resend,
        btn('다음 물품 인식', { kind: 'secondary', icon: 'scan', block: true, onClick: start }));
      result.replaceChildren(...nodes);
    }

    return () => { alive = false; stop(); };
  },
};
