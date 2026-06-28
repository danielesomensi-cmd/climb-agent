# Brief D — Audit: Guided Session Countdown Beep Silent (Last 3s)

**Status:** Phase 0 (read-only) — awaiting OK before Phase 1
**Date:** 2026-05-04
**Scope:** Frontend only (Next.js 16 PWA, iPhone standalone)
**Author:** Claude (Sonnet)

---

## 1. Executive summary

**Root cause (confidence: high):** `exercise-timer.tsx` is the *only* timer in the codebase that uses a **1000 ms `setInterval`** to drive a countdown that depends on `secondsLeft` passing through the values `3 → 2 → 1` exactly once per second. The countdown beep is gated by a `useEffect` on `[secondsLeft]`, which only fires when the *value* changes. Any tick drift, throttling, or coalesced tick on iOS Safari PWA can cause `Math.ceil(remainingMs/1000)` to skip a value (e.g. 4 → 1), silently dropping 1–3 of the countdown beeps.

The transition beep is robust because it fires on `remainingMs <= 0` — any tick that lands after expiry triggers it, regardless of timing precision.

The 4 other in-repo timers (`CircuitTimer`, `custom-rest-timer`, `custom-exercise-step`, `tabata`) use **200–250 ms ticks** and/or strict-equality + dedup pattern — they are immune. The fix pattern is already in the codebase.

**Scope:** `exercise-timer.tsx` only — i.e. all guided sessions launched from `/today` and `/guided/[date]/[sessionId]`. Circuit, custom session playback, free-session rest timer, and tabata are unaffected.

---

## 2. File mapping

| File | Purpose | LoC | Last commit |
|------|---------|-----|-------------|
| `frontend/src/lib/audio-unlock.ts` | Singleton AudioContext + iOS unlock | 56 | (origin: `dce788a` 2026-02-24, GS-02 iPhone PWA fix) |
| `frontend/src/lib/voice-cues.ts` | Web Speech API wrapper | 64 | (mod: `baa88ed` 2026-03-13, A123 voice encouragement) |
| `frontend/src/components/guided/exercise-timer.tsx` | **Guided session timer (BUG HERE)** | 906 | last touched `1b1f032` 2026-04-20 (A211 — added playback page; this file unchanged in that commit), countdown logic untouched since `521e295` 2026-02-24 + `14faee2` 2026-02-28 |
| `frontend/src/components/circuit/CircuitTimer.tsx` | Core circuit timer (200 ms ticks — robust) | 645 | `b9366d4` 2026-03-26 |
| `frontend/src/components/session-play/custom-rest-timer.tsx` | Custom session rest timer (250 ms + dedup — robust) | 175 | `1b1f032` 2026-04-20 |
| `frontend/src/components/session-play/custom-exercise-step.tsx` | Custom session work timer (200 ms + dedup — robust) | ~250 | `1b1f032` 2026-04-20 |
| `frontend/src/components/free-session/rest-timer.tsx` | Free-session rest timer (no countdown beep, voice only) | 116 | (older) |
| `frontend/src/app/(main)/tabata/page.tsx` | Tabata (200 ms ticks — robust) | ~750 | `3983650` 2026-03-20 |
| `frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx` | Guided session host page — wires `unlockAudio` on touchstart + visibilitychange | 627 | various |

Discovery commands used:

```bash
find frontend/src -type f \( -name "*.tsx" -o -name "*.ts" \) | xargs grep -l -i "countdown\|beep\|playSound\|AudioContext"
git log --since="120 days ago" -- frontend/src/components/guided/exercise-timer.tsx ...
```

---

## 3. Audio architecture

**One singleton AudioContext** (`frontend/src/lib/audio-unlock.ts:10`):

```ts
let _ctx: AudioContext | null = null;
export function getAudioContext(): AudioContext { /* lazy create */ }
export async function unlockAudio(): Promise<void> {
  // Resume + play 1-sample silent buffer to satisfy iOS user-gesture gate
}
```

