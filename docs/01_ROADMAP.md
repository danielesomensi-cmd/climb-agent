# ROADMAP — climb-agent

## Stato attuale (sintesi)
- Resolver P0 deterministico e spiegabile (hard filters + tie-break stabile).
- Log pipeline hardened (schema_version gating + quarantine + tests).
- UI-0 Gradio in Colab (template → actual → append).
- Libreria sessioni/templates ampliata (blocx power/aerobic/technique + finger endurance + deload).

---

## Next steps (locked order)

### P0 hygiene track (parallel, small PRs)
- Manual sanity scenarios: keep out/manual_sanity outputs readable
- Explainability: add per-block filter_trace counts (no silent skips)
- Data-first cleanup: remove/archive legacy selection.filters where unused



### A) Manual sanity + UI E2E (bloccante operativo)
**DoD**
- manual sanity produce `.out.json` leggibili e sensati
- UI legge template, scrive actual, append va su log principale (reject solo per invalid)

### B) Planner v1 (12–16 settimane) — focus adesso (alta ROI)
**DoD**
- genera un piano deterministico (macro-fasi + schedule settimanale)
- supporta planning modes (strength/endurance/peak/maintenance)
- produce `plan.json` + “explain” (perché questa sessione quel giorno)
- non dipende da P1 ranking

### C) Replanner v1 (realtà-first)
**DoD**
- se salti un giorno o fai outdoor: rischedula senza rompere vincoli
- mantiene “budget settimanale” (hard/finger caps)
- preserva deload e spacing minimo hard-days

### D) Progression v1 (loads/maxes)
**DoD**
- aggiorna working loads / maxes da actual (status + RPE + load)
- persist su `data/user_state.json`

### E) Analytics loop (minimo)
- aderenza, trend load, flags (fatigue/pain), rolling summary

### Deferred
- P1 ranking (recency/intensity/fatigue) → dopo Planner/Replanner/Progression.


## Status update
- Planner v1: implemented and deterministic.
- Replanner v1: implemented deterministic override/ripple + event-driven replanning (`scripts/replan_week.py`, `plan_event.v1`).
- Closed-loop V1: implemented (resolve planned day + log done/skipped + user_state recency/fatigue updates).

- Next milestone: Replanning V2 (cross-week backlog carry + fatigue-aware replacement policy).
