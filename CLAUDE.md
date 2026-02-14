# CLAUDE.md — climb-agent

## Project context

climb-agent is a deterministic climbing training engine. It generates personalised weekly training plans, resolves abstract sessions into concrete exercises with sets/reps/load, and adapts progression through closed-loop feedback. No LLM is used at runtime — all logic is rule-based and testable.

## Principles

- **Deterministic**: Given the same user state and inputs, output is always the same.
- **Closed-loop**: Every session outcome feeds back into user state for future planning.
- **Data-driven**: Sessions, exercises, and templates are JSON catalogs — logic is separate from data.
- **Test-first**: All engine behaviour is covered by pytest. Tests must pass before merging.

## Key commands

```bash
# Run all tests
python -m pytest backend/tests -q

# Run a single test file
python -m pytest backend/tests/test_planner_v1.py -q

# Start API dev server
uvicorn backend.api.main:app --reload

# Type-check (if mypy is installed)
mypy backend/engine/
```

## Repository structure

```
backend/
  engine/            # Core logic: planner, resolver, replanner, progression, closed-loop
    adaptation/      # Closed-loop adaptation (multiplier-based adjustments)
  api/               # FastAPI app — health endpoint, future REST API
  catalog/           # JSON data: exercises, sessions, templates (versioned under v1/)
  data/              # user_state.json + JSON schemas for log validation
  tests/             # Pytest suite with fixtures/
frontend/            # Placeholder for future frontend
docs/                # vocabulary_v1.md, DESIGN_GOAL_MACROCICLO_v1.1.md — domain docs & design goals
_archive/            # Legacy scripts, docs, config (do not modify)
```

## Import conventions

All Python imports use the `backend.` prefix:

```python
from backend.engine.planner_v1 import generate_week_plan
from backend.engine.resolve_session import resolve_session
```

Data paths are relative to the repo root:

```python
"backend/catalog/sessions/v1/strength_long.json"
"backend/data/user_state.json"
```

## Catalog status (post Fase 0 expansion)

- **Exercises**: ~102 in `backend/catalog/exercises/v1/exercises.json`
- **Sessions**: ~28 in `backend/catalog/sessions/v1/`
- **Templates**: 11 in `backend/catalog/templates/v1/` (unchanged)

### Exercise categories covered
- Finger strength: max hang, repeaters, long duration, min edge, pinch, density, one-arm
- Power & contact strength: campus (laddering, bumps, dynos), limit bouldering, board bouldering
- Power endurance: 4x4, linked boulders, route intervals, ARC, threshold
- Endurance/regeneration: continuity climbing, easy laps, easy traverse
- Pulling strength: pullup variants (weighted, L-sit, archer, typewriter, one-arm), rows, lock-offs
- Push/antagonist: pushups, dips, pike pushup, shoulder press, ring pushup, bench, face pull
- Core: hollow hold, L-sit, front lever, hanging leg raise, ab wheel, pallof, side plank, dead bug, windshield wipers, toes-to-bar
- Prehab: wrist curls, forearm rotation, rotator cuff, scapular pullups, finger extensors, elbow eccentrics, shoulder CARs
- Technique drills: silent feet, no readjust, downclimbing, slow climbing, flag practice
- Flexibility: hip opener, shoulder stretch, forearm stretch, full body flow, active hip mobility
- Complementary - handstand: wall hold, wall walk-up, shoulder taps, freestanding, HSPU
- Complementary - conditioning: jump rope, TGU, farmer carry, bear crawl, band pull-apart

### Equipment note
`pangullich` has been renamed to `campus_board` as canonical equipment ID.
Equipment marked in `equipment_required` is truly mandatory (cannot do the exercise without it).
Optional equipment is mentioned in `prescription_defaults.notes` only.

## Testing

Tests live in `backend/tests/`. The `conftest.py` adds the repo root to `sys.path` so `import backend.*` works. Run with:

```bash
python -m pytest backend/tests -q
```
