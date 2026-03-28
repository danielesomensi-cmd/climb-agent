# D164 Audit — Macrocycle & Assessment

**Data:** 2026-03-27
**Scope:** `backend/engine/macrocycle_v1.py`, `backend/engine/assessment_v1.py`
**Stato test:** Tutti i test passano (test_macrocycle_v1 + test_macrocycle_boulder: 66/66 OK)

---

## 1. Assessment (`assessment_v1.py`)

### 1.1 Profilo 5-assi — computazione corretta
- **finger_strength**: ratio su benchmark + fallback grade-based. OK.
- **pulling_strength**: 1RM diretto o stima Brzycki + fallback grade-based. OK.
- **power_endurance**: combinazione pesata (repeater 40% + gap 40% + self_eval 20%). Matematicamente corretto.
- **technique**: gap RP-OS + self_eval penalty. OK.
- **endurance**: derivato da PE * 0.8 + anni di esperienza + hang duration modifier. OK.

### 1.2 Gestione dati mancanti
- **Nessun test fisico:** fallback a stima basata su gradi corrente/target. `score = (current_idx / target_idx) * 70`. OK.
- **Peso corporeo mancante:** default 70 kg. OK.
- **Gradi mancanti:** gap_score default a 50. OK.
- **Target grade sotto i benchmark:** `_benchmark_for()` trova il grado noto piu vicino. OK.

### 1.3 Grade gap calculation
- `grade_gap(a, b)` = indice(a) - indice(b) in half-grade steps. Corretto.
- GRADE_ORDER copre 5a-9a+ (24 gradi). Manca V-scale per boulder puro, ma il sistema usa French scale internamente. Accettabile.

### 1.4 Brzycki 1RM formula
- Formula: `weight * 36 / (37 - reps)`. Corretta (equivalente alla formula standard).
- **P3 — Edge case reps=36**: restituisce `weight * 36` (36x il peso). Estremo ma non crashante. Il commento dice "accurate per 1-10 reps" il che e corretto. Suggerimento: limitare a reps <= 15 per evitare stime irrealistiche.
- reps=0 -> 0.0, reps=1 -> weight, reps >= 37 -> weight. Tutti gestiti.

### 1.5 Findings assessment

| # | Severita | Descrizione |
|---|----------|-------------|
| A1 | P3 | **Brzycki non limitata per reps > 15.** Per reps=30 la formula produce stime imprecise (~5x). Suggerire un cap a 15 reps o loggare un warning. |
| A2 | P3 | **Doc inaccuracy in `_compute_power_endurance`.** Il docstring dice "20% self_eval" ma il self_eval non ha un peso indipendente — e un penalty additivo sul gap_score, non un asse separato. Nessun impatto funzionale. |
| A3 | P3 | **Endurance double-penalty.** Se `primary_weakness == "pump_too_early"`, sia `_compute_power_endurance` (-8) che `_compute_endurance` (-10) penalizzano. Intenzionale (PE e endurance sono correlati ma distinti) ma potenzialmente severo (-18 combinato). |

---

## 2. Macrocycle Generation (`macrocycle_v1.py`)

### 2.1 Phase durations sum to total weeks

**Lead (default 12 settimane):**
- Base durations: 4+3+2+2+1 = 12. OK.
- Weakness adjustment (+1/-1) preserva la somma. OK.
- Flex phase (base) assorbe surplus/deficit. OK nella maggioranza dei casi.

**Boulder (default 10 settimane):**
- Base durations: 2+4+1+2+1 = 10. OK.
- Flex phase (strength_power). OK.

**P2 — BUG: `_compute_phase_durations` puo produrre totale != target per total_weeks=9 (lead, profilo senza debolezze).**
- Percorso: base=4, sp=3, pe=2, perf=2, deload=1 -> sum=12. diff=-3.
- `base = max(2, 4-3) = 2`. Somma = 10, target = 9.
- Seconda correzione: `base = max(2, 2 + 9-10) = max(2, 1) = 2`. Ancora 10.
- Causa: solo flex_phase assorbe il deficit, ma se tocca il floor, le altre fasi (sp=3) non vengono ridotte.
- Impatto: raro in produzione (default 12 settimane), ma possibile con total_weeks=9-11 e profili bilanciati.
- Mitigation esistente: `_MIN_TOTAL_WEEKS = 9` impedisce valori < 9, ma non impedisce il bug *a* 9.

### 2.2 from_phase="current" preserved in all call sites

