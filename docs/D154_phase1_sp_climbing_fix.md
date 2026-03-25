# D154 — Phase 1: Fix S&P Climbing Distribution

> **Type:** A (feature) + B (bugfix)
> **Priority:** P1.5 — affects training quality for all users in S&P phase
> **Risk:** MEDIUM — touches macrocycle pool + planner metadata + new session JSON
> **Origin:** Phase 0 audit (2026-03-25) confirmed 1 limit boulder session vs 2-3 expected
> **Depends on:** Phase 0 complete ✅

---

## Context (from Phase 0 audit)

The S&P phase currently generates weeks with only **1 hard on-wall climbing session** (power_contact_gym on Tue). Literature (Hörst, Lattice) expects **2-3 limit bouldering sessions** per week in S&P. Root causes:

1. Pool has only 1 limit boulder session (power_contact_gym)
2. `finger_strength_home` metadata says `climbing=True` but has zero on-wall climbing
3. No minimum on-wall constraint in planner

---

## Implementation Plan

### Fix 1: Metadata correction (XS) — `finger_strength_home` → `climbing: false`

**File:** `backend/engine/planner_v2.py` (SESSION_META or equivalent)

Change `finger_strength_home` metadata:
- `climbing: True` → `climbing: False`
- This session is pure hangboard — marking it as climbing is dishonest

**Test:** Existing planner tests should still pass. Add 1 assertion: `finger_strength_home` is not counted as a climbing session.

---

### Fix 2: Create `limit_boulder_gym` session (M)

**File:** `backend/catalog/v1/sessions/limit_boulder_gym.json`

This is a **dedicated limit projecting session** — distinct from `power_contact_gym`:

| Aspect | power_contact_gym (existing) | limit_boulder_gym (NEW) |
|--------|------------------------------|------------------------|
| **Focus** | Contact strength, explosive moves, coordination | Projecting, reading, sustained max attempts |
| **Style** | Short explosive sequences, dyno practice, campus-style boulder | Multi-move limit problems, beta refinement, 3-4 attempts per boulder |
| **Rest** | 3-5 min between attempts | 5-8 min between attempts (full neural recovery) |
| **Volume** | Higher attempt count, shorter problems | Fewer problems, longer engagement per problem |
| **Cue** | "Explosive first move. Commit fully." | "Read the whole problem. Rest long. Quality over quantity." |

**Session structure (template blocks in order):**

```
1. Warmup: Pulse Raise + Dynamic Mobility Flow (5-8 min)
2. Climbing Activation: easy boulders, progressive difficulty (10-15 min)
3. MAIN: Limit Bouldering — 4-6 problems at V_max to V_max-1
   - 3-4 attempts per problem max
   - Rest 5-8 min between problems (FULL recovery)
   - Total: 30-40 min of work
   - Process cue: "Project mindset: read, visualize, attempt, analyze"
4. Supplementary: 1-2 sets pulling (archer pullup or weighted pullup) (10 min)
5. Cooldown: Forearm & Wrist Stretch + 1 general stretch (5-10 min)
```

**Session metadata:**
```json
{
  "id": "limit_boulder_gym",
  "name": "Limit Bouldering (Projecting)",
  "hard": true,
  "climbing": true,
  "finger": false,
  "intensity": "max",
  "load_score": 85,
  "location": ["gym"],
  "required_equipment": ["gym_boulder"],
  "duration_minutes": 75,
  "domains": {
    "finger_strength": 0.2,
    "pulling_strength": 0.15,
    "power_endurance": 0.05,
    "volume_climbing": 0.3,
    "technique": 0.2,
    "core_prehab": 0.1
  }
}
```

**Note:** The `domains` here differ from `power_contact_gym` — this one has higher `volume_climbing` and `technique` weight because projecting involves more reading, movement quality, and sustained engagement than pure contact strength.

**Use existing exercises from catalog** — do NOT create new exercises. The session template should reference existing block IDs for:
- Limit bouldering: `climbing_limit_boulder` pattern exercises
- Pulling: `archer_pullup`, `weighted_pullup` etc.
- Warmup/cooldown: existing warmup and stretch exercises

