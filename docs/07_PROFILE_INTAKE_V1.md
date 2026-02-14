# Profile Intake v1

`profile_intake.v1` è il formato canonico per bootstrap/aggiornare in modo deterministico le parti operative di `data/user_state.json` necessarie all'uso daily.

## Obiettivo

Applicare un intake iniziale senza toccare i blocchi ufficiali storici (`baselines`, `tests`, `history_index`) e senza introdurre non-determinismo.

## Input/Output

- Schema intake: `data/schemas/profile_intake.v1.json`
- Script: `scripts/apply_profile_intake.py`
- Esempio template: `out/intake_templates/profile_intake.example.json`

CLI:

```bash
python scripts/apply_profile_intake.py \
  --in out/intake_templates/profile_intake.example.json \
  --user-state data/user_state.json \
  --out /tmp/user_state.bootstrap.json
```

## Campi aggiornati (e solo questi)

Lo script aggiorna esclusivamente:

- `equipment.gyms`
- `availability`
- `planning_prefs`
- `defaults`
- `context`

Tutti gli altri campi del `user_state` restano invariati.

## Blocchi protetti (mai sovrascritti)

Se presenti nel `user_state` di input, vengono preservati byte-equivalenti in output:

- `baselines`
- `tests`
- `history_index`

## Determinismo

La procedura è deterministic by construction:

- nessun uso di wall-clock/time/random
- sort stabile su `equipment.gyms` (per `gym_id`)
- sort stabile su liste equipment/locations
- dump JSON canonico (`indent=2`, `sort_keys=true`, trailing newline)

## Validazioni

1) Validazione JSON Schema (`profile_intake.v1`).
2) Validazione vocabolario canonico (`docs/vocabulary_v1.md`) per:
   - location (`home|gym|outdoor`)
   - equipment (insieme chiuso v1: `hangboard`, `pullup_bar`, `band`, `weight`, `dumbbell`, `kettlebell`, `pangullich`, `spraywall`, `board_kilter`, `gym_boulder`, `gym_routes`)

Su errore, lo script fallisce esplicitamente con messaggio diagnostico.


Note inventory palestre reali: ogni voce `equipment.gyms[]` può includere `priority` (intero crescente, 1 migliore) per consentire selezione palestra deterministica quando lo slot non impone `gym_id`.
