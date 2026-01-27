# Alignment Playbook (repo ↔ docs ↔ workflow)

**Source of truth = repo.** Se non è nel codice, non è “vero”.

## 0) Pre-flight (sempre)
Shell (Colab `%%bash`):
- `cd /content/climb-agent`
- `python scripts/check_repo_integrity.py`
- `git status -sb`
- `git log -n 5 --oneline`

## 1) Gates end-to-end (ordine vincolante)
Shell (Colab `%%bash`):
1. `python scripts/audit_vocabulary.py`
2. `python -m py_compile catalog/engine/resolve_session.py`
3. `python -m unittest discover -s tests -p "test_*.py" -v`
4. `python scripts/run_baseline_session.py`

## 2) Baseline: location truth (evitare incoerenze)
Il resolver usa `session.context.location` come priorità.
Quindi per test home vs gym:
- generare/risolvere session scenario-specific
- non affidarsi a `user_state.context.location`

## 3) UI-0 in Colab: evitare “sembra bloccato”
Non lanciare UI in `%%bash` (output spesso non streamma).
Standard:
- Python cell: `!python -u scripts/ui_day_view_gradio.py --server_port 7862`
- Python cell: `output.serve_kernel_port_as_iframe(7862, ...)`
- Consigliato: `share=False` nello `launch()`.

## 4) Checklist path/nomenclatura
### Path
Error tipico: `/content/scripts/...` invece di `/content/climb-agent/scripts/...`.
Fix: sempre `cd /content/climb-agent` prima dei comandi.

### Nomenclatura
- I nomi script citati nei docs devono esistere davvero nel repo.
- Se rinomini uno script, aggiorna docs + `check_repo_integrity.py`.

## 5) Export zip per nuove chat
Shell (Colab `%%bash`):
- `bash scripts/export_context_bundle.sh`
