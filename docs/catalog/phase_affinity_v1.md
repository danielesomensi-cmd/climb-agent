# `phase_affinity` — come si assegna (v1, A257)

Riferimento operativo per il campo `phase_affinity` del catalogo esercizi.
Serve a due cose: capire perché un esercizio ha i valori che ha, e sapere cosa
scrivere quando se ne aggiunge uno nuovo.

## Cos'è e chi lo usa

`phase_affinity` elenca le fasi del macrociclo in cui l'esercizio è
**metodologicamente appropriato**. È una **preferenza di ranking**, non un
filtro: `adhoc_builder._rank_key` mette davanti gli esercizi che corrispondono
alla fase corrente dell'utente, e a parità ordina per id.

Unico consumer: `backend/engine/adhoc_builder.py` (il composer di sessioni
ad-hoc del coach). Il planner (`resolve_session`, `planner_v2`) **non** lo legge
— la periodizzazione del piano passa da `_SESSION_POOL` in `macrocycle_v1`.

Fino ad A257 il campo esisteva su 1 esercizio su 255: il criterio non
discriminava mai e la selezione collassava sull'ordine alfabetico dell'id
(diagnosi completa in `docs/audit/D261_adhoc_selection_ranking.md`).

## La regola

Un esercizio è appropriato a una fase quando **entrambe** le condizioni valgono:

1. **L'asse di allenamento che esercita è enfatizzato in quella fase**, secondo
   `_BASE_WEIGHTS` di `macrocycle_v1` (design doc §4.3, Hörst 4-3-2-1). Un asse
   conta per una fase se il suo peso lì è ≥ la media del peso di quell'asse
   sulle cinque fasi. Se la distribuzione è **piatta** (spread ≤ 0.05, come per
   `core_prehab`) l'asse non esprime preferenza: vale in tutte le fasi, e a
   discriminare resta l'intensità.
2. **L'intensità dell'esercizio rientra nella banda della fase** (derivata da
   `PHASE_INTENSITY_CAP`):

   | fase | banda d'intensità |
   |---|---|
   | base | low, medium |
   | strength_power | high, max |
   | power_endurance | medium, high |
   | performance | high, max |
   | deload | very_low, low |

**Eccezione — deload.** L'affinità al deload si concede sulla sola intensità,
ignorando l'asse: una settimana di scarico non enfatizza un asse, chiede lavoro
*leggero*. Senza questa eccezione interi focus (le dita, per esempio) restavano
senza un solo candidato adatto in scarico.

### Dominio → asse

| asse (`_BASE_WEIGHTS`) | domini del catalogo |
|---|---|
| `finger_strength` | finger_strength, finger_max_strength, contact_strength |
| `pulling_strength` | strength_pulling, strength_general, lock_off_endurance, power |
| `power_endurance` | power_endurance, anaerobic_capacity, finger_strength_endurance |
| `volume_climbing` | aerobic_capacity, finger_aerobic_endurance, climbing_routes |
| `technique` | technique_* (tutti), handstand_skill |
| `core_prehab` | core, prehab_shoulder, prehab_elbow, prehab_wrist, prehab_finger |
| *recovery* (fuori tabella) | mobility, flexibility, regeneration → `["base", "deload"]` |

`recovery` non è un asse di carico: mobilità e rigenerazione appartengono alla
costruzione di base e allo scarico, non alle fasi di intensità.

### Fasi risultanti per asse

| asse | fasi |
|---|---|
| finger_strength | base, strength_power |
| pulling_strength | base, strength_power |
| power_endurance | power_endurance, performance |
| volume_climbing | base, performance |
| technique | base, power_endurance, performance |
| core_prehab | tutte (asse piatto) |

## Esempi di controllo

| esercizio | dominio | intensità | affinità | perché |
|---|---|---|---|---|
| `max_hang_5s` | finger_max_strength | max | strength_power | asse dita → base+SP; `max` esclude base |
| `dead_bug` | core | low | base, deload | asse piatto; `low` ammesso solo lì |
| `front_lever_tuck` | core | high | strength_power, power_endurance, performance | asse piatto; `high` ammesso lì |
| `lock_off_isometric` | strength_pulling | high | strength_power | tirata → base+SP; `high` esclude base |
| `cooldown_hip_pigeon` | flexibility, mobility | low | base, deload | recovery |
| `repeater_15_15` | finger_strength_endurance | medium | power_endurance | asse PE → PE+perf; `medium` esclude perf |

## Aggiungere un esercizio nuovo

Applica la regola a mano: guarda il dominio → trova l'asse → prendi le fasi di
quell'asse → tieni solo quelle la cui banda contiene l'`intensity_level`
dell'esercizio; aggiungi `deload` se l'intensità è `very_low`/`low`.

Il test `backend/tests/test_a257_phase_affinity.py` verifica la coerenza
(copertura, id di fase validi, rispetto della banda d'intensità), quindi un
valore incoerente fa fallire la suite. **Non esiste uno script di
rigenerazione**: i valori sono dati di catalogo, versionati e rivedibili a mano
come tutto il resto.

## Limiti noti (v1)

- L'affinità discrimina l'appropriatezza alla fase, **non ordina dentro** il
  gruppo che corrisponde: a parità di fase si torna all'ordine alfabetico. Se
  in futuro servisse una preferenza più fine (es. "il miglior esercizio per
  questa fase", non "uno appropriato"), serve un punteggio, non un elenco.
- Essendo una preferenza e non un filtro, quando i candidati appropriati si
  esauriscono (cap di diversità, budget di tempo) la coda della selezione può
  pescare esercizi non appropriati — per esempio lavoro `high` in una settimana
  di scarico. Tracciato come `A-ADHOC-DELOAD-CAP` in roadmap.
- In fase `performance` gli assi di forza sono de-enfatizzati per metodologia
  (`pulling_strength` pesa 0.05): una richiesta di bloccaggi in quella fase non
  trova candidati "appropriati" e torna all'ordine alfabetico. È corretto, ma
  spiega perché il guadagno non è uniforme su tutti i focus.
