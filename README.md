# climb-agent

Deterministic climbing training planning engine. Generates personalised weekly plans based on assessment, goal, and availability. Resolves sessions into concrete exercises with loads. Adapts progression via closed-loop feedback. No LLM in the planning loop.

## Features

- **Assessment** — 6-axis radar profile (finger strength, pulling, power endurance, technique, endurance, body composition)
- **Macrocycle** — Hörst 4-3-2-1 periodization with DUP, 10-13 weeks, 5 phases
- **Weekly planner** — phase-aware, 2-pass algorithm, gym/home/outdoor slot handling
- **Session resolver** — selects concrete exercises with sets/reps/load, cross-session recency
- **Closed-loop adaptation** — feedback drives multiplier-based load adjustments
- **Outdoor logging** — spot management, route/attempt logging, stats (onsight%, grade histogram)
- **Reports** — weekly adherence + highlights, monthly trends + suggestions
- **Motivational quotes** — 200-quote catalog, contextual selection, 30-day rotation

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest backend/tests -q   # ~360 tests
```

## Running the API

```bash
uvicorn backend.api.main:app --reload --reload-exclude "backend/data/*" --port 8000
```

## Repository layout

```
backend/
  engine/            # Core: planner, resolver, replanner, progression, outdoor log, reports, quotes
    adaptation/      # Closed-loop adaptation (multiplier-based)
  api/               # FastAPI app (12 routers, 26 endpoints)
  catalog/           # Exercises (103), sessions (33), templates (19), quotes (200)
  data/              # user_state.json + JSON schemas
  tests/             # ~360 pytest tests
frontend/            # Next.js 14 PWA (React, Tailwind, shadcn/ui) — 19 pages
docs/                # ROADMAP_v2.md, DESIGN_GOAL_MACROCICLO_v1.1.md, vocabulary_v1.md
```

## Stack

- **Backend**: Python 3.11, FastAPI, pure JSON persistence (no database)
- **Frontend**: Next.js 14, React, Tailwind CSS, shadcn/ui, PWA
- **Periodization**: Hörst 4-3-2-1 + Daily Undulating Periodization