- `unlockAudio()` is called on first touchstart of the guided page (`page.tsx:140-147`) and on every `visibilitychange → visible` (`page.tsx:149-167`), where it also resumes the context and replays the silent buffer to re-unlock after backgrounding.
- Beep generation is identical across all timers: `OscillatorNode` (sine, freq, dur) → `GainNode` (volume → exp ramp to 0.001) → `ctx.destination`. Each beep creates a fresh oscillator pair and stops it after `duration` seconds.
- **`countdownTick()` and `transitionBeep()` go through the SAME `beep()` function**, only differing in args:
  - countdown: `beep(660, 0.08, 0.25)` — 660 Hz, 80 ms, vol 0.25
  - transition: `beep(880, 0.2, 0.4)` — 880 Hz, 200 ms, vol 0.4
- This means: an audio infrastructure failure (suspended ctx, blocked output) would kill **both** beeps. The fact that transition beep works rules out that class of bug.

The two paths therefore cannot diverge at the `beep()` level. The divergence must be at the **trigger** — i.e. whether `countdownTick()` is even *called*.

---

## 4. Countdown trigger — VERBATIM

`frontend/src/components/guided/exercise-timer.tsx:155-166`:

```tsx
// Countdown ticks at 3 / 2 / 1 seconds
useEffect(() => {
  if (secondsLeft >= 1 && secondsLeft <= 3) {
    const p = phaseRef.current;
    if (!pausedRef.current && p !== "idle" && p !== "complete") {
      // No countdown ticks during manual work (no timer running)
      if (!(p === "work" && isManual)) {
        countdownTick();
      }
    }
  }
}, [secondsLeft, isManual]);
```

How `secondsLeft` is updated — `exercise-timer.tsx:185-280`:

```tsx
// Main tick — wall-clock based so iOS background suspension doesn't freeze countdown.
// Instead of decrementing a counter, each tick computes remaining = endTime - Date.now().
useEffect(() => {
  clearTimer();

  if (phase === "idle" || phase === "complete" || paused) return;
  if (phase === "work" && isManual) return;

  phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;

  intervalRef.current = setInterval(() => {
    const remainingMs = phaseEndTimeRef.current - Date.now();

    if (remainingMs <= 0) {
      // --- Phase transition ---
      // ... setPhase / setTransitionId / startCountdown ...
      return;
    }

    // Normal tick — update display from wall clock
    setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
  }, 1000);   //  ⬅︎  ONE-SECOND TICK INTERVAL

  return clearTimer;
}, [phase, paused, currentSet, currentRep, sets, reps, totalSets, ...]);
```

Key facts:

- **Trigger condition:** RANGE comparison `secondsLeft >= 1 && secondsLeft <= 3`. NOT strict equality. Daniele's working hypothesis (`=== 3` skip) was *not* what's coded.
- **Comparison operand:** integer (`Math.ceil(remainingMs / 1000)`).
- **`secondsLeft` derivation:** wall-clock — `Math.ceil((phaseEndTimeRef.current - Date.now()) / 1000)`, **not** counter decrement. This is the post-B67 design.
- **Dedup mechanism:** NONE. Relies on `useEffect` only firing when `secondsLeft` *value* changes (React state-bailout for identical updates). If `setSecondsLeft(3)` is called twice in succession, only the first triggers the effect — but if the value 3 is *never set*, the effect never fires for that beep.
- **Tick interval:** `1000 ms` — exactly aligned with the 1-second windows the trigger depends on. **This is the fragile part.** Other timers in this codebase use 200 ms (`CircuitTimer.tsx:283`, `tabata/page.tsx:643`, `custom-exercise-step.tsx:123`) or 250 ms (`custom-rest-timer.tsx:99`).

---

## 5. End-beep trigger — VERBATIM

`exercise-timer.tsx:142-153`:

```tsx
// Transition beep + voice cue + visual flash
useEffect(() => {
  if (transitionId > 0) {
    transitionBeep();
    if (pendingVoiceCueRef.current) {
      speakPhaseTransition(pendingVoiceCueRef.current);
      pendingVoiceCueRef.current = null;
    }
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 300);
    return () => clearTimeout(t);
  }
}, [transitionId]);
```

