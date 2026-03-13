# D121 — Audit: Timer mancanti + Load tracking mancante

> Data: 2026-03-13
> Status: **IN REVIEW** — attende decisione di Daniele per ogni riga

---

## Sommario

| Metrica | Valore |
|---------|--------|
| Esercizi totali nel catalogo | 162 |
| Con `work_seconds` | 74 |
| Con `rest_between_sets_seconds` | 129 |
| Con `rest_between_reps_seconds` | 25 |
| Timer mostrato nel guided session | 156 |
| Senza timer | 6 |
| Load model `bodyweight_only` | 103 |
| Load model `external_load` | 19 |
| Load model `total_load` | 16 |
| Load model `grade_relative` | 24 |

---

## Logica timer nel frontend

**File:** `frontend/src/components/guided/guided-exercise-step.tsx:433-434`

```tsx
{(((exercise.prescription.workSeconds ?? 0) > 0) ||
  ((exercise.prescription.sets ?? 1) > 1 && (exercise.prescription.restSeconds ?? 0) > 0)) && (
  <ExerciseTimer ... />
)}
```

**Regola:**
- Timer **mostrato** se:
  - `workSeconds > 0` → countdown work phase, oppure
  - `sets > 1 AND restSeconds > 0` → modalità manuale (tap "Done set") + countdown rest tra set
- Timer **nascosto** se:
  - `workSeconds == 0` E (`sets <= 1` OPPURE `restSeconds == 0`)

**`ExerciseTimer` internals** (`exercise-timer.tsx:114`):
- `workSeconds === 0` → `isManual = true` → nessun countdown work, solo "Do your set / Tap when done"
- `reps > 1 && workSeconds > 0` → `hasRepLoop = true` → cicla work→rep_rest→work per ogni rep
- `restBetweenRepsSeconds` → usato SOLO quando `hasRepLoop = true` (cioè `workSeconds > 0`)

**Implicazione critica:** `rest_between_reps_seconds` è completamente ignorato quando `work_seconds` è assente. Il timer mostra solo il rest tra set.

**Blocchi `instruction_only`:** Generati dai template di sessione (non dal catalogo esercizi). Hanno un'UI semplificata senza timer — solo testo + "Done". Mostrano durata come testo "X–Y min" ma nessun countdown.

---

## Part 1 — Timer gaps

### 1A. Esercizi con `rest_between_reps_seconds` ma senza `work_seconds` (rep rest ignorato)

Questi esercizi definiscono un rest tra le rep, ma poiché `work_seconds` è assente, il timer opera in modalità manuale e il `rest_between_reps_seconds` **non viene mai usato**. Il timer mostra solo "Do your set / Tap when done" + rest tra set.

| # | exercise_id | category | rest_reps (s) | reps | sets | rest_sets (s) | Semantica reale di "rep" | Decisione |
|---|-------------|----------|---------------|------|------|---------------|--------------------------|-----------|
| 1 | `max_hang_ladder` | main_strength | 15 | 3 | 3 | 240 | Rep = singolo hang nella ladder (3s→6s→9s). Rest 15s tra hang. | |
| 2 | `limit_bouldering` | main_strength | 180 | 5 | 4 | 300 | Rep = tentativo su un boulder. Rest 3min tra tentativi. | |
| 3 | `board_limit_boulders` | main_strength | 180 | 5 | 4 | 300 | Rep = tentativo su un boulder. Rest 3min tra tentativi. | |
| 4 | `breathing_awareness` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 5 | `foothold_stare` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 6 | `hip_rotation_drill` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 7 | `hover_hands` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 8 | `one_hand_climbing` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 9 | `sloth_monkey` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 10 | `sticky_feet` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 11 | `straight_arms` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 12 | `tap_and_place` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 13 | `three_limb_drill` | technique | 60 | 4 | 3 | 120 | Rep = un easy problem. Rest 1min tra problemi. | |
| 14 | `active_finger_curls` | prehab | 10 | 8 | 3 | 120 | Rep = singolo curl + hold 10s. | |
| 15 | `critical_force_test` | test | 3 | null | 1 | null | 7s on / 3s off to failure. Rest 3s è parte del protocollo. | |

