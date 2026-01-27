## UI-0 prerequisite: log template generation (Colab verified)
UI-0 loads the latest template from `out/log_templates/`.

Pipeline:
1) `python scripts/run_baseline_session.py`
2) `python scripts/generate_latest_log_template.py`
3) Python cell: `!python -u scripts/ui_day_view_gradio.py --server_port 7862`
4) Python cell: `output.serve_kernel_port_as_iframe(7862, width=1200, height=800)`

## S3 quarantine (zero data loss)
- Valid -> append to `data/logs/sessions_2026.jsonl`
- Invalid -> append to `data/logs/session_logs_rejected.jsonl` with `errors[]` + original entry
- On invalid, append exits non-zero (gate visibility)

# Contracts

## P0 Resolver contract (non negoziabile)
- Hard filters only:
  - location_allowed
  - equipment_required subset di available_equipment
  - role ANY match (block.role richiesto per selection)
  - domain solo se non azzera (se azzera: non applicarlo)
- No random. Tie-break stabile su exercise_id.
- No silent blocks: ogni block ha status + message se skipped/failed.
- instruction_only:
  - status=selected
  - nessuna selezione esercizi
  - message esplicita
  - filter_trace presente con note e counts vuoto

## Vocabulary coherence (vincolante)
- docs/vocabulary_v1.md è source of truth
- scripts/audit_vocabulary.py deve passare
- se fallisce: correggere vocabulary oppure i file incoerenti

## Colab rule
- shell command => cella con %%bash (mai inline)

## Gates (ordine obbligatorio)
1) python scripts/audit_vocabulary.py
2) python -m py_compile catalog/engine/resolve_session.py
3) python -m unittest discover -s tests -p "test_*.py" -v
4) python scripts/run_baseline_session.py

## Context resolution (P0 expectation)
- `context.location` priority:
  1) session.context.location (if key exists)
  2) user_state_override.context.location (if key exists)
  3) user_state.defaults.location (optional)
  4) fallback: "home"
- `context.gym_id` is independent from location; it must NOT force location="gym".

## instruction_only output contract
- status="selected"
- selected_exercises=[]
- filter_trace.counts={}
- include "instructions" if template contains any of:
  duration_min_range, options, focus, notes, prescription

## Load parameterization (P0.5) — suggested fields
For load-based exercises (e.g., hangboard max hangs), the resolver may add a deterministic `suggested` object
inside `exercise_instances[*]`:

- `suggested.target_total_load_kg`
- `suggested.added_weight_kg` OR `suggested.assistance_kg`
- `suggested.setup` (edge_mm, grip, load_method)
- `suggested.based_on` (bodyweight_kg, max_total_load_kg)
- `suggested.rationale`

User-specific baselines MUST live in `data/user_state.json` (not in templates).

<!-- BEGIN: SESSION_LOGGING_CONTRACTS -->
## Session logging contracts (v1)

### Canonical log
- Append-only file: `data/logs/sessions_2026.jsonl`
- Each line is one JSON object conforming to `data/schemas/session_log_entry.v1.json`
- Must include: `user.id` and at least one item in `exercise_outcomes[]`

### Validation and quarantine (zero data loss)
- Requires Python dependency: `jsonschema` (Colab: `pip install jsonschema`).
- On append, validate against JSON Schema:
  - Valid → append to `data/logs/sessions_2026.jsonl`
  - Invalid → append to `data/logs/session_logs_rejected.jsonl` with `errors[]` + original entry
- The append command exits non-zero on invalid entries (so failures are visible in gates / CI).

### Outcome actual fields (core)
- `actual.status`: `planned|done|skipped|modified` (default `planned` in templates)
- Optional feedback fields:
  - `actual.difficulty_label`: `easy|ok|hard|too_hard` (nullable)
  - `actual.enjoyment`: `dislike|neutral|like` (nullable)
- Load fields:
  - `actual.used_added_weight_kg` / `actual.used_assistance_kg`
- `actual.used_total_load_kg` auto-filled on append when bodyweight is available (priority: `entry.user.bodyweight_kg`, then `data/user_state.json`). Formula: BW + `used_added_weight_kg` - `used_assistance_kg`.

### Determinism
- Logging must be deterministic and append-only.
- No baseline auto-update at append-time (future: candidate update pipeline with manual approval).
<!-- END: SESSION_LOGGING_CONTRACTS -->
