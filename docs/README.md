# docs/ — indice

> Mappa dei documenti del repo. Spostata da `CLAUDE.md` in D285 (2026-10-17).

- `PROJECT_BRIEF.md` — Project status + auto-updated counters (run `python scripts/sync_status.py`)
- `docs/API_ENDPOINTS.md`, `docs/FRONTEND.md`, `docs/DEPLOYMENT.md`, `docs/SESSION_ISOLATION.md` — reference moved out of this file in D285
- `docs/ROADMAP_CURRENT.md` — All open items, priorities, future phases
- `docs/ROADMAP_v2.md` — Archived history (frozen, do not update)
- `docs/vocabulary_v1.md` — Domain glossary (update when adding enums/types)
- `docs/DESIGN_GOAL_MACROCICLO_v1.1.md` — Design doc (update when methodology changes)
- `docs/literature_review_climbing_training.md` — Training science reference
- `docs/docs_literature_hangboard.md` — Hangboard science reference
- `docs/beta_feedback.md` — Beta tester feedback log
- `docs/audit_workflow.md` — Repeatable literature audit process (snapshot extraction → knowledge base audit → implementation brief)
- `docs/ENGINE_ARCHITECTURE.md` — Engine internals reference (how modules work, data flow, key data structures)
- `docs/user_guide_v1.md` — User-facing guide (update after A/B briefs that change UX)
- `docs/attribution_utm_convention.md` — UTM convention per channel (flyer QR, Reddit, email) + how first-touch attribution flows into `user_state.attribution` (A233)
- All audit deliverables live in `docs/audit/<brief-id>_<topic>.md` (singular `audit/`, never `docs/audits/`). Obsolete/closed audits move to `_archive/docs/audit/`.
