# Colab Start — climb-agent

## Regole Colab
- **Shell commands** → cella `%%bash`
- **Eccezione**: la UI Gradio va lanciata in **cella Python** (processo long-running + streaming).

## 0) Working directory (sempre)
Shell (`%%bash`):
- `cd /content/climb-agent`
- `pwd`

## 0.5) Dipendenze Python
Shell (`%%bash`):
- `pip install -r requirements.txt`

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
<!-- CLIMB_AGENT_UI_DAY_VIEW_SECTION_V1 -->

## Gradio UI Day View — Note operative (anti-errori)
- In Colab: **mai spezzare** i comandi. Ogni procedura in **UNA sola cella**.
- Se è bash: prima riga `%%bash`.
- Evita heredoc con delimiter comuni (`PY`, `MD`, ecc.). Se il delimiter compare nel testo, bash tronca lo script.
  - Usa delimiter unici tipo `__DOC_WRITE__`, `__RESOLVE__`, ecc.
  - Oppure (preferito): scrivi i `.md` via Python `Path(...).write_text()`.

Runbook UI: vedi `docs/UI_DAY_VIEW_GRADIO.md`.