`transitionId` is incremented inside the main tick handler (line 200 onwards) **whenever `remainingMs <= 0`**, regardless of which exact second the tick happens to fire on. Excerpt:

```tsx
if (remainingMs <= 0) {
  // ... setPhase("rep_rest"); pendingVoiceCueRef.current = "rep_rest";
  setTransitionId((id) => id + 1);
  startCountdown(restBetweenRepsSeconds);
  return;
}
```

**Why this is robust:** the transition condition is `remainingMs <= 0`, an open-ended threshold. Any tick that fires *at or after* the phase end will fire it. Tick drift, throttling, missed ticks, late ticks — none of them cause the transition to be skipped, only delayed.

**Comparison with countdown:** the countdown depends on a tick landing in *each* of three narrow 1-second windows `(0, 1000]`, `(1000, 2000]`, `(2000, 3000]`. Miss any window → beep dropped. Miss all three (single tick gap ≥ 3 s at the wrong time) → all three beeps dropped, transition still fires.

This **exactly** matches the user's symptom: end beep audible, countdown silent.

---

## 6. iOS PWA tick behavior

The codebase already documents (`exercise-timer.tsx:185-186`):

> Main tick — wall-clock based so iOS background suspension doesn't freeze countdown.
> Instead of decrementing a counter, each tick computes remaining = endTime - Date.now().

This was introduced in **B67 (`14faee2`, 2026-02-28)** to fix a *different* iOS issue: when the PWA was backgrounded, the previous counter-decrement design over-counted (the counter froze, then resumed, but wall-clock had moved). The wall-clock fix correctly handles backgrounding — but it inadvertently introduced the *current* bug:

| Pre-B67 (counter decrement)            | Post-B67 (wall-clock)                              |
|----------------------------------------|----------------------------------------------------|
| `setSecondsLeft(prev => prev - 1)`     | `setSecondsLeft(Math.ceil(remainingMs / 1000))`    |
| Always passes through 3, 2, 1, 0       | Can skip values if a tick lands off-window         |
| Frozen during background                | Survives background (correct)                      |

Pre-B67 design was *fragile to backgrounding* but *robust to drift*. B67's wall-clock design fixed the former and broke the latter. **The countdown beep regression starts at `14faee2` (2026-02-28) and has been live ever since (~2 months).**

iOS Safari standalone PWA setInterval behavior:

- **Foreground, screen on, no interaction**: setInterval drift typically 5–50 ms per tick, cumulative. Over 30 ticks, drift can reach 150–1500 ms. Sufficient to occasionally shift a tick out of the 1-second window for value 3.
- **Aggressive throttling triggers** (any of the following can coalesce ticks for several seconds):
  - Display dimming → standby on iOS (auto-lock, even with screen still showing the timer).
  - "Background-on-Foreground" CPU throttling under low-power mode.
  - Web Audio API garbage collection pauses.
  - Service Worker activation events on first run.
  - User scrolling (timer is in a scrollable container — `<main className="p-4 space-y-4">`).
- **Result:** a single tick gap of 3+ seconds at the wrong moment drops *all three* countdown beeps without affecting the transition.

The repo confirms this design by example — `CircuitTimer.tsx:283` uses 200 ms ticks specifically for this reason. Same author, same constraints, more robust pattern.

Tick-skip 4 → 1 is *possible* under heavy throttling. Tick-skip 4 → 0 (skipping all three countdown values) requires a single 3+ second gap, which iOS PWA can produce under the conditions above.

---

## 7. Git history — regression hunt

```bash
git log --since="180 days ago" -- frontend/src/components/guided/exercise-timer.tsx
```

Suspicious commits affecting countdown / audio / timer logic in `exercise-timer.tsx`:

| Hash      | Date       | Message                                            | Audio/timer impact                                                                          |
|-----------|------------|----------------------------------------------------|---------------------------------------------------------------------------------------------|
| `069efca` | 2026-02-23 | feat: add interactive exercise timer to guided session | **Initial commit** — counter-decrement design, no countdown beeps yet                       |
| `521e295` | 2026-02-24 | fix: guided session timer — sets×reps loop, iOS audio, get-ready, manual-set flow | **Countdown beep introduced** with the current `>= 1 && <= 3` range condition (lines 156-166 unchanged since). Counter still decrement-based at this point. |
| `dce788a` | 2026-02-24 | feat: GS-02 fix audio on iPhone PWA (Safari)        | AudioContext singleton + user-gesture unlock pattern. Audio infrastructure (still in use).  |
| `53ba98b` | 2026-02-27 | fix: B58 equipment filter for test sessions + B60 audio async bug | Made `beep()` async to handle `await ctx.resume()` (current pattern).                     |
| **`14faee2`** | **2026-02-28** | **fix: B67 wall-clock timer for iOS background suspension** | **★ REGRESSION SOURCE.** Replaced counter-decrement with wall-clock derivation. Countdown effect was *not* updated to match — kept the value-change-based trigger, which now depends on tick precision the wall-clock derivation no longer guarantees. |
| `485fcf6` | 2026-02-28 | fix: B59 remove Get Ready countdown between sets    | Phase routing only, audio unchanged.                                                        |
| `3e9e973` | 2026-02-28 | feat: B56 + B57 + B61 — conditioning exercises, rep-rest clarity, voice cues | Added voice cue layer (orthogonal to beep).                                                |
| `baa88ed` | 2026-03-13 | feat: A123 timer enlarge + voice encouragement + prehab load tracking | Enlarged-mode UI, voice encouragement pool. No tick-rate change.                            |
| `2727805` | 2026-03-13 | fix: Hold→Rest label, session elapsed time display (B125) | Label-only.                                                                                 |
| `3ec2bf8` | 2026-03-30 | fix(B169): EMOM timer, 1-on/1-off rest, unilateral alt_sides mode | Phase routing. No tick-rate change.                                                         |
| `740b077` | 2026-03-30 | fix(B172): alt_sides badge + cooldown prescriptions + test form scope | UI only.                                                                                    |
| `3ba8acf` | 2026-03-31 | fix(B178): alt_sides catalog, set counter clamp, FAB start session | Counter clamp. No tick-rate change.                                                         |
| `1b1f032` | 2026-04-20 | A211: session builder playback page with timer      | Did not modify `exercise-timer.tsx` — added separate `custom-exercise-step.tsx` (which used the corrected 200 ms + dedup pattern). |

**Verdict:** the regression is **`14faee2` (B67, 2026-02-28)**. The wall-clock conversion was applied surgically to the tick handler but the countdown trigger above it was not adapted. The file has been touched many times since — but the countdown effect is byte-identical to its 2026-02-24 form (`git blame -L 156,166` confirms `521e295c` for every line). No "fix" attempt has been made in this region.

---

## 8. Test coverage

```bash
find frontend -name "*.test.ts" -o -name "*.test.tsx" | grep -v node_modules
```

- `frontend/src/lib/__tests__/phase-labels.test.ts` — pure data
- `frontend/src/lib/__tests__/gradeUtils.test.ts` — pure data
- `frontend/src/lib/__tests__/weekly-checkin-dates.test.ts` — pure data
- `frontend/src/lib/__tests__/equipment-filter.test.ts` — pure data
- `frontend/src/components/session-play/__tests__/custom-playback.test.ts` — custom-session playback (does *not* reference `countdownTick` or beeps)

**No test exercises the countdown beep.** Vitest is in the toolchain (other tests run), but the only timer-adjacent test covers `custom-playback`, not `exercise-timer`. **Adding a regression test that simulates a tick skip (4 → 1, or 4 → 0) and asserts the right number of `countdownTick` invocations is a Phase 1 deliverable.**

---

## 9. Hypothesis ranking