**Possibili fix:**
- **Opzione A (tecnici):** Aggiungere `work_seconds` a questi esercizi (es. drill tecnici: work_seconds = tempo di scalata stimato). Pro: il timer cicla rep con rest countdown. Contro: il tempo di scalata varia.
- **Opzione B (drill tecnici):** Trattare i drill come "manual reps" dove il timer fa countdown del `rest_between_reps` dopo che l'utente preme "Done rep". Richiede modifica a `ExerciseTimer` per supportare `isManual + hasRepLoop`.
- **Opzione C (limit bouldering):** Queste sono sessioni dove il rest tra tentativi (3min) è il timer più utile. Il timer attuale mostra solo rest tra "set" (5min), ma manca il countdown tra i tentativi singoli.

### 1B. Esercizi senza timer (nessun countdown, nessun set tracker)

| # | exercise_id | category | sets | reps | work_s | rest_sets | rest_reps | Note |
|---|-------------|----------|------|------|--------|-----------|-----------|------|
| 1 | `critical_force_test` | test | 1 | null | null | null | 3 | 7s on / 3s off to failure. Potrebbe avere work=7 + rest_reps=3 per un timer ciclico. |
| 2 | `med_test` | test | 1 | null | null | null | null | Test misura: input manuale. OK senza timer. |
| 3 | `aerobic_pyramid_intervals` | endurance | 7 | 1 | null | null | null | Piramide 1-2-3-4-3-2-1 min. Durate variabili per set → timer statico non adatto. |
| 4 | `test_max_hang_duration_20mm` | test | 1 | null | null | null | null | Test misura: hang fino a failure. Potrebbe usare stopwatch (count-up) anziché countdown. |
| 5 | `test_l_sit_hold` | test | 1 | null | null | null | null | Test misura: hold fino a failure. Potrebbe usare stopwatch. |
| 6 | `test_hip_flexibility` | test | 1 | null | null | null | null | Test misura: cm. Nessun timer necessario. |

### 1C. Warmup con countdown lungo (potenzialmente instruction-only)

| # | exercise_id | work_seconds | Timer attuale | Questione |
|---|-------------|-------------|---------------|-----------|
| 1 | `finger_warmup_generic` | 300 (5 min) | Countdown 5:00→0:00 | Il countdown è utile? O meglio instruction-only con "~5 min"? |
| 2 | `general_pulse_raise` | 240 (4 min) | Countdown 4:00→0:00 | Stessa questione. |

---

## Part 2 — Load gaps

### 2A. Esercizi con equipment che implica carico ma `load_model: bodyweight_only`

Questi esercizi richiedono attrezzatura con peso (dumbbell, band, ecc.) ma il sistema non traccia il carico usato. L'utente non vede "Suggested load" e non può registrare il peso effettivo.

| # | exercise_id | domain | current | should_be | equipment | Ragione |
|---|-------------|--------|---------|-----------|-----------|---------|
| 1 | `elbow_wrist_extensor_eccentric` | prehab_elbow | bodyweight_only | external_load | dumbbell | Tyler Twist / eccentric wrist extension con dumbbell. Tipicamente 1-3 kg, progressivo. |
| 2 | `stick_pronation_supination_eccentric` | prehab_elbow | bodyweight_only | external_load | dumbbell | Pronazione/supinazione eccentrica con dumbbell o stick pesato. Tipicamente 0.5-2 kg. |
| 3 | `wrist_curl` | prehab_wrist | bodyweight_only | external_load | weight | Curl polso con peso. Tipicamente 2-5 kg, progressivo. |
| 4 | `reverse_wrist_curl` | prehab_wrist | bodyweight_only | external_load | weight | Curl polso inverso. Tipicamente 1-3 kg. |
| 5 | `band_external_rotation` | prehab_shoulder | bodyweight_only | external_load? | resistance_band | Rotazione esterna con banda. Il "carico" è la resistenza della banda (leggera/media/pesante), non un kg preciso. |
| 6 | `band_pull_apart` | prehab_shoulder | bodyweight_only | external_load? | resistance_band | Stessa questione: banda ha resistenza variabile, non kg preciso. |
| 7 | `elbow_eccentric_curl` | prehab_elbow | bodyweight_only | external_load? | resistance_band | Curl eccentrico con banda. |
| 8 | `pronator_terres_isometric_hold` | prehab_elbow | bodyweight_only | external_load? | resistance_band | Hold isometrico con banda. |
| 9 | `pallof_press` | core | bodyweight_only | external_load? | resistance_band | Pallof press con banda. Resistenza variabile. |
| 10 | `band_assisted_pullup` | strength_general | bodyweight_only | bodyweight_only | band | La banda RIDUCE il carico, non lo aggiunge. `bodyweight_only` è corretto? L'utente potrebbe voler tracciare "quale banda" (leggera/media/pesante). |
| 11 | `one_arm_pullup_assisted` | strength_general | bodyweight_only | bodyweight_only | band | Stessa questione: banda come assistenza, non carico. |

