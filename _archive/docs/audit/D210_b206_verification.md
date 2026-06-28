# D210 — B206 Verification Audit (before/after comparison)

**Date:** 2026-04-17
**Scope:** Concrete evidence that B206 (commit `948558e`) fixes the location-
precedence bug without introducing regressions.
**Methodology:** Git worktree at `948558e^` (pre-B206) vs main (post-B206). Same
scenario inputs fed to `resolve_session()` on both trees. Equipment compatibility
re-checked against resolver's own equipment list.

---

## 1. Executive summary

**Verdict: ✅ PASS — ship.**

- **Core bug is fixed**: The exact Daniele 2026-04-17 case (`finger_maintenance_gym`
  planned at home) no longer pulls wall-only exercises because the resolver
  respects `user_state.context.location` instead of the stale
  `session.context.location="gym"` template hint.
- **No regression** on any of the 10 planned sessions in Daniele's real
  production state: gym sessions resolve identically; home sessions improve or
  stay the same.
- **One residual issue surfaced** (pre-existing, out of B206 scope):
  `warmup_easy_boulders` in template `warmup_climbing` is referenced by explicit
  `exercise_id` and bypasses P0 equipment filtering, so it still appears in
  hangboard-only home contexts. Logged as **follow-up brief B207 (proposed)**.

---

## 2. Daniele case — exact reproduction

Session `finger_maintenance_gym` placed by planner at `ss.location="home"`
(via `_expand_session_locations` — home has hangboard, satisfies
`required_equipment`).

| | Before B206 | After B206 |
|---|---|---|
| `location_used` | `gym` ❌ | `home` ✅ |
| `available_equipment` | `[gym_boulder, gym_routes, spraywall, hangboard, …]` (first-gym fallback) | `[hangboard, pullup_bar, band, dumbbell, loading_pin, resistance_band, weight]` ✅ |
| Exercise count | 16 | 16 |
| Wall-surface exercises | **2** (`aerobic_pyramid_intervals`, `warmup_easy_boulders`) | **1** (`warmup_easy_boulders` — see §5) |
| Exercises removed | — | `aerobic_pyramid_intervals`, `forearm_pronation_supination`, `scapular_pullup`, `shoulder_car` |
| Exercises added | — | `archer_pullup`, `band_external_rotation`, `band_pull_apart`, `elbow_eccentric_curl` |

The originally-reported bug exercise — `aerobic_pyramid_intervals` — is gone.
Replacement exercises are all hangboard/band-compatible for home context.

---

## 3. Scenario matrix (5 synthetic + 1 Daniele)

All six scenarios run against the worktree at `948558e^` (BEFORE) and main
(AFTER). Columns show `location` and wall-surface exercise count.

| Scenario | BEFORE loc / wall | AFTER loc / wall | Verdict |
|---|---|---|---|
| `daniele_friday` | gym / 2 | home / 1 | ✅ Bug fixed |
| `strength_gym_no_hangboard` | gym / 1 | gym / 1 | ✅ No regression |
| `homewall_boulder` (board_kilter at home) | gym / 1 | home / 2 | ✅ Correct: board expands to gym_boulder so boulder exercises now resolve at home |
| `climbing_gym_full` | gym / 2 | gym / 2 | ✅ No regression |
| `incompatible_gym` (no wall) | gym / 1 | gym / 1 | Identical (shows warmup bypass is pre-existing) |
| `legacy_home_hangboard` | home / 0 | home / 0 | ✅ No regression |

Notable: `homewall_boulder` shows that B206 *enables* a correct behavior that
was previously suppressed — user with `board_kilter` at home now gets boulder
exercises resolved from their board, because `expand_equipment()` maps
`board_kilter → gym_boulder`. Pre-B206, the template's `location=gym` hint
forced the resolver to look at empty gym list and miss these.

---

## 4. Production regression (Daniele's real state, 10 planned sessions)

All 10 non-done/skipped sessions in Daniele's production `week_plans`
(dates `2026-04-17` … `2026-04-26`) resolved against both trees with the
same `user_state` and same planner-assigned `(location, gym_id)` per session.

