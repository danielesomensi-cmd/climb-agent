# ROADMAP — climb-agent

## Stato attuale (sintesi)
- Resolver P0 deterministico e spiegabile (hard filters + tie-break stabile).
- Log pipeline hardened (schema_version gating + quarantine + tests).
- UI-0 Gradio in Colab (template → actual → append).
- Libreria sessioni/templates ampliata (blocx power/aerobic/technique + finger endurance + deload).

---

## Next steps (locked order)

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
