# D170 — Outdoor System Audit

> Date: 2026-04-04
> Type: D (read-only audit)
> Scope: Full outdoor subsystem — planner, replanner, logging, frontend, data flow

---

## 1. Current behavior summary

### How outdoor days enter the system

There are **three distinct paths** to create an outdoor day:

| # | Path | Trigger | Clears sessions? | Sets outdoor fields? |
|---|------|---------|-------------------|---------------------|
| 1 | **Planner auto-detect** | All slots on a day have `preferred_location: "outdoor"` (via availability or weekly override) | N/A (no sessions assigned) | Sets `outdoor_slot: true` on output |
| 2 | **Replan dialog** (day override) | User picks outdoor intent (outdoor_easy/projecting/volume/boulder) in replan dialog | **YES** — `target_day["sessions"] = []` | Sets spot_name, discipline, status="planned" |
| 3 | **Quick-add outdoor** (add_outdoor event) | User adds outdoor via quick-add dialog on today/week page | **NO** — sessions untouched | Sets spot_name, discipline, status="planned" |

### Outdoor session lifecycle

```
[planned] ──── Log routes ────→ [POST /api/outdoor/log] ──→ JSONL/Supabase
                                        │
                                        ▼
                               [complete_outdoor event]
                                        │
                                        ▼
                              outdoor_session_status = "done"
                              outdoor_load_score stored on day
                                        │
                               load >= 65? ──YES──→ Ripple: next day's
                                                    hard→medium, medium→low
```

### Outdoor data storage (dual persistence)

| Store | Content | Written by |
|-------|---------|------------|
| **JSONL / Supabase `outdoor_logs`** | Full session log (routes, attempts, conditions, duration) | `POST /api/outdoor/log`, `PUT /api/outdoor/log` |
| **`state.outdoor_log[]`** | Summary array: `{date, spot_name, discipline, load_score, completed_at}` | `complete_outdoor` event handler in replanner router |
| **`state.week_plans[].days[].outdoor_*`** | Day-level fields: spot_name, spot_id, discipline, session_status, load_score | Replanner events (`add_outdoor`, `complete_outdoor`, `undo_outdoor`, `remove_outdoor`) |
| **`state.outdoor_spots[]`** | Saved spots: `{id, name, discipline, typical_days, notes}` | `POST /api/outdoor/spots` |

### Planner outdoor handling (planner_v2.py)

- `_normalize_availability()` processes slot-level `preferred_location` and `locations` fields
- Lines 682-708: If ALL available slots on a day have `preferred_location == "outdoor"` or `locations == ["outdoor"]`, the day is marked `day_is_outdoor[offset] = True`
- Outdoor-only days are **excluded from session assignment** (line 1134: `if day_is_outdoor[offset]: continue`)
- Output includes `outdoor_slot: true` on those days (line 1306)
- **Critical: outdoor blocks the ENTIRE day**, not individual slots. Even if only morning is outdoor and evening is gym, if all available slots are outdoor, the whole day is skipped.
- Only `regeneration_easy` has outdoor in its location tuple (`("home", "gym", "outdoor")`) — no other session type can be assigned to outdoor days

### Replanner event handlers (replanner_v1.py)

**`add_outdoor`** (lines 933-942):
- Sets: `outdoor_spot_name`, `outdoor_discipline`, `outdoor_spot_id`, `outdoor_session_status = "planned"`
- Does NOT remove existing sessions
- Does NOT check for conflicts

**`complete_outdoor`** (lines 944-1006):
- Sets: `outdoor_session_status = "done"`, stores `outdoor_load_score`
- If load >= 65 (OUTDOOR_RIPPLE_THRESHOLD): replaces next day's sessions:
  - Hard/finger → complementary_conditioning
  - Medium → deload_recovery
  - Low/already done → unchanged
- Respects B120 immutability (never modifies done/skipped sessions)

**`undo_outdoor`** (lines 1008-1011):
- Sets: `outdoor_session_status = "planned"` — does NOT clear `outdoor_load_score`
- Replanner router also calls `remove_outdoor_session()` to delete JSONL entry

**`remove_outdoor`** (lines 1013-1018):
- Removes all `outdoor_*` fields from day
- Refuses if `outdoor_session_status == "done"` (immutability)
- Does NOT restore previously removed sessions (if they were cleared by override)

