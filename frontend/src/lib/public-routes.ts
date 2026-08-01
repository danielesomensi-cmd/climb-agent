import { ONBOARDING_STEPS } from "@/lib/onboarding-steps";

/**
 * A256 — the wizard itself is public.
 *
 * Before: only `/onboarding/welcome` was public, so the "Start assessment" CTA
 * landed straight on a sign-up wall at step 1 of 12. We asked a cold visitor
 * from a flyer to create an account BEFORE showing a single output of the
 * product. The account is now requested at the submit CTA on `/review`, once
 * the user has answered everything and can see their own summary — "sign up to
 * save this", not "sign up to start".
 *
 * Derived from ONBOARDING_STEPS so a newly added step is public by default:
 * the failure mode of forgetting one here is a mid-wizard auth wall, which is
 * exactly the bug this brief removes.
 *
 * Deliberately NOT public: `/onboarding/start-week` and `/onboarding/install`
 * both run AFTER the plan exists (A245 F38), so they have a real user by
 * definition.
 */
const ONBOARDING_WIZARD_ROUTES = ONBOARDING_STEPS.map((s) => `/onboarding/${s}`);

export const PUBLIC_ROUTES = [
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/legal",
  "/demo(.*)",
  "/onboarding/welcome",
  ...ONBOARDING_WIZARD_ROUTES,
  // A256 — linked from the public welcome page ("Lost access? Recover with a
  // code"), so gating it behind auth sent exactly the people who cannot sign
  // in to the sign-in page.
  "/onboarding/recover",
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
  // A262 — the public 5-axis assessment. The whole point is that it works with
  // no account: gating it would turn the one page built to be posted publicly
  // into another sign-in wall.
  "/assessment",
];
