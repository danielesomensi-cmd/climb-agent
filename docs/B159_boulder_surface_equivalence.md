# B159 — Boulder Surface Equivalence + Exercise Equipment Audit

> **Type:** B (bugfix) + D (audit)
> **Priority:** P1 — blocks correct session placement for any user without literal "gym_boulder"
> **Risk:** MEDIUM — touches planner equipment matching + resolver equipment check
> **Origin:** D154/D155 debug: Cocque has spraywall+kilter but no gym_boulder → all boulder sessions fail

---

## Problem Statement

Sessions requiring `gym_boulder` (limit_boulder_gym, power_contact_gym, boulder_circuit_gym, technique_focus_gym, etc.) cannot be placed at gyms that have `spraywall`, `board_kilter`, `board_moonboard`, `board_other` — even though you can absolutely do limit bouldering on a spraywall or Kilter Board.

Same issue with `homewall` — B137 added homewall→gym_boulder expansion, but this was a special case. The real fix is a unified concept.

---

## Phase 0: Audit (read-only, MANDATORY STOP)

### Step 1: Define BOULDER_SURFACES

```python
BOULDER_SURFACES = {
    "gym_boulder",      # standard gym bouldering walls
    "spraywall",        # spray wall
    "board_kilter",     # Kilter Board
    "board_moonboard",  # MoonBoard
    "board_tension",    # Tension Board
    "board_other",      # any other training board
    "homewall",         # home bouldering wall
}
```

### Step 2: Find ALL sessions that require gym_boulder

```bash
grep -r "gym_boulder" backend/catalog/v1/sessions/*.json
grep -r "gym_boulder" backend/engine/planner_v2.py
```

List every session and check: should it work on ANY boulder surface, or is it genuinely gym_boulder-only?

### Step 3: Find ALL exercises that require specific boulder equipment

```bash
grep -r '"equipment"' backend/catalog/exercises/v1/exercises.json | grep -E "gym_boulder|spraywall|board_kilter|board_moonboard|board_tension|board_other|homewall"
```

For each exercise found:
- Is the equipment restriction correct? (e.g., "Board Limit Boulders (Kilter/Moon/Tension)" — should this work on spraywall too? On gym_boulder too?)
- Are there exercises locked to board_kilter that should be available on all boulder surfaces?
- Are there exercises locked to gym_boulder that should also work on boards?

### Step 4: Find the existing homewall→gym_boulder expansion

```bash
grep -r "homewall" backend/engine/planner_v2.py
grep -r "homewall" backend/engine/resolve_session.py
```

Document exactly how B137 expansion works, so we can replace it with the unified approach.

### Step 5: Check vocabulary_v1.md for equipment definitions

Verify all boulder surface equipment values are in the vocabulary.

---

## STOP — Report findings before implementing

Report must include:
1. Complete list of sessions requiring gym_boulder (and whether they should accept all BOULDER_SURFACES)
2. Complete list of exercises with specific boulder equipment filters
3. Any exercises that are overly restrictive (e.g., kilter-only when they could be any board)
4. Current B137 homewall expansion code location
5. Proposed implementation approach

---

## Phase 1: Implementation (after approval)

### Approach: Equipment expansion function

Create a utility function that expands boulder equipment:

```python
BOULDER_SURFACES = {"gym_boulder", "spraywall", "board_kilter", "board_moonboard", "board_tension", "board_other", "homewall"}

def expand_boulder_equipment(user_equipment: set) -> set:
    """If user has ANY boulder surface, they effectively have gym_boulder."""
    if user_equipment & BOULDER_SURFACES:
        return user_equipment | {"gym_boulder"}
    return user_equipment
```

This is applied at TWO points:
1. **Planner** (`_find_best_slot` or equivalent): when checking if a session's required_equipment matches a gym's equipment
2. **Resolver** (`get_location_equipment` or equivalent): when checking if an exercise's required equipment is available

This **replaces** the B137 homewall-specific expansion with a general solution.

### For exercises with specific board requirements

If the audit finds exercises like:
- `board_limit_boulders` requiring `board_kilter` → should accept ANY board surface
- Some exercise requiring `spraywall` → should accept any boulder surface

Then either:
- (a) Change exercise equipment to `gym_boulder` (simplest — means "any boulder surface")
- (b) Add a `BOARD_SURFACES` sub-group if we need to distinguish boards from gym walls

### Tests

1. Session requiring gym_boulder is placed at gym with ONLY spraywall
2. Session requiring gym_boulder is placed at gym with ONLY board_kilter
3. Session requiring gym_boulder is placed at home with homewall
4. Session requiring gym_boulder is NOT placed at gym with only gym_routes (no boulder surface)
5. Exercise requiring gym_boulder resolves at gym with spraywall
6. Daniele's plan: Cocque (spraywall + kilter) gets boulder sessions
7. B137 homewall equivalence still works (regression test)
8. Resolver at home with homewall produces climbing exercises

---

## Acceptance Criteria

- [ ] BOULDER_SURFACES constant defined
- [ ] Planner equipment matching uses expansion
- [ ] Resolver equipment matching uses expansion  
- [ ] B137 homewall expansion replaced by general solution
- [ ] All exercises with overly-specific board requirements are fixed
- [ ] Daniele's real plan places boulder sessions at Cocque
- [ ] All existing tests pass
- [ ] New tests cover all boulder surface combinations
