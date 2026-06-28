# D204 — Session Builder Feasibility Audit

**Date:** 2026-04-10
**Type:** D (read-only audit)
**Status:** Report only — no file modifications

---

## 0.1 — Data model: user_state

### Current top-level keys in user_state

```
assessment, availability, baselines, body, bodyweight_kg, current_week_plan,
equipment, fatigue_proxy, goal, history_index, limitations, macrocycle,
outdoor_spots, performance, planning_prefs, preferences, recent_sessions,
recent_sessions_window_days, schema_version, stimulus_recency, tests, trips,
user, week_plans, working_loads
```

`custom_sessions` does **NOT** exist anywhere in the codebase. No references in backend code, no schema definition, no frontend types.

### Storage location

**Recommended: `state["custom_sessions"]` (JSONB in `users.state`)**

Rationale:
- All user data already lives in the `users.state` JSONB column (Supabase)
- A custom session with 8 exercises ≈ 1.6 KB. 20 sessions ≈ 32 KB. Well within JSONB limits.
- No need for a separate Supabase table — avoids migration complexity and stays consistent with the existing single-state-object architecture.
- Backup/restore via `/api/user/export` and `/api/user/import` works automatically.

### Proposed schema

```json
{
  "custom_sessions": [
    {
      "id": "cs_20260410_1",
      "name": "My Fingerboard Day",
      "created_at": "2026-04-10T10:00:00Z",
      "updated_at": "2026-04-10T10:00:00Z",
      "tags": ["finger", "strength"],
      "exercises": [
        {
          "exercise_id": "max_hang_half_crimp",
          "sets": 5,
          "reps": 1,
          "work_seconds": 10,
          "rest_between_sets_seconds": 180,
          "rest_between_reps_seconds": null,
          "load_kg": 15,
          "notes": ""
        },
        {
          "exercise_id": "weighted_pullup",
          "sets": 4,
          "reps": 5,
          "work_seconds": null,
          "rest_between_sets_seconds": 120,
          "rest_between_reps_seconds": null,
          "load_kg": 10,
          "notes": ""
        }
      ],
      "warmup_template": "general_warmup",
      "cooldown_template": "cooldown_stretch",
      "estimated_load_score": 48,
      "estimated_duration_minutes": 60
    }
  ]
}
```

**Key design decisions:**
- `id` is auto-generated (`cs_YYYYMMDD_N`), not a catalog session_id
- `exercises[].exercise_id` references the catalog — ensures name/description/media can be looked up
- `warmup_template` / `cooldown_template` are optional references to existing templates
- `estimated_load_score` computed at save time from `fatigue_cost` sum (see §0.6)
- `tags` enable future filtering (finger day, strength, endurance, etc.)

---

## 0.2 — Exercise catalog structure

### Coverage

- **198 exercises** in `backend/catalog/exercises/v1/exercises.json`
- **100% have `prescription_defaults`** — every exercise has pre-filled params

### prescription_defaults fields

| Field | Present in N exercises | Required for builder? |
|-------|----------------------|----------------------|
| `sets` | 198 (100%) | **Yes** — always present |
| `reps` | 125 (63%) | Conditional (reps-based) |
| `work_seconds` | 94 (47%) | Conditional (time-based) |
| `rest_between_sets_seconds` | 157 (79%) | Yes |
| `rest_between_reps_seconds` | 40 (20%) | For repeaters/hangs only |
| `notes` | 169 (85%) | Optional |
| `grade_ref` | 31 (15%) | For climbing exercises |
| `grade_offset` | 31 (15%) | For climbing exercises |

### Intensity levels in prescription_defaults

Exercises define defaults at a specific intensity level:
- low: 82, medium: 46, high: 44, max: 19, other: 7