| Date | Session | Planner loc | BEFORE: loc/wall/real-incompat* | AFTER: loc/wall/real-incompat | Δ |
|---|---|---|---|---|---|
| 2026-04-17 | finger_maintenance_gym | home | gym / 2 / **2** | home / 1 / **1** | ✅ −1 incompat |
| 2026-04-18 | power_endurance_gym | gym | gym / 3 / 0 | gym / 3 / 0 | — |
| 2026-04-19 | endurance_aerobic_gym | gym | gym / 2 / 0 | gym / 2 / 0 | — |
| 2026-04-20 | technique_focus_gym | gym | gym / 4 / 0 | gym / 4 / 0 | — |
| 2026-04-21 | finger_strength_home | home | home / 0 / 0 | home / 0 / 0 | — |
| 2026-04-22 | route_endurance_gym | gym | gym / 3 / 0 | gym / 3 / 0 | — |
| 2026-04-23 | power_endurance_gym | gym | gym / 3 / 0 | gym / 3 / 0 | — |
| 2026-04-24 | finger_maintenance_gym | home | gym / 2 / **2** | home / 1 / **1** | ✅ −1 incompat |
| 2026-04-25 | endurance_aerobic_gym | gym | gym / 2 / 0 | gym / 2 / 0 | — |
| 2026-04-26 | flexibility_full | gym | home / 0 / 0 | gym / 0 / 0 | ✅ location corrected |

\* **real-incompat** = exercises whose `equipment_required` / `equipment_required_any`
has no intersection with the equipment actually available at the user's
*planner-assigned* location (home, in incompat cases). Pre-B206 the resolver
falsely reported 0 because it was reading gym equipment while the user was at
home — the real user-facing incompat was 2 per session.

**Delta**: 2 incompatible exercises shipped to Daniele → 1 incompatible
exercise. The residual one is `warmup_easy_boulders` (same root cause in both
finger_maintenance_gym sessions).

---

## 5. Residual finding — `warmup_easy_boulders` template bypass

**Not a B206 regression. Pre-existing gap.**

Template `backend/catalog/templates/v1/warmup_climbing.json` references
`warmup_easy_boulders` by explicit `exercise_id` (not by filter selection):

```json
{"exercise_id": "warmup_easy_boulders", "role": ["warmup"], ...}
```

Exercise requires ANY of:
`[gym_boulder, board_kilter, board_moonboard, board_other, spraywall, homewall]`.

Explicit `exercise_id` references skip P0 equipment filtering — the resolver
assumes the template author vetted compatibility. With the new correct location
resolution, this exercise now surfaces as "incompatible with available
equipment" at home.

**Recommendation**: New brief **B207** — harden `warmup_climbing` template to
either (a) use filter-based selection with equipment gate, or (b) add a
fallback `warmup_general_mobility` for climbing warmup when no wall surface is
available. Out of D210 / B206 scope.

---

## 6. Ship criteria

| Criterion | Status |
|---|---|
| Daniele case `aerobic_pyramid_intervals` gone from home context | ✅ |
| Zero wall-surface regressions at gym locations | ✅ |
| No previously-compatible session became incompatible | ✅ |
| Real-incompat count at home: was 2, now 1 | ✅ (50% improvement; residual is pre-existing) |
| All 1659 unit + integration tests pass | ✅ (run at commit `948558e`) |

**Ready for production: YES.**

Follow-up: open **B207** to close the template-bypass gap for
`warmup_easy_boulders` on hangboard-only home sessions.

---

## 7. Reproduction

```bash
git worktree add /tmp/climb-agent-before 948558e^
/path/to/.venv/bin/python /tmp/d210/harness.py \
  --root /tmp/climb-agent-before \
  --scenarios /tmp/d210/scenarios.json \
  --out /tmp/d210/before.json

/path/to/.venv/bin/python /tmp/d210/harness.py \
  --root /Users/danielesomensi/Projects/climb-agent \
  --scenarios /tmp/d210/scenarios.json \
  --out /tmp/d210/after.json
```

Scenario JSON and harness preserved at `/tmp/d210/` for re-runs.
