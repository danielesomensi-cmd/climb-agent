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
  - 1x `blocx_power_bouldering`
  - 1x `blocx_power_endurance`
  - 1x `blocx_aerobic_endurance` oppure `blocx_technique_boulder` (scelta in base a fatigue)
  - + optional `general_strength_short` se recovery ok

### 2) Strength block
- Priorità finger + power, volume endurance ridotto.
- Mix:
  - 2x `strength_long` (o `finger_max_strength` diretto), **no back-to-back**
  - 1x `blocx_power_bouldering`
  - 1x easy `blocx_technique_boulder` / aerobic easy
  - Deload ogni 4a settimana

### 3) Endurance block
- Priorità aerobic/PE, 1 dose di strength per mantenimento.
- Mix:
  - 1x strength (maintenance) `strength_long` o `finger_max_strength`
  - 1x `blocx_aerobic_endurance`
  - 1x `blocx_power_endurance`
  - 1x `blocx_technique_boulder` / volume easy
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

## Replanner contract (v1)
Input:
- current plan + last actual logs + “what happened” (missed day, outdoor day, extra day)
Output:
- updated remaining days of current week + next week if needed
Rules:
- preserve weekly budget (hard/finger caps)
- reschedule missed high-priority sessions within 7–10 days
- downgrade/replace if fatigue/pain flags

## Nota sulla libreria sessioni
Per iniziare **basta** l’attuale libreria.
Se manca qualcosa: aggiungere una session placeholder “outdoor performance day” e “rest/recovery”.

## Next deliverables (codice + contratti)
- `data/schemas/planner_plan.v1.json`
- `catalog/engine/planner_v1.py` (deterministico)
- `tests/test_planner_v1.py` (snapshot tests)