**`apply_day_override` with outdoor** (lines 1327-1356):
- Maps intent to discipline via `OUTDOOR_INTENT_TO_DISCIPLINE`
- **Clears all sessions**: `target_day["sessions"] = []`
- Validates B120: refuses if any session is done/skipped
- Records adaptation with `"outdoor": True`

### Weekly overrides

- Outdoor can be set at slot level: `weekly_overrides[week]["days"]["friday"]["slots"]["morning"]["location"] = "outdoor"`
- Processed by `merge_override_into_availability()` → feeds into planner's `_normalize_availability()`
- If override makes ALL slots outdoor → planner auto-detects → `outdoor_slot: true`, no sessions assigned
- If override makes SOME slots outdoor → mixed day, planner may still assign sessions to non-outdoor slots

### API endpoints (outdoor.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/outdoor/spots` | Returns `state["outdoor_spots"]` array |
| POST | `/api/outdoor/spots` | Adds spot with auto-generated ID, duplicate check |
| DELETE | `/api/outdoor/spots/{id}` | Removes spot by ID |
| POST | `/api/outdoor/log` | Validates + appends to JSONL/Supabase. Does NOT update state.outdoor_log |
| GET | `/api/outdoor/log/{date}` | Loads from JSONL, filters by date, adds computed load_score |
| PUT | `/api/outdoor/log` | Replaces entry for date. Also syncs state.outdoor_log[] summary |
| DELETE | `/api/outdoor/log/{date}` | Removes from JSONL + state.outdoor_log[] |
| GET | `/api/outdoor/sessions` | Lists all sessions (optional `since` filter), enriched with load_score |
| GET | `/api/outdoor/stats` | Aggregated: total_sessions, total_routes, grade_histogram, send%, top_grade, load |
| POST | `/api/outdoor/convert-slot` | Calls `suggest_sessions()` for alternative sessions at new location |

### Frontend integration

**Today/Week pages:**
- Outdoor card: green dashed border + Mountain icon, shows spot name + discipline
- "Log routes" button opens OutdoorLogForm (checks for existing session → edit vs new)
- After logging: fires `complete_outdoor` event with read-after-write verification (D134)
- "Remove" button fires `remove_outdoor` event
- Route details expandable when status=done (grade + name + style emoji + attempt count)

**Outdoor History page (`/outdoor`):**
- Calls `getOutdoorSessions()` + `getOutdoorStats()` on load
- Route aggregation (A180): deduplicates by `${name}||${spotName}`, tracks best style, total attempts, session count
- Stats cards: total sessions, total routes, send%, top grade
- Grade histogram from `stats.grade_histogram`
- Session list: date, spot, discipline, route count, top grade, load, delete

**Quick-add dialog:**
- Outdoor mode: shows saved spots, discipline picker, inline "add new spot"
- Fires `add_outdoor` event (NOT override — sessions not cleared)

**Replan dialog:**
- 4 outdoor intents: outdoor_easy, outdoor_projecting, outdoor_volume, outdoor_boulder
- Fires `apply_day_override` (sessions ARE cleared)

---

## 2. Data flow diagram

```
USER ACTION                     API CALL                          STATE CHANGE
─────────────────────────────────────────────────────────────────────────────────

[Availability has outdoor]
  └→ GET /api/week/{n}         → planner_v2                     → day.outdoor_slot = true
                                  (all slots outdoor                (no sessions assigned)
                                   → skip day)

[Replan dialog → outdoor]
  └→ POST /api/replanner       → apply_day_override()           → day.sessions = []
      /override                   (outdoor intent detected)       → day.outdoor_spot_name = ...
                                                                  → day.outdoor_session_status = "planned"

[Quick-add → outdoor]
  └→ POST /api/replanner       → apply_events()                 → day.outdoor_spot_name = ...
      /events                     → add_outdoor handler           → day.outdoor_session_status = "planned"
      [{add_outdoor}]                                             → ⚠️ day.sessions UNCHANGED

[Log routes button]
  └→ POST /api/outdoor/log     → validate + store JSONL         → outdoor_logs table
  └→ POST /api/replanner       → apply_events()                 → day.outdoor_session_status = "done"
      /events                     → complete_outdoor              → day.outdoor_load_score = N
      [{complete_outdoor}]        → ripple if load >= 65          → state.outdoor_log[].append(summary)

[Undo outdoor]
  └→ POST /api/replanner       → apply_events()                 → day.outdoor_session_status = "planned"
      /events                     → undo_outdoor                  → ⚠️ outdoor_load_score NOT cleared
      [{undo_outdoor}]          → remove_outdoor_session()        → JSONL entry deleted

[Remove outdoor]
  └→ POST /api/replanner       → apply_events()                 → day.outdoor_* fields removed
      /events                     → remove_outdoor                → ⚠️ sessions NOT restored
      [{remove_outdoor}]

[Convert outdoor slot]
  └→ POST /api/outdoor         → suggest_sessions()             → returns suggestions only
      /convert-slot                                                (no state mutation)
```

