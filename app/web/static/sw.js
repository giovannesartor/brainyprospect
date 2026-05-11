// Brainy Prospect — Service Worker
const VERSION = 'bp-v3';
const CORE = [
  '/app',
  '/static/app.js',
  '/static/admin.js',
  '/manifest.webmanifest',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(CORE.filter(u => !u.includes('cdn')))).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // API: network-first (sem cache, conteúdo dinâmico)
  if (url.pathname.startsWith('/api/')) return;

  // Páginas HTML: network-first com fallback ao cache
  if (req.headers.get('accept')?.includes('text/html')) {
    e.respondWith(
      fetch(req).then(r => {
        const copy = r.clone();
        caches.open(VERSION).then(c => c.put(req, copy)).catch(() => {});
        return r;
      }).catch(() => caches.match(req).then(r => r || caches.match('/app')))
    );
    return;
  }

  // Assets estáticos: cache-first
  e.respondWith(
    caches.match(req).then(cached => cached || fetch(req).then(r => {
      const copy = r.clone();
      if (r.ok) caches.open(VERSION).then(c => c.put(req, copy)).catch(() => {});
      return r;
    }))
  );
});

// Mensagens do app (ex: "showJobNotification")
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'job-done') {
    self.registration.showNotification('🎯 Brainy Prospect', {
      body: data.message || 'Sua prospecção terminou!',
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      tag: 'job-done',
      data: { url: '/app' },
      vibrate: [120, 60, 120],
    });
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type: 'window'}).then(list => {
    for (const c of list) { if (c.url.includes('/app')) return c.focus(); }
    return self.clients.openWindow('/app');
  }));
});
