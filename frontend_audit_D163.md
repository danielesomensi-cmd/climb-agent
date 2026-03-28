# D163 — Frontend Full Audit Report

> **Date:** 2026-03-28
> **Type:** D (audit/review) — read-only, no code changes
> **Scope:** Entire Next.js 14 frontend (31 pages, 58 components, lib/)
> **Method:** 5 parallel subagents, each covering a distinct area

---

## Executive Summary

**Total findings: 67**

| Severity | Count | Description |
|----------|-------|-------------|
| **P1** | 14 | Functional bugs — breaks or confuses the user |
| **P2** | 17 | Design/visual inconsistencies |
| **P3** | 24 | UX friction, improvable flows |
| **P4** | 12 | Accessibility gaps |

### Top 5 Most Impactful Issues

1. **Silent error handling everywhere** — ~20+ `.catch(() => {})` across all areas. Users get no feedback when API calls fail. [KNOWN: R141]
2. **Equipment editor allows saving with 0 locations** — User can accidentally erase all training locations, breaking the planner (settings P1)
3. **Onboarding validation gaps** — Decimal ages, whitespace gym names, timezone-unaware deadlines, no cross-field grade validation
4. **Mobile tap targets < 44px** — Availability grid buttons, gym equipment presets, progress dots, location selectors across onboarding + settings
5. **No keyboard/screen reader support on interactive cards** — Weakness cards, availability grid, progress dots use `onClick` on divs without `role="button"` or keyboard handlers

---

## All Findings by Severity

### P1 — Bug funzionali (14)

**Onboarding:**

- **[onboarding/availability/page.tsx:183-202]** — If user has 0 gyms but marks a slot as "gym", the gym Select dropdown won't render. Slot remains `preferred_location: "gym"` with undefined gym_id → silent backend failures on submission.

- **[onboarding/goals/page.tsx:86, 92]** — Deadline validation doesn't account for timezone offset. User in UTC+12 at 1 AM local can select "yesterday" as deadline because `toISOString()` converts to UTC date.

- **[onboarding/review/page.tsx:126-140]** — `completeOnboarding()` API call has no timeout. If backend hangs, user sees "Generating..." indefinitely with no cancel/retry option.

- **[onboarding/trips/page.tsx:63-68]** — Auto-adjust end_date on start_date change doesn't re-run when start_date is moved again. Can result in end_date < start_date.

- **[onboarding/limitations/page.tsx:95-98]** — If hasLimitations is true but limitations array is empty (sessionStorage corruption), `limitations.every()` returns true — validation passes with no actual limitations data.

- **[onboarding/locations/page.tsx:268-272]** — Gym name validation catches empty string but whitespace-only names pass. User can add a gym named "   " and proceed.

**Dashboard & Navigation:**

- **[today/page.tsx:215, 244, 252]** — Silent `.catch(() => {})` on daily quote, outdoor routes, free sessions. UI stays blank/incomplete with no error feedback. [KNOWN: R141]

- **[week/page.tsx:811]** — `catch { /* ignore */ }` on `deleteFreeSession()`. If deletion fails, session stays rendered; later re-fetches may show duplicates.

- **[training/day-card.tsx:650-654]** — "Rest" label fragile: won't appear if freeSessions is truthy-but-empty-array.

**Session & Workout:**

- **[guided/[date]/[sessionId]/page.tsx:494-504]** — Double-confirm exit: rapid double-tap can navigate away before `setConfirmLeave(false)` completes, leaving localStorage in pending state.

- **[guided/exercise-timer.tsx:176-186]** — Wall-clock recalculation on visibility change doesn't check `pausedRef.current`, causing brief time flicker on iOS foreground transitions.

**Settings:**

- **[equipment-editor.tsx:266]** — No validation prevents saving with zero training locations (0 gyms + home disabled). Planner will fail or generate invalid sessions.

- **[profile-assessment-editor.tsx:104]** — No cross-field validation: user can set Lead RP = "9a+" and Lead OS = "5a" (nonsensical). No RP ≥ OS guard.

**Infrastructure:**

- **[outdoor/page.tsx:192-195]** — Grade histogram: if all grades have count=0, `Math.max()` returns -Infinity → NaN width on bars.

### P2 — Design/Visual (17)

**Onboarding:**

- **[onboarding/step-indicator.tsx:8-9]** — Progress bar doesn't account for start-week step. Shows 100% at review but step-indicator shows 11/12 dots.

- **[onboarding/availability/page.tsx:188]** — Gym Select dropdown is 24px tall (`h-6`) with `text-[10px]`. Tap target far below 44px minimum.

- **[onboarding/tests/page.tsx:248-258]** — Label + Switch overlap on narrow screens (<320px). No `gap-` between elements.

- **[onboarding/weaknesses/page.tsx:74-75]** — Disabled card at `opacity-40` in dark mode has insufficient text contrast.

- **[onboarding/locations/page.tsx:209-220]** — Quick-fill preset buttons ~28px tall (below 44px tap target).