---

## 3. Bug diagnosis: outdoor + indoor session coexistence

### Reported behavior

"Today (Fri 3 Apr) shows BOTH an outdoor session (Franken, lead, 'Planned') AND a Strength Day (Long Session) assigned by the planner."

### Investigation — Daniele's state (2026-04-04)

```
Availability friday: { evening: { gym_id: "3c7f08e0", available: true, preferred_location: "gym" } }
Weekly overrides: (empty)
```

**April 3 (Thu):** outdoor_spot=Berdorf, status=planned, sessions=0, load=15, day_status=done
**April 4 (Fri):** outdoor_spot=Kronthal, status=planned, sessions=0, load=0, day_status=done
**April 5 (Sat):** outdoor_spot=Kronthal, status=planned, sessions=0

Current state shows sessions=0 — the bug was likely observed BEFORE a replan cleared sessions, or state was patched since then.

### Root cause: `add_outdoor` does not clear sessions

The `add_outdoor` event handler (replanner_v1.py:933-942) **only adds outdoor fields** — it does not touch `day["sessions"]`. This means:

1. Planner generates a week plan → Friday gets a Strength Day session
2. User adds outdoor via quick-add dialog → fires `add_outdoor` event
3. `add_outdoor` sets `outdoor_spot_name`, `outdoor_discipline`, `outdoor_session_status = "planned"`
4. **Existing sessions remain** → both outdoor card AND strength day card render

In contrast, `apply_day_override()` with outdoor intent (lines 1327-1356) correctly does `target_day["sessions"] = []` before setting outdoor fields.

### Why two different paths exist

- **Quick-add** was designed for adding extra sessions (quick-add indoor adds alongside existing). The outdoor quick-add follows the same add-only pattern.
- **Replan dialog** was designed for replacing the day's plan. The outdoor replan correctly clears and replaces.

### Fix needed (not implemented — audit only)

`add_outdoor` handler should clear non-completed sessions, same as `apply_day_override`:

```python
# In add_outdoor handler, before setting outdoor fields:
completed = [s for s in day.get("sessions", []) if s.get("status") in ("done", "skipped")]
if completed:
    raise ValueError("Cannot add outdoor: completed sessions exist")
day["sessions"] = []
```

---

## 4. Gaps and issues found

### Critical (P1)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| **F1** | `add_outdoor` doesn't clear sessions → outdoor + indoor coexist | replanner_v1.py:933-942 | Users see conflicting sessions on same day |
| **F2** | `undo_outdoor` doesn't clear `outdoor_load_score` field | replanner_v1.py:1008-1011 | Stale load score persists after undo |

### Moderate (P2)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| **F3** | `remove_outdoor` doesn't restore cleared sessions | replanner_v1.py:1013-1018 | If sessions were cleared by override, removing outdoor leaves empty day |
| **F4** | `POST /api/outdoor/log` doesn't update `state.outdoor_log[]` — only `PUT` and `complete_outdoor` do | outdoor.py:82-113 vs 128-157 | Dual persistence diverges: JSONL has data, state summary doesn't until `complete_outdoor` fires |
| **F5** | `convert-slot` likely has parameter mismatch: passes `user_state=state` but `suggest_sessions()` expects `plan` as first arg | outdoor.py:216-220 | Endpoint may error or return wrong suggestions |
| **F6** | `typical_days` field on outdoor spots is stored but never consumed by planner or any engine logic | outdoor_spot.v1.json, planner_v2.py | Dead data — potential future feature, currently misleading |
| **F7** | Day status inconsistency: April 3 has `outdoor_session_status: "planned"` + `day.status: "done"` + `outdoor_load_score: 15` | Daniele's state | Suggests `undo_outdoor` was called after `complete_outdoor` but `_recompute_day_status` set status incorrectly, or state was patched |

