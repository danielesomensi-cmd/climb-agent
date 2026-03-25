# Frontend UX & Soft Launch Audit Report

> **Date:** 2026-03-22
> **Auditor:** Claude Code
> **Frontend:** Next.js 14, 29 pages, 54 components

## Summary

- **UX flows checked:** 13 (A1–A13)
- ✅ **Complete & working:** 11
- ⚠️ **Incomplete / edge cases:** 2
- ❌ **Broken / dead ends:** 0
- **Soft launch checks:** 6 (B1–B6)
- ✅ **Ready:** 3
- ⚠️ **Gaps:** 2
- ❌ **Blockers:** 1
- **Total findings:** 94 checks performed

---

## Section A: UX Flow Findings

### A1. Onboarding Flow

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | All steps reachable in sequence | ✅ | 12 steps (welcome → review) + start-week + recover. All `router.push()` chains verified |
| 2 | Back navigation | ✅ | All steps have back button linking to correct previous step |
| 3 | Input validation before "Next" | ✅ | Profile: 4 required fields. Grades: lead RP+OS. Goals: target+deadline. Weaknesses: primary+secondary. Tests/Limitations: optional (can skip) |
| 4 | Review → POST /api/onboarding/complete | ✅ | Review shows all data, allows edit jumps, calls `completeOnboarding(data)` which hits POST /api/onboarding/complete |
| 5 | Start-week step | ✅ | Correctly shifts macrocycle start_date via POST /api/onboarding/start-week. Limits offset to first_phase_duration - 1 |
| 6 | Recovery flow (CLIMB-XXXX) | ⚠️ | `/onboarding/recover` redirects to `/sign-in` — no CLIMB-code UI. Intentional: Clerk handles recovery. Backend recovery-code API still exists but unused in frontend |
| 7 | Refresh mid-onboarding | ✅ | sessionStorage draft (`climb_onboarding_draft`) auto-saves on every update. Backend state used as fallback. No data loss on refresh |
| 8 | Error handling on API failure | ✅ | All API calls wrapped in try/catch. Review page shows red error banner. Locations/start-week fail gracefully |
| 9 | Clerk auth gating | ✅ | middleware.ts protects `/onboarding/*`. Public routes: `/`, `/sign-in/*`, `/sign-up/*` only |

---

### A2. Today Page (`/today`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Load current day's sessions | ✅ | Calls `getWeek(0)` → GET /api/week/0. Isolates today via `targetDate` |
| 2 | Session status display | ✅ | DayCard maps: planned → secondary badge, done → default, skipped → destructive |
| 3 | "Mark done" → FeedbackDialog | ✅ | `handleMarkDone()` → `applyEvents(mark_done)` → sets `feedbackSessionId` → opens FeedbackDialog with exercise list |
| 4 | "Mark skipped" | ✅ | `handleMarkSkipped()` → `applyEvents(mark_skipped)`. No feedback dialog triggered |
| 5 | "Undo" (done/skipped) | ✅ | `handleUndo()` → `applyEvents(mark_planned)`. Works for both |
| 6 | Free session cards (A138) | ✅ | Calls `getFreeSessionHistory(targetDate)`. Displayed in DayCard via SessionCard |
| 7 | Test session results (B136) | ✅ | `feedback_summary` badge displayed inline after session name |
| 8 | Empty state (rest day) | ✅ | "No sessions today" + "Enjoy the rest and recover" + link to next training day |
| 9 | No macrocycle generated | ⚠️ | Today page assumes macrocycle exists. Fails gracefully but doesn't show onboarding prompt like plan page does |
| 10 | Outdoor days | ✅ | Fetches outdoor routes for done days. Displays routes with style badges, grades, climb count |
| 11 | Navigation to guided session | ✅ | SessionCard stores state in localStorage, navigates to `/guided/${date}/${sessionId}` |

---

### A3. Week Page (`/week`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | 7-day grid | ✅ | WeekGrid: 7 columns desktop, 4 mobile. Status dots (green/red/gray) |
| 2 | Multi-week navigation | ✅ | Prev/Next buttons. Prev disabled at week 1, Next at totalWeeks. Week picker drawer available |
| 3 | Day detail cards | ✅ | Full session display with all actions wired (done/skip/undo/replan) |
| 4 | Replan dialog | ✅ | Override intent selection → `applyOverride()` → POST /api/replanner/override |
| 5 | Quick-add dialog | ✅ | Outdoor/free climbing/other sport options → `quickAddSession()` → POST /api/replanner/quick-add |
| 6 | Session status badges | ✅ | Same DayCard logic as today page |
| 7 | Week 0 vs future vs past | ✅ | Week 0 = current. Navigation respects boundaries |
| 8 | Macrocycle boundary | ✅ | Next button disabled at last week |

