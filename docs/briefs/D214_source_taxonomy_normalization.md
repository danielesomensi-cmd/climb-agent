# D214 — Source Taxonomy Normalization (Bundle B continuation)

**Type:** D (cross-module refactor, read → design → implementation)
**Priority:** Pre-paid-launch (closes F1 + F3 from D-TESTUSER-VERIFY)
**Prerequisites:** B209 ✅ merged, B210 ✅ merged (on `main`)
**Model:** Opus for Phase 0 + Phase 1 (per handoff)
**Branch rule:** backend + docs only → push directly to `main` (no preview)

> This brief was reconstructed on 2026-04-20 from the 3 audit reports below.
> The original `D211_source_taxonomy_normalization.md` handoff file was not
> found on disk. Brief number bumped to **D214** because D211 is already
> used for `D211_body_part_picker_audit`.

## 1. Context

Bundle B = baseline + test-week remediation. Two briefs already merged:

- **B209** wired `test_max_hang_7s` into the planner (closed RC1 from D-TESTWEEK-AUDIT).
- **B210** dropped `estimated_at` fallback in the finger-axis freshness check + bypassed the freshness check when `inject_tests=True` (closed RC2).

Empirical verification on `daniele.somensi@ferrero.com` (D-TESTUSER-VERIFY,
2026-04-19) confirmed B210 works and surfaced two **open** findings:

- **F1 (HIGH):** `_estimate_hangboard_baseline` (progression_v1.py:665) ignores
  a user-entered `max_hang_20mm_7s_total_kg=150` at onboarding and overrides it
  with a grade-based estimate. The 150 lives in `assessment.tests.*` but never
  reaches `baselines.hangboard[0].max_total_load_kg`.
- **F3 (HIGH):** `_estimate_pulling_baseline` (progression_v1.py:740) stamps
  `updated_at=today` when seeding a baseline from a grade/pullup estimate.
  Same bug class B210 fixed for finger, still latent for pulling. Masked for
  new users by the `inject_tests=True` bypass, but blocks natural
  last-week-of-phase retests for 42 days post-onboarding.

**Out of scope, do NOT touch:** the known `_PHASE_TEST_MAP["base"]` behavioural
gap (only 1 of 3 tests scheduled in Week 1 with 2 available days, other 2 lost
because repeater retest re-enabled only in Week 3). Parked post-launch.

## 2. Goal

Introduce a **2-level source taxonomy** on every `assessment.tests.*` scalar,
so the engine can distinguish **measured** (user-entered test results or
post-session feedback) from **estimated** (derived from grade/experience).

## 3. Frozen design decisions (do NOT re-litigate)

1. **Two levels only:** `"estimated"` | `"measured"`. No third level, no
   confidence scores.
2. **Schema shape — Option A (sidecar):** `assessment.tests_source: {test_id:
   "estimated"|"measured"}`, parallel to `assessment.tests`. Scalars in
   `assessment.tests` remain scalar.
3. **No migration script** for existing beta testers. Default `"estimated"`
   applied silently in the reader when the key is missing.
4. **F1 and F3 are IN scope** and must be fully closed by this refactor.

## 4. Modules in scope

- `backend/engine/progression_v1.py` (`_estimate_hangboard_baseline`,
  `_estimate_pulling_baseline`, `_update_test_from_log`)
- `backend/api/routers/onboarding.py` (writer at intake)
- `backend/api/routers/week.py` (freshness check → `source=="measured"`
  instead of `updated_at`)
- `backend/api/routers/feedback.py` (indirect: goes through
  `_update_test_from_log`)
- `backend/engine/assessment_v1.py` (read-only — no gating required;
  assessment score math is source-agnostic by design)
- `backend/engine/resolve_session.py` — `suggest_max_hang_load` fallback at
  line 153 reads `assessment.tests`; evaluate whether to gate on source
- `docs/vocabulary_v1.md` (add §2.10.3 or similar — formal definition of
  `assessment.tests_source`)

## 5. Scope boundary

- `baselines.*.source` keeps its existing values and semantics
  (`"estimated_from_grade"`, `"estimated_from_pullup"`, `"assessment"`,
  `"test"`, `"test_session"`). The new `tests_source` sidecar operates at a
  different layer (scalar origin, not baseline origin).
- Loading-pin baselines are out of scope — orthogonal and already use
  `source: "test"` correctly.
- `tests` (top-level history log, append-only) is not touched — each entry
  already records `confidence`/`freshness_policy`.

## 6. Protocol

- **Phase 0:** analysis-only, output = `docs/briefs/D214_phase0_analysis.md`,
  followed by hard **STOP** and wait for explicit `OK Phase 1`.
- **Phase 1:** implementation in 3 atomic commits (refactor / tests / docs).
- **Phase 2:** full `pytest` + empirical verification on ferrero test user
  (F1 + F3 closure), `sync_status.py`, push.
