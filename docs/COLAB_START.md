# Colab Start — climb-agent

**Regola:** comandi shell in cella `%%bash`.  
**Eccezione:** la UI Gradio va lanciata in **cella Python** (non `%%bash`) perché Colab spesso non streamma stdout per processi long-running (server), quindi “sembra bloccato”.

## 0) Set working directory (sempre)
**Shell (Colab `%%bash`):**
- `cd /content/climb-agent`
- `pwd`

## 1) Gates end-to-end (ordine vincolante)
**Shell (Colab `%%bash`):**
- `python scripts/check_repo_integrity.py`
- `python scripts/audit_vocabulary.py`
- `python -m py_compile catalog/engine/resolve_session.py`
- `python -m unittest discover -s tests -p "test_*.py" -v`
- `python scripts/run_baseline_session.py`

## 2) UI-0 (Day View) — pipeline corretta (Colab verified)

### A) Genera template (shell)
**Shell (Colab `%%bash`):**
- `python scripts/run_baseline_session.py`
- `python scripts/generate_latest_log_template.py`
- `ls -la out/log_templates | tail -n 5`

### B) Avvia UI (Python cell; streaming)
**Python cell:**
- `!python -u scripts/ui_day_view_gradio.py --server_port 7862`

### C) Apri UI nel notebook (iframe)
**Python cell:**
- `from google.colab import output`
- `output.serve_kernel_port_as_iframe(7862, width=1200, height=800)`

Troubleshooting rapido:
- Se vedi errori tipo `/content/scripts/...` ⇒ non sei nel repo root: fai `cd /content/climb-agent`.
- Se “Executing…” infinito in `%%bash` ⇒ normale: stai lanciando un server senza streaming. Usa la cella Python.