**Nota sulle bande elastiche:** Le bande non hanno un peso preciso in kg — hanno una resistenza variabile (es. "leggera", "media", "pesante"). Il `load_model: external_load` attuale richiede un valore in kg. Opzioni:
- **A)** Aggiungere `external_load` e lasciare che l'utente stimi (es. "banda rossa = ~5 kg")
- **B)** Creare un nuovo `load_model: band_resistance` con valori qualitativi (light/medium/heavy)
- **C)** Lasciare `bodyweight_only` per esercizi con banda e aggiungere solo un campo note

**Nota sugli esercizi con dumbbell/weight (righe 1-4):** Questi hanno un carico preciso in kg e dovrebbero quasi certamente diventare `external_load`. Il prehab ha progressione di carico nella letteratura (Tyler Twist protocol, wrist curl protocol).

### 2B. Nota architetturale: `load_model` vs `inject_targets()` hardcoded sets

**Scoperta critica:** Cambiare `load_model` nel catalogo da `bodyweight_only` a `external_load` **non è sufficiente** per attivare il suggerimento di carico. La funzione `inject_targets()` in `progression_v1.py` (linea 678+) usa **set hardcoded di exercise_id**, non il campo `load_model`:

```python
# progression_v1.py — exercise sets hardcoded
EXTERNAL_LOAD_EXERCISES = {"barbell_row", "bench_press", "dumbbell_bench_press", ...}
HANGBOARD_EXERCISES = {"max_hang_5s", "max_hang_10s", ...}
```

**Implicazione per i fix:** Per ogni esercizio che passa da `bodyweight_only` → `external_load`, serve:
1. Aggiornare `load_model` nel catalogo JSON
2. Aggiungere l'exercise_id al set corrispondente in `progression_v1.py`
3. Definire un fallback di carico (es. `EXTERNAL_LOAD_FALLBACK_PCT_BW`)
4. Verificare che il frontend mostri il campo "Actual load used"

### 2C. Campo `hold_seconds` — mai usato

Il campo `hold_seconds` menzionato nel brief **non esiste nel catalogo** (0/162 esercizi). Tutti gli esercizi con durata di hold usano `work_seconds`. Non c'è un campo separato `hold_seconds` nello schema `prescription_defaults`.

### 2D. Esercizi con `external_load` o `total_load` — verifica correttezza (nessun gap trovato)

Tutti i 19 `external_load` e 16 `total_load` sono correttamente assegnati:
- `external_load`: split_squat, romanian_deadlift, bench_press, overhead_press, barbell_row, face_pull, turkish_getup, farmers_carry, dumbbell_bench_press, bicep_curl, lateral_raise, goblet_squat, + 7 loading_pin exercises
- `total_load`: weighted_pullup, one_arm_hang_assisted, + 14 hangboard exercises
- `grade_relative`: 24 climbing exercises (bouldering, lead, traversi)

Nessun esercizio con `external_load` manca l'equipment corrispondente. Coerenza OK.

---

## Riepilogo gap e priorità suggerite

| Tipo | Count | Impatto | Priorità suggerita |
|------|-------|---------|--------------------|
| Rep rest ignorato (drill tecnici, 9 esercizi) | 9 | Timer mostra solo rest tra set, manca rest 1min tra problemi | Media — UX incompleta ma non bloccante |
| Rep rest ignorato (bouldering, 2 esercizi) | 2 | Manca countdown 3min tra tentativi boulder | Media — utile per sessioni lunghe |
| Rep rest ignorato (altri, 4 esercizi) | 4 | Vari: max_hang_ladder, active_finger_curls, critical_force_test | Media-bassa |
| Test senza stopwatch (2 esercizi) | 2 | max_hang_duration e l_sit: utente deve usare orologio esterno | Bassa — test infrequenti |
| Warmup countdown (2 esercizi) | 2 | Countdown 4-5 min funziona, ma instruction-only potrebbe essere meglio | Bassa — cosmetico |
| Load gap dumbbell/weight (4 esercizi) | 4 | Prehab con carico progressivo non tracciato | Alta — progressione persa |
| Load gap banda (7 esercizi) | 7 | Banda senza tracking, ma kg non è la metrica giusta | Bassa — richiede design decision |

---

## Prossimi passi

Daniele rivede ogni riga e segna:
- ✅ Fix it → nuovo brief o estensione B122
- ❌ Leave as-is → motivazione
- 🔄 Discuss → conversazione qui
