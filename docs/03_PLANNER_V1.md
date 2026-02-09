# Planner v1 — Macro plan (12–16 weeks)

## Why
Vogliamo un piano long-term **deterministico** che:
- pianifica macro-fasi (periodizzazione stile Hörst)
- genera un weekly schedule (sessioni dal catalog)
- è robusto alla realtà (skip, outdoor, fatica, cambio giorni disponibili)
- prepara input puliti al resolver (che resta P0/P1 indipendente)

## Entities (separazione pulita)
1) **PlannerProfile** (intent stabile, scelto dall’utente)
   - goal_mode, horizon_weeks, target_days_per_week, allowed_locations, constraints
2) **PlannerState** (derivato dai log)
   - adherence, fatigue flags, pain flags, rolling load, recent finger days
3) **Plan** (output)
   - weeks[] → days[] → sessions[] + explain

## Planning modes (MVP)
Ogni mode definisce una sequenza di fasi + un “mix” settimanale di sessioni.

### 1) Balanced / Performance (default)
- Struttura tipica 4 settimane: **Build → Build → Build → Deload**
- Mix (settimana Build):
  - 1x `strength_long` (include `finger_max_strength`)
  - 1x `gym_power_bouldering`
  - 1x `gym_power_endurance`
  - 1x `gym_aerobic_endurance` oppure `gym_technique_boulder` (scelta in base a fatigue)
  - + optional `general_strength_short` se recovery ok

### 2) Strength block
- Priorità finger + power, volume endurance ridotto.
- Mix:
  - 2x `strength_long` (o `finger_max_strength` diretto), **no back-to-back**
  - 1x `gym_power_bouldering`
  - 1x easy `gym_technique_boulder` / aerobic easy
  - Deload ogni 4a settimana

### 3) Endurance block
- Priorità aerobic/PE, 1 dose di strength per mantenimento.
- Mix:
  - 1x strength (maintenance) `strength_long` o `finger_max_strength`
  - 1x `gym_aerobic_endurance`
  - 1x `gym_power_endurance`
  - 1x `gym_technique_boulder` / volume easy
  - Deload ogni 4a settimana

### 4) Maintenance (busy weeks)
- 2–3 giorni: 1 hard + 1 easy + 1 optional.
- Obiettivo: mantenere adattamenti senza accumulare fatica.

## Output contract (plan)
JSON:
- `plan_version: "planner.v1"`
- `start_date: "YYYY-MM-DD"`
- `profile_snapshot: {...}`
- `weeks[]`:
  - `week_index`, `phase`, `targets` (hard_days, finger_days, deload_factor)
  - `days[]`: `date`, `sessions[]`
    - session: `{ session_id, location, intent, priority, constraints_applied[], explain[] }`

## Core constraints (MVP)
- No consecutive finger-strength days
- Cap hard days/week (config)
- Deload every 4th week (volume/intensity scaler)
- Performance day (outdoor) può sostituire una planned hard day e attiva replanning


## Availability contract (v1, backward compatible)
Planner accepts both slot shapes:
- Legacy: `{available, locations[]}`
- Extended: `{available, locations[], preferred_location, gym_id}`

Normalization guarantees every slot has:
- `available`
- `locations[]` (compatibility)
- `preferred_location` (nullable)
- `gym_id` (nullable)

`preferred_location` is treated as a hard preference inside allowed + feasible locations.

## Deterministic gym_id rule
When planner emits a session with `location="gym"`, `gym_id` is resolved deterministically in order:
1. `availability.<weekday>.<slot>.gym_id`
2. `planning_prefs.default_gym_id` (from `user_state.planning_prefs` or `user_state.planning.planning_prefs`)
3. `equipment.gyms[0].gym_id`
4. `work_gym` if present
5. deterministic error

`profile_snapshot` includes compact `planning_prefs` and `availability_summary` for reproducible debugging.

## Replanner contract (v1)
Input:
- current plan + last actual logs + “what happened” (missed day, outdoor day, extra day)
Output:
- updated remaining days of current week + next week if needed
Rules:
- preserve weekly budget (hard/finger caps)
- reschedule missed high-priority sessions within 7–10 days
- downgrade/replace if fatigue/pain flags

Replanner v0 (cluster cooldown, deterministico):
- cluster_key(exercise) = domain|role|equipment_required|pattern/movement (campi ordinati, forma stabile).
- user_state.cooldowns.per_cluster["<cluster_key>"] conserva until_date/reason/last_updated.
- Se feedback "hard/too_hard/fail" aggiorna il cooldown del cluster per +1/+2 giorni.
- In resolver: per ogni block “main”, se target_date <= until_date, evita l’exercise main del cluster.
- Fallback deterministico: candidate nello stesso domain+equipment (role != main preferito), ordinati per id; nessun ranking P1.

## Usage (deterministic planner/replanner V1)
Generate a week plan:

```bash
python scripts/plan_week.py --start-date 2026-01-05 --mode balanced --out out/plans/plan_week.json
```

Apply tomorrow override + recovery ripple (next 2 days):

```bash
python scripts/plan_day_override.py \
  --plan out/plans/plan_week.json \
  --reference-date 2026-01-05 \
  --intent strength \
  --location gym \
  --out out/plans/plan_week_override.json
```

Both scripts produce deterministic JSON files under `out/plans/`.

## Nota sulla libreria sessioni
Per iniziare **basta** l’attuale libreria.
Se manca qualcosa: aggiungere una session placeholder “outdoor performance day” e “rest/recovery”.

## Next deliverables (codice + contratti)
- `data/schemas/planner_plan.v1.json`
- `catalog/engine/planner_v1.py` (deterministico)
- `tests/test_planner_v1.py` (snapshot tests)


## End-to-end deterministic loop (Planner → Resolver → Log → User State)
1) Plan week:
```bash
python scripts/plan_week.py --start-date 2026-01-05 --mode balanced --out out/plans/plan_week.json
```
2) Optional override/replanning:
```bash
python scripts/plan_day_override.py --plan out/plans/plan_week.json --reference-date 2026-01-05 --intent recovery --location home --out out/plans/plan_week_override.json
```
3) Resolve one planned date into concrete blocks/exercises:
```bash
python scripts/resolve_planned_day.py --plan out/plans/plan_week.json --date 2026-01-05 --out out/plans/plan_week__2026-01-05__resolved.json
```
4) Mark execution outcome and close the loop:
```bash
python scripts/log_resolved_day.py --resolved out/plans/plan_week__2026-01-05__resolved.json --status done --notes "session completed"
```
This updates `data/logs/sessions_2026.jsonl` and `data/user_state.json` deterministically.
