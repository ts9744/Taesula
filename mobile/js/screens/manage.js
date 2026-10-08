// 물품 관리: 목록 · 검색 · 수정 · 삭제
import { api } from '../api.js';
import { h, icon, btn, busy, toast, openSheet, field, locationSelect, itemBadge } from '../ui.js';

export default {
  title: '물품 관리',

  render(root) {
    let alive = true;
    let items = [];
    let locations = [];
    let query = '';

    const search = h('input', { type: 'search', placeholder: '물품명 또는 QR 검색', 'aria-label': '물품 검색', enterKeyHint: 'search',
      onInput: (e) => { query = e.target.value.trim().toLowerCase(); renderList(); } });
    const count = h('span', { class: 'label-sm', style: { fontSize: '14px' } }, '불러오는 중…');
    const reload = h('button', { type: 'button', class: 'text-btn', style: { display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }, onClick: () => load(true) },
      icon('refresh', 16), '전체 조회');
    const list = h('div', { class: 'list' });

    root.append(
      h('div', { class: 'search' }, icon('search', 18), search),
      h('div', { class: 'card-head' }, count, reload),
      list);

    load(false);

    async function load(showToast) {
      try {
        const [its, locs] = await Promise.all([api.items(), api.locations().catch(() => [])]);
        if (!alive) return;
        items = its; locations = locs;
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

    function renderList() {
      const shown = items.filter((it) => !query ||
        String(it.name).toLowerCase().includes(query) || String(it.qr_code).toLowerCase().includes(query));
      count.textContent = query ? `검색 결과 ${shown.length} / ${items.length}` : `등록 물품 ${items.length}`;
      if (!shown.length) {
        list.replaceChildren(h('div', { class: 'empty' }, items.length ? '검색 결과가 없습니다.' : '등록된 물품이 없습니다. 등록 탭에서 추가하세요.'));
        return;
      }
      list.replaceChildren(...shown.map((it) => {
        const row = h('button', { type: 'button', class: 'list-item', 'aria-expanded': 'false', 'aria-haspopup': 'dialog' },
          h('span', { class: 'id' }, String(it.id).padStart(2, '0')),
          h('span', { class: 't', style: { display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, minWidth: 0 } },
            h('span', { class: 'n', style: { fontSize: '15px', fontWeight: 600 } }, it.name),
            h('span', { class: 's mono', style: { fontSize: '12px', color: 'var(--muted)' } }, `${it.qr_code} · ${zoneName(it.destination_id)}`)),
          itemBadge(it.status));
        row.addEventListener('click', () => edit(it, row));
        return row;
      }));
    }

    function edit(item, row) {
      row.setAttribute('aria-expanded', 'true');
      const nameInput = h('input', { class: 'input', value: item.name, autocomplete: 'off', maxLength: 60 });
      const dest = locationSelect(locations, item.destination_id);
      let close;
      const done = () => { row.setAttribute('aria-expanded', 'false'); };

      const save = btn('수정 저장', { kind: 'primary', block: true, type: 'submit' });
      const del = btn('삭제', { kind: 'danger' });
      del.addEventListener('click', () => {
        if (!confirm(`'${item.name}'을(를) 삭제할까요? 되돌릴 수 없습니다.`)) return;
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
      document.querySelectorAll('.scrim, .sheet').forEach((n) => n.remove());
    };
  },
};
