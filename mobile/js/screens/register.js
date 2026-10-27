// 물품 등록: 서버 DB에 저장하고 QR 코드 발급
import { api } from '../api.js';
import { h, icon, btn, busy, toast, field, locationSelect } from '../ui.js';

export default {
  title: '물품 등록',

  render(root) {
    let alive = true;
    let locations = [];
    let current = null; // { name, qr, zone }

    const nameInput = h('input', { class: 'input', placeholder: '예: 부품 박스 01', autocomplete: 'off', maxLength: 60, enterKeyHint: 'done' });
    let destSelect = locationSelect([]);
    destSelect.id = 'reg-dest';
    const destWrap = h('div', { style: { display: 'flex', gap: '8px' } }, destSelect,
      h('button', { type: 'button', class: 'btn btn-secondary', style: { width: '44px', padding: 0, flexShrink: 0 },
        'aria-label': '목적지 새로고침', onClick: () => loadLocations(true) }, icon('refresh', 18)));
    const submit = btn('DB 저장 + QR 생성', { kind: 'primary', icon: 'db', block: true, type: 'submit' });

    const form = h('form', { class: 'card', onSubmit: (e) => { e.preventDefault(); busy(submit, register); } },
      field('물품명', nameInput),
      h('div', { class: 'field' }, h('label', { for: 'reg-dest' }, '목적지'), destWrap),
      h('p', { style: { margin: 0, fontSize: '13px', lineHeight: 1.5, color: 'var(--muted)' } },
        'QR 코드 안에는 물품명이 그대로 들어갑니다. (현재 서버 규칙: 물품명 = QR 값)'),
      submit);

    const preview = h('section', { class: 'card' });
    root.append(form, preview);
    renderPreview();
    loadLocations(false);

    async function loadLocations(showToast) {
      try {
        locations = await api.locations();
        if (!alive) return;
        const selected = destSelect.value;
        const next = locationSelect(locations, selected);
        next.id = 'reg-dest';
        destSelect.replaceWith(next);
        destSelect = next;
        if (showToast) toast(`목적지 ${locations.length}곳을 불러왔습니다.`);
      } catch (e) {
        if (alive) toast(`목적지를 불러오지 못했습니다.\n${e.message}`, 'error');
      }
    }

    async function register() {
      const name = nameInput.value.trim();
      if (!name) { toast('물품명을 입력하세요.', 'error'); nameInput.focus(); return; }
      if (!destSelect.value) { toast('목적지가 없습니다. 격자 탭에서 목적지를 먼저 등록하세요.', 'error'); return; }
      const qr = name;
      try {
        await api.createItem(name, qr, Number(destSelect.value));
        if (!alive) return;
        const loc = locations.find((l) => String(l.id) === destSelect.value);
        current = { name, qr, zone: loc ? loc.zone_name : '' };
        renderPreview();
        toast('서버 DB에 저장하고 QR 코드를 만들었습니다.', 'ok');
      } catch (e) {
        toast(e.message, 'error');
      }
    }

    function renderPreview() {
      const headRow = h('div', { class: 'card-head' }, h('h2', null, 'QR 미리보기'),
        current ? h('span', { class: 'badge done' }, '저장 완료') : null);
      if (!current) {
        preview.replaceChildren(headRow, h('div', { class: 'empty' }, '물품을 저장하면 여기에 QR 코드가 나옵니다.'));
        return;
      }
      const src = api.qrImageUrl(current.qr);
      const img = h('img', { src, alt: `${current.name} QR 코드`, width: 168, height: 168 });
      img.addEventListener('error', () => {
        img.replaceWith(h('div', { class: 'empty', style: { width: '168px' } }, 'QR 이미지를 만들지 못했습니다. 서버에 qrcode 패키지가 설치되어 있는지 확인하세요.'));
      });
      const saveBtn = btn('PNG 저장', { kind: 'dark', icon: 'download' });
      saveBtn.addEventListener('click', () => busy(saveBtn, () => savePng(src, current.qr)));
      const shareBtn = btn('공유', { icon: 'share' });
      shareBtn.addEventListener('click', () => busy(shareBtn, () => sharePng(src, current)));
      preview.replaceChildren(headRow,
        h('div', { class: 'qr-box' },
          h('div', { class: 'qr' }, img),
          h('div', { class: 'meta' }, h('b', null, current.name), h('span', null, `QR 값: ${current.qr}${current.zone ? ` · 목적지 ${current.zone}` : ''}`))),
        h('div', { class: 'row' }, saveBtn, shareBtn),
        btn('새 물품 등록', { block: true, onClick: () => { current = null; nameInput.value = ''; renderPreview(); nameInput.focus(); } }));
    }

    return () => { alive = false; };
  },
};

async function fetchPng(src) {
  const res = await fetch(src);
  if (!res.ok) throw new Error('QR 이미지를 받지 못했습니다.');
  return res.blob();
}

function safeName(s) { return (s || 'qr_code').replace(/[\\/:*?"<>|\s]+/g, '_'); }

async function savePng(src, qr) {
  try {
    const blob = await fetchPng(src);
    const url = URL.createObjectURL(blob);
    const a = h('a', { href: url, download: `${safeName(qr)}.png` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { toast(e.message, 'error'); }
}

async function sharePng(src, item) {
  try {
    const blob = await fetchPng(src);
    const file = new File([blob], `${safeName(item.qr)}.png`, { type: 'image/png' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: `${item.name} QR 코드` });
    } else {
      toast('이 브라우저는 파일 공유를 지원하지 않습니다. PNG 저장을 사용하세요.');
    }
  } catch (e) {
    if (e.name !== 'AbortError') toast(e.message, 'error');
  }
}
