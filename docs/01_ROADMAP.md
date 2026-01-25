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

<!-- BEGIN: FUTURE_FACING_ROADMAP -->
## Closed-loop logging (Option B) — status and validation

### Done (today)
- **S2 — `actual.status`** added to log templates: `planned|done|skipped|modified` (default `planned`).
- **S3 — schema validation + quarantine (zero data loss)** on append:
  - Valid entries → `data/logs/session_logs.jsonl`
  - Invalid entries → `data/logs/session_logs_rejected.jsonl` with `errors[]` + original entry
- **Derived field autofill** on append: `actual.used_total_load_kg` computed when possible (from `bodyweight_kg` + `used_added_weight_kg` / `used_assistance_kg`).

### Next (1–3 sessions)
- **UI-0 (Colab Gradio)**: load latest log template, fill actual fields, validate, append, show last entry + mini stats.
- **Minimal analytics script** (read last N logs): adherence (% done), preference counts (`enjoyment`), difficulty distribution (`difficulty_label`).
- **Planner state snapshot** (`data/planner_state.json`): recency counters + fatigue flags derived from logs (no baseline auto-update yet).

### Medium term (2–6 weeks): toward a dynamic planner
- **P1 deterministic ranking** over P0 shortlist: recency penalty, fatigue penalty, preference penalty, phase alignment.
- **Constraints**: no consecutive max finger strength days; protect performance days; minimum rest windows.
- **Baseline update pipeline**: start with “candidate updates” (manual approval), then consider optional automation.

### Long term (3–4 months): periodization + expansion
- Introduce macrocycle phases (base / strength / power-endurance / peak / deload) with phase-weighted ranking.
- Expand exercises/templates only for coverage (added-weight, assistance, reps+load, time-based, instruction-only).
<!-- END: FUTURE_FACING_ROADMAP -->