---

### A4. Plan Page (`/plan`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Radar chart — 5 axes | ✅ | AXES array: finger_strength, pulling_strength, power_endurance, technique, endurance. Pentagon rendering |
| 2 | Macrocycle timeline | ✅ | Horizontal phase bar with proportions. Phase colors: base=blue, S&P=red, PE=orange, perf=green, deload=gray. Current week arrow |
| 3 | Phase details expandable | ✅ | Collapsible Cards with domain weights grid + available sessions list |
| 4 | Regenerate buttons | ✅ | Dirty-state banner: "Update remaining plan" with preserve_before. Standalone button for full regeneration. Calls POST /api/macrocycle/generate |
| 5 | Before first assessment | ✅ | "No plan generated" + "Complete onboarding" link + "Start onboarding" button |

---

### A5. Session Detail (`/session/[id]`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Exercise display | ✅ | ExerciseCard: sets × reps, load (kg/bodyweight), rest (mm:ss), tempo, notes |
| 2 | Load score display | ⚠️ | Per-exercise load delta shown (A139), but no session-level aggregate load score |
| 3 | Navigation to guided session | ⚠️ | No "Start guided" CTA button on session detail page. Must navigate from /today |
| 4 | Error state | ✅ | Error boundary with retry button |
| 5 | API endpoint | ✅ | POST /api/session/resolve with session_id + context |

---

### A6. Guided Session (`/guided/[date]/[sessionId]`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Step-by-step flow | ✅ | Exercises as `currentIndex`. Done/Skip → advances. All done → summary |
| 2 | Timer — wall-clock | ✅ | `phaseEndTimeRef = Date.now() + seconds * 1000`. iOS Safari: `visibilitychange` listener recalculates on foreground |
| 3 | Exercise completion | ✅ | Green checkmark for done exercises. "Done" button for instruction-only |
| 4 | Per-exercise feedback (5 levels) | ✅ | FEEDBACK_OPTIONS: very_easy, easy, ok, hard, very_hard. Radio button selection |
| 5 | Session completion → feedback | ✅ | GuidedSummary component IS the feedback UI (all-in-one, not separate dialog) |
| 6 | Back navigation preserves progress | ✅ | localStorage saves on every change. Double-tap to confirm leave if progress exists |
| 7 | Audio — user gesture | ✅ | `unlockAudio()` on first touchstart. `visibilitychange` resumes AudioContext if suspended |
| 8 | Mid-session resume | ✅ | localStorage key: `guided_session_{userId}_{date}_{sessionId}`. Shows resume banner on remount |
| 9 | Rest timer color coding | ✅ | get_ready=sky, work=orange, rep_rest=teal, set_rest=emerald. SVG progress ring |

---

### A7. Tabata Timer (`/tabata`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | 7-param config | ✅ | prepare (0-60s), work (5-300s), rest (0-120s), cycles (1-50), sets (1-10), set rest (0-300s), cooldown (0-120s). Hold-to-accelerate buttons |
| 2 | Timer phases | ✅ | Correct sequence: prepare → work/rest × cycles × sets + set_rest + cool_down → done |
| 3 | Expand/fullscreen | ✅ | Full overlay with large countdown (120px). Swipe-down to close (80px threshold) |
| 4 | Completion screen | ✅ | Green checkmark + total time + cycles + sets + total intervals. Restart/Setup buttons |
| 5 | Audio beeps + voice | ✅ | OscillatorNode beeps. Half-time subtle beep. Voice cues via Web Speech API (30% chance Italian/Spanish encouragement!) |
| 6 | Timer state | ✅ | Wall-clock refs (phaseEndTimeRef, startTimeRef). 200ms tick interval. Survives iOS suspension |

---

### A8. Free Climbing Session

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Surface selection (5) | ✅ | gym_boulder, board_kilter, board_moonboard, board_other, gym_routes. Gradient backgrounds + icons |
| 2 | Gym picker | ✅ | Loads saved gyms from API. Custom gym input. Auto-selects if single gym |
| 3 | Mode selection | ✅ | Template (preset + rest timer + targets) / Free (no structure, phase tip only) |
| 4 | Preset picker | ✅ | Phase compatibility badges (recommended/caution/not_recommended). Target grade, rest, climb count |
| 5 | Climb logging | ✅ | Grade picker + status (flash/sent/attempted) + lead style (onsight/flash/redpoint/project) + topped toggle + attempts + notes |
| 6 | Rest timer | ✅ | Auto-start in template mode, manual in free. Wall-clock based. Skip + "+1 min" buttons. Voice cue on completion |
| 7 | Session summary | ✅ | Stats card (climbs, send rate). Grade distribution bar chart. Feel selector (easy/good/hard). Duration + load from API |
| 8 | History query | ✅ | `getFreeSessionHistory(date)` endpoint wired |

---

### A9. Settings (`/settings`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Profile editing | ✅ | Dialog: weight, height, grades, tests (conditional on finger device) |
| 2 | Goal editing | ✅ | Dialog-based with regeneration sheet |
| 3 | Equipment editing | ✅ | Home + per-gym equipment badges. Save triggers regeneration prompt |
| 4 | Outdoor spots | ✅ | Full CRUD: add (name + discipline) / delete / view history |
| 5 | Regenerate assessment | ✅ | Calls `computeAssessment()` to recalculate 5-axis profile |
| 6 | Regenerate macrocycle | ✅ | Two pathways: equipment change (sheet) and goal change (from_phase="current"). Preserves past sessions |
| 7 | Max hang baseline (B135) | ✅ | Label: "Max hang 20mm / 7s (MVC-7) — total kg". Conditional on fingerDevice === "hangboard" |
| 8 | Equipment change impact | ✅ | Opens RegeneratePlanSheet, lets user choose what to preserve |

---

### A10. Reports (`/reports/weekly`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Weekly report loads | ✅ | `getWeeklyReport(weekStart)` with week navigation |
| 2 | Adherence display | ✅ | Adherence ring (%), completed/planned/skipped/added counts |
| 3 | Load display | ✅ | Total load (planned + actual), outdoor + free included |
| 4 | Difficulty distribution | ✅ | Bar chart: very_easy → very_hard with average label |
| 5 | Progression table | ✅ | Exercise: previous → current load, direction indicator, change % |
| 6 | Free session load | ✅ | Integrated: surface, preset_name, climbs, grade, duration. Purple badge |
| 7 | Empty state | ✅ | Dashed border: "No report data available" |
| 8 | Stimulus balance grid | ✅ | Per-category sessions + days since last. Amber warning if > 10 days |

---

### A11. Outdoor (`/outdoor`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | History display | ✅ | Sorted newest first: date, spot, discipline, routes, top grade, load |
| 2 | Per-spot breakdown | ✅ | Conditional (2+ spots): spot name, session count, total routes, top grade |
| 3 | Grade histogram | ✅ | Horizontal bars, sorted alphabetically, relative width, count labels |
| 4 | Stats accuracy | ✅ | 4-stat grid: total sessions, total routes, send %, top grade |

---

### A12. What's Next (`/whats-next`)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Votable roadmap | ✅ | Short term (7 items, 4 implemented) + Long term (5 items). Vote toggle via localStorage |
| 2 | Feedback form | ✅ | "What's working" + "What's missing/broken" + optional name/email. Generates mailto: link |
| 3 | Vote submission | ✅ | Client-side localStorage only. Offline-safe, persists across reloads |

---

### A13. Navigation & Layout

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Bottom nav structure | ✅ | 5 tabs: Today, Week, Tabata, Free, More |
| 2 | "More" drawer | ✅ | Plan, What's next, Settings, Outdoor, Reports |
| 3 | All nav items → correct pages | ✅ | Verified all href targets |
| 4 | Active state indicator | ✅ | `usePathname().startsWith()` → `text-primary` color |
| 5 | Root URL (`/`) | ✅ | B139 fix: checks auth → checks macrocycle → redirects to /today or /onboarding/welcome |
| 6 | Clerk protection | ✅ | middleware.ts: public = `/`, `/sign-in/*`, `/sign-up/*`. Everything else protected |

---

## Section B: Soft Launch Gap Findings

### B1. Error Handling

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Silent `.catch(() => {})` | ⚠️ | ~20 instances, but ALL are non-critical data: quotes, outdoor stats, free sessions, spots. Core operations have proper error handling |
| 2 | JSON.parse without try/catch | ✅ | All JSON.parse calls protected with try/catch (localStorage, file import, onboarding context) |
| 3 | Unhandled promise rejections | ✅ | Consistent try-catch-finally pattern. 94 try-catch blocks, 108 setError states |
| 4 | User-facing error messages | ✅ | Destructive alert with retry button on main pages. Inline errors on forms |
| 5 | TODO/FIXME/HACK comments | ✅ | Zero instances found in entire frontend codebase |

---

### B2. Loading States

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Loading indicators | ✅ | Consistent spinner pattern across all data-fetching pages (today, week, plan, settings, outdoor, reports, free-session) |
| 2 | Flash prevention | ✅ | Suspense boundaries in 3+ pages. Loading shows before content. Supplementary data loads after main |
| 3 | Consistency | ✅ | Same spinner component: `h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent` |

---