- **[onboarding/availability/page.tsx:127-143]** — Availability grid `text-xs` buttons with `gap-1`. On 320px screens, columns ~70px wide, text truncates.

**Dashboard:**

- **[today/page.tsx:728-748]** — Background climber image (`daniclimb.jpg`) covers 55vh on small screens. Gradient fade-out obscures scrollable content on iPhone SE.

- **[plan/page.tsx:209-212]** — MacrocycleTimeline phase labels truncate and overlap on screens <320px.

- **[training/session-card.tsx:70-76]** — `very_easy` and `easy` feedback both map to green badge. No visual distinction between the two levels.

- **[week/page.tsx:686-699]** — Load badge aggregates across multiple weeks without clarification. Users think it's week-scoped.

**Session:**

- **[session/[id]/page.tsx:141-184]** — Rest timer section shows static "0:00" + "Coming soon" copy. Confusing because suggested rest times are displayed but timer doesn't work.

- **[guided/guided-exercise-step.tsx:24-29]** — Feedback colors (`bg-green-600`, `bg-yellow-500`, etc.) hardcoded without Tailwind safelist. May be purged in production builds.

**Settings:**

- **[settings/page.tsx:791]** — Backup message `text-green-500` may lack contrast in dark mode. Needs `dark:text-green-400`.

- **[settings/page.tsx:860-888]** — Two-step macrocycle restart confirmation has inconsistent wording between dialogs.

- **[settings/page.tsx:650]** — Outdoor spot "Remove" button has no confirmation dialog. Accidental deletion possible.

**Infrastructure:**

- **[reports/weekly/page.tsx:39-73]** — Hardcoded color strings (DIFFICULTY_COLORS, STATUS_COLORS) not dark-mode-aware.

- **[whats-next/feedback-section.tsx:9]** — Hardcoded email `daniele.somensi@gmail.com` should be env var.

### P3 — UX Friction (24)

**Onboarding:**

- **[onboarding/locations/page.tsx:37-47]** — `getOnboardingDefaults()` failure leaves empty equipment grid with no explanation. [KNOWN: R141]

- **[onboarding/profile/page.tsx:26-30]** — Age accepts decimal values (25.5). No `step="1"` constraint.

- **[onboarding/profile/page.tsx:86]** — Weight `step={0.1}` is excessive precision for onboarding.

- **[onboarding/experience/page.tsx:42-48]** — Experience slider `max={30}` with no help text. Users >30 years can't represent true experience.

- **[onboarding/goals/page.tsx:53-60]** — Navigating back to grades page and changing them doesn't reset target_grade. User can have target below current grade.

- **[onboarding/availability/page.tsx:145-230]** — Three-state system (Yes/No/Other) has no onboarding affordance. Users may not discover "Other" option.

- **[onboarding/locations/page.tsx:74-95]** — Every equipment checkbox toggle re-serializes entire object to sessionStorage. No debounce.

- **[onboarding/limitations/page.tsx:59]** — hasLimitations toggle state not persisted. Returning to page shows no limitations even if data.limitations has items.

- **[onboarding/review/page.tsx:92-100]** — Empty/malformed availability shows "0 days, 0 slots" with no warning or re-prompt.

**Dashboard:**

- **[today/page.tsx:265-287, week/page.tsx:374-390]** — Feedback dialog dismissable without submitting. Session marked done but feedback skipped entirely. No enforcement.

- **[today/page.tsx:790]** — Weekly checkin card checks `isViewingToday`, not actual day-of-week. Hidden when viewing past dates even if it's Sunday.

- **[today/page.tsx:249-253]** — Free sessions not re-fetched after day-scoped mutations. Shows stale data until page navigation.

- **[plan/page.tsx:155-164]** — No empty state for incomplete assessment. Blank space instead of "assess yourself" CTA.

**Session:**

- **[guided/[date]/[sessionId]/page.tsx:78-84]** — Resume banner auto-dismisses after 4s. May not be enough time on slow networks.

- **[guided/exercise-timer.tsx:308-337]** — Manual "Done rep" tap has no visual feedback during transition. Causes multiple taps.

- **[guided/guided-progress-bar.tsx:18-41]** — Progress dots size-3 (~12px). Hit area too small on mobile with 20+ exercises.

- **[tabata/page.tsx:470-551]** — Zero-duration rest phase causes `advancePhase()` to loop indefinitely in work phase. No guard or warning.

- **[guided/guided-exercise-step.tsx:981-1007]** — Per-exercise notes field collapsed by default. Users may not discover it for critical exercises (tests, max efforts).

**Settings:**

- **[goal-editor.tsx:102-109]** — "Short timeframe" warning has no guidance on what "compressed" means or how to fix it.

- **[goal-editor.tsx:111-112]** — "Aggressive plan" warning is vague. No estimated weekly intensity shown.

- **[availability-editor.tsx:132-148]** — Disabling all 3 slots on a day makes it a rest day with no visual feedback.

- **[settings/page.tsx:744-788]** — Import flow immediately opens file picker with no warning that it overwrites current data.

