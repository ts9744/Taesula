// 격자 생성: 공장 지도 편집 (장애물 · 시작점 · 목적지) 후 서버 DB에 저장
import { api } from '../api.js';
import { h, icon, btn, busy, toast, openSheet, field } from '../ui.js';

const MODES = [
  { id: 'free', label: '이동 가능', swatch: '#FFFFFF' },
  { id: 'obstacle', label: '장애물', swatch: 'var(--ink)' },
  { id: 'start', label: '시작점', swatch: 'var(--blue)' },
  { id: 'location', label: '목적지 등록', swatch: 'var(--green)' },
];
const VALUE_NAME = ['이동 가능', '장애물', '시작점', '목적지'];
const MAX_SIZE = 40;

export default {
  title: '격자 생성',

  render(root, ctx) {
    let alive = true;
    let rows = 10, cols = 10;
    let grid = empty(rows, cols);
    let start = null;          // [row, col]
    let labels = {};           // "r,c" -> zone_name
    let mode = 'obstacle';
    let dirty = false;
    let updatedAt = null;

    ctx.setHeaderAction(h('button', { type: 'button', class: 'text-btn', onClick: () => {
      if (!confirm('격자를 모두 비울까요? 서버에 저장하기 전까지는 반영되지 않습니다.')) return;
      grid = empty(rows, cols); start = null; labels = {}; dirty = true; draw();
    } }, '초기화'));

    // --- 크기
    const rowsIn = h('input', { class: 'input input-num', type: 'number', min: 1, max: MAX_SIZE, value: rows, inputMode: 'numeric', id: 'g-rows' });
    const colsIn = h('input', { class: 'input input-num', type: 'number', min: 1, max: MAX_SIZE, value: cols, inputMode: 'numeric', id: 'g-cols' });
    const makeBtn = btn('생성', { kind: 'dark', onClick: () => {
      const r = parseInt(rowsIn.value, 10), c = parseInt(colsIn.value, 10);
      if (!(r >= 1 && c >= 1 && r <= MAX_SIZE && c <= MAX_SIZE)) { toast(`행과 열은 1~${MAX_SIZE} 사이의 정수로 입력하세요.`, 'error'); return; }
      if (dirty && !confirm('새 격자를 만들면 지금 편집한 내용이 사라집니다. 계속할까요?')) return;
      rows = r; cols = c; grid = empty(rows, cols); start = null; labels = {}; dirty = true; draw();
    } });
    const tools = h('div', { class: 'grid-tools' },
      h('div', null, h('label', { for: 'g-rows' }, 'Rows'), rowsIn),
      h('div', null, h('label', { for: 'g-cols' }, 'Cols'), colsIn),
      h('div', { class: 'spacer' }), makeBtn);

    // --- 모드
    const modeBtns = MODES.map((m) => {
      const b = h('button', { type: 'button', class: 'mode', 'aria-pressed': String(m.id === mode), onClick: () => setMode(m.id) },
        h('i', { style: { background: m.swatch } }), m.label);
      b.dataset.mode = m.id;
      return b;
    });
    const modes = h('div', { class: 'modes', role: 'group', 'aria-label': '편집 모드' }, modeBtns);

    // --- 격자
    const gridBox = h('div', { class: 'grid-map edit' });
    const wrap = h('div', { class: 'grid-wrap', style: { overflowX: 'auto' } }, gridBox);
    // 장애물·이동 가능 모드: 누른 채로 끌어서 여러 칸을 한 번에 칠한다.
    // 처음 누른 칸이 장애물이면 끄는 동안 지우고, 아니면 끄는 동안 장애물로 칠한다.
    let paint = null; // { value, visited:Set }
    const cellAt = (x, y) => {
      const el = document.elementFromPoint(x, y);
      const cell = el && el.closest ? el.closest('.cell') : null;
      return cell && gridBox.contains(cell) ? cell : null;
    };
    gridBox.addEventListener('pointerdown', (e) => {
      if (mode !== 'obstacle' && mode !== 'free') return;
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      const cell = e.target.closest('.cell');
      if (!cell) return;
      e.preventDefault();
      const r = Number(cell.dataset.r), c = Number(cell.dataset.c);
      if (grid[r][c] === 3) { toast('목적지로 등록된 칸은 바꿀 수 없습니다. (목적지는 서버 목록에서 관리됩니다)', 'error'); return; }
      const value = mode === 'free' ? 0 : (grid[r][c] === 1 ? 0 : 1);
      paint = { value, visited: new Set(), last: [r, c] };
      paintCell(r, c);
    });
    gridBox.addEventListener('pointermove', (e) => {
      if (!paint) return;
      const cell = cellAt(e.clientX, e.clientY);
      if (!cell) return;
      const r = Number(cell.dataset.r), c = Number(cell.dataset.c);
      // 빠르게 끌어서 중간 칸을 건너뛰어도 빠짐없이 칠하도록 이전 칸부터 직선으로 채운다
      const [r0, c0] = paint.last;
      const steps = Math.max(Math.abs(r - r0), Math.abs(c - c0));
      for (let i = 1; i <= steps; i++) {
        paintCell(Math.round(r0 + ((r - r0) * i) / steps), Math.round(c0 + ((c - c0) * i) / steps));
      }
      paint.last = [r, c];
    });
    const endPaint = () => {
      if (!paint) return;
      paint = null;
      drawStatus();
    };
    window.addEventListener('pointerup', endPaint);
    window.addEventListener('pointercancel', endPaint);

    // 클릭: 시작점·목적지 모드, 그리고 키보드(Enter/Space)로 칸을 누른 경우
    gridBox.addEventListener('click', (e) => {
      const cell = e.target.closest('.cell');
      if (!cell) return;
      const isKeyboard = e.detail === 0;
      if ((mode === 'obstacle' || mode === 'free') && !isKeyboard) return; // 마우스·터치는 pointerdown에서 처리됨
      onCell(Number(cell.dataset.r), Number(cell.dataset.c));
    });

    const modeText = h('strong');
    const modeHint = h('span');
    const locCount = h('span');
    const hint = h('div', { class: 'hint' }, h('span', null, '모드: ', modeText, modeHint), locCount);
    const updated = h('div', { class: 'label-sm', style: { fontWeight: 500, textAlign: 'center' } });

    const saveBtn = btn('DB 저장', { kind: 'primary', icon: 'db' });
    saveBtn.addEventListener('click', () => busy(saveBtn, save));
    const loadBtn = btn('불러오기', { icon: 'refresh' });
    loadBtn.addEventListener('click', () => {
      if (dirty && !confirm('저장하지 않은 편집 내용이 사라집니다. 서버에서 다시 불러올까요?')) return;
      busy(loadBtn, () => load(true));
    });

    root.append(tools, modes, wrap, hint, h('div', { class: 'row' }, saveBtn, loadBtn), updated);
    setMode(mode);
    draw();
    load(false);

    function setMode(m) {
      mode = m;
      modeBtns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === m)));
      modeText.textContent = MODES.find((x) => x.id === m).label;
      modeHint.textContent = {
        obstacle: ' · 끌어서 여러 칸 · 다시 탭하면 지워집니다',
        free: ' · 끌어서 여러 칸을 지웁니다',
        start: ' · 다시 탭하면 해제됩니다',
        location: ' · 칸을 탭하세요',
      }[m];
      // 칠하는 모드에서는 격자 위 드래그가 화면 스크롤이 되지 않도록 막는다
      gridBox.style.touchAction = (m === 'obstacle' || m === 'free') ? 'none' : '';
    }

    function makeCell(r, c) {
      const cell = h('button', { type: 'button' }, h('span', { style: { overflow: 'hidden', textOverflow: 'clip', whiteSpace: 'nowrap', maxWidth: '100%' } }));
      cell.dataset.r = r; cell.dataset.c = c;
      styleCell(cell, r, c);
      return cell;
    }

    function styleCell(cell, r, c) {
      const v = grid[r][c];
      const label = v === 2 ? 'S' : v === 3 ? (labels[`${r},${c}`] || '') : '';
      cell.className = `cell${v ? ` v${v}` : ''}`;
      cell.setAttribute('aria-label', `(${c + 1}, ${r + 1}) ${VALUE_NAME[v] || ''}${label && v === 3 ? ` ${label}` : ''}`);
      cell.firstChild.textContent = label;
    }

    // 드래그 중에는 격자 전체를 다시 그리지 않고 해당 칸만 바꾼다
    function paintCell(r, c) {
      const key = `${r},${c}`;
      if (paint.visited.has(key)) return;
      paint.visited.add(key);
      const v = grid[r][c];
      if (v === 3 || v === paint.value) return;
      if (start && start[0] === r && start[1] === c) start = null;
      grid[r][c] = paint.value;
      dirty = true;
      const cell = gridBox.children[r * cols + c];
      if (cell) styleCell(cell, r, c);
    }

    function draw() {
      gridBox.style.setProperty('--cols', cols);
      gridBox.style.minWidth = `${cols * 28 + (cols - 1) * 3}px`;
      const cells = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) cells.push(makeCell(r, c));
      }
      gridBox.replaceChildren(...cells);
      drawStatus();
    }

    function drawStatus() {
      const n = Object.keys(labels).length;
      locCount.textContent = `목적지 ${n}곳`;
      rowsIn.value = rows; colsIn.value = cols;
      updated.textContent = dirty ? '저장하지 않은 변경 사항이 있습니다.' : (updatedAt ? `마지막 저장 · ${updatedAt}` : '');
    }

    function onCell(r, c) {
      const v = grid[r][c];
      if (mode === 'location') { registerLocation(r, c); return; }
      if (v === 3) { toast('목적지로 등록된 칸은 바꿀 수 없습니다. (목적지는 서버 목록에서 관리됩니다)', 'error'); return; }
      if (mode === 'obstacle') {
        // 장애물 모드: 빈 칸은 장애물로, 이미 장애물인 칸은 다시 누르면 지워진다
        if (start && start[0] === r && start[1] === c) start = null;
        grid[r][c] = v === 1 ? 0 : 1;
      } else if (mode === 'free') {
        if (start && start[0] === r && start[1] === c) start = null;
        grid[r][c] = 0;
      } else if (mode === 'start') {
        if (start && start[0] === r && start[1] === c) {
          // 이미 시작점인 칸을 다시 누르면 해제
          grid[r][c] = 0;
          start = null;
        } else {
          if (v === 1) { toast('장애물 칸에는 시작점을 둘 수 없습니다.', 'error'); return; }
          if (start) grid[start[0]][start[1]] = 0;
          start = [r, c];
          grid[r][c] = 2;
        }
      }
      dirty = true;
      draw();
    }

    function registerLocation(r, c) {
      const v = grid[r][c];
      if (v === 1) { toast('장애물 칸에는 목적지를 등록할 수 없습니다.', 'error'); return; }
      if (v === 2) { toast('시작점 칸에는 목적지를 등록할 수 없습니다.', 'error'); return; }
      if (v === 3) { toast(`이미 목적지(${labels[`${r},${c}`] || ''})로 등록된 칸입니다.`, 'error'); return; }
      const x = c + 1, y = r + 1;
      const input = h('input', { class: 'input', placeholder: '예: A-1', autocomplete: 'off', maxLength: 20 });
      const ok = btn('목적지 저장', { kind: 'primary', block: true, type: 'submit' });
      let close;
      const form = h('form', { style: { display: 'flex', flexDirection: 'column', gap: '14px' }, onSubmit: (e) => {
        e.preventDefault();
        const zone = input.value.trim();
        if (!zone) { toast('구역 이름을 입력하세요.', 'error'); return; }
        busy(ok, async () => {
          try {
            await api.createLocation(zone, x, y);
            grid[r][c] = 3; labels[`${r},${c}`] = zone;
            close(); draw();
            toast(`${zone} 목적지를 서버에 저장했습니다. 좌표 (${x}, ${y})`, 'ok');
          } catch (e) {
            toast(e.status === 500 ? '저장하지 못했습니다. 같은 이름의 구역이 이미 있는지 확인하세요.' : e.message, 'error');
          }
        });
      } }, field('구역 이름', input), ok, btn('취소', { block: true, onClick: () => close() }));
      close = openSheet({ title: '목적지 등록', sub: `좌표 (${x}, ${y})`, body: form });
    }

    async function load(showToast) {
      try {
        const [gm, locs] = await Promise.all([api.gridMap(), api.locations().catch(() => [])]);
        if (!alive) return;
        if (!gm || !gm.raw_grid) {
          if (showToast) toast('서버에 저장된 격자 지도가 없습니다. 새로 만들어 저장하세요.');
          applyLocations(locs); draw();
          return;
        }
        rows = gm.rows; cols = gm.cols;
        grid = gm.raw_grid.map((row) => row.map((v) => (v === 3 ? 0 : v))); // 목적지는 서버 목록 기준으로 다시 표시
        start = null;
        grid.forEach((row, r) => row.forEach((v, c) => { if (v === 2) start = [r, c]; }));
        applyLocations(locs);
        updatedAt = gm.updated_at || null;
        dirty = false;
        draw();
        if (showToast) toast('서버에서 격자 지도를 불러왔습니다.');
      } catch (e) {
        if (alive) toast(`격자 지도를 불러오지 못했습니다.\n${e.message}`, 'error');
      }
    }

    function applyLocations(locs) {
      labels = {};
      for (const l of locs) {
        const r = l.y - 1, c = l.x - 1;
        if (r >= 0 && r < rows && c >= 0 && c < cols && grid[r][c] !== 1 && grid[r][c] !== 2) {
          grid[r][c] = 3;
          labels[`${r},${c}`] = l.zone_name;
        }
      }
    }

    async function save() {
      if (!start) { toast('저장하기 전에 시작점 모드로 로봇 시작 위치를 고르세요.', 'error'); setMode('start'); return; }
      try {
        await api.setRobotStatus(start[1] + 1, start[0] + 1, 'idle');
        await api.saveGridMap({
          rows, cols,
          raw_grid: grid,
          pathfinding_grid: grid.map((row) => row.map((v) => (v === 1 ? 1 : 0))),
        });
        dirty = false;
        updatedAt = new Date().toLocaleString('ko-KR', { hour12: false });
        draw();
        toast('격자 지도와 로봇 시작 위치를 저장했습니다.', 'ok');
      } catch (e) {
        toast(e.message, 'error');
      }
    }

    const beforeUnload = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', beforeUnload);

    return () => {
      alive = false;
      window.removeEventListener('beforeunload', beforeUnload);
      window.removeEventListener('pointerup', endPaint);
      window.removeEventListener('pointercancel', endPaint);
      document.querySelectorAll('.scrim, .sheet').forEach((n) => n.remove());
    };
  },
};

function empty(r, c) {
  return Array.from({ length: r }, () => Array(c).fill(0));
}
