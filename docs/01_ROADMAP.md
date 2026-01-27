# ROADMAP — climb-agent

## Stato attuale (sintesi)
- Resolver P0 deterministico e spiegabile (hard filters + tie-break stabile).
- Logging Option B: template -> compile actual -> append (S3 quarantine).
- UI-0 (Gradio) gira in Colab ma va documentata correttamente (run in Python cell, non in %%bash).

---

## Next steps (locked order)
### A) Stabilizzazione “Dev UX” (bloccante)
1) **Allineare docs ↔ repo** (source of truth = file nel repo)
2) **UI-0 Colab-safe** (no black-box, no share tunnel, path guardrail)
3) **Integrity/Gates** sempre in ordine

### B) UI-0 (end-to-end) (bloccante per usare il sistema)
- Pipeline: baseline resolve → template → UI → S3 append → mini stats
- Output attesi:
  - un template in `out/log_templates/`
  - UI che carica template e consente edit actual
  - append valida e scrive su `data/logs/sessions_2026.jsonl`
  - invalid quarantena su `data/logs/session_logs_rejected.jsonl`

### C) Planner long-term (non bloccante oggi)
- `planner_profile.json`: disponibilità, obiettivi, preferenze (stabile, “user intent”)
- Macro-cycle (28d/12w) con periodizzazione stile Hörst (forza → power → endurance → peak/deload)
- `planner_state.json`: derivato dai log (recency/fatigue flags) **senza** auto-update baseline

### D) P1 ranking (non bloccante)
- ranking deterministico su shortlist (recency/intensity/fatigue/preference/phase)
- si può implementare dopo: oggi non impedisce l’uso del sistema

---

## Issues aperti (da chiudere)
### 1) Colab UI non va lanciata in `%%bash`
- In Colab l’output di processi long-running (server) in `%%bash` spesso non streamma → “sembra bloccato”.
- Standard: lanciare la UI con una cella Python: `!python -u ...` e aprire con `serve_kernel_port_as_iframe`.

### 2) Path / working directory
- Standard: sempre `cd /content/climb-agent` prima di ogni comando.
- Guardrail consigliato nello script UI per evitare path tipo `/content/scripts/...`.

### 3) Naming e file presence
- Uniformare i nomi degli script (es. `generate_latest_log_template.py` vs altri).
- Aggiungere `scripts/check_repo_integrity.py` per fallire subito se manca un file richiesto.