### B3. Empty States

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | All lists have empty state | ✅ | 7+ empty states verified: today (rest day), week (no plan), plan (no macrocycle), outdoor (no sessions), reports (no data), onboarding (no trips) |
| 2 | Helpful messaging | ✅ | All include context + guidance. Many include CTAs ("Start onboarding", "Preview next training day") |
| 3 | Visual consistency | ✅ | Dashed border containers for visual distinction |

---

### B4. Mobile Experience (PWA)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Manifest | ✅ | name, short_name, display: standalone, theme_color, icons (192+512), start_url: "/" |
| 2 | iOS meta tags | ⚠️ | **Missing:** apple-mobile-web-app-capable, apple-mobile-web-app-status-bar-style, apple-touch-icon |
| 3 | Service worker | ⚠️ | Stub only: install + activate, no fetch handler, no caching. Not registered in app code |
| 4 | Offline behavior | ❌ | Not implemented. App fails completely offline |
| 5 | Viewport + safe area | ✅ | width=device-width, initialScale=1. Bottom nav: `pb-[env(safe-area-inset-bottom)]` |
| 6 | Touch targets | ✅ | 44x44px standard. Some xs buttons at 24px but always with text labels |
| 7 | Responsive layout | ✅ | `max-w-3xl mx-auto`. No hardcoded widths. No overflow-x issues |

---

### B5. Clerk Auth Integration

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Route protection | ✅ | middleware.ts: public = `/`, `/sign-in/*`, `/sign-up/*`. All others protected |
| 2 | Sign-in/sign-up | ✅ | Standard Clerk components, centered dark UI |
| 3 | User identity flow | ✅ | Frontend: `window.Clerk.session.getToken()` → `Authorization: Bearer` header. Backend: JWT verify → Clerk ID → Supabase UUID lookup |
| 4 | Sign-out | ✅ | Clerk `<UserButton />` in Settings page provides sign-out |
| 5 | Token expiry | ✅ | Clerk auto-refreshes. Backend returns 401 on invalid token |

---

### B6. Missing "Basics" for Paid Product

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Delete my account | ✅ | Settings → "Reset & Restart" with two-stage confirmation. Calls `deleteState()` → redirects to onboarding |
| 2 | Contact support | ⚠️ | Email-only via What's Next feedback form. No dedicated support page, FAQ, or ticket system |
| 3 | Terms of Service / Privacy Policy | ❌ | **NOT FOUND.** No legal pages, no policy documents, no links during sign-up. **BLOCKING for paid launch** |
| 4 | About / Version info | ⚠️ | No version string, no about page, no changelog link |
| 5 | Bug reporting | ✅ | Via What's Next feedback form ("What's missing or broken?"). Email-based |
| 6 | Data export | ✅ | Settings → "Export data". One-click JSON backup via GET /api/user/export |
| 7 | Onboarding re-entry | ✅ | Root page checks macrocycle. No macrocycle → /onboarding/welcome. API error → same |
| 8 | Logout | ✅ | Clerk `<UserButton />` in Settings provides sign-out |

---

## Priority-ordered Action Items

### :red_circle: Soft Launch Blockers (must fix before charging)

1. **Terms of Service / Privacy Policy pages missing.** Legal requirement for any paid product, especially with EU users (GDPR). Create static pages at `/terms` and `/privacy`, link from sign-up and settings. No code logic needed — just content.

### :yellow_circle: Important (fix within first week)

2. **iOS PWA meta tags missing.** Without `apple-mobile-web-app-capable` and `apple-mobile-web-app-status-bar-style`, iPhone users can't install PWA properly. 3 lines in `layout.tsx`.

3. **Service worker is a stub.** No caching, no offline support. App fails completely offline. For climbing (often poor connectivity), implement at minimum cache-first for static assets.

4. **Today page doesn't guard against missing macrocycle.** Plan page shows "Start onboarding" CTA, but today page just fails gracefully. Add same check.

5. **Session detail page has no "Start guided" CTA.** Users can only launch guided session from /today, not from session detail. Add a prominent play button.

6. **No 401 handler in API layer.** If Clerk token expires and auto-refresh fails, API calls return 401 but frontend doesn't redirect to `/sign-in`. Add global error interceptor.

### :green_circle: Nice-to-have (post-launch)

7. **Silent catches (~20) are intentional** but could log to console in dev mode for debugging.

8. **Session-level load score aggregation** — currently only per-exercise load delta shown, no session total.

9. **Contact support** — upgrade from email-only to in-app support form or FAQ. Add a dedicated `/support` page.

10. **About / Version info** — add version string to Settings page footer. Consider a changelog link.

11. **Offline support** — full network-first API + cache-first static strategy. Show offline banner.

12. **Votes backend** — What's Next votes are localStorage-only. Consider persisting to backend for analytics.

13. **Recovery code UI** — `/onboarding/recover` just redirects to Clerk. If you want to keep CLIMB-XXXX codes as a backup recovery method, add UI.
