# climb-agent

Deterministic climbing training engine. Generates personalised weekly plans, resolves sessions into concrete exercises, and adapts progression via closed-loop feedback — no LLM in the loop.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest backend/tests -q
```

## Repository layout

```
backend/
  engine/            # Core planning, resolving, progression, replanning
    adaptation/      # Closed-loop adaptation logic
  api/               # FastAPI application (health + planned endpoints)
  catalog/           # Exercises, sessions, templates (v1 JSON data)
  data/              # User state + JSON schemas
  tests/             # Pytest suite + fixtures
frontend/            # Future frontend app
docs/                # Domain vocabulary
_archive/            # Legacy scripts, docs, config (kept for reference)
```

## Running the API

```bash
uvicorn backend.api.main:app --reload
```

## Running tests

```bash
python -m pytest backend/tests -q
```
