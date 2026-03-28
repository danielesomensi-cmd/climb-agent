# Frontend Code Audit — D164

**Date:** 2026-03-27
**Scope:** `frontend/src/` (106 files: 83 `"use client"` components, 6 lib modules, 1 middleware, 16 UI primitives)

## Summary

- Files scanned: 106
- Findings: 22 (P1: 2, P2: 10, P3: 10)

---

## P1 — Launch Blockers

### [F1-001] Profanity in voice cues — shipped to production
- **File:** `frontend/src/lib/voice-cues.ts`
- **Lines:** 42-43
- **Issue:** The encouragement pool contains `"Vaffanculo!"` (Italian expletive) and `"Punani!"` (slang). These are spoken aloud via Web Speech API during timer work phases with 30% probability. Users in public gyms, shared spaces, or around children will hear the app shouting profanity. This is a reputation risk for a paid product.
- **Fix:** Remove both entries from `ENCOURAGEMENT_POOL`. Replace with appropriate Italian encouragements (e.g., "Forza!", "Dai!").

### [F1-002] `useSearchParams` without Suspense boundary in session page
- **File:** `frontend/src/app/(main)/session/[id]/page.tsx`
- **Line:** 35
- **Issue:** `useSearchParams()` is called directly in the page component without a wrapping `<Suspense>` boundary. In Next.js 14 App Router, this causes a build error or SSR bailout in production. Other pages that use `useSearchParams` (today, reports/weekly, free-session) correctly wrap with `<Suspense>`.
- **Fix:** Add a Suspense wrapper pattern like today/page.tsx uses: export a default wrapper component with `<Suspense>` around the inner component.

---

## P2 — Fix Soon After Launch

### [F2-001] Outdoor page silently swallows API errors — no error state
- **File:** `frontend/src/app/(main)/outdoor/page.tsx`
- **Lines:** 25
- **Issue:** The `.catch(() => {})` on the data fetch provides no user feedback when the API call fails. The page shows a spinner, then shows "No outdoor sessions logged yet" — misleading if the issue is a network error or auth failure. No `error` state variable exists.
- **Fix:** Add `error` state and display an error card with retry button, matching the pattern in today/page.tsx and session/[id]/page.tsx.

### [F2-002] `as any` type escape in availability editor
- **File:** `frontend/src/components/settings/availability-editor.tsx`
- **Line:** 74
- **Issue:** `const meta = dd._day_meta as any;` bypasses TypeScript's type system. The `_day_meta` structure is accessed without type guards, which can cause runtime errors if the shape changes.
- **Fix:** Define a `DayMeta` interface for the `_day_meta` shape and cast to it. At minimum use `Record<string, unknown>` with proper checks.

### [F2-003] PHASE_LABELS duplicated in 4 files
- **Files:**
  - `frontend/src/app/(main)/week/page.tsx` (line 35)
  - `frontend/src/app/(main)/plan/page.tsx` (line 24)
  - `frontend/src/app/(main)/reports/weekly/page.tsx` (line 31)
  - `frontend/src/components/training/macrocycle-timeline.tsx` (line 30)
- **Issue:** The same `PHASE_LABELS` Record is copy-pasted in 4 files. Adding a new phase requires updating all 4 locations. Violates DRY.
- **Fix:** Extract to a shared constant in `lib/constants.ts` or `lib/phase-rationales.ts` (which already exists and is phase-related).

### [F2-004] `todayISO()` utility duplicated
- **Files:**
  - `frontend/src/app/(main)/today/page.tsx` (line 53)
  - `frontend/src/app/(main)/week/page.tsx` (line 44)
- **Issue:** Same `todayISO()` helper function duplicated. Minor DRY violation but creates divergence risk.
- **Fix:** Move to `lib/utils.ts`.

### [F2-005] Silent `.catch(() => {})` on 16+ API calls
- **Files:** Multiple (today/page.tsx, week/page.tsx, outdoor/page.tsx, onboarding-context.tsx, equipment-editor.tsx, etc.)
- **Issue:** At least 16 API calls use `.catch(() => {})` which silently swallows errors. While some are intentional (optional data like quotes, spots), several are for primary data fetches where failure should be communicated to the user. Notable cases:
  - `outdoor/page.tsx:25` — primary page data
  - `today/page.tsx:244` — outdoor sessions fetch
  - `week/page.tsx:166` — free session history
  - `session-card.tsx:292` — exercise catalog
