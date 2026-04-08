// Service worker — cache-first for static assets, network-first for API.
// CACHE_NAME is injected at build time from VERCEL_GIT_COMMIT_SHA / git rev,
// so every deploy produces a different sw.js → browser triggers install of
// the new SW → activate event purges all old caches. Without this versioning
// (B196), PWA users were stuck with stale JS bundles after every deploy.
const CACHE_NAME = "climb-agent-__BUILD_ID__";
const STATIC_ASSETS = ["/", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  // Activate the new SW immediately instead of waiting for all PWA tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Purge every cache that doesn't match the current build — this handles
      // both stale climb-agent-* caches and any leftover from previous schemes.
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)));
      // Take control of all open PWA clients without requiring a reload.
      await self.clients.claim();
    })()
  );
});

// Allow the page to force-activate a waiting SW via postMessage({type:"SKIP_WAITING"}).
// Used by the "new version available" update banner so the user can refresh
// without quitting the PWA from the iOS app switcher.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and API requests
  if (request.method !== "GET" || url.pathname.startsWith("/api")) return;

  // Cache-first for static assets (JS, CSS, images, fonts)
  if (
    url.pathname.match(/\.(js|css|png|jpg|svg|woff2?|ico)$/) ||
    url.pathname.startsWith("/_next/static/")
  ) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
            }
            return response;
          })
      )
    );
    return;
  }

  // Network-first for HTML pages — fallback to cache if offline
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok && request.mode === "navigate") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
