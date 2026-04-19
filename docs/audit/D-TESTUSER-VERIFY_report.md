# D-TESTUSER-VERIFY — Post-B209/B210 test user state verification

**Type:** D (read-only verification audit)
**Date:** 2026-04-19
**User audited:** `daniele.somensi@ferrero.com` (UUID `98f77487-5f4d-4d74-bd24-90661bbfa3da`)
**Storage row updated_at:** `2026-04-19T11:04:56+00:00` UTC
**Code state:** main @ `91c493d` (post-B209 `4911c17` + post-B210 `1dd6efe`)

---

## §1 — State dump

Source: Supabase `users` table, column `state` (JSONB). Full snapshot saved to `/tmp/d-testuser/state.json`.

### body
```
age: 3
height_cm: 33
weight_kg: 33
```

### goal
```
discipline: lead
goal_type: lead_grade
current_grade: 6c
target_grade: 7c+
target_style: redpoint
total_weeks: 12
deadline: ""                        # empty string
primary_weakness: (NOT IN goal)
secondary_weakness: (NOT IN goal)
```

### preferences
```
finger_training_device: hangboard
grade_system_boulder: (not set)
```

### equipment.home
```
["hangboard", "homewall"]
```
(Note: **no `pullup_bar`** — relevant for §3 placement logic.)

### equipment.gyms[0]
```
gym_id: fb27d294
name: Gym 1
equipment: [gym_boulder, gym_routes, spraywall, board_kilter, board_moonboard,
            board_other, campus_board, hangboard, loading_pin, pinch_block,
            pullup_bar, weight, dumbbell, barbell, bench, cable_machine,
            leg_press, resistance_band, rings, foam_roller, ab_wheel]
```

### availability
```
mon: evening / preferred=gym
tue: lunch   / preferred=gym
wed: evening / preferred=gym
thu: evening / preferred=home
fri: evening / preferred=home
sat: (no entry — unavailable)
sun: (no entry — unavailable)
```
→ **5 available slots, Fri/Sat/Sun rest**.

### initial_tests_requested
```
True
```

### assessment.profile (radar)
```
finger_strength: 100
pulling_strength: 100
power_endurance: 40
technique: 30
endurance: 42
```

