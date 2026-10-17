// Service worker — app shell precache, cache-first static, network-first
// (with timeout) for pages and RSC payloads.
//
// CACHE_NAME is injected at build time from VERCEL_GIT_COMMIT_SHA / git rev,
// so every deploy produces a different sw.js → browser triggers install of
// the new SW → activate event purges all old caches. Without this versioning
// (B196), PWA users were stuck with stale JS bundles after every deploy.
const CACHE_NAME = "climb-agent-__BUILD_ID__";

// B386 — two caches that do NOT carry the build id, because what they hold does
// not change with a deploy.
//
// Before B386 every cache was named after the commit SHA and `activate` purged
// everything else, so a deploy that changed nothing in the app (a docs or
// counter commit) still made every PWA re-download ~284 KB br of identical
// `/_next/static/*` chunks and every exercise image it had seen.
//
// - STATIC: `/_next/static/*` is content-addressed (the hash is in the file
//   name), so a cached entry is correct forever. A new build simply asks for new
//   names; the ones it no longer uses age out through the entry cap.
// - IMAGES: `/_next/image` and `/icons/*` are NOT hashed (same URL if the file
//   changes), so an entry is served from cache but re-fetched in the background
//   once it is older than IMAGE_REVALIDATE_MS.
//
// These names are fixed on purpose — they are the only names here that may ever
// be bumped by hand, and only if the cached FORMAT changes, never per deploy.
// CACHE_NAME (HTML/RSC shells, unhashed public files) stays per-build.
const STATIC_CACHE_NAME = "climb-agent-static-v1";
// Una build ha ~100-150 chunk: il tetto ne tiene 3-4 build, poi sfratto FIFO.
const STATIC_CACHE_MAX_ENTRIES = 600;
const IMAGE_CACHE_NAME = "climb-agent-images-v1";
// ~120 voci = tutte le immagini degli esercizi che un utente incontra in
// qualche settimana di piano, senza far crescere la cache all'infinito.
const IMAGE_CACHE_MAX_ENTRIES = 120;
const IMAGE_REVALIDATE_MS = 7 * 24 * 60 * 60 * 1000;

// A245 B-1 (F1) — the precache used to be just ["/", "/manifest.json"], so a
// cold start with no network could not reach any real screen.
//
// B292 — but `/today` and `/week` must NOT be precached here. They are behind
// Clerk, and at install time the request answered 404, so `cache.add()` failed
// for exactly the two screens the whole feature exists for. Worse, the failure
// was swallowed per-URL, so the install "succeeded" with an empty shell and the
// PWA still would not open offline.
//
// Only genuinely public documents are precached now. `/today` and `/week` are
// cached by the fetch handler the first time the signed-in user visits them,
// which is both correct and enough: you cannot need them offline before you
// have opened them online at least once.
const STATIC_ASSETS = [
  "/",
  "/manifest.json",
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
            // B292: this used to be a console.warn nobody reads, which is how
            // an empty app shell shipped. Still non-fatal (one bad URL must not
            // abort the whole install), but loud.
            console.error(
              `[sw] PRECACHE FAILED for ${url} — the app will not open offline:`,
              err
            );
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
      // both stale climb-agent-* caches and any leftover from previous schemes
      // (including the pre-B386 per-build `climb-agent-<sha>-images`). The two
      // version-agnostic caches survive by name.
      const keys = await caches.keys();
      const keep = new Set([CACHE_NAME, STATIC_CACHE_NAME, IMAGE_CACHE_NAME]);
      await Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)));
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

/**
 * A286 E1 — le immagini degli esercizi non venivano cacciate da nessuno.
 *
 * `next/image` serve tutto da `/_next/image?url=...`: un path senza estensione,
 * che il regex degli statici (`\.(js|css|png|...)$`) non matcha mai. Offline il
 * circuito core era cieco — e le figure sono metà del motivo per cui uno apre la
 * scheda di un esercizio.
 */
function isImageRequest(url) {
  return url.pathname === "/_next/image" || url.pathname.startsWith("/icons/");
}

/** FIFO cap: cache.keys() is in insertion order, so the first are the oldest. */
async function trimCache(cache, maxEntries) {
  const keys = await cache.keys();
  const excess = keys.length - maxEntries;
  if (excess > 0) {
    await Promise.all(keys.slice(0, excess).map((k) => cache.delete(k)));
  }
}

/** True when a cached response is older than `maxAgeMs` (by its Date header). */
function isOlderThan(response, maxAgeMs) {
  const date = Date.parse(response.headers.get("date") || "");
  // No usable Date header: treat as stale so it gets one refresh, not never.
  return !Number.isFinite(date) || Date.now() - date > maxAgeMs;
}

