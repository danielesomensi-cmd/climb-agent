
## 2026-01-28 — Stabilization complete, shifting to Planner

✅ Done
- Resolver P0 deterministico + tests green
- Log pipeline hardening: strict schema_version gating + quarantine (invalid/rejected + legacy/_bak) + tests
- Local schema registry + validate_log_entry + tests
- Repo hygiene: ignore/untrack out/ + logs
- Vocabulary coherence audit: PASS

➡️ Next (high ROI, before any P1 ranking)
1) Planner v1 (12–16 weeks): generate macro plan (periodization) using existing sessions/templates
2) Replanner v1: reschedule based on actual outcomes while keeping weekly load integrity + constraints (no finger strength back-to-back, etc.)
3) Progression v1: update proposed loads / maxes from outcomes (RPE/status/load); persist into user_state
4) Analytics loop: minimal dashboards/summary (trend load, adherence, flags)

Deferred
- P1 ranking (recency/intensity/fatigue): only after planner/replanner/progression stabilize

## 2026-02-10 — Doc alignment report (P0.5 Progression v1)

### Già implementato (repo state check)
- Planner v1 deterministico: `catalog/engine/planner_v1.py`, CLI `scripts/plan_week.py`.
- Replanner v1 event-driven deterministico: `catalog/engine/replanner_v1.py`, CLI `scripts/replan_week.py`, schema `data/schemas/plan_event.v1.json`.
- Closed-loop v1: resolve/log/update `scripts/resolve_planned_day.py`, `scripts/log_resolved_day.py`, `catalog/engine/closed_loop_v1.py`, schema `data/schemas/resolved_day_log_entry.v1.json`.
- Resolver P0 hard filters già merged e coperti da test: `catalog/engine/resolve_session.py`, `tests/test_resolver_p0.py`.

### Gap principali verso “usable loop”
- Mancava un post-processing progression esplicito e separato per target eseguibili (load e grade).
- Mancava update deterministico `working_loads` guidato da feedback per-exercise.
- Target boulder in scala Font non formalizzati (parser/stepper/offset deterministici).
- Log non esplicitava in modo standard feedback per exercise-instance orientati alla progressione.

### Docs aggiornate in questo change e perché
- `docs/01_ROADMAP.md`: riallineato next milestone a **Progression v1 (usable daily loop)**.
- `docs/04_PROGRESSION_V1.md`: esteso con target Font v0, benchmark derivation da `user_state`, esempi output suggeriti.
- `STATUS.md`: questo report di allineamento richiesto dal contratto operativo.