- **Fix:** For optional/supplementary data (quotes, spots), silent catch is acceptable. For primary data, add error state or at minimum log the error. Audit each `.catch(() => {})` and classify as intentional vs. needs error handling.

### [F2-006] console.warn/error left in production code
- **Files:**
  - `frontend/src/lib/api.ts:45` — `console.warn` on 401 retry
  - `frontend/src/components/free-session/climb-logger.tsx:157` — `console.error` on climb log failure
  - `frontend/src/components/training/session-card.tsx:606` — `console.error` on exercise removal failure
- **Issue:** Console statements in production code. The api.ts one is arguably useful for debugging auth issues, but the component-level ones should use proper error state instead.
- **Fix:** Remove component-level console statements; replace with user-visible error feedback. The api.ts warn can stay as a debug aid (gated behind `process.env.NODE_ENV === 'development'` ideally).

### [F2-007] eslint-disable for react-hooks/exhaustive-deps
- **Files:**
  - `frontend/src/app/(main)/today/page.tsx:216`
  - `frontend/src/app/(main)/reports/weekly/page.tsx:129`
- **Issue:** `eslint-disable` comments suppress dependency warnings. The today/page.tsx case (`[weekPlan]` without including `dayPlan`, `phaseId`) may cause stale closures where the quote context doesn't update when the day changes within the same week plan.
- **Fix:** Audit the dependency arrays. For the quote fetch, extract relevant dependencies (phaseId, sessionIds) and include them, or use `useMemo` to derive the context.

### [F2-008] Hardcoded email in feedback section
- **File:** `frontend/src/components/whats-next/feedback-section.tsx`
- **Line:** 9
- **Issue:** `const FEEDBACK_EMAIL = "daniele.somensi@gmail.com"` is hardcoded. If the support email changes, it requires a code change and redeploy.
- **Fix:** Move to an environment variable `NEXT_PUBLIC_FEEDBACK_EMAIL` or a shared constants file.

### [F2-009] `window.location.href` for navigation instead of Next.js router
- **File:** `frontend/src/app/(main)/reports/weekly/page.tsx`
- **Line:** 374
- **Issue:** `window.location.href = "/outdoor"` triggers a full page reload instead of client-side navigation. This breaks the SPA experience and causes unnecessary re-renders and data refetching.
- **Fix:** Use `router.push("/outdoor")` from `useRouter()`.

### [F2-010] `window.location.href` for auth redirect in API layer
- **File:** `frontend/src/lib/api.ts`
- **Line:** 50
- **Issue:** `window.location.href = "/sign-in"` in the API request helper causes a hard redirect on 401. This can interrupt in-flight operations and lose unsaved state (e.g., during a guided session feedback submission). It also bypasses Next.js router.
- **Fix:** Consider using `router.push` via a callback, or throw a specific `AuthError` that components can catch and handle gracefully (e.g., save state to localStorage before redirecting).

---

## P3 — Backlog

### [F3-001] Monster components — today/page.tsx (994 lines), tabata/page.tsx (1175 lines), session-card.tsx (1081 lines)
- **Files:** `today/page.tsx`, `tabata/page.tsx`, `session-card.tsx`
- **Issue:** Three components exceed 1000 lines. `today/page.tsx` manages 30+ state variables. These are difficult to maintain and test. Risk of prop drilling and stale closure bugs increases with component size.
- **Fix:** Extract sub-components (e.g., TodayOutdoorSection, TodayFreeSessionSection from today/page.tsx). Extract timer logic from tabata/page.tsx into a custom hook.

### [F3-002] No lazy loading for any route or heavy component
- **Issue:** No `React.lazy()` or `next/dynamic` usage found anywhere. All components are eagerly loaded. Pages like tabata (1175 lines with SVG timer), circuit timer, and guided session add to the initial bundle even when not visited.
- **Fix:** Use `next/dynamic` with `{ ssr: false }` for the timer-heavy pages (tabata, circuit, guided) that are only accessed on-demand and require browser APIs.

### [F3-003] RadarChart is inline SVG — no lazy loading
- **File:** `frontend/src/components/onboarding/radar-chart.tsx`
- **Issue:** Custom SVG radar chart. Not a third-party library (good for bundle size), but it's rendered on the plan page which is loaded eagerly. Minor optimization opportunity.
- **Fix:** No action needed now. If chart complexity grows, consider lazy loading.

