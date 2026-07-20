export const PUBLIC_ROUTES = [
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/legal",
  "/demo(.*)",
  "/onboarding/welcome",
  // B292 — both were auth-protected and answered 404 to anyone not signed in.
  //
  // `/offline` is the service worker's navigation fallback: it can only ever be
  // useful when it is already in the cache, and it could never GET into the
  // cache because `cache.add("/offline")` received a 404 at install time. The
  // page renders no user data at all.
  //
  // `/manifest.json` is the PWA manifest. The middleware matcher excludes
  // `.webmanifest` but NOT `.json` (`js(?!on)`), so this one file was being
  // gated behind auth — breaking install prompt and theming for logged-out
  // visitors, which is exactly the acquisition surface.
  "/offline",
  "/manifest.json",
];
