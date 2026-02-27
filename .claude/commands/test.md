Esegui la test suite:

```bash
source .venv/bin/activate && python3 -m pytest backend/tests/ -q 2>&1 | tail -5
```

- Se tutti i test sono **verdi**: riporta il numero totale di test passati.
- Se ci sono **test rossi**: mostra i failure completi e correggili prima di procedere con qualsiasi altra attività.
