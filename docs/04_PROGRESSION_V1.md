# Progression v1 (Update maxes & proposed loads)

## Why
We need proposed weights/assistance to adapt based on outcomes:
- "actual.status", RPE, completion
- used_total_load_kg / used_added_weight_kg / used_assistance_kg
- keep stable progress without runaway jumps

## Inputs
- session log entries (v1 only)
- current user_state.maxes + progression rules

## Outputs
- updated user_state.maxes (per exercise_id or per pattern)
- updated "proposed" loads for next instances (heuristics)

## MVP heuristics
- If status=done and RPE <= 8 → +2.5% load next time (or +1–2 kg step)
- If status=done and RPE 9–10 → keep
- If status=modified/skipped or pain flags → -5–10% and set fatigue flag
- Update "estimated 1RM" only for relevant patterns (weighted pullups, hangboard loads, etc.)

## Next deliverables
- data/schemas/user_state_maxes.v1.json (optional)
- catalog/engine/progression_v1.py
- tests/test_progression_v1.py
