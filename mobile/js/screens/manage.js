// 물품 관리: 목록 · 검색 · 수정 · 삭제 · 여러 개 선택 삭제
import { api } from '../api.js';
import { h, icon, btn, busy, toast, openSheet, confirmDialog, field, locationSelect, itemBadge } from '../ui.js';

export default {
  title: '물품 관리',

  render(root) {
    let alive = true;
    let items = [];
    let locations = [];
    let query = '';
    let selecting = false;          // 선택 삭제 모드
    const selected = new Set();     // 선택한 물품의 qr_code
    let deleting = false;

    const search = h('input', { type: 'search', placeholder: '물품명 또는 QR 검색', 'aria-label': '물품 검색', enterKeyHint: 'search',
      onInput: (e) => { query = e.target.value.trim().toLowerCase(); renderList(); } });

    // --- 목록 위 도구 줄: [개수 · 취소]  ...  [전체 조회] [휴지통]
    const count = h('span', { class: 'label-sm', style: { fontSize: '14px' } }, '불러오는 중…');
    const cancelBtn = h('button', { type: 'button', class: 'text-btn', hidden: true, onClick: () => exitSelect() }, '취소');
    const left = h('div', { class: 'select-bar' }, count, cancelBtn);
    const reload = h('button', { type: 'button', class: 'text-btn', style: { display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }, onClick: () => load(true) },
      icon('refresh', 16), '전체 조회');
    const trashCount = h('span', { class: 'count', hidden: true });
    const trash = h('button', { type: 'button', class: 'trash-btn', 'aria-pressed': 'false', 'aria-label': '여러 물품 선택해서 삭제', onClick: onTrash },
      icon('trash', 20), trashCount);
    const list = h('div', { class: 'list' });

    root.append(
      h('div', { class: 'search' }, icon('search', 18), search),
      h('div', { class: 'card-head' }, left, h('div', { class: 'list-tools' }, reload, trash)),
      list);

    load(false);

    // ---------- 데이터 ----------
    async function load(showToast) {
      try {
        const [its, locs] = await Promise.all([api.items(), api.locations().catch(() => [])]);
        if (!alive) return;
        items = its; locations = locs;
        // 사라진 물품은 선택에서 뺀다
        const alive_qr = new Set(items.map((it) => it.qr_code));
        [...selected].forEach((qr) => { if (!alive_qr.has(qr)) selected.delete(qr); });
        renderList();
        if (showToast) toast('목록을 새로 불러왔습니다.');
      } catch (e) {
        if (!alive) return;
        count.textContent = '불러오기 실패';
        list.replaceChildren(h('div', { class: 'empty' }, e.message));
      }
    }

    function zoneName(id) {
      const l = locations.find((x) => x.id === id);
      return l ? l.zone_name : `목적지 ${id}`;
    }

    // ---------- 그리기 ----------
    function renderList() {
      const shown = items.filter((it) => !query ||
        String(it.name).toLowerCase().includes(query) || String(it.qr_code).toLowerCase().includes(query));
      list.classList.toggle('selecting', selecting);
      if (!shown.length) {
        list.replaceChildren(h('div', { class: 'empty' }, items.length ? '검색 결과가 없습니다.' : '등록된 물품이 없습니다. 등록 탭에서 추가하세요.'));
      } else {
        list.replaceChildren(...shown.map((it) => {
          const row = h('button', { type: 'button', class: 'list-item' },
            h('span', { class: 'check', 'aria-hidden': 'true' }, icon('check', 16, 3)),
            h('span', { class: 'id' }, String(it.id).padStart(2, '0')),
            h('span', { class: 't', style: { display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, minWidth: 0 } },
              h('span', { class: 'n', style: { fontSize: '15px', fontWeight: 600 } }, it.name),
              h('span', { class: 's mono', style: { fontSize: '12px', color: 'var(--muted)' } }, `${it.qr_code} · ${zoneName(it.destination_id)}`)),
            itemBadge(it.status));
          row.dataset.qr = it.qr_code;
          row.__item = it;
          styleRow(row);
          return row;
        }));
      }
      renderTools();
    }

    function styleRow(row) {
      if (selecting) {
        row.setAttribute('role', 'checkbox');
        row.setAttribute('aria-checked', String(selected.has(row.dataset.qr)));
        row.removeAttribute('aria-haspopup');
        row.removeAttribute('aria-expanded');
      } else {
        row.removeAttribute('role');
        row.removeAttribute('aria-checked');
        row.setAttribute('aria-haspopup', 'dialog');
        row.setAttribute('aria-expanded', 'false');
      }
    }

    function renderTools() {
      const n = selected.size;
      if (selecting) {
        count.textContent = n ? `${n}개 선택됨` : '삭제할 물품을 고르세요';
      } else {
        const shownCount = list.querySelectorAll('.list-item').length;
        count.textContent = query ? `검색 결과 ${shownCount} / ${items.length}` : `등록 물품 ${items.length}`;
      }
      cancelBtn.hidden = !selecting;
      trash.setAttribute('aria-pressed', String(selecting));
      trash.setAttribute('aria-label', selecting ? (n ? `선택한 물품 ${n}개 삭제` : '선택 삭제 끝내기') : '여러 물품 선택해서 삭제');
      trashCount.hidden = !(selecting && n);
      trashCount.textContent = String(n);
    }

    // ---------- 선택 모드 ----------
    function enterSelect() {
      selecting = true;
      list.classList.add('selecting');
      list.querySelectorAll('.list-item').forEach(styleRow);
      renderTools();
    }

    function exitSelect() {
      selecting = false;
      selected.clear();
      list.classList.remove('selecting');
      list.querySelectorAll('.list-item').forEach(styleRow);
      renderTools();
    }

    function setChecked(row, on) {
      if (on) selected.add(row.dataset.qr); else selected.delete(row.dataset.qr);
      row.setAttribute('aria-checked', String(on));
    }

    async function onTrash() {
      if (deleting) return;
      if (!selecting) { enterSelect(); return; }
      if (!selected.size) { exitSelect(); return; }
      const n = selected.size;
      const ok = await confirmDialog({
        title: '정말 삭제하시겠습니까?',
        message: `선택한 물품 ${n}개가 삭제되며 되돌릴 수 없습니다.`,
      });
      if (!ok || !alive) return; // '아니오'를 누르면 선택은 그대로 둔다
      deleting = true;
      trash.disabled = true;
      const targets = [...selected];
      const results = await Promise.allSettled(targets.map((qr) => api.deleteItem(qr)));
      deleting = false;
      trash.disabled = false;
      if (!alive) return;
      const failed = targets.filter((_, i) => results[i].status === 'rejected');
      targets.forEach((qr, i) => { if (results[i].status === 'fulfilled') selected.delete(qr); });
      if (failed.length) {
        toast(`${targets.length - failed.length}개 삭제, ${failed.length}개는 삭제하지 못했습니다.\n실패한 물품은 선택된 채로 남겨 두었습니다.`, 'error');
        await load(false);
      } else {
        toast(`물품 ${targets.length}개를 삭제했습니다.`, 'ok');
        exitSelect();
        await load(false);
      }
    }

    // ---------- 누르기 · 드래그로 여러 개 체크 ----------
    // 처음 누른 물품이 체크돼 있으면 끄는 동안 해제, 아니면 끄는 동안 체크한다.
    let drag = null; // { on, last }
    const rows = () => [...list.querySelectorAll('.list-item')];
    const rowAt = (x, y) => {
      const el = document.elementFromPoint(x, y);
      const row = el && el.closest ? el.closest('.list-item') : null;
      return row && list.contains(row) ? row : null;
    };

    list.addEventListener('pointerdown', (e) => {
      if (!selecting) return;
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      const row = e.target.closest('.list-item');
      if (!row) return;
      e.preventDefault();
      const on = !selected.has(row.dataset.qr);
      setChecked(row, on);
      drag = { on, last: rows().indexOf(row) };
      renderTools();
    });
    list.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const row = rowAt(e.clientX, e.clientY);
      if (!row) return;
      const all = rows();
      const i = all.indexOf(row);
      if (i < 0 || i === drag.last) return;
      // 빠르게 끌어서 건너뛴 물품도 빠짐없이 처리
      const step = i > drag.last ? 1 : -1;
      for (let k = drag.last + step; k !== i + step; k += step) setChecked(all[k], drag.on);
      drag.last = i;
      renderTools();
    });
    const endDrag = () => { drag = null; };
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);

    list.addEventListener('click', (e) => {
      const row = e.target.closest('.list-item');
      if (!row) return;
      if (selecting) {
        // 마우스·터치는 pointerdown에서 처리, 키보드(Enter/Space)만 여기서 체크
        if (e.detail === 0) { setChecked(row, !selected.has(row.dataset.qr)); renderTools(); }
        return;
      }
      edit(row.__item, row);
    });

    // ---------- 한 개 수정 · 삭제 (기존) ----------
    function edit(item, row) {
      row.setAttribute('aria-expanded', 'true');
      const nameInput = h('input', { class: 'input', value: item.name, autocomplete: 'off', maxLength: 60 });
      const dest = locationSelect(locations, item.destination_id);
      let close;
      const done = () => { row.setAttribute('aria-expanded', 'false'); };

      const save = btn('수정 저장', { kind: 'primary', block: true, type: 'submit' });
      const del = btn('삭제', { kind: 'danger' });
      del.addEventListener('click', async () => {
        const ok = await confirmDialog({ title: '정말 삭제하시겠습니까?', message: `'${item.name}'이(가) 삭제되며 되돌릴 수 없습니다.` });
        if (!ok) return;
        busy(del, async () => {
          try {
            await api.deleteItem(item.qr_code);
            toast('삭제했습니다.', 'ok');
            close(); await load(false);
          } catch (e) { toast(e.message, 'error'); }
        });
      });

      const form = h('form', { style: { display: 'flex', flexDirection: 'column', gap: '14px' }, onSubmit: (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        if (!name) { toast('물품명을 입력하세요.', 'error'); return; }
        if (!dest.value) { toast('목적지를 고르세요.', 'error'); return; }
        busy(save, async () => {
          try {
            await api.updateItem(item.qr_code, name, Number(dest.value));
            toast('수정했습니다.', 'ok');
            close(); await load(false);
          } catch (e) { toast(e.message, 'error'); }
        });
      } },
        field('물품명', nameInput),
        field('목적지', dest),
        h('p', { style: { margin: 0, fontSize: '13px', color: 'var(--muted)', lineHeight: 1.5 } },
          '이름을 바꿔도 QR 값은 그대로라서 이미 붙인 QR 라벨을 계속 쓸 수 있습니다.'),
        save,
        h('div', { class: 'row' }, btn('취소', { onClick: () => close() }), del));

      close = openSheet({ title: '물품 수정', sub: `#${String(item.id).padStart(2, '0')} · ${item.qr_code}`, body: form, onClose: done });
    }

    return () => {
      alive = false;
      window.removeEventListener('pointerup', endDrag);
      window.removeEventListener('pointercancel', endDrag);
      document.querySelectorAll('.scrim, .sheet, .dialog').forEach((n) => n.remove());
    };
  },
};