### assessment.tests
```
max_hang_20mm_5s_total_kg: 150
max_hang_20mm_7s_total_kg: 150
weighted_pullup_1rm_total_kg: 160
last_test_date: 2026-04-16
```
→ `tests_source` **absent** (correctly — that's D211 scope).
→ `last_test_date = 2026-04-16` is 3 days before macrocycle start (2026-04-20) — provenance unclear, see §4.

### assessment.self_eval
```
primary_weakness: technique_errors
secondary_weakness: cant_read_routes
```
→ Weaknesses **are** stored here (not in `goal` as brief hinted).

### assessment.grades
```
lead_max_os: 5b
lead_max_rp: 6c
```

### assessment.last_assessed
```
2026-04-20
```

### baselines.hangboard[0]
```
source: estimated_from_grade          ← NOT "test" / "test_session" / "assessment"
grade_used: 6c
edge_mm: 20
grip: half_crimp
hang_seconds: 7
max_total_load_kg: 33.0                ← = bodyweight only (external load = 0)
estimated_at: 2026-04-19
updated_at: (NOT SET)
```

### baselines.pulling
```
source: assessment
weighted_pullup_1rm_total_kg: 160.0
max_external_load_kg: 127.0            ← = 160 − 33
bodyweight_kg: 33.0
updated_at: 2026-04-19                 ← ★ populated by onboarding estimator (RC2-symmetry risk)
```

### baselines.working_loads
```
count: 0                               ← fresh onboarding, no sessions done yet
```

### macrocycle
```
start_date: 2026-04-20                 ← Monday ✓
total_weeks: 12
generated_at: 2026-04-19T11:04:45
phases:
  - phase_id: base,            start_week: 1,  weeks: null    ← implied 4
  - phase_id: strength_power,  start_week: 5,  weeks: null    ← implied 3
  - phase_id: power_endurance, start_week: 8,  weeks: null    ← implied 2
  - phase_id: performance,     start_week: 10, weeks: null    ← implied 2
  - phase_id: deload,          start_week: 12, weeks: null    ← implied 1
```
→ Sum of implied deltas = 12 ✓. `weeks` field consistently `null`.

### week_plans["2026-04-20"] (Week 1, cached)
```
generated_at: 2026-04-19T11:04:53
planned_load: 210 (= 65+40+65+40)
days:
  2026-04-20 mon: [test_max_hang_7s]              load=65 ✓ B209 wiring live
  2026-04-21 tue: [endurance_aerobic_gym]         load=40
  2026-04-22 wed: [test_repeater_7_3]             load=65
  2026-04-23 thu: [technique_focus_gym]           load=40
  2026-04-24 fri: []                              ← EMPTY despite availability
  2026-04-25 sat: []                              (no availability)
  2026-04-26 sun: []                              (no availability)
```

### test_queue
```
None                                   ✓ as expected per D-TESTWEEK-AUDIT §4 H-B
```

---

## §2 — Onboarding input → state mapping

| Input (UI label) | Value entered | Stored at path | Stored value | Source annotation | Verdict |
|---|---|---|---|---|---|
| Weight | 33 kg | `body.weight_kg` | 33 | — | OK (absurd, no validation) |
| Height | 33 cm | `body.height_cm` | 33 | — | OK (absurd, no validation) |
| Age | 3 | `body.age` | 3 | — | OK (absurd, no validation) |
| Discipline | lead | `goal.discipline` | `lead` | — | OK |
| Current grade | 6c | `goal.current_grade` | `6c` | — | OK |
| Current grade | 6c | `assessment.grades.lead_max_rp` | `6c` | — | OK (duplicated on both paths) |
| Lead OS | 5b | `assessment.grades.lead_max_os` | `5b` | — | OK |
| Target grade | 7c+ | `goal.target_grade` | `7c+` | — | OK |
| Deadline | 12 weeks | `goal.total_weeks` | 12 | — | OK |
| Deadline | 12 weeks | `goal.deadline` | `""` | — | **ANOMALY**: deadline string empty despite total_weeks=12 |
| Primary weakness | technique_errors | `goal.primary_weakness` | **(not stored)** | — | **ANOMALY (spec drift)**: brief expects it here |
| Primary weakness | technique_errors | `assessment.self_eval.primary_weakness` | `technique_errors` | — | OK (actual storage path) |
| Secondary weakness | cant_read_routes | `assessment.self_eval.secondary_weakness` | `cant_read_routes` | — | OK |
| Primary weakness effect | technique_errors | `assessment.profile.technique` | 30 | — | OK (penalty applied, see `assessment_v1.py:264-270`) |
| Max Hang 20mm / 7s | 150 kg | `assessment.tests.max_hang_20mm_7s_total_kg` | 150 | (none — pre-D211) | OK (stored verbatim) |
| Max Hang 20mm / 7s | 150 kg | `assessment.tests.max_hang_20mm_5s_total_kg` | 150 | (none) | OK (dual-key write per D-BASELINE-AUDIT §2) |
| Max Hang 20mm / 7s | 150 kg | `baselines.hangboard[0].max_total_load_kg` | **33.0** | `source=estimated_from_grade`, `grade_used=6c` | **⚠️ ANOMALY**: user's 150 kg is **NOT propagated**. Baseline is estimated from grade (33 + 0 offset = 33 kg = bodyweight). |
| Weighted Pull-up 1RM | 160 kg | `assessment.tests.weighted_pullup_1rm_total_kg` | 160 | (none) | OK (stored verbatim) |
| Weighted Pull-up 1RM | 160 kg | `baselines.pulling.weighted_pullup_1rm_total_kg` | 160.0 | `source=assessment`, `updated_at=2026-04-19` | OK (propagated — but see §3.2 re: `updated_at`) |
| Weighted Pull-up 1RM | 160 kg | `baselines.pulling.max_external_load_kg` | 127.0 | (=160−33) | OK |
| Finger training device | hangboard | `preferences.finger_training_device` | `hangboard` | — | OK |
| Availability (5 days) | mon/tue/wed/thu/fri | `availability.{wd}.{slot}` | as listed | — | OK |
| Initial tests | "Do a test week first" | `initial_tests_requested` | `True` | — | OK |
| Last test date | (derived?) | `assessment.tests.last_test_date` | `2026-04-16` | — | **ANOMALY**: 3 days before macrocycle start_date. No user input matches this value — provenance unclear. |

**Core-question answer (user-entered values vs. baselines):**
- **Max hang 150 kg is NOT used** to populate `baselines.hangboard`. The baseline is re-estimated from `lead_max_rp=6c` via `GRADE_TO_HANG_OFFSET` table (`progression_v1.py:122-129`), yielding `bodyweight + 0 = 33 kg`. The scalar survives in `assessment.tests.*` but is decoupled from the baseline.
  - Reference: `progression_v1.py:682-697` — `_estimate_hangboard_baseline` always prefers `lead_max_rp` grade over user-entered scalars. **Priority 2 (user scalar) only fires if no `lead_max_rp` is set.**
  - This is a **design gap**, not a bug introduced by B209/B210. Flagged here for D211 scope.
- **Pullup 160 kg IS propagated** to `baselines.pulling` via `_estimate_pulling_baseline` (`progression_v1.py:740-776`), which reads `assessment.tests.weighted_pullup_1rm_total_kg` directly.

---

## §3 — Why no pulling test in Week 1?

### Observed

Production-cached `week_plans["2026-04-20"]`: Fri `[]` (empty) — no `test_max_weighted_pullup` or `test_pullup_bw` anywhere in Week 1.

### Check 3.1 — Was it ever considered?

`planner_v2.py:1280`:
```python
_pulling_test_sid = _pick_pulling_test_session(pulling_baseline, max_pullups_bw)
```

With this user's data (`pulling_baseline` present, `max_pullups_bw=None`):
`planner_v2.py:575-576` returns `"test_max_weighted_pullup"` (pulling_baseline truthy → first branch hit).

**Reproduced live** (Python repl, current main code):
```
_pick_pulling_test_session returned: test_max_weighted_pullup
```
✅ Considered.

### Check 3.2 — Did the freshness check skip it?

`week.py:338-340` (current post-B210):
```python
_pulling_bl = (state.get("baselines") or {}).get("pulling") or {}
if _pulling_bl.get("updated_at"):
    _recent_test_dates["pulling"] = _pulling_bl["updated_at"]
```

This user's state: `baselines.pulling.updated_at = "2026-04-19"`.
→ `recent_test_dates["pulling"] = "2026-04-19"` at planner call.

**Who wrote `updated_at`?** `_estimate_pulling_baseline` at `progression_v1.py:771`:
```python
new_pulling = {
    ...
    "source": "assessment",
    "updated_at": today,                 # ← onboarding "today", NOT a real test completion
}
```

→ **This IS the RC2-symmetry bug** on the pulling axis. `updated_at` is stamped with onboarding's date, identical pattern to the finger-axis bug that B210 fixed via `estimated_at` drop. On the pulling axis, the field name is `updated_at` (same name the planner trusts as "last real test date"), so week.py cannot discriminate estimate from completion.

**Does it block this specific user?** Planner `inject_tests=True` → B210 bypass at `planner_v2.py:1318` kicks in:
```python
if last_date_str and not inject_tests:  # B210: ...
```
→ Freshness check **bypassed for this user**. NOT the blocker here.

**BUT**: on normal last-week-of-phase retest injection (no `inject_tests` flag), the pulling retest will be skipped for 42 days post-onboarding. See §5 F3 for impact.

### Check 3.3 — Was it dropped during placement?

Since 3.1 returned a valid session_id and 3.2 didn't block it (inject_tests=True bypass), placement is the remaining suspect.

**Live reproduction** with current main code + saved state → **Fri gets `test_max_weighted_pullup`**:
```
2026-04-20 mon: [test_max_hang_7s]
2026-04-21 tue: [endurance_aerobic_gym]
2026-04-22 wed: [test_repeater_7_3]
2026-04-23 thu: [technique_focus_gym]
2026-04-24 fri: [test_max_weighted_pullup]   ← placed
```

Cached state: Fri `[]` (empty).

→ **The cached plan is stale — generated with pre-B210 planner code**.

**Timing evidence:**
| Event | Time (UTC) |
|---|---|
| B209 git push | 10:35:57 |
| B210 git push | 10:54:27 |
| Railway redeploy (typical) | +2–3 min |
| Macrocycle generated | 11:04:45 |
| Week plan generated | 11:04:53 |
| State row persisted | 11:04:56 |

→ ~10 min between B210 push and state persist. Either Railway was slower than typical, or the onboarding request hit a container that hadn't reloaded yet. Not reproducible post-factum.

**Simulation** of pre-B210 planner against this state (monkey-patched `if last_date_str:` without the `and not inject_tests` guard):
```
2026-04-20 mon: [test_max_hang_7s]
2026-04-21 tue: [endurance_aerobic_gym]
2026-04-22 wed: [test_repeater_7_3]
2026-04-23 thu: [technique_focus_gym]
2026-04-24 fri: [boulder_circuit_gym]        ← complementary (not empty), NOT test
2026-04-25 sat: []
2026-04-26 sun: []
```
Pre-B210 simulation fills Fri with `boulder_circuit_gym`, not empty. Observed state has Fri **empty**. Neither of my reproductions (pre-B210 or current) produces exactly empty Fri. The divergence suggests the production run had a further difference (different defaults for `planning_prefs.target_training_days_per_week`, or a cached `current_week_plan` truncation), but the **root cause of the missing pulling test is RC2-symmetry + stale cache**.

### One-line root cause

The cached Week 1 plan was computed before B210 reached the Railway container; the pre-B210 freshness check treated the onboarding-written `baselines.pulling.updated_at` as a fresh real test and skipped the pulling retest. Post-B210, the planner now places `test_max_weighted_pullup` on Fri for this exact state.

---

## §4 — Incoherence scan

| Check | Result | Evidence |
|---|---|---|
| **Radar profile finite/clean with absurd inputs?** | Yes — all values in [0, 100], no NaN/inf. Finger and pulling **saturate to 100**; technique penalized to 30 (weakness applied); PE=40, endurance=42. | `assessment.profile` dump in §1; reproduced via `compute_assessment_profile`. |
| **`macrocycle.start_date` a Monday?** | **Yes**. `2026-04-20` → `Monday`. | `datetime.strptime("2026-04-20").strftime("%A")` |
| **Phase `weeks` sum to 12?** | Sum via `start_week` deltas = 12 ✓. But `phases[].weeks` is **consistently `null`** — consumer unknown. | §1 macrocycle dump. |
| **Week 1 load = sum of session loads?** | 65+40+65+40 = 210 = `planned_load` ✓ | §1 dump |
| **Weakness → technique axis penalty?** | Yes. `technique_errors` → technique=30 (low end of scale). `assessment_v1.py:264-270` applies penalty. | Code + state |
| **Hangboard baseline grade source?** | `lead_max_rp=6c` → offset 0 → `bw + 0 = 33` kg. `GRADE_TO_HANG_OFFSET["6c"] = 0` at `progression_v1.py:123`. | Code + state |
| **User's 150 kg hang value vs. grade estimate — silently diverge?** | **Yes — silently**. User-entered 150 kg (3.5× BW, implausible) is stored in `assessment.tests.max_hang_20mm_7s_total_kg` but `baselines.hangboard[0].max_total_load_kg = 33`. No validation bounds on the input (absurd numbers accepted); no warning on 117× discrepancy. | §2 + code |
| **Pull-up 1RM handling — direct use?** | Yes. `_estimate_pulling_baseline` reads `weighted_pullup_1rm_total_kg` and writes baseline directly, computing `max_external = 160 − 33 = 127 kg` (3.8× BW, also absurd). | `progression_v1.py:753-772` |
| **`test_queue` empty/None for fresh onboarding?** | `None` ✓. | §1 dump |
| **Onboarding `last_test_date` provenance** | `2026-04-16` — 3 days before macrocycle start. No user input date matches. No explicit writer identified in a quick grep. **Low-severity provenance anomaly**. | State dump — writer not conclusively traced in this audit. |
| **`goal.deadline` empty string while `total_weeks=12`** | `""` stored — downstream consumers reading `deadline` will see empty. Unknown if intentional or onboarding gap. | §1 dump |
| **`baselines.pulling.updated_at` = onboarding date** | `2026-04-19` = today. Stamped by estimator, not by test completion. **RC2-symmetry risk** (see §5 F3). | `progression_v1.py:771` |
| **Home equipment lacks `pullup_bar`** | Yes — Fri slot preferred=home would fail pulling test equipment gate even if placement allowed empty-day injection. | §1 dump |

---

### Validation gate before §5

- [x] User state dump captured in §1 (all fields listed)
- [x] Onboarding input mapping table in §2 (21 rows)
- [x] Check 3.1 completed: `_pick_pulling_test_session` → `test_max_weighted_pullup`
- [x] Check 3.2 completed: `baselines.pulling.updated_at` exists, written by `_estimate_pulling_baseline` at `progression_v1.py:771`
- [x] Check 3.3 completed: stale cache + pre-B210 freshness produced the observed absence
- [x] 13 incoherence checks executed with evidence
- [x] Root cause of pulling-test absence stated in one line (§3 last paragraph)

---

## §5 — Findings summary

| ID | Finding | Severity | Recommendation |
|---|---|---|---|
| **F1** | **`_estimate_hangboard_baseline` ignores user-entered `max_hang_20mm_7s_total_kg`.** Priority 1 is `lead_max_rp` grade; Priority 2 (pullup 1RM) only fires if no `lead_max_rp`. The explicit user input is never considered. For this user, declared 150 kg is stored in `assessment.tests` but baseline remains at 33 kg (grade estimate). All downstream training loads are computed from the grade estimate, not the user's measurement. | **HIGH** | Fold into D211: add Priority 0 — if `assessment.tests.max_hang_20mm_7s_total_kg` is set, use it directly as `max_total_load_kg` with `source="user_entered"` or `source="measured"`. Preserves current fallback chain for users who skip. |
| **F2** | **No validation bounds on body metrics or test inputs.** `BW=33 kg`, `height=33 cm`, `age=3`, `max_hang=3.5× BW`, `pullup=3.8× BW` all accepted silently. Radar saturates to 100 on finger/pulling without warning. | **MEDIUM** | Add input validation at onboarding endpoint (reasonable ranges: BW 35–150 kg, height 120–220 cm, age 10–80, max_hang ≤ 3× BW as soft-warn). Not blocking for v1 launch; flag for onboarding hardening brief. |
| **F3** | **RC2-symmetry on pulling axis**: `_estimate_pulling_baseline` writes `updated_at = today` on onboarding estimate (`progression_v1.py:771`). Same conflation bug pattern as the finger-axis bug B210 fixed via `estimated_at` drop, but on pulling the field is literally `updated_at` (the name week.py trusts). B210's `inject_tests=True` planner bypass masks this for new users' test-week flow. **But**: on natural `is_last_week_of_phase` pulling retests (no `inject_tests`), pulling retest is skipped for 42 days after onboarding. | **HIGH** | Fold into D211. Two options: (a) stop writing `updated_at` in `_estimate_pulling_baseline` (align with finger where estimator writes `estimated_at` and consumer drops the fallback), or (b) add `source`-based freshness gating in `week.py` (`updated_at` honored only when `source in {"test", "test_session"}`). D211's source-based semantics is the cleaner fix. |
| **F4** | **Cached week plan can be stale vs. current code.** Onboarding completed ~10 min after B210 push; plan generated by pre-B210 code persists in `week_plans["2026-04-20"]` even though post-B210 reproduction yields different output. No regeneration trigger on deploy. | **LOW** | Accept. Users affected by deploy-window stale plans can re-trigger via `force=true` on `/api/week/0` or Settings → regenerate. Not worth a forced invalidation — bounded to a ~5 min window per deploy. Mention in user guide or monitoring. |
| **F5** | **`primary_weakness`/`secondary_weakness` stored at `assessment.self_eval.*`, NOT at `goal.*`.** Brief anticipated `goal.primary_weakness` — not present. Weaknesses work correctly (technique penalty applied), but any consumer looking at `goal.primary_weakness` would see `None`. | **LOW** | Verify all consumers read from `assessment.self_eval.*`. If any reads `goal.*`, fix the read site (not the write). Spec-drift, not behavioral bug. |
| **F6** | **`macrocycle.phases[].weeks` field consistently `null`.** Sum via `start_week` deltas gives 12 correctly, but any consumer iterating `phases[].weeks` will see `null`. | **LOW** | Audit consumers (quick grep). If all compute from `start_week` deltas, remove the field from schema (D211 scope). If some read `weeks` directly, populate at generation. |
| **F7** | **`goal.deadline` empty string while `total_weeks=12`**. Onboarding stores `deadline=""` when deadline derived from `total_weeks`. | **LOW** | Cosmetic. Fix write path to compute ISO date from `total_weeks + start_date`, or drop the field. Not blocking. |
| **F8** | **`assessment.tests.last_test_date = "2026-04-16"`** (3 days before macrocycle start). No user input matches; writer not traced in this audit's time-box. | **COSMETIC** | Park. Add a quick grep in D211 Phase 0 to identify the writer; if it's the legacy-update path in progression_v1.py, scope into D211 test-log cleanup. |
| **F9** | **Pass 3 placement requires non-empty day** (`planner_v2.py:1360`: `if not day_sessions[offset]: continue`). Tests can only replace existing sessions, never inject into empty slots. Combined with hard-day spacing (gap=1), users with few available days can silently lose test sessions. | **MEDIUM** | Investigate in a follow-up brief. For this specific user Fri was filled post-B210, so no immediate impact. But the `required=False` flag on pulling test means in constrained weeks it will still be the first to drop. Consider loosening the empty-day rule for test sessions, or ordering `required=True` first across axes. |

**Scope guidance for D211:**
- **F1 and F3 must be addressed** in D211. Both are source-of-truth semantics that D211 targets directly. F1 adds a priority for user-entered hang value; F3 switches pulling freshness to source-based gating.
- **F2** is orthogonal (input validation) — park as a separate onboarding hardening brief.
- **F5/F6/F7/F8** are spec-drift or cosmetic. Don't block D211. Bundle them if D211 touches adjacent paths; otherwise park.
- **F4** is deploy-timing artifact, not a code bug.
- **F9** is a pre-existing planner constraint, out of B209/B210/D211 scope. File as separate brief if it recurs.

---

## §6 — STOP gate

```
═══════════════════════════════════════════════
  D-TESTUSER-VERIFY COMPLETE — STOP
═══════════════════════════════════════════════
Anomalies found: 9 (BLOCKER: 0, HIGH: 2, MEDIUM: 2, LOW: 4, COSMETIC: 1)
Pulling test absence root cause: Cached Week 1 was generated by pre-B210 code (stale cache); the pre-B210 freshness check treated onboarding-written baselines.pulling.updated_at as a fresh real test. Post-B210 reproduction now places test_max_weighted_pullup on Fri for this exact state.
Ready for Daniele to decide: fold F1+F3 into D211 scope; park or split F2/F5-F9.
═══════════════════════════════════════════════
```
