# BACKLOG — climb-agent

> Ultimo aggiornamento: 2026-02-15 (post Cluster 2 fixes)

Feature da implementare nelle prossime fasi. Per ognuna: titolo, descrizione,
fase suggerita, dipendenze.

---

## B1. Sessione core standalone

- **Descrizione**: Sessione `core_conditioning_home.json` per slot pranzo (30-45min). Intensity "low"/"medium", dominio core + prehab. Ab wheel, hollow hold, pallof press, dead bug, front lever progressions.
- **Fase suggerita**: Inizio Fase 2
- **Dipendenze**: Nessuna (il catalogo esercizi ha già gli esercizi core)
- **Note**: Va nel pool di tutte le fasi come complementare (Pass 2)

## B2. Sessioni outdoor

- **Descrizione**: Sessioni tipo `projecting_outdoor`, `volume_outdoor`. Intent "outdoor" nel replanner. Outdoor NON è una sessione risolta dall'engine: è logging di quello che l'utente fa in falesia, con gradi/stile/tentativi.
- **Fase suggerita**: Fase 2 (tracking)
- **Dipendenze**: Trip planning, feedback contract
- **Note**: Integrazione con trip planning (deload pre-trip ora funzionante). Il logging outdoor ha uno schema diverso dalle sessioni indoor resolved.

## B3. Validazione piano vs letteratura

- **Descrizione**: Confronto struttura macrociclo con:
  - Hörst "Training for Climbing" — rapporto volume/intensità per fase, durate 4-3-2-1, distribuzione hard days (2-3/sett)
  - Lattice Training — finger training frequency e protocolli
  - Eva López — periodizzazione finger strength
- **Output**: Report "allineato" vs "devia e perché"
- **Fase suggerita**: Dopo Cluster 2, prima di Fase 2 (validazione)
- **Dipendenze**: Nessuna (analisi documentale)

## B4. Load score / fatica settimanale

- **Descrizione**: Ogni sessione nel planner deve avere un `estimated_load_score`. Modello numerico da decidere: RPE-based? stress tag aggregation? TRIMP-like? Placeholder semplice (low=20, medium=40, high=65, max=85)?
- **Output**: Weekly summary con totale load, hard days count, confronto vs target
- **Fase suggerita**: Fase 2 (tracking), design discussion prima
- **Dipendenze**: `load_model_hint` nelle sessioni (parziale, vedi strength_long)
- **Note**: Serve per: monitoraggio overtraining, input per adaptive deload, visualizzazione nella UI

## ~~B5. Replanner phase-aware + intent completi [F6, F7]~~ DONE

- **Risolto in**: Cluster 2, commit fix(F6,F7)
- **Stato**: Replanner ora usa planner_v2 `_SESSION_META`, 12 intent mappati, `phase_id` propagato

## ~~B6. PE assessment — repeater test + no double counting [F5]~~ DONE

- **Risolto in**: Cluster 2, commit fix(F5)
- **Stato**: `_compute_power_endurance()` usa repeater test (40%) + gap (40%) + self_eval (20%). Penalty ridotte.

## ~~B7. Validazioni edge case [F8, F9, F10]~~ DONE

- **Risolto in**: Cluster 2, commits fix(F9), fix(F10), fix(F8)
- **Stato**:
  - Goal validation: warning se target ≤ current o gap > 8 half-grades
  - Floor minimo: 2 settimane per fase non-deload
  - Pre-trip deload: `pretrip_dates` blocca sessioni hard, flag nel piano