---

### Fix 3: Add `limit_boulder_gym` to S&P primary pool (S)

**File:** `backend/engine/macrocycle_v1.py` (or wherever PHASE_POOLS / session pools are defined)

Add `limit_boulder_gym` to the `strength_power` phase primary pool.

**DUP rotation logic for users with limited gym days:**

- **3+ gym days/week:** Planner places BOTH `power_contact_gym` AND `limit_boulder_gym` (+ hangboard session). Full S&P coverage.
- **2 gym days/week:** Planner places `power_contact_gym` OR `limit_boulder_gym` (alternating week-to-week via DUP) + 1 hangboard session. Each week still has 1 limit boulder + 1 hangboard.
- **1 gym day/week:** Planner places whichever boulder session scores highest for the week. Hangboard at home.

**Important:** The planner already has DUP logic for alternating sessions. The new session should plug into this naturally. If DUP alternation is not already handled for primary pool overflow, document this gap but do NOT implement rotation logic — just add to pool and let the planner's existing scoring pick.

---

### Fix 4: Update SESSION_META in planner (S)

**File:** `backend/engine/planner_v2.py`

Add `limit_boulder_gym` to `_SESSION_META` (or equivalent mapping) with:
```python
"limit_boulder_gym": {
    "hard": True,
    "climbing": True,
    "finger": False,
    "intensity": "max",
    "load": 85,
    "domains": ["finger_strength", "pulling_strength", "volume_climbing", "technique"],
}
```

---

## Files to modify (summary)

| File | Change | Risk |
|------|--------|------|
| `backend/engine/planner_v2.py` | Fix `finger_strength_home` climbing=False + add `limit_boulder_gym` to SESSION_META | LOW |
| `backend/engine/macrocycle_v1.py` | Add `limit_boulder_gym` to S&P primary pool | LOW |
| `backend/catalog/v1/sessions/limit_boulder_gym.json` | NEW FILE — session definition | LOW |
| `backend/catalog/v1/templates/` | Template blocks for the new session (use existing exercises) | LOW |
| `backend/tests/` | New tests (see below) | — |

---

## Tests required

1. **Metadata fix test:** `finger_strength_home` is NOT classified as climbing in planner scoring
2. **New session valid:** `limit_boulder_gym.json` passes schema validation
3. **Pool membership:** `limit_boulder_gym` is in S&P primary pool
4. **Session resolves:** `limit_boulder_gym` resolves to concrete exercises without errors
5. **Differentiation test:** `limit_boulder_gym` and `power_contact_gym` resolve to DIFFERENT exercise sets (not identical sessions)
6. **S&P week with 2+ gym days:** generates a week with ≥2 on-wall hard sessions
7. **S&P week with 1 gym day:** does not crash, still generates valid plan
8. **Exercise ordering:** limit bouldering exercises appear AFTER warmup, BEFORE cooldown (safety-critical ordering check)
9. **Immutability:** past weeks with old S&P plans are NOT affected (standard immutability invariant)

---

## Acceptance Criteria

- [ ] `finger_strength_home` has `climbing: False` in planner metadata
- [ ] `limit_boulder_gym` session exists, validates, resolves
- [ ] S&P primary pool includes `limit_boulder_gym`
- [ ] A user with 2+ gym days in S&P gets ≥2 on-wall climbing sessions per week
- [ ] `limit_boulder_gym` and `power_contact_gym` are meaningfully different (different template blocks)
- [ ] All existing tests pass (zero regressions)
- [ ] `sync_status.py` updated
- [ ] No changes to past/completed sessions (immutability invariant)

---

## What NOT to do

- Do NOT add a `min_on_wall_sessions` constraint to the planner (deferred — let's see if pool fix alone solves it)
- Do NOT modify `power_contact_gym` — it works fine as-is
- Do NOT modify `strength_long` — keep it as hangboard-focused
- Do NOT create new exercises — use existing catalog entries
- Do NOT touch `replanner_v1.py`, `resolve_session.py` core logic, or `closed_loop_v1.py`