### [F3-004] Hardcoded "Coming soon" rest timer placeholder on session detail page
- **File:** `frontend/src/app/(main)/session/[id]/page.tsx`
- **Lines:** 140-155
- **Issue:** The session detail page shows a "Rest timer between sets. Coming soon." message, but rest timers already exist in the guided session flow. This placeholder is misleading and outdated.
- **Fix:** Either remove the placeholder or link to the guided session flow where rest timers are functional.

### [F3-005] `dangerouslySetInnerHTML` for service worker registration
- **File:** `frontend/src/app/layout.tsx`
- **Line:** 58
- **Issue:** Uses `dangerouslySetInnerHTML` to inject the SW registration script. The content is a static string so there is no XSS risk, but it's a code smell flagged by security scanners.
- **Fix:** Move to a `sw-register.ts` client component or use the `next-pwa` plugin. Low priority since the string is hardcoded.

### [F3-006] Feature roadmap votes stored only in localStorage
- **File:** `frontend/src/components/whats-next/roadmap-section.tsx`
- **Issue:** User votes on roadmap features are only stored in `localStorage`. They are lost on device switch, browser reset, or incognito mode. There is no backend endpoint to persist or aggregate votes.
- **Fix:** If votes are meant to inform product decisions, add a simple backend endpoint to aggregate them. If they are purely cosmetic UX (user sees their own thumbs-up), current approach is acceptable.

### [F3-007] Guided session state stored in localStorage with Clerk-based key
- **Files:** `session-card.tsx:886-888`, `guided/[date]/[sessionId]/page.tsx:30,40`
- **Issue:** Guided session state uses `guided_session_${userId}_${date}_${sessionId}` as the localStorage key, where userId is "clerk" when signed in. This means all Clerk users on the same browser share the same key space (they all get userId="clerk"). In practice this is fine because session IDs include dates, but the key design is fragile.
- **Fix:** Use the actual Clerk user ID instead of the literal string "clerk". Low priority since collisions require same browser + same date + same session ID.

### [F3-008] Recovery code reference in guide content is stale
- **File:** `frontend/src/lib/guide-content.tsx`
- **Line:** 477
- **Issue:** The user guide mentions "Your account has a recovery code (format: CLIMB-XXXX-XXXX)" but the API comment at `api.ts:311` says "Recovery code functions removed -- Clerk handles account recovery". The guide content is out of date.
- **Fix:** Update the guide content to reflect that Clerk handles account recovery, or remove the recovery code section.

### [F3-009] No `<img>` tags found — but native `<img>` used instead of `next/image`
- **File:** `frontend/src/app/(main)/today/page.tsx`
- **Line:** 742-747
- **Issue:** Uses `<img src="/daniclimb.jpg">` instead of Next.js `<Image>` component. Missing automatic optimization (WebP conversion, lazy loading, srcset generation). The image has `alt=""` (correctly marked as decorative).
- **Fix:** Replace with `next/image` for automatic optimization. Low priority since it is a decorative background image with `opacity-20`.

### [F3-010] DOMAIN_LABELS duplicated across files
- **Files:**
  - `frontend/src/app/(main)/plan/page.tsx` (line 33)
  - Used inline in other components
- **Issue:** Similar to PHASE_LABELS, domain labels are defined inline. Less duplicated than PHASE_LABELS (only 1-2 files), but same DRY concern.
- **Fix:** Extract to shared constants alongside PHASE_LABELS.

---

## Not Found (Verified Clean)

- **Secrets exposure:** No API keys, admin secrets, or sensitive data in frontend bundle. Clerk keys are handled server-side. `ADMIN_SECRET` not referenced in frontend.
- **iOS AudioContext:** Properly handled via `audio-unlock.ts` with user gesture unlock, silent buffer trick, and `visibilitychange` re-resume. All 4 timer components (exercise-timer, circuit-timer, tabata, rest-timer) use the shared AudioContext correctly.
- **Timer suspension (iOS PWA):** All timer components use `Date.now()`-based elapsed time calculation and `visibilitychange` listeners to recalculate on foreground return. No naive `setInterval`-only timing.
- **TypeScript:** Only 1 `as any` found (F2-002). No `@ts-ignore` or `@ts-nocheck`. Types are well-defined in `lib/types.ts` (611 lines, comprehensive interfaces).
- **Accessibility:** aria-labels present on all interactive timer controls, progress bars, and icon-only buttons. Decorative image has `alt=""`. Not comprehensive but reasonable for current stage.
- **Auth gating:** All data-fetching pages gate on `useAuth().isLoaded` before making API calls (B155 pattern). Middleware protects non-public routes.
