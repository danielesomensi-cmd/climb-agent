# Start Here — climb-agent (Operational Contract)

Questo file è la **source of truth operativa**: layout repo, gates, e “new chat kit”.
Se un path o una regola cambia, si aggiorna **qui**.

## Repo layout (canonical paths)

### Catalogs
- **Exercises**: `catalog/exercises/v1/exercises.json`
- **Templates**: `catalog/templates/v1/*.json`
- **Sessions**: `catalog/sessions/v1/*.json`
- **Engine**: `catalog/engine/*.py`

### Data
- **Schemas**: `data/schemas/*.json`
- **User state**: `data/user_state.json`

### Local-only (non committare)
- **Logs**: `data/logs/*.jsonl` (append-only, contiene dati reali/test)
- **Artifacts**: `out/` (manual sanity, templates UI, bundle, ecc.)

## Gates (ordine vincolante)
In Colab, shell = cella `%%bash`:
- `bash scripts/check_all.sh`

## Dipendenze Python
Shell (`%%bash`):
- `pip install -r requirements.txt`

## New Chat Kit (cosa allegare)
Standard: allega **un solo zip** (context bundle) che contiene:
- `README.md`, `STATUS.md`, `pytest.ini`
- `docs/*.md`
- `catalog/**`, `data/schemas/**`, `data/user_state.json`
- `scripts/**`, `tests/**`

**Non includere per default**: `data/logs/*.jsonl`, `out/` (solo se richiesto).

### Come generare il context bundle
Shell (`%%bash`):
- `bash scripts/export_context_bundle.sh`

### Evitare 403 in Colab
1) Mount Drive (Files → Mount Drive)
2) Copia zip su: `/content/drive/MyDrive/climb-agent_bundles/`
3) Scarica da drive.google.com → MyDrive → `climb-agent_bundles/`
4) Nella nuova chat: allega lo zip + incolla un prompt breve (stato + next task).
