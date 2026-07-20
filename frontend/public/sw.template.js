// Service worker — app shell precache, cache-first static, network-first
// (with timeout) for pages and RSC payloads.
//
// CACHE_NAME is injected at build time from VERCEL_GIT_COMMIT_SHA / git rev,
// so every deploy produces a different sw.js → browser triggers install of
// the new SW → activate event purges all old caches. Without this versioning
// (B196), PWA users were stuck with stale JS bundles after every deploy.
const CACHE_NAME = "climb-agent-__BUILD_ID__";

// A245 B-1 (F1) — the precache used to be just ["/", "/manifest.json"], so a
// cold start with no network could not reach any real screen. The app shell is
// now precached: /today and /week are the two views that must open in falesia.
const STATIC_ASSETS = [
  "/",
  "/manifest.json",
  "/today",
  "/week",
  "/offline",
];

// A245 B-1 (F21) — the old network-first had no timeout: `.catch` only fired
// once the TCP connection actually failed, which on a flapping cell link is
// tens of seconds of blank screen. Race the network against a short timer and
// serve the cache the moment the network looks unhealthy.
const NETWORK_TIMEOUT_MS = 3000;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // NOT cache.addAll: it is all-or-nothing, so a single 404 (a route
      // renamed, a build without /offline) would abort the whole install and
      // leave the user with no precache at all.
      Promise.all(
        STATIC_ASSETS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn(`[sw] precache skipped ${url}:`, err);
          })
        )
      )
    )
  );
  // A245 B-1 (F22) — self.skipWaiting() was called unconditionally here, so a
  // new worker never sat in `waiting`: the update banner could never appear
  // (dead code) and clients.claim() forced a reload on every deploy, including
  // mid-workout. Activation is now driven by the banner's SKIP_WAITING message.
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

/** Fetch that gives up early so a stalled connection cannot hold the UI. */
function fetchWithTimeout(request, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("sw-network-timeout")), ms);
    fetch(request).then(
      (response) => {
        clearTimeout(timer);
        resolve(response);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

/**
 * A245 B-1 (F2) — App Router navigations are RSC fetches, not document
 * navigations, so the old `request.mode === "navigate"` condition meant they
 * were NEVER cached. Offline the RSC fetch failed and Next silently stayed put:
 * tapping the bottom nav simply did nothing, with no feedback at all.
 */
function isRscRequest(request, url) {
  return request.headers.get("RSC") === "1" || url.searchParams.has("_rsc");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and API requests. Offline mutations are the outbox's job
  // (B-4), not the SW's — replaying them here would be invisible to the UI.
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

  const isNavigation = request.mode === "navigate";
  const isRsc = isRscRequest(request, url);
  if (!isNavigation && !isRsc) return;

  // Network-first with timeout, then cache, then the offline page.
  event.respondWith(
    (async () => {
      try {
        const response = await fetchWithTimeout(request, NETWORK_TIMEOUT_MS);
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        // A navigation with nothing cached: show the offline page rather than
        // the browser's error screen. RSC fetches get a plain failure so Next
        // can surface it to the app (see the offline guard in the UI).
        if (isNavigation) {
          const offline = await caches.match("/offline");
          if (offline) return offline;
        }
        return Response.error();
      }
    })()
  );
});
