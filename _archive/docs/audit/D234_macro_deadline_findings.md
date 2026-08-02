# D234 — `goal.deadline` vs `total_weeks` coupling (read-only follow-up to D233)

**Brief:** D-MACRO-DEADLINE (D234)
**Date:** 2026-05-07
**Mode:** Read-only — no source / state mutations.
**Time:** ~25 min.
**Question:** Is `goal.deadline` (ISO date) coupled to `total_weeks` anywhere, or are
they independent inputs?

---

## Conclusion: **A** — they are independent inputs.

`total_weeks` is the *source of truth*. `goal.deadline` is **derived from
`total_weeks`** in every UX path that creates or modifies a macrocycle, and is
**never read back to compute `total_weeks`** anywhere in the engine, the routers,
or the frontend regenerate flow. The "what to do with weeks before cycle start"
problem from KB Q4-a does not exist in the current architecture: capping
`total_weeks ≤ 16` is sufficient and self-contained.

The only nuance — and it is small — is that the **Settings → Edit Goal** dialog
lets the user pick a date directly, but that date is saved to `state.goal.deadline`
**without** recomputing `total_weeks`. The subsequent macrocycle regenerate uses
either the previous cycle's `total_weeks` (incremental) or a hardcoded `12`
(restart). See §Caveat below.

---

## Check 1 — Where is `goal.deadline` read and written?

### Writers (UI surfaces that set `goal.deadline`)

| File:line | Path | What it writes |
|---|---|---|
| `frontend/src/app/onboarding/goals/page.tsx:255` | Onboarding step 7 (Goals) | `setGoal({ total_weeks: v, deadline: weeksToDeadlineIso(v) })` — slider sets weeks; deadline computed as `today + N×7 days` |
| `frontend/src/components/settings/start-new-macrocycle-dialog.tsx:246-248` | Settings → Plan Next Cycle | Sends to backend `{ deadline: weeksToDeadlineIso(deadlineWeeks), total_weeks: deadlineWeeks }` — both derived from slider |
| `frontend/src/components/settings/goal-editor.tsx:140` | Settings → Edit Goal | Sends `{ deadline }` from a `<Input type="date">` — the **only** UX surface where the user picks a date directly |

### Backend writes

| File:line | What it writes |
|---|---|
| `backend/api/routers/macrocycle.py:202` | `new_goal["deadline"] = goal_in.deadline` — pass-through during `start-new-cycle` |
| `backend/api/routers/onboarding.py` (no direct write) | `goal.deadline` flows through the standard `PUT /api/state` deep-merge from the onboarding payload |

### Readers

| File:line | What it does | Classification |
|---|---|---|
| `backend/api/routers/macrocycle.py:51-62` | `POST /api/macrocycle/generate`: validates `deadline` is not in the past; non-fatal on parse failure | **Validation only** — never derives `total_weeks` |
| `backend/api/routers/macrocycle.py:158-168` | `POST /api/macrocycle/start-new-cycle`: validates `goal_in.deadline` is not closer than the engine minimum (`today + 5 weeks`) | **Validation only** |
| `backend/engine/macrocycle_v1.py:649` | Copies `goal.get("deadline")` into `goal_snapshot` on the macrocycle dict | **Decorative** — used for UI labels, never re-read by the engine |
| `frontend/src/app/(main)/settings/page.tsx:434-436` | Renders the deadline as a localized date in the goal card | **UI display only** |
| `frontend/src/components/settings/goal-editor.tsx:64-115` | Form state + future-date validation | **UI form state only** |
| `frontend/src/components/settings/start-new-macrocycle-dialog.tsx:174-175` | `deadlineIsoToWeeks(currentGoal.deadline, ...)` to seed the slider with the current cycle's duration | **One-way conversion** for slider seeding; the slider then becomes the source of truth |

**No reader anywhere derives `total_weeks` from `deadline`.**

---

## Check 2 — Is `total_weeks` derived from `deadline` in any code path?

Searched for: `(deadline - start)`, `toordinal()`, `days // 7`, `weeks_from_deadline`,
`compute_total_weeks_from_deadline`, and ad-hoc patterns involving `deadline` and a
weeks computation in the same expression.

**No matches.**

The closest things to a derivation are the two helper functions in
`frontend/src/components/shared/deadline-weeks-selector.tsx`:

- `weeksToDeadlineIso(weeks)` (line 79): `today + N×7 days → ISO string`. This goes
  weeks → date.
- `deadlineIsoToWeeks(deadlineIso, defaultWeeks, min, max)` (line 86): `(date − today) / 7,
  rounded`, with a fallback to `defaultWeeks` if outside `[min, max]`. This goes
  date → weeks.

