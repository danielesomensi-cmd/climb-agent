# E2E Test Results — Macrocycle Engine

> Date: 2026-02-14 (original), updated 2026-02-15 post Cluster 1+2 fixes
> Tester: Claude Code + Daniele Somensi
> Engine version: Fase 1 complete + Cluster 1 + Cluster 2 fixes
> User state: v1.5 (goal: 8b redpoint, current: 8a+, 77kg, 10y experience)
> Tests: 155 passing

---

## Test Flow

9 step sequenziali, ognuno validato interattivamente dall'utente (climber reale).

| Step | Area | Verdict |
|------|------|---------|
| 1. Verify data | user_state.json | ✅ Corretto dopo fix |
| 2. Assessment | 6-axis profile | ✅ PE score corretto con repeater test |
| 3. Macrocycle | 12w generation | ✅ Struttura ok, goal validation, floor minimo |
| 4. Week plans | Per-phase weeks | ✅ 2-pass algorithm, distribuzione ok |
| 5. Session resolve | Drill-down 3 sessioni | ✅ Inline blocks supportati |
| 6. Day simulation | Feedback loop | ✅ Funziona |
| 7. Replanning | Day override | ✅ Phase-aware, 12 intent |
| 8. Edge cases | 4 scenari stress | ✅ Pre-trip deload, floor minimo, goal validation |

---

## Findings Status

### P0 — Bloccanti — ALL RESOLVED

#### F1. ~~Resolver ignora inline blocks~~ ✅ FIXED (Cluster 1)
- Added `_resolve_inline_block()` function in resolve_session.py
- 6 new tests, all sessions resolve with ≥3 exercises

#### F2. ~~Planner v2 — pool non cicla~~ ✅ FIXED (Cluster 1)
- Rewrote planner with 2-pass algorithm (pass1: primary/climbing, pass2: complementary)
- Pool cycling with max 2 full cycles

#### F3. ~~Base phase — zero finger work~~ ✅ FIXED (Cluster 1)
- Created `finger_maintenance_home.json` (intensity "medium", submaximal repeaters)
- Added to Base phase session pool

#### F4. ~~Test suite — nessun integration test~~ ✅ FIXED (Cluster 1)
- Created `test_resolve_real_sessions.py` — resolves all 28 real session files

### P1 — Importanti — ALL RESOLVED

#### F5. ~~PE score — double counting + no test oggettivi~~ ✅ FIXED (Cluster 2)
- `_compute_power_endurance()` now uses repeater test (40%) + gap (40%) + self_eval (20%)
- Added `_PE_REPEATER_BENCHMARK` table (7a→9a+, 18→44 reps)
- Reduced self_eval penalties: primary -15→-8, secondary -8→-4
- 5 new tests

#### F6. ~~Replanner — intent mancanti~~ ✅ FIXED (Cluster 2)
- `INTENT_TO_SESSION` expanded from 7 to 12 intents
- Added: core, prehab, flexibility, finger_maintenance, finger_max

#### F7. ~~Replanner usa planner_v1~~ ✅ FIXED (Cluster 2)
- Replanner now imports from planner_v2 (`_SESSION_META`, `generate_phase_week`)
- `apply_day_override` accepts `phase_id` parameter
- `set_availability` handler uses `generate_phase_week` (phase-aware)
- 4 new tests

#### F8. ~~Pre-trip deload solo annotazione~~ ✅ FIXED (Cluster 2)
- `generate_phase_week()` accepts `pretrip_dates` parameter
- Hard/max sessions blocked on pretrip dates
- Days flagged with `pretrip_deload=True`
- 3 new tests

#### F9. ~~Nessuna validazione goal vs livello attuale~~ ✅ FIXED (Cluster 2)
- `_validate_goal()` checks target ≤ current (warning) and gap > 8 (ambitious warning)
- Warnings included in macrocycle output
- 6 new tests

#### F10. ~~Base crolla a 1 settimana con macrociclo corto~~ ✅ FIXED (Cluster 2)
- `_compute_phase_durations()` enforces min 2 weeks for non-deload phases
- 3 new tests

### P2 — Miglioramenti

#### F11. ~~Sessioni climbing-related non prioritizzate~~ ✅ FIXED (Cluster 1)
- 2-pass algorithm: pass1 places climbing/hard sessions first, pass2 fills complementary
- 1 new test

#### F12. ~~board_moonboard non in vocabulary~~ ✅ FIXED (Cluster 2)
- Added `board_moonboard`, `bench`, `barbell` to vocabulary_v1.md

#### F13. ~~Distribuzione sessioni non uniforme~~ ✅ FIXED (Cluster 1)
- Resolved by 2-pass algorithm with spacing constraints
- 5 new tests for distribution

#### F14. Outdoor climbing non supportato — DEFERRED to B2
- Intent "outdoor" not yet in replanner (no outdoor sessions exist in catalog)
- Tracked as backlog item B2

---

## Data corrections during test

| Campo | Prima | Dopo | Motivo |
|-------|-------|------|--------|
| `assessment.experience.climbing_years` | 5 | 10 | Dato reale dell'utente |
| `assessment.experience.structured_training_years` | 1 | 5 | Dato reale |
| `goal.target_grade` | 7c+ | 8b | Obiettivo reale |
| `goal.current_grade` | 7b | 8a+ | Livello reale |
| `planning_prefs.target_training_days_per_week` | 4 | 6 | Preferenza utente |
| `equipment.gyms` | 2 gyms | 3 gyms | Aggiunta BKL |
| `baselines.hangboard[0].max_total_load_kg` | 102.0 | 125.0 | Dato reale (48kg added + 77kg BW) |
| `assessment.tests.max_hang_20mm_5s_total_kg` | 102.0 | 125.0 | Consistenza |
| `assessment.tests.repeater_7_3_max_sets_20mm` | null | 24 | Dato reale (Cluster 2) |
| `tests.max_strength[0].external_load_kg` | 25.0 | 48.0 | Dato reale |
| `tests.max_strength[0].total_load_kg` | 102.0 | 125.0 | Dato reale |

---

## What works well

1. **Assessment 6-axis** — profilo ragionevole con repeater test integrato
2. **Macrocycle structure** — Hörst 4-3-2-1 con DUP, floor minimo, goal validation
3. **2-pass planner** — climbing-first, poi complementari, distribuzione uniforme
4. **Determinismo** — stessi input → stessi output confermato
5. **Inline block resolution** — tutte le sessioni risolvono correttamente
6. **Phase-aware replanner** — 12 intent, phase_id propagato
7. **Pre-trip deload** — sessioni hard bloccate prima dei trip
8. **Feedback contract** — struttura feedback granulare ben definita

---

## Summary

| Metric | Value |
|--------|-------|
| Total findings | 14 |
| Fixed (Cluster 1) | 6 (F1, F2, F3, F4, F11, F13) |
| Fixed (Cluster 2) | 7 (F5, F6, F7, F8, F9, F10, F12) |
| Deferred | 1 (F14 → B2) |
| Tests before | ~100 |
| Tests after | 155 |
