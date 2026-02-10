# Closed-loop V1 (deterministic)

## Scope
Closed-loop V1 closes: planner day -> resolver output -> day log append -> `data/user_state.json` update.

## Contracts
- planned gym sessions now require non-null `gym_id`; resolver guardrail fails fast otherwise.
- Canonical user state store: `data/user_state.json` (`schema_version: "1.4"`).
- Canonical session log path: from `history_index.session_log_paths` (prefer `data/logs/sessions_2026.jsonl`).
- Log schema version: `log_version: "closed_loop.v1"`.

### Log entry fields (`closed_loop.v1`)
- `date` (`YYYY-MM-DD`)
- `status` (`done|skipped`)
- `location`, `gym_id`
- `session_ids[]`
- `planned` (resolved/planned sessions snapshot)
- `actual` (optional outcomes object)
- `actual_feedback_v1` (mirrors `actual.exercise_feedback_v1`)
- `notes`
- `summary` (deterministic derived summary: count + categories + ids)

Reference schema: `data/schemas/resolved_day_log_entry.v1.json`.

## User state deterministic updates
- `schema_version` bumped to `1.4`.
- Added planning inputs:
  - `planning_prefs.target_training_days_per_week` (default 4)
  - `planning_prefs.hard_day_cap_per_week` (default 3)
  - `availability.<weekday>.<slot>.{available, locations?, preferred_location, gym_id}`
  - ensure `equipment.gyms[]` contains `gym_id="work_gym"`.
- Added recency/fatigue state:
  - `stimulus_recency.{finger_strength,boulder_power,endurance,complementaries}`
  - `fatigue_proxy` counters (`done/skipped/hard/finger/endurance totals`, `last_updated_date`)
- Added progression state:
  - `working_loads.entries[]` keyed deterministically by exercise + setup/surface
  - `progression_counters.*` for deterministic streak counting
  - `test_queue[]` for upcoming retest recommendations

## Progression feedback contract (v1)
Input source: `actual.exercise_feedback_v1[]`.

Per-item expected fields:
- common: `exercise_id`, `feedback_label`, `completed`
- load-based: `used_total_load_kg` or `used_external_load_kg`
- grade-based: `used_grade`, optional `surface_selected`

Effects:
- updates `working_loads.entries[]` next targets used by next `inject_targets`.
- does not rewrite official max/baseline from normal sessions.
- queues retest in `test_queue` on deterministic hard/easy streak thresholds.

## Test sessions (minimal planning integration)
- If `test_queue.recommended_by_date` falls within planned week, planner may insert `test_max_hang_5s`.
- Inserted session respects existing constraints:
  - hard cap per week
  - no consecutive finger days
- Test session carries deterministic markers:
  - `session_id: "test_max_hang_5s"`
  - `tags.test = true`
  - `test_id = "max_hang_5s_total_load"`

## Official tests update path
Only explicit test session logging updates official maxima:
- logging `test_*` with `max_hang_5s` + `used_total_load_kg` updates:
  - `user_state.tests.max_strength[]`
  - `user_state.baselines.hangboard[0].max_total_load_kg`

## Equipment compatibility in resolver (P0)
- `equipment_required`: AND semantics. Every listed item must be in `context.available_equipment`.
- `equipment_required_any`: OR semantics. At least one listed item must be in `context.available_equipment`.
- If both are present, both constraints apply (`ALL` from `equipment_required` + `ANY` from `equipment_required_any`).

### How `available_equipment` is determined from `user_state`
- Location is resolved from session context first (`session.context.location`), then override/default fallbacks.
- For `location="home"`: resolver uses `user_state.equipment.home`.
- For `location="gym"`: resolver requires `gym_id` and uses `user_state.equipment.gyms[*]` matching that `gym_id`.
- Resolver normalizes the final list deterministically (e.g., removes `floor`, can expose canonical `weight` if subtypes are present).

## CLI
Initialize/upgrade user state (idempotent):
```bash
python scripts/init_user_state_planning.py --user-state data/user_state.json
```
Resolve one planned day:
```bash
python scripts/resolve_planned_day.py --plan out/plans/plan_week.json --date 2026-01-05 --out out/plans/plan_week__2026-01-05__resolved.json
```
Log done/skipped day + update user state:
```bash
python scripts/log_resolved_day.py --resolved out/plans/plan_week__2026-01-05__resolved.json --status done --notes "felt good" --outcome-json '{"rpe":"hard"}'
```

End-to-end test run with tmp state/log (keeps repo data clean):
```bash
python scripts/resolve_planned_day.py \
  --plan out/plans/plan_week.json \
  --date 2026-01-05 \
  --user-state /tmp/user_state.e2e.json \
  --out /tmp/resolved_day.e2e.json

python scripts/log_resolved_day.py \
  --resolved /tmp/resolved_day.e2e.json \
  --status done \
  --user-state /tmp/user_state.e2e.json \
  --log-path /tmp/sessions.e2e.jsonl
```