**For Session Builder:** use `prescription_defaults` as-is (the exercise's authored default). No need to select intensity — the user can edit values if they want.

### Minimal exercise entry for builder

```json
{
  "exercise_id": "weighted_pullup",
  "sets": 4,
  "reps": 5,
  "work_seconds": null,
  "rest_between_sets_seconds": 120,
  "rest_between_reps_seconds": null,
  "load_kg": 10,
  "notes": ""
}
```

`load_kg` is **not** in prescription_defaults — it comes from `working_loads` in user_state. For the builder, default to 0 (bodyweight) and let the user set it.

---

## 0.3 — Free session infrastructure

### Endpoints (8 total)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/free-session/surfaces` | Available surfaces + user gyms |
| GET | `/api/free-session/presets` | Presets for surface |
| POST | `/api/free-session/start` | Start session |
| POST | `/api/free-session/{id}/log-climb` | Log a climb |
| POST | `/api/free-session/{id}/finish` | Finish + compute load |
| GET | `/api/free-session/history` | Sessions for a date |
| DELETE | `/api/free-session/{id}/climb/{idx}` | Delete climb |
| DELETE | `/api/free-session/{id}` | Delete session |

### Session modes

Free sessions support three modes: `template`, `free`, `circuit`.

**Circuit mode** is the closest analog to a custom session:
- Stores `circuit.exercises: [{name, duration}]` and `circuit.completed_exercises`
- Load = `completed_exercises × 0.5` (simple formula)
- No per-exercise feedback or closed-loop

### `custom_sessions` does not exist

No implementation found. Zero results for `custom_session` in the entire codebase.

### Integration point

Two options:
1. **New session_mode `"custom"`** in free session system — reuses start/finish flow, persistence in `state["free_sessions"]`
2. **Separate system** — custom sessions stored in `state["custom_sessions"]`, played back via a new guided-session-like page, logged to `state["free_sessions"]` on completion

**Recommendation: Option 2.** Custom sessions are reusable templates (CRUD), not one-off logs. They belong in their own data structure. On completion, log result to `free_sessions` (or a new `custom_session_logs`) for history/load tracking.

---

## 0.4 — Quick-add and Today/Week integration

### Current quick-add flow

```
User clicks [+ Add Session]
  → QuickAddDialog opens
  → Fetches GET /api/replanner/suggest-sessions
  → User picks session from catalog suggestions
  → POST /api/replanner/quick-add { session_id, target_date, slot, location }
  → Backend: apply_day_add() in replanner_v1.py
  → apply_day_add() REQUIRES session_id in _SESSION_META (hardcoded catalog)
```

### Blocker: `apply_day_add()` requires catalog ID

`_meta_for(session_id)` looks up the session in `_SESSION_META` (line 188, replanner_v1.py). Custom sessions have no catalog ID → **cannot use existing quick-add path.**

### Proposed integration

**Two-tab approach in QuickAddDialog:**
- Tab 1: "Suggested" (existing catalog quick-add)
- Tab 2: "My Sessions" (list of user's custom sessions)

**Custom session add bypasses replanner.** Instead:
1. Frontend writes directly to `week_plans[week].days[day].sessions[]` via a new endpoint
2. New endpoint: `POST /api/session/add-custom` — accepts `custom_session_id`, `target_date`, `slot`
3. Backend: looks up custom session from `state["custom_sessions"]`, creates a session slot entry with `source: "custom"`, writes to week plan

**Alternatively:** use `apply_events()` with a new event type `"add_custom_session"` — this is cleaner and follows existing patterns (outdoor, other_activity both use events).

### No ripple effects needed

Custom sessions don't have `hard`/`finger` metadata from `_SESSION_META`. Options:
- Infer from exercise tags (if exercises include finger exercises → `finger: true`)
- Let user tag the session (finger / hard / easy)
- Skip ripple entirely (simplest for v1)

---

## 0.5 — Warmup / cooldown blocks

### Available templates

**Warmup (3 templates):**
| Template | File | Focus |
|----------|------|-------|
| `general_warmup` | `backend/catalog/templates/v1/general_warmup.json` | Pulse raise + mobility + shoulder activation |
| `warmup_climbing` | `warmup_climbing.json` | General + easy boulders + climbing activation |
| `warmup_strength` | `warmup_strength.json` | General + progressive hang ramp-up |

**Cooldown (1 template):**
| Template | File | Focus |
|----------|------|-------|
| `cooldown_stretch` | `cooldown_stretch.json` | Forearm/wrist + hip + general flexibility |

### Exercises in catalog

- **7 warmup exercises**: `finger_warmup_generic`, `general_pulse_raise`, `dynamic_mobility_flow`, `active_hip_mobility`, `hang_rampup_progressive`, `warmup_easy_boulders`, `warmup_repeaters_large`
- **7+ cooldown exercises**: `cooldown_forearm_wrist_stretch`, `cooldown_hip_pigeon`, `cooldown_hip_frog`, `cooldown_shoulder_chest`, `cooldown_hamstring_fold`, `cooldown_spinal_twist`, `cooldown_deep_squat_hold`

### Builder integration

**Proposed UX:** Two optional shortcut buttons in the builder:
- "Add Warmup" → shows 3 warmup templates, user picks one → exercises from template are prepended to the session
- "Add Cooldown" → shows 1 cooldown template → exercises appended

**Implementation:** Resolve the template at builder time (not runtime). The exercises become concrete entries in the custom session's `exercises[]` array — no template dependency at playback time.

**Alternative (simpler):** Store `warmup_template` and `cooldown_template` as string references in the custom session schema. At playback, resolve them. This is lighter on storage but adds runtime dependency.

---

## 0.6 — Load score calculation

### Planned sessions (resolve_session.py)

```python
# resolve_session.py:1644-1650
ex_fatigue = {e.get("id"): e.get("fatigue_cost", 0) for e in exercises}
raw_fatigue = sum(
    ex_fatigue.get(inst.get("exercise_id"), 0)
    for inst in exercise_instances
)
session_load_score = round(min(85, raw_fatigue * 1.5))
```

**Key insight:** Load score is computed from **`fatigue_cost`** per exercise (integer field in `exercises.json`, present on all 198 exercises). It's a **static catalog attribute** — does NOT depend on sets/reps/load.

- `fatigue_cost` range: 1 (warmup) to 9 (max hang, campus)
- Formula: `sum(fatigue_cost for each exercise in session) × 1.5`, capped at 85

### Free sessions (free_session.py)

Different formula based on climbs: `sum(relative_difficulty × status_weight × attempt_modifier) × 4.0`

### Custom session load score

**Can be computed trivially from static params:**

```python
def compute_custom_session_load(exercise_ids: list[str], exercises_catalog: dict) -> int:
    """Sum fatigue_cost for each exercise, scale ×1.5, cap 85."""
    raw = sum(exercises_catalog[eid].get("fatigue_cost", 0) for eid in exercise_ids)
    return round(min(85, raw * 1.5))
```

**No resolver needed.** The fatigue_cost is per-exercise, not per-set. A session with 5 exercises that have fatigue_costs [3, 7, 5, 2, 9] = 26 × 1.5 = 39 ≈ "medium" load.

**Note:** This doesn't account for the user's prescription (more sets = more fatigue). For v1 this is acceptable — same limitation exists in the resolver. A v2 enhancement could weight by sets: `fatigue_cost × sets × 0.3`.

---

## Gap analysis

### What exists

| Component | Status | Details |
|-----------|--------|---------|
| Exercise catalog | ✅ Ready | 198 exercises, all with `prescription_defaults` + `fatigue_cost` |
| Warmup/cooldown templates | ✅ Ready | 3 warmup + 1 cooldown, exercises in catalog |
| Load score formula | ✅ Ready | `sum(fatigue_cost) × 1.5`, works from exercise IDs alone |
| Free session logging | ✅ Ready | Can reuse for completion logging (circuit mode analog) |
| Quick-add dialog | ⚠️ Partial | Exists but hardwired to catalog sessions. Needs second tab |
| Week plan persistence | ✅ Ready | `persist_week_plan()` handles writes |
| Guided session page | ✅ Ready | `/guided/[date]/[sessionId]` — could be adapted for custom sessions |

### What needs building

| Component | Effort | Details |
|-----------|--------|---------|
| `custom_sessions` data model | S | New key in user_state, CRUD endpoints |
| Custom session CRUD API | S | 4-5 endpoints: list, get, create, update, delete |
| Session Builder page (frontend) | L | Exercise picker, drag-reorder, param editing, warmup/cooldown shortcuts |
| Load score preview | S | `compute_custom_session_load()` — trivial from fatigue_cost |
| Integration with Today/Week | M | New tab in QuickAddDialog + new event type in replanner |
| Custom session playback | M | Adapt guided session page or create new flow |
| Completion logging | S | Log to `free_sessions` with `session_mode: "custom"` |

---

## Risk flags

1. **No per-exercise feedback / closed-loop**: By design (Christie's request). But this means custom sessions don't contribute to `working_loads` or `stimulus_recency`. Users who primarily use custom sessions will have stale progression. **Mitigation:** Document this clearly; consider adding optional exercise-level feedback in v2.

2. **Load score is exercise-count-based, not volume-based**: `fatigue_cost` doesn't scale with sets/reps. A 3-set max hang and a 10-set max hang have the same fatigue_cost. For v1 this matches the resolver's behavior, but it's a known limitation. **Mitigation:** Acceptable for v1. Add `fatigue_cost × sets × 0.3` in v2.

3. **Quick-add integration requires replanner awareness**: Adding a custom session to a day needs a new event type. If the custom session is "hard" (has finger exercises), the day-after ripple logic won't fire unless we add metadata inference. **Mitigation:** For v1, skip ripple. Add `tags` field to custom sessions for v2 ripple.

4. **Exercise catalog changes break saved sessions**: If an `exercise_id` is renamed or removed, saved custom sessions will have dangling references. **Mitigation:** Exercise IDs are stable (198 exercises, never renamed). Add validation on load that skips missing exercises with a warning.

5. **No guided session timer for custom sessions**: The existing guided session page (`/guided/[date]/[sessionId]`) expects resolver output with blocks. Custom sessions have flat exercise lists. **Mitigation:** Either adapt guided page to accept flat lists, or build a simpler playback page.

---

## Effort estimate

**Overall: M-L** (3-4 briefs, ~2-3 sessions of work)

| Phase | Effort | Scope |
|-------|--------|-------|
| Backend CRUD + data model | S | A205: custom_sessions in user_state, 5 API endpoints, load score |
| Frontend Session Builder page | L | A206: exercise picker, search, drag-reorder, param editing, warmup/cooldown, save |
| Today/Week integration | M | A207: QuickAddDialog second tab, new replanner event, completion logging |
| Playback page (optional) | M | A208: guided-session adaptation or new page for step-by-step execution |

---

## Recommended implementation phases

### Phase 1 — Backend + data model (A205)

- Add `custom_sessions: []` to user_state
- 5 CRUD endpoints: `GET/POST/PUT/DELETE /api/custom-session/*`
- `compute_custom_session_load(exercise_ids)` utility
- Endpoint to list exercises suitable for builder (filtered by category, searchable)
- Tests for CRUD + load score

### Phase 2 — Session Builder page (A206)

- New page `/session-builder` (or `/session-builder/[id]` for edit)
- Exercise search/filter (by category, equipment, muscle group)
- Drag-to-reorder exercise list
- Per-exercise param editing (pre-filled from `prescription_defaults`)
- Warmup/cooldown shortcut buttons
- Live load score preview
- Save to `state["custom_sessions"]`

### Phase 3 — Integration + playback (A207)

- QuickAddDialog: "My Sessions" tab listing saved custom sessions
- New replanner event `add_custom_session` to write to week plan
- Completion flow: finish → log to `free_sessions` with `session_mode: "custom"`
- Optional: adapt `/guided` page for flat exercise lists (step-by-step with timer)
- Free Session page: "My Sessions" section for quick launch

---

## References

| File | Purpose |
|------|---------|
| `backend/catalog/exercises/v1/exercises.json` | Exercise catalog (198 entries) |
| `backend/catalog/templates/v1/general_warmup.json` | Warmup template |
| `backend/catalog/templates/v1/cooldown_stretch.json` | Cooldown template |
| `backend/engine/resolve_session.py:1644-1650` | Load score formula |
| `backend/engine/free_session.py:158-188` | Free session load formula |
| `backend/engine/replanner_v1.py:354-473` | `apply_day_add()` — catalog-only quick-add |
| `backend/engine/replanner_v1.py:794-1012` | `apply_events()` — event-based day modifications |
| `backend/api/routers/free_session.py` | Free session endpoints |
| `frontend/src/components/training/quick-add-dialog.tsx` | Quick-add dialog UI |
| `frontend/src/app/(main)/guided/[date]/[sessionId]/page.tsx` | Guided session page |
