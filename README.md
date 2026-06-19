# climb-agent

Deterministic climbing training engine. Generates personalised weekly plans, resolves sessions into concrete exercises with sets/reps/load, and adapts through closed-loop feedback. No LLM at runtime — all logic is rule-based and testable.

Methodology: Hörst 4-3-2-1 adaptive periodization with DUP (Daily Undulating Periodization).

## Status

<!-- STATUS_TABLE_START -->
| Metric | Count |
|--------|-------|
| Tests (passing) | 2229 |
| Exercises | 225 |
| Sessions (active) | 35 |
| Templates | 19 |
| API endpoints | 77 |
| Frontend pages | 43 |
| Frontend components | 81 |
<!-- STATUS_TABLE_END -->

## Architecture

```
Assessment (5 dimensions → radar profile 0-100)
  → Goal (lead_grade or boulder_grade, target + deadline)
  → Macrocycle (Hörst 4-3-2-1 + DUP, 10-13 weeks, 5 phases)
  → Week (planner_v2: multi-pass, phase-aware, location-aware)
  → Session (resolver: templates → concrete exercises with loads)
  → Feedback (per-exercise, 5 levels) → Adaptation (closed-loop)
```

## Tech stack

- **Backend:** Python / FastAPI on Railway
- **Frontend:** Next.js 16 PWA (React + Tailwind + shadcn/ui) on Vercel
- **Auth:** Clerk
- **Persistence:** Supabase Postgres + JSONB (production), JSON files (dev/test)
- **Methodology:** Hörst 4-3-2-1 with DUP concurrent training

## Repository layout

```
backend/
  engine/       # Core: planner, resolver, replanner, progression, closed-loop
  api/          # FastAPI REST API
  catalog/      # JSON: exercises, sessions, templates
  tests/        # pytest suite
frontend/       # Next.js 16 PWA
docs/           # Design docs, vocabulary, roadmap
scripts/        # Automation (sync_status.py)
```

## Development

```bash
# Run tests
source .venv/bin/activate && python -m pytest backend/tests -q

# Start backend (port 8000)
uvicorn backend.api.main:app --reload --port 8000

# Start frontend (port 3000)
cd frontend && npm run dev

# Sync project counters
python scripts/sync_status.py
```

## Deployment

Auto-deploy on push to main (~2-3 min).

| Service | Platform | URL |
|---------|----------|-----|
| Backend | Railway | https://web-production-fb1e9.up.railway.app |
| Frontend | Vercel | https://climb-agent.vercel.app |
