# Closed-loop IO log

## Run metadata
- date:
- branch/commit:
- scenario: (e.g., weighted_pullup / max_hang / finger session / day replanning)

## INPUT (what the agent saw)
### user_state snapshot (minimal)
- baseline metric(s):
  - e.g. pullup_1rm / pullup_2rm / max_hang_10mm_kg / etc
- last 3 outcomes:
  - [date] exercise: ... | prescribed: ... | actual: ... | feedback_label: ...
- current constraints:
  - location:
  - equipment:
  - energy/fatigue: (low/med/high)

### proposed prescription (before feedback)
- exercise_id:
- proposed load / reps / sets / rest:
- derived from: (baseline + multiplier)

## FEEDBACK (what happened)
- actual load/reps/sets:
- feedback_label (canonical): (very_easy | easy | ok | hard | very_hard)
- legacy difficulty (optional compat only): (too_easy | easy | ok | hard | too_hard | fail)
- notes: (optional)

## OUTPUT (what changed)
- next prescription delta:
  - load change:
  - reps/volume change:
- updated adjustment state:
  - multiplier_before -> multiplier_after
  - clamps applied? (yes/no)
- baseline update:
  - updated? (yes/no) + why
- safety flags:
  - (e.g., “hard/very_hard twice in a row -> retest queued +7d”)

## Notes / next action
- what to test next:
- bugs/suspicions:
