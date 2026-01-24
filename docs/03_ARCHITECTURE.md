# Architecture — Resolver/Compiler

## P0 pipeline (per block)
- mode == instruction_only -> status=selected, no exercise selection, message, filter_trace.note
- else:
  - explicit exercise_id? -> select that
  - else pick_best_exercise_p0 hard-filters:
    start -> after_location -> after_equipment -> after_role -> after_domain (solo se non azzera)
- Deterministic pick: smallest exercise_id