| Call site | from_phase handling | Stato |
|-----------|-------------------|-------|
| `macrocycle.py` router | `from_phase == "current"` -> risolve via `current_phase_and_week()` -> phase_id concreto | OK |
| `onboarding.py` | Non passa from_phase (full generation). Corretto. | OK |
| Test suite | Testa from_phase con phase_id concreti e None. | OK |

### 2.3 start_date Monday invariant
- `generate_macrocycle()` riga 518: se `start.weekday() != 0`, shifta indietro al lunedi precedente. OK.
- Router: usa `ensure_monday()` prima di passare start_date. Double-safe. OK.
- Test dedicati: `test_b119_start_date_monday.py`. Copertura adeguata.

### 2.4 Trip integration
- `_check_pretrip_overlap()`: trova trip con finestra 5 giorni prima che cade nella fase. OK.
- `compute_pretrip_dates()`: genera tutte le date in finestra pre-trip. OK.
- `check_pretrip_deload()`: controlla se un trip inizia entro 5 giorni. OK.
- Nota: se un trip non ha `start_date`, viene silenziosamente ignorato. Corretto.

### 2.5 Findings macrocycle generation

| # | Severita | Descrizione |
|---|----------|-------------|
| M1 | **P2** | **Phase durations sum mismatch per total_weeks vicini al minimo.** `_compute_phase_durations(profile_bilanciato, 9)` produce somma 10 invece di 9. Il flex_phase tocca il floor e nessun'altra fase viene ridotta. Serve un cascade: dopo che flex tocca floor, ridurre sp o un'altra fase sopra il floor. |
| M2 | P3 | **`_compute_remaining_durations` hardcoded shrink floor a 2.** Riga 340: `if durations[shr] > 2` non rispetta `discipline == "boulder"` dove il floor e 1. Per boulder, la weakness adjustment non scatta quando la fase da ridurre e a 2 (dovrebbe scattare perche 2 > 1 = floor). |

---

## 3. Phase transitions

### 3.1 PHASE_ORDER consistency
- `PHASE_ORDER = ("base", "strength_power", "power_endurance", "performance", "deload")`.
- Usata in: ordinamento fasi, from_phase index, incremental regen filter. Coerente ovunque.
- Tutti i dict (`PHASE_NAMES`, `PHASE_ENERGY`, `PHASE_INTENSITY_CAP`, `_BASE_WEIGHTS`, `_SESSION_POOL`) coprono tutte e 5 le fasi. OK.

### 3.2 PHASE_INTENSITY_CAP
- base: medium, strength_power: max, power_endurance: high, performance: max, deload: low.
- Coerente con la metodologia Horst. OK.
- Test `test_all_pool_sessions_respect_intensity_cap` verifica che ogni sessione nel pool rispetti il cap. OK.

---

## 4. Deload logic

### 4.1 apply_deload_week()
- Rimuove sessioni con `tags.hard == True`.
- Cap a 5 sessioni totali (coerente con letteratura: 4-6 sessioni leggere).
- Setta `deload_factor: 0.5` nei targets. OK.
- **Nota:** la funzione filtra su `tags.hard` ma NON controlla l'intensity level (high/max). Se una sessione ha intensity=high ma `hard=False`, passa il filtro. Questo potrebbe essere intenzionale (il planner gia filtra per intensity cap nella fase deload).

### 4.2 should_extend_phase() e should_trigger_adaptive_deload()
- extend: 2+ settimane consecutive hard/very_hard. Corretto.
- adaptive deload: 5+ feedback very_hard consecutivi. Corretto.
- Nota: `should_trigger_adaptive_deload` non include "hard" (solo "very_hard"). Piu conservativo, evita false positives. OK.

### 4.3 Findings deload

| # | Severita | Descrizione |
|---|----------|-------------|
| D1 | P3 | **`apply_deload_week()` filtra solo su `tags.hard`, non su intensity.** Una sessione con intensity=high e hard=False passerebbe. In pratica non problematico perche la fase deload ha pool con solo sessioni low, ma la funzione puo ricevere week plan di altre fasi (pre-trip deload). |

---

## 5. _BASE_WEIGHTS analysis

### 5.1 Pre-normalization sums

| Fase | Lead | Boulder |
|------|------|---------|
| base | **1.050** | **1.050** |
| strength_power | 1.000 | **1.050** |
| power_endurance | 1.000 | **1.050** |
| performance | 1.000 | **1.050** |
| deload | **0.400** | **0.400** |

### 5.2 Findings

