// Taesula 모바일 앱 — 화면 전환(해시 라우터)과 공통 레이아웃
import { h, icon } from './ui.js';
import home from './screens/home.js';
import scan from './screens/scan.js';
import register from './screens/register.js';
import manage from './screens/manage.js';
import grid from './screens/grid.js';

const SCREENS = {
  home: { mod: home, tab: '홈', icon: 'home' },
  scan: { mod: scan, tab: '인식', icon: 'scan' },
  register: { mod: register, tab: '등록', icon: 'plus' },
  manage: { mod: manage, tab: '관리', icon: 'list' },
  grid: { mod: grid, tab: '격자', icon: 'grid' },
};

const appbar = document.getElementById('appbar');
const screen = document.getElementById('screen');
const tabbar = document.getElementById('tabbar');

let cleanup = null;

function currentRoute() {
  const name = (location.hash || '').replace(/^#\/?/, '');
  return SCREENS[name] ? name : 'home';
}

function renderTabs(active) {
  tabbar.replaceChildren(...Object.entries(SCREENS).map(([name, s]) =>
    h('a', { class: 'tab', href: `#/${name}`, 'aria-current': name === active ? 'page' : null },
      icon(s.icon, 22, name === active ? 2.1 : 1.8), h('span', null, s.tab))));
}

function renderAppbar(mod, ctx) {
  if (mod.renderHeader) {
    appbar.replaceChildren(...[].concat(mod.renderHeader(ctx)));
    return;
  }
  appbar.replaceChildren(
    h('a', { class: 'back', href: '#/home', 'aria-label': '홈으로' }, icon('back', 22, 2)),
    h('h1', null, mod.title),
  );
}

function show() {
  const name = currentRoute();
  const { mod } = SCREENS[name];

  if (cleanup) { try { cleanup(); } catch { /* 이전 화면 정리 실패는 무시 */ } }
  cleanup = null;

  document.title = name === 'home' ? 'Taesula' : `${mod.title} · Taesula`;
  renderTabs(name);
  screen.replaceChildren();
  window.scrollTo(0, 0);

  const ctx = {
    appbar,
    setHeaderAction(node) {
      const old = appbar.querySelector('[data-action]');
      if (old) old.remove();
      if (node) { node.dataset.action = '1'; appbar.append(node); }
    },
  };
  renderAppbar(mod, ctx);
  // 각 화면의 render는 동기로 그리고, 화면을 떠날 때 부를 정리 함수를 돌려준다
  cleanup = mod.render(screen, ctx) || null;
}

window.addEventListener('hashchange', show);
show();

// 오프라인에서도 앱 화면이 열리도록 서비스 워커 등록 (HTTPS 또는 localhost에서만 동작)
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
