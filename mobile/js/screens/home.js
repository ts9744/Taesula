// 홈: 로봇 상태 · 빠른 이동 · 최근 물품
import { api, getServerUrl, setServerUrl } from '../api.js';
import { h, icon, btn, busy, toast, openSheet, field, gridView, mergeLocations, itemBadge, robotStatusLabel, sida, sidaFace } from '../ui.js';

// 서버 obstacle.py 의 MAX_RETRIES 와 같은 값 (자동 재시도 횟수)
const MAX_RETRIES = 4;

export default {
  title: '홈',

  renderHeader() {
    return [
      h('div', { class: 'brand' },
        h('div', { class: 'brand-mark' }, sidaFace(30)),
        h('div', null, h('span', { class: 'brand-name' }, 'Taesula'), h('span', { class: 'brand-sub' }, '스마트 물류 로봇 관제'))),
      h('button', { type: 'button', class: 'icon-btn', 'aria-label': '서버 설정', onClick: openSettings }, icon('settings', 22)),
    ];
  },

  render(root) {
    let alive = true;
    let grid = null;       // 서버 raw_grid + 목적지 합친 것
    let labels = null;
    let locations = [];

    // --- 로봇 카드
    const mapBox = h('div', { class: 'grid-map' });
    const conn = h('span', { class: 'conn off' }, '연결 확인 중');
    const pos = h('span', { class: 'v big' }, '—');
    const state = h('span', { class: 'v' }, '—');
    const stage = h('div', { class: 'robot-stage' }, sida('idle', 190));

    // --- 길이 막혔을 때 안내 (no_path: 자동 재시도 중 / manual_required: 사람이 처리)
    const navText = h('p', { class: 'msg' });
    const resumeBtn = btn('다시 시도', { kind: 'primary', icon: 'refresh', block: true });
    resumeBtn.hidden = true;
    resumeBtn.addEventListener('click', () => busy(resumeBtn, async () => {
      try {
        const r = await api.resume();
        if (r.status === 'resumed') toast('새 경로로 다시 출발합니다.', 'ok');
        else toast('아직 갈 수 있는 길이 없습니다. 장애물과 직접 표시한 칸을 확인하세요.', 'error');
        pollStatus();
      } catch (e) { toast(e.message, 'error'); }
    }));
    const navAlert = h('div', { class: 'nav-alert', role: 'status' },
      h('div', { class: 'row' }, icon('alert', 18, 2), navText), resumeBtn);
    navAlert.hidden = true;

    function setNav(ob) {
      const nav = ob ? ob.nav_status : 'idle';
      if (nav === 'no_path') {
        navText.textContent = `길이 막혀 다른 길을 찾는 중입니다 (${ob.retry_count || 0}/${MAX_RETRIES})`;
        navAlert.classList.remove('manual');
        resumeBtn.hidden = true;
        navAlert.hidden = false;
      } else if (nav === 'manual_required') {
        navText.textContent = '경로를 찾지 못했습니다. 장애물을 치우고, 지도에 직접 표시한 칸이 있으면 해제한 뒤 다시 시도를 눌러 주세요.';
        navAlert.classList.add('manual');
        resumeBtn.hidden = false;
        navAlert.hidden = false;
      } else {
        navAlert.hidden = true;
      }
    }

    let stageState = 'idle';
    const robotCard = h('section', { class: 'robot-card', 'aria-label': '로봇 SIDA 상태' },
      h('div', { class: 'head' }, h('span', { class: 'name' }, 'SIDA', h('small', null, '물류 로봇')), conn),
      stage,
      h('div', { class: 'robot-body' },
        mapBox,
        h('div', { class: 'robot-info' },
          h('div', null, h('span', { class: 'k' }, '현재 위치'), pos),
          h('div', null, h('span', { class: 'k' }, '상태'), state))),
      navAlert);

    // 이동 중이면 카트에 탄 SIDA, 아니면 카트에서 내린 SIDA
    function setStage(status) {
      const next = status || 'offline';
      if (next === stageState) return;
      stageState = next;
      stage.replaceChildren(sida(next, 190));
    }

    // --- 빠른 이동
    const cta = h('a', { class: 'btn btn-primary btn-lg btn-block', href: '#/scan' }, icon('scan', 22, 2), 'QR 인식 시작');
    const RETURN_MSG = {
      returning: '시작점으로 복귀를 시작합니다.',
      already_home: '이미 시작점에 있습니다.',
      no_path: '복귀 경로가 막혀 있습니다. 잠시 뒤 다시 찾습니다.',
    };
    const returnBtn = btn('시작점으로 복귀', { kind: 'secondary', icon: 'home', block: true });
    returnBtn.addEventListener('click', () => busy(returnBtn, async () => {
      try {
        const r = await api.returnHome();
        const ok = r.status === 'returning' || r.status === 'already_home';
        toast(RETURN_MSG[r.status] || r.detail || r.message || '복귀하지 못했습니다.', ok ? 'ok' : 'error');
        pollStatus();
      } catch (e) { toast(e.message, 'error'); }
    }));
    const quick = h('div', { class: 'quick' },
      [['register', 'plus', '물품 등록'], ['manage', 'list', '물품 관리'], ['grid', 'grid', '격자 생성']].map(([r, ic, t]) =>
        h('a', { href: `#/${r}` }, h('div', { class: 'ico' }, icon(ic, 20, 2)), t)));

    // --- 최근 물품
    const recentList = h('div', { class: 'item-rows' });
    const recent = h('section', { class: 'card', style: { gap: '6px' } },
      h('div', { class: 'card-head' }, h('h2', null, '최근 물품'),
        h('a', { href: '#/manage', style: { fontSize: '14px', fontWeight: 600, textDecoration: 'none' } }, '전체 보기')),
      recentList);

    root.append(robotCard, cta, returnBtn, quick, recent);

    let mapEl = mapBox;
    function setMap(robot, blocked = []) {
      if (!grid) {
        mapEl.replaceChildren(h('div', { style: { gridColumn: '1 / -1', fontSize: '12px', color: '#B9CFD0', lineHeight: 1.5 } },
          '격자 지도가 아직 없습니다. 격자 탭에서 만들어 주세요.'));
        return;
      }

      const shown = grid.map((row) => row.slice());
      for (const b of blocked) {
        const r = b.y - 1, c = b.x - 1;
        if (shown[r] && shown[r][c] === 0) shown[r][c] = 1;
      }
      const next = gridView(shown, { dark: true, robot });
      next.setAttribute('aria-label', '공장 격자 지도와 로봇 위치');
      const keys = new Set(blocked.map((b) => `${b.x},${b.y}`));
      next.style.cursor = 'pointer';
      next.addEventListener('click', async (e) => {
        const cell = e.target.closest('.cell');
        if (!cell) return;
        const idx = Array.prototype.indexOf.call(next.children, cell);
        const cols = grid[0].length;
        const r = Math.floor(idx / cols), c = idx % cols;
        const v = grid[r][c];
        if (v === 1) { toast('지도 장애물은 격자 탭에서 수정하세요.', 'error'); return; }
        if (v === 2 || v === 3) { toast('시작점과 목적지 칸에는 표시할 수 없습니다.', 'error'); return; }
        const isBlocked = keys.has(`${c + 1},${r + 1}`);
        try {
          const res = await api.manualBlock(c + 1, r + 1, !isBlocked);
          if (res.status === 'ok') toast(isBlocked ? '장애물을 해제했습니다.' : '장애물을 표시했습니다.', 'ok');
          else toast(res.reason || '표시하지 못했습니다.', 'error');
          pollStatus();
        } catch (err) { toast(err.message, 'error'); }
      });
      mapEl.replaceWith(next);
      mapEl = next;
    }

    async function loadStatic() {
      try {
        const [gm, locs, items] = await Promise.all([
          api.gridMap().catch(() => null),
          api.locations().catch(() => []),
          api.items(),
        ]);
        if (!alive) return;
        locations = locs;
        if (gm && gm.raw_grid) ({ grid, labels } = mergeLocations(gm.raw_grid, locations));
        renderRecent(items);
      } catch (e) {
        if (!alive) return;
        recentList.replaceChildren(h('div', { class: 'empty' }, e.message));
      }
    }

    function renderRecent(items) {
      const zone = Object.fromEntries(locations.map((l) => [l.id, l.zone_name]));
      const latest = [...items].sort((a, b) => b.id - a.id).slice(0, 3);
      if (!latest.length) {
        recentList.replaceChildren(h('div', { class: 'empty', style: { marginBottom: '12px' } }, '아직 등록된 물품이 없습니다.'));
        return;
      }
      recentList.replaceChildren(...latest.map((it) =>
        h('div', { class: 'item-row' },
          h('div', { class: 't' }, h('span', { class: 'n' }, it.name),
            h('span', { class: 's' }, `${it.qr_code} · ${zone[it.destination_id] || `목적지 ${it.destination_id}`}`)),
          itemBadge(it.status))));
    }

    async function pollStatus() {
      try {
        const s = await api.status();
        if (!alive) return;
        const ob = await api.obstacles().catch(() => null);
        const blocked = ob && ob.blocked ? ob.blocked : [];
        const r = s.robot_status || {};
        conn.className = 'conn';
        conn.textContent = '연결됨';
        const hasPos = r.current_x != null && r.current_y != null;
        pos.textContent = hasPos ? `(${r.current_x}, ${r.current_y})` : '—';
        // 경로 끝의 stop 은 이동이 아니므로 세지 않는다 (지금 이동 중인 묶음은 이미 경로에서 빠져 있다)
        const remaining = (s.current_path || []).filter((c) => c !== 'stop').length;
        state.textContent = `${robotStatusLabel(r.status)}${remaining ? ` · 남은 이동 ${remaining}칸` : ''}`;
        setMap(hasPos ? { x: r.current_x - 1, y: r.current_y - 1 } : null, blocked);
        setStage(r.status);
        setNav(ob);
      } catch {
        if (!alive) return;
        conn.className = 'conn off';
        conn.textContent = '연결 끊김';
        setMap(null);
        setStage('offline');
        setNav(null);
      }
    }

    loadStatic().then(pollStatus);
    const timer = setInterval(pollStatus, 3000);

    return () => { alive = false; clearInterval(timer); };
  },
};

function openSettings() {
  const input = h('input', {
    class: 'input', type: 'url', inputMode: 'url', autocomplete: 'off',
    placeholder: `비워 두면 ${location.origin}`, value: getServerUrl(),
  });
  let close;
  const save = btn('저장', {
    kind: 'primary', block: true, onClick: () => {
      const v = input.value.trim();
      if (v && !/^https?:\/\/[^\s/]+/i.test(v)) { toast('http:// 또는 https:// 로 시작하는 주소를 입력하세요.', 'error'); return; }
      setServerUrl(v);
      close();
      toast('서버 주소를 저장했습니다.', 'ok');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }
  });
  close = openSheet({
    title: '서버 설정',
    body: h('div', { style: { display: 'flex', flexDirection: 'column', gap: '14px' } },
      h('p', { style: { margin: 0, fontSize: '14px', lineHeight: 1.6, color: 'var(--muted)' } },
        '라즈베리파이 서버의 /app 주소로 앱을 열었다면 비워 두세요. 다른 곳에서 열었다면 서버 주소를 적습니다. 예: http://192.168.0.20:8000'),
      field('서버 주소', input),
      save,
      btn('취소', { block: true, onClick: () => close() })),
  });
}