async function fetchAndStore(cacheName, request, maxEntries) {
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(cacheName);
    await cache.put(request, response.clone());
    await trimCache(cache, maxEntries);
  }
  return response;
}

/**
 * Cache-first con tetto. B386: the cache survives deploys, and since these
 * URLs are not content-hashed an entry older than IMAGE_REVALIDATE_MS is
 * refreshed in the background (the user still gets the cached copy now).
 */
async function imageCacheFirst(event, request) {
  const cache = await caches.open(IMAGE_CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) {
    if (isOlderThan(cached, IMAGE_REVALIDATE_MS)) {
      event.waitUntil(
        fetchAndStore(IMAGE_CACHE_NAME, request, IMAGE_CACHE_MAX_ENTRIES).catch(() => {})
      );
    }
    return cached;
  }
  return fetchAndStore(IMAGE_CACHE_NAME, request, IMAGE_CACHE_MAX_ENTRIES);
}

/** B386 — `/_next/static/*`: content-addressed, so cache-first with no expiry. */
async function hashedStaticCacheFirst(request) {
  const cached = await caches.match(request, { cacheName: STATIC_CACHE_NAME });
  if (cached) return cached;
  return fetchAndStore(STATIC_CACHE_NAME, request, STATIC_CACHE_MAX_ENTRIES);
}

/**
 * A286 E2 — navigazioni stale-while-revalidate, ma SOLO su queste route.
 *
 * Criterio (volutamente stretto): shell statica prerenderizzata, pubblica in
 * `PUBLIC_ROUTES`, e zero dati utente nell'HTML. `/` è la start_url della PWA,
 * quindi è la rotta che decide se l'app "si apre subito" o no.
 *
 * Le shell sotto auth (`/today`, `/week`, ...) restano network-first di
 * proposito: passano da `auth.protect()` nel proxy Clerk, e servire dalla cache
 * una di quelle significa saltare il redirect a sign-in di un utente che si è
 * appena disconnesso o a cui è scaduta la sessione. Offline continuano a essere
 * servite dalla cache dal ramo di fallback qui sotto, che è il caso che conta.
 */
const SWR_NAVIGATION_ROUTES = new Set([
  "/",
  "/offline",
  "/legal",
  "/demo",
  "/assessment",
  "/onboarding/welcome",
]);

function isSwrNavigation(url) {
  const path = url.pathname.replace(/\/+$/, "") || "/";
  return SWR_NAVIGATION_ROUTES.has(path);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and API requests. Offline mutations are the outbox's job
  // (B-4), not the SW's — replaying them here would be invisible to the UI.
  if (request.method !== "GET" || url.pathname.startsWith("/api")) return;

  // A286 E1 — prima degli statici: /icons/*.png matcherebbe anche il regex qui
  // sotto, e va invece nella cache con il tetto.
  if (isImageRequest(url)) {
    event.respondWith(
      imageCacheFirst(event, request).catch(() => caches.match(request).then((c) => c || Response.error()))
    );
    return;
  }

  // B386 — hashed build assets: version-agnostic cache, survives deploys.
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      hashedStaticCacheFirst(request).catch(() =>
        caches.match(request).then((c) => c || Response.error())
      )
    );
    return;
  }

  // Cache-first for the other (unhashed) static files — per-build cache, since
  // the same URL can carry new bytes after a deploy.
  if (url.pathname.match(/\.(js|css|png|jpg|svg|woff2?|ico)$/)) {
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

  // A286 E2 — stale-while-revalidate sulle sole shell statiche pubbliche:
  // risposta immediata dalla cache, rete in sottofondo che aggiorna la copia
  // per la prossima apertura. Niente `fetchWithTimeout` qui: la richiesta di
  // rete non blocca nessuno, può prendersi il tempo che vuole.
  if (isNavigation && isSwrNavigation(url)) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);
        const network = fetch(request)
          .then(async (response) => {
            // `response.ok` esclude anche gli opaqueredirect (status 0): una
            // shell che il proxy ha redirezionato non va messa in cache.
            if (response.ok) {
              const cache = await caches.open(CACHE_NAME);
              await cache.put(request, response.clone());
            }
            return response;
          })
          .catch(() => null);

        if (cached) {
          event.waitUntil(network);
          return cached;
        }
        const fresh = await network;
        if (fresh) return fresh;
        const offline = await caches.match("/offline");
        return offline || Response.error();
      })()
    );
    return;
  }

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
