# Planner v1 (Macro plan 12–16 weeks)

## Why
We want a deterministic long-term plan that:
- produces a weekly schedule of sessions (from existing sessions/templates)
- supports periodization (Eric Hörst style: build → peak → deload)
- is robust to reality: missed days, outdoor days, fatigue

## Inputs
- user_state (constraints, availability, current maxes)
- catalog sessions/templates (what can be scheduled)
- target horizon: default 12 weeks (configurable)

## Output (contract proposal)
A JSON plan with:
- weeks[] → days[] → sessions[]
Each session references an existing session file or template_id, plus intent metadata.

Suggested structure:
- plan_version: "planner.v1"
- start_date (YYYY-MM-DD)
- weeks: [
  {
    week_index: 0,
    focus: "base|build|peak|deload",
    days: [
      { date: "...", sessions: [ { session_id, intent, constraints_applied[], notes } ] }
    ]
  }
]

## Core constraints (MVP)
- avoid consecutive finger_max_strength days
- deload every 4th week (reduced intensity/volume)
- limit hard days per week (config)
- allow "performance day" (outdoor climbing) to override planned day

## Next deliverables
- data/schemas/planner_plan.v1.json
- catalog/engine/planner_v1.py (generate plan deterministically)
- scripts/generate_plan.py (CLI)
- tests/test_planner_v1.py (determinism + constraints)
