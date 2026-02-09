# Alignment Playbook (repo ↔ docs ↔ workflow)

## Agent Ops Contract (must-follow)

**Read first (always):**
- docs/00_START_HERE.md
- docs/02_CONTRACTS.md
- docs/vocabulary_v1.md
- docs/COLAB_START.md (Colab workflow)
- docs/UI_DAY_VIEW_GRADIO.md (only if UI work)

**Non-negotiables**
- Source of truth = repo + docs contracts. If it’s not in code/docs, it’s not true.
- No push from Codex/agents. Only prepare changes; human pushes from Colab.
- In Colab: shell commands go in **one single** `%%bash` cell (do not split).
- UI: interactive runs in **Python cell** (see docs/COLAB_START.md). Bash+nohup allowed **only** for smoke tests (see UI runbook).
- Gates: run `bash scripts/check_all.sh` before declaring done.
- Vocabulary: `docs/vocabulary_v1.md` is source of truth; `python scripts/audit_vocabulary.py` must pass.

**Docs update rule**
If you change workflow, gates, schemas, vocabulary, or folder layout, you must update the relevant docs in the same change:
- 00_START_HERE.md (entrypoint + bundle rules)
- 02_CONTRACTS.md (behavioral contracts)
- COLAB_START.md / UI_DAY_VIEW_GRADIO.md (runbooks)
- vocabulary_v1.md (if tags/equipment/patterns change)


**Source of truth = repo.** Se non è nel codice o nei contratti docs, non è “vero”.

## 0) Pre-flight (sempre)
Shell (`%%bash`):
- `cd /content/climb-agent`
- `git status -sb`
- `git log -n 5 --oneline`

Se vedi tracked logs/artifacts: **STOP** → untrack (keep local) e aggiorna `.gitignore`.

## 1) Gates (ordine vincolante)
Shell (`%%bash`):
- `bash scripts/check_all.sh`

## 2) Coerenza vocabolario (vincolante)
- `docs/vocabulary_v1.md` è source of truth
- `python scripts/audit_vocabulary.py` deve passare
- Se fallisce: o aggiorni `vocabulary_v1.md` o riallinei i JSON/catalog.

## 3) Context & location truth
Il resolver usa `session.context.location` come priorità.
Per test home vs gym:
- usare session scenario-specific
- non affidarsi solo a `user_state.context.location`

## 4) UI-0 in Colab
Non lanciare UI in `%%bash` (spesso non streamma e “sembra bloccato”).
Standard:
- Python cell: `!python -u scripts/ui_day_view_gradio.py --server_port 7862`
- Python cell: `output.serve_kernel_port_as_iframe(7862, width=1200, height=800)`