### H1 — *Original* (Daniele): tick skips a value and trigger uses strict equality (`=== 3 / 2 / 1`).
**Status: REFUTED.** The trigger uses range comparison `>= 1 && <= 3`, not strict equality. See section 4.

### H2 — *Refined* (this audit): tick skips *all three* values because tick rate (1000 ms) matches window width (1 s); any drift / throttle / coalesced tick can produce a single ≥3 s gap that lands outside `(0, 3000]` ms-from-end.
**Status: STRONGLY SUPPORTED.** Confidence: high. Evidence:

- All 4 sister timers (`CircuitTimer`, `custom-rest-timer`, `custom-exercise-step`, `tabata`) use 200–250 ms tick rates and/or strict-equality + dedup. Same codebase, same author, more robust — these are unaffected by the bug.
- The transition beep (`remainingMs <= 0`) cannot be skipped by drift, only delayed. Matches symptom (end beep works).
- Wall-clock derivation (`Math.ceil(remainingMs/1000)`) only guarantees value coverage if at least one tick lands in each 1-s window. With 1000 ms ticks, this is exactly one tick per window — zero margin.
- B67 commit changed the tick semantics without updating the countdown gate. Pre-B67 (counter decrement), no skip was possible. Post-B67, skip is possible.

### H3 — AudioContext suspension between transition beeps silently kills countdown beeps.
**Status: PLAUSIBLE BUT WEAKER.** If the ctx silently suspends mid-phase (without backgrounding), `ctx.state !== "running"` would cause `beep()` to return without sound. **However:** the transition beep at the end of the same phase would also fail under this hypothesis, contradicting the symptom. Cannot be the *primary* cause. May contribute as a secondary failure mode for *some* sessions.

### H4 — Web Audio Oscillator creation throttling on iOS PWA for very short bursts (80 ms).
**Status: VERY UNLIKELY.** No documented iOS limit on rapid oscillator creation/disposal at this rate (3 oscillators in 3 seconds). Other timers create oscillators at the same cadence and work.

### H5 — React 18 batching coalesces multiple `setSecondsLeft(...)` calls in rapid succession (e.g. catch-up after suspension), causing useEffect to fire only at the final value.
**Status: POSSIBLE EDGE CASE.** Visibility-change → tick-storm scenarios on iOS PWA could produce this. The visibility handler at line 286-298 already calls `setSecondsLeft` inline before the next tick, so on visible-change the bug is partially mitigated for that path. But same end result: skipped values → skipped beeps. **This is a sub-case of H2** — same fix applies.

**Concluding rank:**
1. **H2 (tick rate / drift / wall-clock skip)** — primary, ~90% confidence.
2. **H5 (batching after tick-storm)** — secondary, contributes under specific iOS PWA conditions; same fix.
3. **H3 (AudioContext silent suspension)** — possible but cannot be the only cause; not the focus.
4. **H1, H4** — refuted / very unlikely.

---

## 10. Cross-device scope

From code alone:

- **iOS PWA standalone (Safari)**: most affected. Drift, throttling, audio-context lifecycle quirks all skew toward this surface.
- **iOS Safari (in-browser, not installed)**: same engine — same bug surface. Likely also affected, possibly less severely.
- **Android Chrome PWA**: setInterval is more reliable; tick drift typically <10 ms. May *occasionally* miss the "3" beep under heavy load; "0 of 3 beeps" scenario very rare. Likely indistinguishable from the user's POV — *probably* fine in normal use.
- **Desktop Chrome/Firefox/Safari**: setInterval typically holds within 5 ms when the tab is focused. Should hit all three windows reliably. Bug effectively invisible.

**Daniele to confirm post-Phase-0:** play a guided session on Android (if accessible) and desktop browser. Expectation: countdown beeps fire reliably on both, confirming the bug is iOS-PWA-specific.

---

## 11. Phase 1 fix outline (NOT IMPLEMENTED)

Two minimal options, in order of preference:

### Option A (preferred): adopt the in-repo "200 ms + dedup" pattern from `custom-rest-timer.tsx`

```tsx
// exercise-timer.tsx
const lastBeepedSecRef = useRef<number>(-1);

// Reset on every phase boundary (already happens via startCountdown)
const startCountdown = useCallback((seconds: number) => {
  phaseEndTimeRef.current = Date.now() + seconds * 1000;
  lastBeepedSecRef.current = -1;            // ⬅︎ NEW — reset dedup
  setSecondsLeft(seconds);
}, []);

// In the main tick handler — REPLACE the useEffect-on-secondsLeft pattern
//                                  ↓↓↓
intervalRef.current = setInterval(() => {
  const remainingMs = phaseEndTimeRef.current - Date.now();

  if (remainingMs <= 0) { /* transition unchanged */ return; }

  const remainingS = Math.max(0, Math.ceil(remainingMs / 1000));

  // Idempotent countdown trigger — fires once per second value, even if
  // multiple ticks land in the same 1-s window.
  if (
    remainingS >= 1 && remainingS <= 3 &&
    lastBeepedSecRef.current !== remainingS &&
    !pausedRef.current && phaseRef.current !== "idle" && phaseRef.current !== "complete" &&
    !(phaseRef.current === "work" && isManual)
  ) {
    lastBeepedSecRef.current = remainingS;
    countdownTick();
  }

  setSecondsLeft(remainingS);
}, 200);                                    // ⬅︎ 200 ms — matches CircuitTimer
```

Then **remove** the separate `useEffect` on `[secondsLeft, isManual]` for `countdownTick` (lines 156-166).

**Why preferred:**
- Resilient to drift (5 ticks per 1 s window — virtually no skip possible).
- Resilient to coalesced ticks (dedup ensures one beep per second-value).
- Resilient to React batching (in-tick check, no useEffect dependency).
- Same pattern already in 4 other places in the codebase — proven and consistent.
- Visibility-change handler at lines 286-298 still works as-is (sets `secondsLeft`; next tick picks up).

### Option B (smaller diff, less robust)

Just change tick rate from `1000 → 200` ms and leave the existing useEffect-on-secondsLeft countdown gate. This works because secondsLeft transitions through 3, 2, 1 cleanly with 5 ticks per window. **But** it leaves the React-batching tick-storm edge case (H5) only partially handled. If we trust that visibility-change resyncs cover that, Option B is acceptable. Smaller blast radius.

### Tests (Phase 1 deliverable)

Add `frontend/src/components/guided/__tests__/exercise-timer-countdown.test.tsx` (Vitest + React Testing Library). Test cases:

1. `phaseEndTimeRef.current` is set, simulate ticks at sub-second cadence — assert exactly 3 calls to `countdownTick` for a 30-s phase.
2. Simulate one ≥3-s tick gap (mock `Date.now()` jumping from `phaseStart + 27000` to `phaseStart + 30500`) — Option A asserts countdown still fires when tick lands inside `(0, 3000]`. Wait — this case can't fire under any pattern (the tick *did not happen* in the window). Reword: assert `transitionBeep` still fires once, and total beep count = 1 (only transition).
3. Simulate small drift (50 ms cumulative per tick) — assert all 3 countdown beeps + 1 transition.
4. Tick storm (5 ticks fired in 100 ms catching up after a backgrounding) — assert no double-beep for the same second value.
5. Pause during countdown — assert no beep while paused.
6. Manual work phase — assert no countdown ticks (existing behavior preserved).

### Manual QA checklist before merge (Phase 1)

- [ ] iPhone 13/14 PWA installed (standalone): start a `prehab_maintenance` or `strength_long` guided session, complete one rest phase, count countdown beeps (target: 3 / 3).
- [ ] iPhone PWA with screen auto-lock: confirm transition beep fires after lock-then-wake (existing behavior).
- [ ] Android Chrome PWA: same drill.
- [ ] Desktop Chrome (foreground tab): same drill.
- [ ] Existing CircuitTimer countdown still works (regression check on shared `audio-unlock.ts`).

---

## Phase 0 audit ready, awaiting OK.