- **[limitations-editor.tsx:74-75]** — New limitation entry has all fields empty. Save disabled with no inline validation feedback explaining why.

**Infrastructure:**

- **[~13 instances across all pages]** — Silent `.catch(() => {})` on API calls. [KNOWN: R141]

### P4 — Accessibility (12)

**Onboarding:**

- **[onboarding/weaknesses/page.tsx:69-86]** — WeaknessCard uses `onClick` on div. No keyboard support (`role="button"`, `tabindex="0"`).

- **[onboarding/availability/page.tsx:127-143]** — Availability buttons lack `aria-pressed` / `aria-selected`. Screen readers can't determine selection state.

- **[onboarding/tests/page.tsx:241-319]** — Conditionally shown test sections have no `aria-expanded` or `role="region"` markers.

**Dashboard:**

- **[layout/top-bar.tsx:17-22]** — Back button (SVG chevron only) lacks `aria-label`.

- **[layout/bottom-nav.tsx:138-149]** — Nav SVG icons missing `aria-hidden="true"`. Screen readers may announce icon twice.

- **[training/day-card.tsx:156, 162, 167]** — Dynamic form sections toggled by boolean state have no `aria-live` region.

- **[training/macrocycle-timeline.tsx:77]** — Phase bars use `title` for tooltip only. Not accessible on touch devices.

**Session:**

- **[guided/exercise-timer.tsx:684-694]** — Timer aria-label doesn't include current rep/set number. Screen reader users can't track progress.

- **[circuit/CircuitTimer.tsx:323-363]** — Back/Next phase buttons have no descriptive aria-labels beyond "Back"/"Next".

- **[tabata/page.tsx:976-984]** — Phase transitions (WORK→REST) not announced via `aria-live` region.

**Settings:**

- **[goal-editor.tsx:248-257, limitations-editor.tsx:251-257]** — Warning boxes use color only. No icon or pattern for color-blind users (WCAG).

- **[settings/page.tsx:285-286]** — Loading spinner has no `role="status"` or `aria-label`.

---

## Cross-Cutting Patterns

| Pattern | Occurrences | Areas |
|---------|-------------|-------|
| Silent `.catch(() => {})` | ~20+ | All 5 areas | [KNOWN: R141] |
| Tap targets < 44px | 6 | Onboarding (3), Settings (1), Session (1), Dashboard (1) |
| Missing `aria-label` on icon buttons | 5 | Dashboard (3), Session (2) |
| No empty/error state | 4 | Dashboard (2), Onboarding (1), Settings (1) |
| Color-only feedback (no icon/pattern) | 3 | Settings (1), Dashboard (1), Reports (1) |
| Missing form validation | 3 | Onboarding (2), Settings (1) |
| Stale data after mutations | 2 | Dashboard (2) |
| No confirmation on destructive action | 2 | Settings (2) |

---

## Already Tracked in Roadmap

| Finding | Roadmap Item | Status |
|---------|-------------|--------|
| Silent `.catch(() => {})` (~20 instances) | R141 — Frontend Error Handling Hardening | Open |
| api.ts 590+ lines, inconsistent patterns | R144 — Frontend API Layer Refactor | Open |
| settings/ 1018 lines, today/ 971, week/ 889 | R145 — Spezzare pagine componente grandi | Open |
| Duplicated logic (useSessionHandlers, shared states) | R146 — Estrarre logica duplicata | Open |
| Missing React.memo, performance signals | R149 — Frontend performance | Open |
| Audio util duplication (CircuitTimer + Tabata) | R160 — Audio util dedup | Open |

---

## Recommended Action Plan

### Before launch (P1 + high-impact P2)

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 1 | Equipment editor: prevent save with 0 locations | XS | Prevents broken planner state |
| 2 | Profile editor: add RP ≥ OS cross-validation | XS | Prevents nonsensical assessment |
| 3 | Grade histogram: guard against -Infinity/NaN | XS | Prevents broken chart render |
| 4 | Onboarding complete: add timeout + retry button | S | Prevents stuck user on slow network |
| 5 | Tabata: guard zero-duration rest phase | XS | Prevents infinite loop |
| 6 | Guided exit: prevent double-tap race condition | S | Prevents data loss |
| 7 | Rest timer "Coming soon" → hide section entirely | XS | Reduces confusion |
| 8 | Feedback badge: distinguish very_easy from easy | XS | Visual correctness |
| 9 | Outdoor spot delete: add confirmation dialog | XS | Prevents accidental deletion |
| 10 | Import flow: add pre-import confirmation | XS | Prevents accidental data overwrite |

### Post-launch (batch with R141/R144/R145)

- All silent `.catch(() => {})` → error toasts (R141)
- Tap target pass: increase all interactive elements to ≥ 44px
- Accessibility pass: aria-labels, keyboard support, aria-live regions
- Empty state pass: add CTA/message for missing assessment, 0 sessions, API failures
- Mobile responsive pass: test all pages at 320px width

---

*Generated by D163 frontend audit — 5 parallel subagents, 2026-03-28*