The second helper is the only "deadline drives weeks" routine in the codebase.
It is invoked in **exactly one place**: `start-new-macrocycle-dialog.tsx:174` to
seed the slider's *initial* value from the existing goal's deadline. The user
then adjusts the slider, which becomes the source of truth for the rest of the
flow. This is a one-shot UI seed — not a runtime coupling.

---

## Check 3 — Onboarding flow

```
frontend/src/app/onboarding/goals/page.tsx
  └─ <DeadlineWeeksSelector min=8 max=24 />        (slider)
       └─ on change: setGoal({ total_weeks: v, deadline: weeksToDeadlineIso(v) })
                                                    └─ both fields go into state.goal

[user submits]
  └─ POST /api/onboarding/complete                  (backend: routers/onboarding.py)
       ├─ default_weeks = 10 if discipline=="boulder" else 12   (line 416)
       ├─ total_weeks = goal.get("total_weeks", default_weeks)  (line 416) ← reads goal.total_weeks
       ├─ total_weeks = max(min_weeks, min(total_weeks, 52))    (line 419) ← clamps to [5/9, 52]
       └─ generate_macrocycle(..., total_weeks=total_weeks)     (line 420)
                                                    └─ deadline is NOT consulted
```

The onboarding form asks for **a number of weeks** (slider). The deadline is
*emitted* alongside `total_weeks` so the goal card can display "target by Oct 30",
but only `total_weeks` reaches the engine. The user does not pick a date directly
in onboarding.

---

## Caveat — Settings → Edit Goal can desync deadline from total_weeks

The `GoalEditor` dialog (`frontend/src/components/settings/goal-editor.tsx`) lets
the user pick a `<Input type="date">` deadline (line 230-236). On confirm
(`handleGoalConfirm` in `settings/page.tsx:222-237`):

1. `await putState({ goal: newGoal })` — saves the new deadline into `state.goal`.
2. `await computeAssessment(...)` — recomputes profile against the new goal.
3. Opens the regen sheet.
4. Regen sheet calls `generateMacrocycle(undefined, 12, fromPhase)` (`settings/page.tsx:286`):
   - Hardcoded `12` weeks.
   - With `fromPhase="current"`, the backend (`routers/macrocycle.py:84`) **ignores**
     the request's `total_weeks` and uses `old_mc.get("total_weeks", 12)` instead.
   - With `fromPhase=undefined` (Restart), the backend uses the request's
     `total_weeks=12` verbatim.

Net effect: editing the goal's deadline in Settings **does not change
`total_weeks`**. `goal.deadline` becomes a label-only field that may diverge from
what the macrocycle actually plans. This is a small UX inconsistency, not a
correctness issue for the upcoming cap rewrite — but it confirms that the engine
side of the system treats the two as fully independent.

If the A-brief wants a tighter UX, it could either:
- Replace the Edit-Goal date picker with a weeks slider (consistent with onboarding).
- Or, on goal-confirm, recompute `total_weeks = round((deadline - today) / 7)`
  clamped to `[min_weeks, 16]` and pass it explicitly to `generateMacrocycle`.

Neither change is required to land the 16-week cap — it just removes a long-
standing soft inconsistency.

---

## Recommendation for the A-brief

Treat `total_weeks` as the **single source of truth** for cycle length.
`goal.deadline` is a derived/decorative field; do not introduce a new
deadline → total_weeks derivation in the engine.

Concrete plan items the A-brief should include (all small):

1. **Cap `total_weeks` at 16** at three layers (matches the existing pattern):
   - `frontend/src/components/shared/deadline-weeks-selector.tsx:37` — change
     `max = 24` → `max = 16`.
   - `backend/api/routers/onboarding.py:419` — change `min(total_weeks, 52)` →
     `min(total_weeks, 16)`.
   - `backend/api/routers/macrocycle.py:112` — change `_TOTAL_WEEKS_MAX = 52` →
     `_TOTAL_WEEKS_MAX = 16`.
   - Add a peer constant `_MAX_TOTAL_WEEKS = 16` in `macrocycle_v1.py` next to
     `_MIN_TOTAL_WEEKS = 9` and raise on excess (defense in depth).
2. **Optionally** (out of cap scope, in scope of the same A-brief if cheap):
   harmonize the Settings goal-editor to either drop the date picker for a
   slider, or recompute `total_weeks` on goal-confirm. Flag in the A-brief PR
   description if deferred.
3. **No engine logic needs to consult `goal.deadline`.** Continue passing
   `total_weeks` explicitly.
4. The follow-up "phase cap" work from D233 (base ≤ 4, performance floor for
   advanced lead, etc.) is fully orthogonal to deadline handling — design it on
   `total_weeks` alone.

The KB Q4-a worry ("what about weeks between cycle end and the absolute
deadline?") **does not arise** because there is no absolute deadline driving the
plan length — the user picks a duration, and the plan ends when it ends.

---

*End of D234 findings. Awaiting OK before any A-brief implementation moves
forward.*
