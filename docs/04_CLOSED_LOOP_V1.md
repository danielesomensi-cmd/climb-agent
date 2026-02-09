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