### Design limitations (P3 — document for redesign)

| # | Issue | Notes |
|---|-------|-------|
| **F8** | Outdoor blocks entire day, not individual slots | Planner checks if ALL slots are outdoor → skips whole day. No support for "morning outdoor + evening gym" |
| **F9** | Only `regeneration_easy` has outdoor in its location tuple | Planner can't assign any real training session to outdoor days |
| **F10** | Outdoor logging (JSONL) is completely separate from week plan sessions | Two parallel data systems that don't reference each other |
| **F11** | No same-day conflict check on `add_outdoor` | Can add outdoor to a day that already has outdoor planned (overwrites silently) |
| **F12** | No bidirectional link between outdoor log entry and week_plan day | Outdoor routes are fetched by date matching, not by reference ID |
| **F13** | Quick-add dialog and replan dialog use different code paths for the same conceptual action (adding outdoor to a day) | UX inconsistency: one clears sessions, one doesn't |

---

## 5. Recommendations for redesign brief

### R1 — Unify outdoor entry paths (P1, blocks redesign)

`add_outdoor` and `apply_day_override` outdoor should have identical session-clearing behavior. Either:
- (a) `add_outdoor` clears non-completed sessions (simple fix), or
- (b) Quick-add outdoor routes through `apply_day_override` instead of `add_outdoor` (structural fix)

### R2 — Slot-level outdoor support (P2, enables "morning outdoor + evening gym")

Replace the all-or-nothing day detection with per-slot outdoor handling:
- Planner assigns sessions to non-outdoor slots normally
- Outdoor slot gets `outdoor_slot: true` independently
- Requires refactoring `day_is_outdoor` from boolean per day to per-slot logic

### R3 — Unified session model (P2, long-term)

Outdoor sessions should be first-class entries in `day["sessions"]` rather than parallel day-level fields:
```json
{
  "session_id": "outdoor_lead",
  "slot": "morning",
  "location": "outdoor",
  "outdoor_spot_id": "spot_abc",
  "status": "planned"
}
```
Benefits: single data model, consistent completion flow, natural coexistence with indoor sessions, no dual persistence.

### R4 — Remove or activate `typical_days` (P3)

Either:
- Wire `typical_days` into planner's availability normalization (auto-suggest outdoor on those days), or
- Remove the field to reduce confusion

### R5 — Outdoor load score cleanup on undo (P3)

`undo_outdoor` should also clear `outdoor_load_score` to avoid stale data.

---

## Appendix: Key file locations

| File | Role |
|------|------|
| `backend/engine/planner_v2.py` (682-708, 1134, 1306) | Outdoor day detection + skip + output flag |
| `backend/engine/replanner_v1.py` (933-1018, 1327-1356) | 4 event handlers + day override |
| `backend/engine/outdoor_log.py` | JSONL logging, load scoring, stats computation |
| `backend/api/routers/outdoor.py` | 10 endpoints (spots CRUD, session CRUD, convert-slot) |
| `backend/api/routers/replanner.py` (299-348) | Event enrichment (load score lookup, state.outdoor_log sync) |
| `backend/engine/storage_file.py` (178-290) | JSONL file backend |
| `backend/engine/storage_supabase.py` (159-247) | Supabase outdoor_logs table |
| `frontend/src/app/(main)/outdoor/page.tsx` | Outdoor history page |
| `frontend/src/app/(main)/today/page.tsx` (566-697) | Today page outdoor handlers |
| `frontend/src/components/training/day-card.tsx` (396-550) | Outdoor card rendering |
| `frontend/src/components/training/OutdoorLogForm.tsx` | Route logging form |
| `frontend/src/components/training/quick-add-dialog.tsx` (370-480) | Quick-add outdoor mode |
| `frontend/src/components/training/replan-dialog.tsx` (41-44) | Outdoor intents |
