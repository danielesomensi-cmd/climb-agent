# BACKLOG — climb-agent

> Ultimo aggiornamento: 2026-02-15 (post fix cluster E2E)

Feature da implementare nelle prossime fasi. Per ognuna: titolo, descrizione,
fase suggerita, dipendenze.

---

## B1. Sessione core standalone

- **Descrizione**: Sessione `core_conditioning_home.json` per slot pranzo (30-45min). Intensity "low"/"medium", dominio core + prehab. Ab wheel, hollow hold, pallof press, dead bug, front lever progressions.
- **Fase suggerita**: Cluster 2 o inizio Fase 2
- **Dipendenze**: Nessuna (il catalogo esercizi ha già gli esercizi core)
- **Note**: Va nel pool di tutte le fasi come complementare (Pass 2)

## B2. Sessioni outdoor

- **Descrizione**: Sessioni tipo `projecting_outdoor`, `volume_outdoor`. Intent "outdoor" nel replanner. Outdoor NON è una sessione risolta dall'engine: è logging di quello che l'utente fa in falesia, con gradi/stile/tentativi.
- **Fase suggerita**: Fase 2 (tracking)
- **Dipendenze**: Replanner phase-aware (B5), trip planning, feedback contract
- **Note**: Integrazione con trip planning (deload pre-trip). Il logging outdoor ha uno schema diverso dalle sessioni indoor resolved.

## B3. Validazione piano vs letteratura

- **Descrizione**: Confronto struttura macrociclo con:
  - Hörst "Training for Climbing" — rapporto volume/intensità per fase, durate 4-3-2-1, distribuzione hard days (2-3/sett)
  - Lattice Training — finger training frequency e protocolli
  - Eva López — periodizzazione finger strength
- **Output**: Report "allineato" vs "devia e perché"
- **Fase suggerita**: Dopo Cluster 1, prima di Fase 2 (validazione)
- **Dipendenze**: Nessuna (analisi documentale)

## B4. Load score / fatica settimanale

- **Descrizione**: Ogni sessione nel planner deve avere un `estimated_load_score`. Modello numerico da decidere: RPE-based? stress tag aggregation? TRIMP-like? Placeholder semplice (low=20, medium=40, high=65, max=85)?
- **Output**: Weekly summary con totale load, hard days count, confronto vs target
- **Fase suggerita**: Fase 2 (tracking), design discussion prima
- **Dipendenze**: `load_model_hint` nelle sessioni (parziale, vedi strength_long)
- **Note**: Serve per: monitoraggio overtraining, input per adaptive deload, visualizzazione nella UI

## B5. Replanner phase-aware + intent completi [F6, F7]

- **Descrizione**: replanner_v1 usa planner_v1 SESSION_LIBRARY, non conosce macrociclo. Intent mancanti: core, prehab, flexibility, outdoor, projecting. Il replanner deve consultare il session_pool della fase corrente.
- **Fase suggerita**: Cluster 2
- **Dipendenze**: B1 (core session), B2 (outdoor sessions)

## B6. PE assessment — repeater test + no double counting [F5]

- **Descrizione**: `_compute_power_endurance()` non usa il repeater test oggettivo (24 reps a 60% max, in user_state.tests.endurance). Double counting: gap RP-OS + penalty self_eval pump_too_early.
- **Fase suggerita**: Cluster 2
- **Dipendenze**: Nessuna
- **Note**: Il repeater test esiste già in user_state. Aggiungere benchmark per grado (es. 8b target → 30+ reps expected)

## B7. Validazioni edge case [F8, F9, F10]

- **Descrizione**:
  - Pre-trip deload reale (non solo annotazione) — inserire settimana di deload prima del trip
  - Validazione goal ≤ current → warning o errore
  - Floor minimo 2 settimane per fase (1w solo per deload)
- **Fase suggerita**: Cluster 2
- **Dipendenze**: Nessuna
