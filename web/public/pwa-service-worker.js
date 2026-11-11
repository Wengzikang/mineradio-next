'use strict';

const CACHE_NAME = 'starwave-pwa-v2';
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/starwave-icon-192.png',
  './icons/starwave-icon-512.png',
  './vendor/three.r128.min.js',
  './vendor/music-tempo.min.js',
  './vendor/gsap.min.js',
  './starwave-netease.js',
  './starwave-netease-login.js',
  './starwave-phase2.js',
  './starwave-phase3.js',
  './starwave-phase4b.js',
  './starwave-phase5.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(CORE_ASSETS))
      .catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put('./index.html', copy)).catch(() => undefined);
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // .js 走网络优先：部署后下一次加载即取新版，不再被旧缓存钉住；
  // 离线时回退缓存（v2 预缓存 + 运行期写入），离线行为不变。
  // 只缓存成功的响应，避免 404 等错误响应污染缓存。
  if (/\.js$/i.test(url.pathname)) {
    event.respondWith(
      fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => undefined);
        }
        return response;
      }).catch(() => caches.match(request))
    );
    return;
  }

  if (/\.(?:html|css|png|jpg|jpeg|webp|svg|json|webmanifest|bin)$/i.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => undefined);
        return response;
      }))
    );
  }
});
