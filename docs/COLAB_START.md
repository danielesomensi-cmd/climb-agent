# Colab Start — climb-agent

## Regole Colab
- **Shell commands** → cella `%%bash`
- **Eccezione**: la UI Gradio va lanciata in **cella Python** (processo long-running + streaming).

## 0) Working directory (sempre)
Shell (`%%bash`):
- `cd /content/climb-agent`
- `pwd`

## 1) Gates end-to-end (ordine vincolante)
Shell (`%%bash`):
- `bash scripts/check_all.sh`

## 2) UI-0 (Day View) — pipeline corretta (Colab verified)

### A) Genera baseline + template
Shell (`%%bash`):
- `python scripts/run_baseline_session.py`
- `python scripts/generate_latest_log_template.py`
- `ls -la out/log_templates | tail -n 5`

### B) Avvia UI (Python cell)
Python cell:
- `!python -u scripts/ui_day_view_gradio.py --server_port 7862`

### C) Apri UI nel notebook (iframe)
Python cell:
- `from google.colab import output`
- `output.serve_kernel_port_as_iframe(7862, width=1200, height=800)`

## 3) Hygiene (importante)
- Non committare `data/logs/*.jsonl` e `out/`
- Se qualcosa “sembra duplicato” (es. bundle unzip dentro repo), pulire `out/` e rieseguire gates.
