// service-worker.js — Beelee PWA
//
// Bump these whenever index.html changes, or returning users keep the old UI.
const CACHE_NAME    = 'beelee-v3';
const RUNTIME_CACHE = 'beelee-runtime-v3';
const DATA_CACHE    = 'beelee-data-v3';

// Stable key for the product file — the app appends ?t=<timestamp> for
// cache-busting, which would otherwise create a new multi-MB cache entry
// on every single load.
const DATA_KEY = 'beelee-products-data';

// The scope the SW was registered under — '/' at a domain root,
// '/beelee/' on GitHub Pages. Everything local is resolved against it.
const SCOPE = new URL(self.registration.scope).pathname;
const SHELL = SCOPE + 'index.html';

const STATIC_ASSETS = [
  SCOPE,
  SHELL,
  SCOPE + 'manifest.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/react@18/umd/react.production.min.js',
  'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js',
  'https://unpkg.com/@babel/standalone/babel.min.js',
  'https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // One bad URL fails the whole addAll, so cache them individually
      .then((cache) => Promise.allSettled(
        STATIC_ASSETS.map(url =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => null)
        )
      ))
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
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // ── API (Render backend) — network first, fall back to cache ──
  if (url.origin === 'https://beelee-backend.onrender.com') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // ── products.xlsx — network first, cache as offline fallback ──
  // The data file gains columns over time (subcategory, barcode, nutriscore…),
  // so a stale copy means missing features. Always prefer the network and
  // keep exactly one cached copy under a fixed key.
  if (url.pathname.includes('products.xlsx')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(DATA_CACHE).then(c => c.put(DATA_KEY, copy));
          }
          return res;
        })
        .catch(() => caches.open(DATA_CACHE).then(c => c.match(DATA_KEY)))
    );
    return;
  }

  // ── The app shell — stale-while-revalidate ──
  // Serve instantly from cache, but always refresh in the background so a
  // new deploy lands on the next open without waiting for a version bump.
  if (req.mode === 'navigate' || url.pathname === SCOPE || url.pathname.endsWith('/index.html')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(SHELL).then((cached) => {
          const fresh = fetch(req)
            .then((res) => {
              if (res.ok) cache.put(SHELL, res.clone());
              return res;
            })
            .catch(() => cached);
          return cached || fresh;
        })
      )
    );
    return;
  }

  // ── Everything else — cache first, fall back to network ──
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then(c => c.put(req, copy));
        }
        return res;
      });
    })
  );
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});
