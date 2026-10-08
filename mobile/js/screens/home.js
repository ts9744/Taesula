// 홈: 로봇 상태 · 빠른 이동 · 최근 물품
import { api, getServerUrl, setServerUrl } from '../api.js';
import { h, icon, btn, toast, openSheet, field, gridView, mergeLocations, itemBadge, robotStatusLabel } from '../ui.js';

export default {
  title: '홈',

  renderHeader() {
    return [
      h('div', { class: 'brand' },
        h('div', { class: 'brand-mark' }, icon('robot', 20, 2)),
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
    const robotCard = h('section', { class: 'robot-card', 'aria-label': '로봇 SIDA 상태' },
      mapBox,
      h('div', { class: 'robot-info' },
        h('div', { class: 'top' }, h('span', null, '로봇 SIDA'), conn),
        h('div', null, h('span', { class: 'k' }, '현재 위치'), pos),
        h('div', null, h('span', { class: 'k' }, '상태'), state)));

    // --- 빠른 이동
    const cta = h('a', { class: 'btn btn-primary btn-lg btn-block', href: '#/scan' }, icon('scan', 22, 2), 'QR 인식 시작');
    const quick = h('div', { class: 'quick' },
      [['register', 'plus', '물품 등록'], ['manage', 'list', '물품 관리'], ['grid', 'grid', '격자 생성']].map(([r, ic, t]) =>
        h('a', { href: `#/${r}` }, h('div', { class: 'ico' }, icon(ic, 20, 2)), t)));

    // --- 최근 물품
    const recentList = h('div', { class: 'item-rows' });
    const recent = h('section', { class: 'card', style: { gap: '6px' } },
      h('div', { class: 'card-head' }, h('h2', null, '최근 물품'),
        h('a', { href: '#/manage', style: { fontSize: '14px', fontWeight: 600, textDecoration: 'none' } }, '전체 보기')),
      recentList);

    root.append(robotCard, cta, quick, recent);

    let mapEl = mapBox;
    function setMap(robot) {
      if (!grid) {
        mapEl.replaceChildren(h('div', { style: { gridColumn: '1 / -1', fontSize: '12px', color: '#9EA2A9', lineHeight: 1.5 } },
          '격자 지도가 아직 없습니다. 격자 탭에서 만들어 주세요.'));
        return;
      }
      const next = gridView(grid, { dark: true, robot });
      next.setAttribute('aria-label', '공장 격자 지도와 로봇 위치');
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
        const r = s.robot_status || {};
        conn.className = 'conn';
        conn.textContent = '연결됨';
        const hasPos = r.current_x != null && r.current_y != null;
        pos.textContent = hasPos ? `(${r.current_x}, ${r.current_y})` : '—';
        const remaining = (s.current_path || []).length;
        state.textContent = `${r.status || '—'} · ${robotStatusLabel(r.status)}${remaining ? ` · 남은 명령 ${remaining}` : ''}`;
        setMap(hasPos ? { x: r.current_x - 1, y: r.current_y - 1 } : null);
      } catch {
        if (!alive) return;
        conn.className = 'conn off';
        conn.textContent = '연결 끊김';
        setMap(null);
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
  const save = btn('저장', { kind: 'primary', block: true, onClick: () => {
    const v = input.value.trim();
    if (v && !/^https?:\/\/[^\s/]+/i.test(v)) { toast('http:// 또는 https:// 로 시작하는 주소를 입력하세요.', 'error'); return; }
    setServerUrl(v);
    close();
    toast('서버 주소를 저장했습니다.', 'ok');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } });
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
