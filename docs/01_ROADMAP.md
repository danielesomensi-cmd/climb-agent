# Roadmap — climb-agent

## Now (P0 baseline)
- P0 resolver deterministico + spiegabile
- baseline session under test (una sessione reale nel repo)
- 2 contesti: home+hangboard, gym+blocx

## Next
- Structured I/O: session_request.v1 / session_instance.v1

## Next+ (P1 ranking)
- deterministico su shortlist P0 (recency/intensity/fatigue cost), design-first

## Later
- planner + multi-session/day + load settimanale + nutrizione + UI app

## Next (closed loop MVP)
- Execute → Log:
  capture outcomes per exercise_instance (weight/assist, reps/time, RPE, pain flags, notes)
  append to data/logs/*.jsonl (session_log_entry schema)
- Update:
  update user_state (recency, last_performed, simple fatigue/pain signals)
  keep P0 unchanged (no ranking yet)

### Closed loop: Execute → Log → Update (user-specific)
- Store user identity in `data/user_state.json` under `user.{id,name}`.
- Log executed sessions to `data/logs/session_logs.jsonl` (one JSON per session), including:
  planned (suggested) vs actual (used weight/assist, sets done, RPE, notes).
- Maintain baseline history in `data/logs/baseline_history.jsonl` when max_total_load_kg is updated.