| # | Severita | Descrizione |
|---|----------|-------------|
| W1 | **P2** | **Deload weights sum to 0.40, non ~1.0.** `_BASE_WEIGHTS["deload"]` e `_BASE_WEIGHTS_BOULDER["deload"]` sommano a 0.40. Dopo `_adjust_domain_weights()` vengono rinormalizzati a 1.0, quindi l'output finale e corretto. Ma i pesi pre-normalization sono inconsistenti col design intent: le 6 dimensioni dovrebbero partire da ~1.0. Impatto: i rapporti relativi tra le dimensioni nella fase deload sono comunque rispettati, ma un eventuale uso dei pesi pre-normalization produrrebbe valori sbagliati. |
| W2 | P3 | **Lead base weights sum to 1.05.** Eccesso di 0.05. Rinormalizzato a 1.0 dopo `_adjust_domain_weights`. Nessun bug funzionale ma indica un errore nel data entry originale. |
| W3 | P3 | **Tutti i pesi boulder (non-deload) sommano a 1.05.** Stesso issue di W2. |

### 5.3 Boulder weights — ragionevolezza
- Boulder: finger_strength piu alto in strength_power (0.40 vs 0.35 lead). Corretto — boulder richiede piu forza dita.
- Boulder: power_endurance piu basso in base (0.05 vs 0.15 lead). Corretto — PE meno rilevante per boulder.
- Boulder: volume_climbing piu alto in base/performance. Corretto — boulder = piu volume su problemi corti.
- Boulder: core_prehab stabile a 0.10 ovunque. Ragionevole.

---

## 6. _SESSION_POOL analysis

### 6.1 Catalog coverage
- **Tutte le sessioni referenziate nei pool esistono nel catalogo.** 0 sessioni mancanti. OK.
- 12 sessioni in catalogo non in nessun pool: test sessions (7), heavy_conditioning_gym, upper_body_weights, lower_body_gym, legs_strength, pulling_strength_gym. Corretto — test sessions e sessioni supplementari non in pool di fase.

### 6.2 Lead vs boulder pool differences
- **Base:** Lead ha endurance_aerobic_gym e route_endurance_gym (climbing su via). Boulder ha solo boulder_circuit_gym e core_training. Coerente.
- **Strength_power:** Identici tranne boulder aggiunge core_training, lead aggiunge finger_maintenance_gym/finger_endurance_short/route_endurance_gym. Ragionevole.
- **Power_endurance:** Lead usa power_endurance_gym (via). Boulder usa boulder_circuit_gym. Coerente con disciplina.
- **Performance:** Lead aggiunge route_projecting_gym. Boulder aggiunge core_training. OK.
- **Deload:** Identici tra lead e boulder. OK.

### 6.3 Findings session pool

| # | Severita | Descrizione |
|---|----------|-------------|
| S1 | P3 | **Boulder PE pool manca una sessione PE specifica.** Il pool power_endurance boulder usa boulder_circuit_gym come primary, ma non ha una sessione specifica di power endurance per boulder (tipo 4x4 boulder). Funzionalmente accettabile dato che boulder_circuit_gym a volume medio copre il ruolo, ma una sessione dedicata migliorerebbe la specificita. |

---

## Riepilogo findings

| ID | Sev | Modulo | Descrizione |
|----|-----|--------|-------------|
| M1 | **P2** | macrocycle_v1 | Phase durations sum != total_weeks per valori vicini al minimo (9-11 settimane, profilo bilanciato). Solo flex_phase assorbe deficit, manca cascade. |
| W1 | **P2** | macrocycle_v1 | Deload _BASE_WEIGHTS sommano a 0.40 (non ~1.0). Rinormalizzazione corregge output ma design intent violato. |
| M2 | P3 | macrocycle_v1 | `_compute_remaining_durations` shrink floor hardcoded a 2, ignora discipline boulder (floor=1). |
| A1 | P3 | assessment_v1 | Brzycki non limitata per reps > 15 — stime imprecise. |
| A2 | P3 | assessment_v1 | Docstring PE: "20% self_eval" e impreciso — e un penalty su gap_score. |
| A3 | P3 | assessment_v1 | Endurance double-penalty per "pump_too_early" (PE -8 + endurance -10 = -18). |
| W2 | P3 | macrocycle_v1 | Lead base weights sum 1.05 (non 1.00). Rinormalizzato, nessun bug funzionale. |
| W3 | P3 | macrocycle_v1 | Tutti i boulder weights (non-deload) sum 1.05. Stesso issue di W2. |
| D1 | P3 | macrocycle_v1 | `apply_deload_week()` filtra solo `tags.hard`, non intensity level. |
| S1 | P3 | macrocycle_v1 | Boulder PE pool manca sessione PE-specifica per boulder. |

**P1: 0 | P2: 2 | P3: 8**
