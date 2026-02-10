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


## Boulder grade targets (Font) v0

### Contract
- Parser/normalizer Font deterministico (`6A`..`8A+`, supporto esteso disponibile in tabella interna).
- Stepper deterministico: `step_grade(grade, steps)` con clamp su estremi scala.
- Target boulder scritto in `exercise_instance.suggested.suggested_boulder_target` con:
  - `schema_version: "boulder_grade_font_v0"`
  - `surface_options` (subset deterministico ordinato di `[board_kilter, spraywall, gym_boulder]`)
  - `target_grade`
  - `intensity_label` (`easy|medium|hard`)

### Benchmark derivation da user_state (senza file paralleli)
Ordine deterministico:
1. `user_state.performance.gym_reference.kilter.benchmark.grade`
2. `user_state.performance.current_level.boulder.worked.grade`
3. fallback: `6C`

### Offset rules (deterministiche, configurabili)
- warmup/technique: `benchmark -2`
- power_endurance/volume: `benchmark -1`
- limit/power: `benchmark +0`
- override opzionali: `user_state.progression_config.boulder_targets.offsets.*`

### Esempi output
```json
{
  "suggested_boulder_target": {
    "schema_version": "boulder_grade_font_v0",
    "surface_options": ["board_kilter", "spraywall"],
    "target_grade": "7A+",
    "intensity_label": "hard"
  }
}
```

```json
{
  "suggested_boulder_target": {
    "schema_version": "boulder_grade_font_v0",
    "surface_options": ["gym_boulder"],
    "target_grade": "6C",
    "intensity_label": "medium"
  }
}
```
