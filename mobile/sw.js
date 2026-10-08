// 앱 화면 파일만 캐시합니다. 서버 API(로봇·물품·카메라)는 항상 네트워크로 요청합니다.
const CACHE = 'taesula-v1';
const SHELL = [
  './', './index.html', './manifest.webmanifest', './css/app.css',
  './js/app.js', './js/api.js', './js/ui.js',
  './js/screens/home.js', './js/screens/scan.js', './js/screens/register.js',
  './js/screens/manage.js', './js/screens/grid.js',
  './icons/icon-192.png', './icons/apple-touch-icon.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const inScope = url.origin === location.origin && url.pathname.startsWith(new URL('./', location.href).pathname);
  if (e.request.method !== 'GET' || !inScope) return;
  // 네트워크 우선, 실패하면 캐시 (코드를 고치면 바로 반영되도록)
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('./index.html'))),
  );
});
