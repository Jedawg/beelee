// service-worker.js - Beelee PWA
const CACHE_NAME = 'beelee-v2'; // bumped version
const RUNTIME_CACHE = 'beelee-runtime-v2';
const DATA_CACHE = 'beelee-data-v2';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/react@18/umd/react.production.min.js',
  'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js',
  'https://unpkg.com/@babel/standalone/babel.min.js',
  'https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS.map(url => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter(n => n !== CACHE_NAME && n !== RUNTIME_CACHE && n !== DATA_CACHE)
          .map(n => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API (Render backend) — network first, fall back to cache
  if (url.origin === 'https://beelee-backend.onrender.com') {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          caches.open(RUNTIME_CACHE).then(c => c.put(event.request, res.clone()));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // products.xlsx — cache first, update in background
  if (url.href.includes('products.xlsx')) {
    event.respondWith(
      caches.open(DATA_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const networkFetch = fetch(event.request).then((res) => {
            cache.put(event.request, res.clone());
            return res;
          });
          return cached || networkFetch;
        })
      )
    );
    return;
  }

  // Everything else — cache first, fall back to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        if (res.status === 200) {
          caches.open(RUNTIME_CACHE).then(c => c.put(event.request, res.clone()));
        }
        return res;
      });
    })
  );
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});
