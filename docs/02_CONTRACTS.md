# Contracts

## P0 Resolver contract (non negoziabile)
- Hard filters only:
  - location_allowed
  - equipment_required subset di available_equipment
  - role ANY match (block.role richiesto per selection)
  - domain solo se non azzera (se azzera: non applicarlo)
- No random. Tie-break stabile su exercise_id.
- No silent blocks: ogni block ha status + message se skipped/failed.
- instruction_only:
  - status=selected
  - nessuna selezione esercizi
  - message esplicita
  - filter_trace presente con note e counts vuoto

## Vocabulary coherence (vincolante)
- docs/vocabulary_v1.md è source of truth
- scripts/audit_vocabulary.py deve passare
- se fallisce: correggere vocabulary oppure i file incoerenti

## Colab rule
- shell command => cella con %%bash (mai inline)

## Gates (ordine obbligatorio)
1) python scripts/audit_vocabulary.py
2) python -m py_compile catalog/engine/resolve_session.py
3) python -m unittest discover -s tests -p "test_*.py" -v
4) python scripts/run_baseline_session.py
