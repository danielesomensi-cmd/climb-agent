# Replanning V1 (event-driven, deterministic)

## Event contract (`plan_event.v1`)
Schema: `data/schemas/plan_event.v1.json`.

Required envelope:
- `schema_version: "plan_event.v1"`
- `event_version: 1`
- `event_type`: `mark_done | mark_skipped | move_session | set_availability`

### Event types
- `mark_done`: `date` + (`session_ref` or `slot`), optional `outcomes`
- `mark_skipped`: `date` + (`session_ref` or `slot`), optional `reason`
- `move_session`: `from_date` + `from_slot` -> `to_date` + `to_slot`, optional `session_ref`
- `set_availability`: slot/day availability update by `date` or by `availability.weekday`

## Deterministic replanning rules
- Events are applied in-order.
- `move_session`: remove source session deterministically; insert into target slot (replace target slot if occupied).
- If move leaves source slot empty, refill deterministically:
  - recovery fill (`deload_recovery`) by default
  - accessory fill (`general_strength_short`) when day still has hard stimulus
- `mark_skipped`: remove selected session and replace same slot with `deload_recovery`.
- `mark_done`: removes matching planned session from remaining plan (reality-first bookkeeping).
- `set_availability`: update availability and regenerate deterministic week from current planner profile.

### Constraints re-enforced after events
- weekly `hard_day_cap_per_week`
- no consecutive finger-strength days
- deterministic tie-breakers: slot order (`morning`, `lunch`, `evening`) then priority then `session_id`
- `plan_revision` is bumped deterministically (`+1`).

## CLI
Single event:
```bash
python scripts/replan_week.py \
  --plan out/plans/plan_week.json \
  --event out/plans/event.move.json \
  --user-state data/user_state.json \
  --out out/plans/plan_week_replanned.json
```

Multiple events (`.jsonl`):
```bash
python scripts/replan_week.py \
  --plan out/plans/plan_week.json \
  --events out/plans/events.jsonl \
  --user-state data/user_state.json \
  --out out/plans/plan_week_replanned.json
```

## Examples
- Anticipate tomorrow’s session:
  - emit `move_session` from tomorrow slot to today slot.
- Skip today and replan:
  - emit `mark_skipped` for today hard slot; replanner replaces it with deterministic recovery in the same slot.
