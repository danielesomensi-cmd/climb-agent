# D-BASELINE-AUDIT — Report

**Tipo**: Audit read-only
**Data**: 2026-04-18
**Contesto**: Pre-paid-launch review del modello dati baselines + hardcoding inventory. Nessuna modifica al codice. Driver di scoping per eventuali remediation brief.
**Correlato**: D-TESTWEEK-AUDIT (RC1 + RC2 confermati qui in forma più ampia)

---

## 🛑 STOP GATE

**Questo brief è read-only. NON implementare nessun fix in questa sessione.**

Il report fornisce:
1. Inventory completo del modello baselines (scritture, letture, `source` taxonomy).
2. Mappatura input onboarding → state (28 righe).
3. Hardcoding map (27+ occorrenze stringhe test session ID, 8 policy dict statici, 15+ magic number).
4. Matrice axis-by-axis symmetry (finger vs pulling vs repeater).
5. Proposta di remediation in bundle A/B/C con severity + stima giorni.

**Decisione richiesta a Daniele (dopo lettura)**: aprire brief remediation (quale bundle?) oppure parcheggiare in `docs/briefs/D-BASELINE-AUDIT_parked.md`.

---

## §1 — Modello dati baselines

### 1.1 Schema attuale in `user_state`

`user_state.baselines` contiene quattro chiavi, con strutture **non uniformi**:

| Chiave | Tipo | Forma | Popolato da |
|---|---|---|---|
| `baselines.hangboard` | **lista** di entry | `[{grip, edge_mm, hang_seconds, max_total_load_kg, source, estimated_at, updated_at, grade_used?}, ...]` | onboarding estimate + test completion + `_pick_hangboard_baseline` match |
| `baselines.pulling` | **dict singolo** | `{max_external_load_kg, variant, source, updated_at}` | onboarding estimate (da `assessment.tests.weighted_pullup_1rm_*`) + test completion |
| `baselines.power_endurance` | **assente** | N/A | Nessuno — il repeater non ha baseline dedicato |
| `baselines.working_loads` | **dict** | `{<exercise_id>: {load_kg, difficulty, updated_at}, ...}` | closed-loop dopo feedback (non tema di questo audit) |

**Implicazioni**:
- `hangboard` è una **lista** perché un utente può avere più coppie (edge/grip). Il resolver fa matching su (grip, edge_mm, hang_seconds) via `_pick_hangboard_baseline` (resolve_session.py:115).
- `pulling` è un **dict singolo** perché esiste un solo protocollo canonico (weighted pullup).
- `power_endurance/repeater` **non ha baseline** — è rappresentato come scalar in `assessment.tests.repeater_7_3_max_sets_20mm` + storia in `tests.repeater_strength_endurance[]`. Questa è la **prima asimmetria strutturale** (vedi §1.4).

### 1.2 Tassonomia `source`

Cinque valori sono **effettivamente scritti** in produzione:

| `source` | Axis | File:line scrittore | Semantica |
|---|---|---|---|
| `estimated_from_grade` | hangboard | progression_v1.py:697 | Onboarding: stima dal grade (`lead_max_rp`) |
| `estimated_from_pullup` | hangboard | progression_v1.py:708 | Onboarding: fallback da pullup 1RM |
| `assessment` | pulling | progression_v1.py:770 | Onboarding: stima da `assessment.tests.weighted_pullup_1rm_*` |
| `test` | hangboard | progression_v1.py:1120, 1157 | Test completato in-app (max_hang_5s o max_hang_7s) |
| `test_session` | pulling | progression_v1.py:1251 | Test completato in-app (test_max_weighted_pullup) |

**Valori residui mai usati**: `measured`, `self_reported`, `manual` (compaiono in docs ma non in codice).

**Source "fantasma"**: `grade_fallback` è citato in progression_v1.py:588 (`"grade_fallback"`) dentro `_max_hang_suggested` come valore **letto** per routare logica, ma **non è mai scritto** in baseline — è un output transiente del suggestion engine. Confusione tra output e input vocabulary.

**Asimmetria**: hangboard ha 3 source possibili (`estimated_from_grade`, `estimated_from_pullup`, `test`); pulling ha 2 (`assessment`, `test_session`). Le parole chiave sono **diverse fra axis** senza motivo semantico (`estimated_from_*` vs `assessment` vs `test` vs `test_session`).

### 1.3 Readers del campo `source`

Solo **3 reader baseline-aware** in tutto `backend/`:

| File:line | Funzione | Usa `source` per |
|---|---|---|
| progression_v1.py:578-599 | `_max_hang_suggested` | Output field `load_source: "estimated"` se `source` contiene `"estimated"` o `== "grade_fallback"` |
| progression_v1.py:675 | `_estimate_hangboard_baseline` | **Protezione**: non sovrascrive baseline con `source == "test"` |
| progression_v1.py:746 | `_estimate_pulling_baseline` | **Protezione**: non sovrascrive baseline con `source in ("test", "test_session")` |

**Source-blind readers** (leggono baseline senza ispezionare `source` — bug latenti):

1. `_get_pulling_baseline()` (progression_v1.py:222) → usato da prescrizione pulling, non distingue `assessment` vs `test_session`.
2. `suggest_max_hang_load()` (resolve_session.py:127) → legge `max_total_load_kg` ignorando `source`; fallback **inverso** a `assessment.tests` se baseline assente (line 150-156).
3. `_loading_pin_suggested()` (progression_v1.py:604) → ignora `source` completamente.
4. `week.py:323-328` (freshness check finger) → fallback a `estimated_at` se `updated_at` assente → **RC2 del brief D-TESTWEEK-AUDIT**: stima grade-based viene trattata come "test fresco", il planner skippa l'iniezione del test vero.
5. `week.py:338-340` (freshness check pulling) → legge solo `updated_at`, **no fallback** → asimmetria opposta rispetto a hangboard.

**Conseguenza**: la taxonomia `source` esiste ma è sotto-utilizzata. Le prescrizioni di carico trattano baseline estimate e test come identici. L'unico posto dove la distinzione è attiva è il gating di sovrascrittura (evitare che una stima onboarding cancelli un test completato).

### 1.4 Matrice axis-by-axis symmetry

| Aspetto | Finger (hangboard) | Pulling | Power_endurance (repeater) |
|---|---|---|---|
| State path | `baselines.hangboard[list]` | `baselines.pulling` (dict) | **N/A** — nessun baseline |
| Onboarding estimate writer | progression_v1.py:665 `_estimate_hangboard_baseline` | progression_v1.py:740 `_estimate_pulling_baseline` | **N/A** — nessuna funzione |
| Onboarding `source` value | `estimated_from_grade` o `estimated_from_pullup` | `assessment` | N/A |
| Test completion writer | progression_v1.py:1120 (7s), 1157 (5s) | progression_v1.py:1251 | progression_v1.py:1185 — scalar only, no baseline write |
| Test `source` value | `test` | `test_session` | N/A |
| Freshness check in week.py | 323-328 — legge `updated_at` **OR `estimated_at`** | 338-340 — legge solo `updated_at` | 329-337 — legge tail di `tests.repeater_strength_endurance[]` |
| Freshness usa `estimated_at` fallback? | **SÌ (RC2)** | NO | N/A |
| Planner test session ID (device=hangboard) | `test_max_hang_5s` (hardcoded) **mentre il catalog ha `test_max_hang_7s.json`** | `test_max_weighted_pullup` o `test_pullup_bw` | `test_repeater_7_3` |
| Planner test session ID (device=loading_pin) | `test_lp_max_5s` | N/A | `test_lp_repeater` |
| Resolver fallback chain | `baselines.hangboard` → `assessment.tests.max_hang_20mm_7s_total_kg` | `baselines.pulling` (no fallback) | N/A |
| `assessment.tests` scalar key | `max_hang_20mm_7s_total_kg` / `max_hang_20mm_5s_total_kg` | `weighted_pullup_1rm_*`, `weighted_pullup_2rm_total_kg` | `repeater_7_3_max_sets_20mm` |
| Grade input usato per estimate | `lead_max_rp` (prio 1), `weighted_pullup_1rm_*` (prio 2) | N/A | N/A |

**Conclusioni di simmetria**:

- **Most symmetric**: Pulling. Ha baseline dedicato, writer onboarding + test, protection su sovrascrittura. Manca solo il fallback chain nel resolver.
- **Least symmetric**: Power_endurance/repeater. **Non ha baseline**. Freshness check basato su history tail anziché baseline. Nessun onboarding estimate. Nessun test che scriva un baseline strutturato. Il carico prescritto è phase-fisso, non baseline-driven.
- **Most broken**: Finger. Ha baseline ma il freshness fallback su `estimated_at` è **incompatibile** con la semantica "stima vs test" — causa diretta di RC2.

---

## §2 — Mappatura input onboarding → baselines

Trace dai 16 step onboarding ai campi in `user_state`, con evidenza di quali input **toccano baselines/tests** vs quali finiscono in `assessment.profile` o `preferences`.

### 2.1 Tabella di 28 input

| # | Step wizard | Input field | Destination path in state | Feeds baseline? | Via quale writer |
|---|---|---|---|---|---|
| 1 | profile | birth_year | `profile.birth_year` | No | onboarding.py |
| 2 | profile | weight_kg | `profile.body.weight_kg` | **Indirettamente** (pulling baseline BW ref) | onboarding.py → `_estimate_pulling_baseline` |
| 3 | profile | sex | `profile.sex` | No | onboarding.py |
| 4 | discipline | discipline | `goal.discipline` | No (ma routing test) | onboarding.py |
| 5 | experience | years_climbing | `profile.years_climbing` | No (ma gate hangboard D35) | onboarding.py |
| 6 | experience | hangboard_experience_years | `profile.hangboard_experience_years` | No (ma gate D35) | onboarding.py |
| 7 | grades | lead_max_onsight | `goal.lead.max_onsight` | No | onboarding.py |
| 8 | grades | lead_max_rp | `goal.lead.max_rp` | **SÌ** (input principale hangboard estimate) | → progression_v1.py:683 |
| 9 | grades | boulder_max_onsight | `goal.boulder.max_onsight` | No | onboarding.py |
| 10 | grades | boulder_max_rp | `goal.boulder.max_rp` | **SÌ** (discipline=boulder) | → progression_v1.py |
| 11 | goals | target_discipline_goal | `goal.target` | No | onboarding.py |
| 12 | weaknesses | selected_weakness | `goal.primary_weakness` | No (macrocycle adjustment) | macrocycle_v1.py:_WEAKNESS_ADJUSTMENTS |
| 13 | tests | test_week_requested (bool) | `initial_tests_requested` | **SÌ** (trigger injection) | onboarding.py:385 → week.py:310 |
| 14 | tests | max_hang_20mm_7s_total_kg | `assessment.tests.max_hang_20mm_7s_total_kg` | **SÌ** (feed a `_estimate_hangboard_baseline`) | assessment → progression |
| 15 | tests | max_hang_20mm_5s_total_kg (legacy) | `assessment.tests.max_hang_20mm_5s_total_kg` | **SÌ** (fallback) | assessment → progression |
| 16 | tests | weighted_pullup_1rm_total_kg | `assessment.tests.weighted_pullup_1rm_total_kg` | **SÌ** (pulling baseline + hangboard fallback) | progression_v1.py:770, 708 |
| 17 | tests | max_pullups_bw | `assessment.tests.max_pullups_bw` | **SÌ** (gate per `_pick_pulling_test_session`) | planner_v2.py:576 |
| 18 | tests | repeater_7_3_max_sets_20mm | `assessment.tests.repeater_7_3_max_sets_20mm` | No baseline — scalar only | assessment_v1.py |
| 19 | limitations | injury_flags | `profile.limitations` | No | onboarding.py |
| 20 | locations | primary_gym_id | `equipment.gyms[].gym_id` | No (ma filtering equipment) | onboarding.py → `_ensure_gym_ids` |
| 21 | locations | gym_equipment | `equipment.gyms[i].equipment[]` | No (ma filtering session) | resolve_session |
| 22 | locations | home_equipment | `equipment.home[]` | No | filtering |
| 23 | locations | finger_training_device | `preferences.finger_training_device` | **SÌ** (routing test session ID: hangboard vs loading_pin) | planner_v2.py:1276 |
| 24 | availability | sessions_per_week | `availability.sessions_per_week` | No | macrocycle_v1 |
| 25 | availability | preferred_days | `availability.preferred_days` | No | planner |
| 26 | availability | slot_preferences | `availability.slots` | No | planner |
| 27 | trips | outdoor_trips[] | `outdoor.trips[]` | No | planner ripple |
| 28 | start-week | start_date | `goal.start_date` | No (ma Monday invariant) | `ensure_monday()` |

### 2.2 Distinguibilità test onboarding vs test in-app

**Punto critico**: né `assessment.tests.max_hang_20mm_7s_total_kg` né `assessment.tests.weighted_pullup_1rm_total_kg` portano un campo `source`. Non c'è modo di distinguere in `state` se quel valore è stato:

- Inserito manualmente durante onboarding (utente digita un numero), oppure
- Calcolato da `_estimate_*` tramite grade/pullup, oppure
- Aggiornato post-test in-app (feedback da sessione completata).

**Implicazione**: un utente che digita 30kg come max hang in onboarding è **indistinguibile** da un utente che ha completato un test reale da 30kg. Il planner "trust" entrambi con lo stesso peso. Nessun flag di "self-reported" vs "measured".

**Unica difesa**: il `source` sul *baseline* (`estimated_from_grade`, `estimated_from_pullup`, `test`, `test_session`) preserva questa info, ma solo se il baseline è scritto. Gli scalar in `assessment.tests.*` restano "anonimi".

### 2.3 Flag `initial_tests_requested`

- Scrittura: `onboarding.py:385-386` — `if data.test_week_requested: state["initial_tests_requested"] = True`
- Lettura: `week.py:310-312` — `want_tests = state.get("initial_tests_requested") and ctx["is_first_week_of_phase"] and ctx["phase_id"] == "base" and not is_last`
- Effetto downstream: `want_tests=True` → passa `inject_tests=True` al planner → bypassa `_PHASE_TEST_MAP` gate.

**Criticità**: anche con `inject_tests=True`, la freshness check (week.py:315-337) **non viene bypassata** — quindi RC2 opera anche quando l'utente ha richiesto esplicitamente la test week.

---

## §3 — Hardcoding inventory

### 3.1 Session ID dispatch (test sessions)

Occorrenze letterali delle 8 stringhe test session ID (grep `backend/`):

| Session ID | Count | Ruolo primario |
|---|---|---|
| `test_max_hang_5s` | 11 | **INJECTION hardcoded** (planner_v2.py:1276, 1555) + `_SESSION_META` (:53) + test map (:1267) + tests |
| `test_max_hang_7s` | 2 | **Solo catalog** (file JSON) + 1 test fixture. **MAI nel planner** → orphan (RC1) |
| `test_lp_max_5s` | 4 | Device branching (:1276) + `_SESSION_META` (:54) + tests |
| `test_repeater_7_3` | 8 | INJECTION (:1277, 1572) + `_SESSION_META` (:55) + test map (:1268) + tests |
| `test_lp_repeater` | 4 | Device branching (:1277) + `_SESSION_META` (:56) + tests |
| `test_max_weighted_pullup` | 8 | `_pick_pulling_test_session` (:574) + `_SESSION_META` (:57) + tests |
| `test_pullup_bw` | 5 | `_pick_pulling_test_session` (:577) + `_SESSION_META` (:58) + tests |

**Smoking gun** (RC1): `planner_v2.py:1276`:
```python
_finger_test_sid = "test_lp_max_5s" if finger_device == "loading_pin" else "test_max_hang_5s"
```
Nessun codepath del planner contiene `test_max_hang_7s`. Il file catalog D85-era è **orfano**.

### 3.2 Static policy dict

8 dict registrati staticamente in moduli engine:

| Dict | File:line | Mutato? | Cardinalità reader |
|---|---|---|---|
| `_SESSION_META` | planner_v2.py:38-73 | No | Multi-reader (filter, scoring, injection) |
| `_PHASE_TEST_MAP` | planner_v2.py:79-105 | No | 1 (`_should_schedule_test`) ma axis names ripetuti in 3 posti |
| `_INTENSITY_ORDER` / `_INTENSITY_TO_LOAD` | planner_v2.py:134-137 | No | 2 posti ciascuno |
| `_BASE_DURATIONS` | macrocycle_v1.py:243-246 | No | ~3 posti |
| `_BASE_DURATIONS_BOULDER` | macrocycle_v1.py:220-223 | No | ~3 posti |
| `_WEAKNESS_ADJUSTMENTS` | macrocycle_v1.py:232-238 | No | ~2 posti |
| `PULLING_1RM_PCT` | progression_v1.py:76-93 | No | 1 posto (pulling estimation) |
| `HANGBOARD_DEFAULT_INTENSITY_PCT` | progression_v1.py:131-143 | No | 1 posto (estimation) |
| `EXTERNAL_LOAD_FALLBACK_PCT_BW` | progression_v1.py:35-45 | No | ~2 posti |
| `PULLING_EXTERNAL_SCALING` | progression_v1.py:96-99 | No | 1 posto |

Nessun dict è mutato a runtime — tutti sono "registries" che duplicano concetti già presenti nel JSON catalog (es. `_SESSION_META.required_equipment` duplica `catalog/sessions/v1/*.json:required_equipment`).

### 3.3 Magic number

| Valore | File:line | Uso | Score brittleness |
|---|---|---|---|
| `42` | planner_v2.py:1265 (`TEST_FRESHNESS_DAYS`) | Giorni di freschezza test | MEDIUM (named, ma test hardcodano "42" in stringhe) |
| `2` | planner_v2.py:1569 (`min_repeater = hang_offset + 2`) | Gap 48h finger days | MEDIUM (non named) |
| `12` | planner_v2.py:106 (`MAX_WEEKS_UNTESTED`) | Maintenance retest threshold | LOW (named) |
| `4,3,2,1` | macrocycle_v1.py:243-246 | Hörst phase durations (lead) | LOW (named dict) |
| `2,4,1,2,1` | macrocycle_v1.py:220-223 | Boulder phase durations | LOW (named dict) |
| `50` | macrocycle_v1.py:288, 346 | Weakness score threshold | MEDIUM (duplicato 2 posti) |
| `1/2` | macrocycle_v1.py:287, 296-299 | Floor phase length (boulder/lead) | MEDIUM (scattered) |
| `15` | planner_v2.py:576 | Pullup BW count gate | MEDIUM (letterale + test hardcoda) |
| `0.60, 0.15` | progression_v1.py:97-98 | Pulling external scaling | MEDIUM |
| `0.90` | progression_v1.py:134 | Hörst max strength % MVC | HIGH (deve allineare con catalog exercise.intensity_pct) |
| `0.30, 0.40, 0.15, 0.08, ...` | progression_v1.py:35-45 | %BW fallback pulling exercises | MEDIUM |
| `20, 40, 65, 85` | planner_v2.py:137 | Intensity-to-load fallback | LOW (named dict) |
| `+10` | planner_v2.py:808 | Evening slot bonus | LOW |
| `9, 5` | macrocycle_v1.py:241, 268 | Min total weeks lead/boulder | LOW (named) |

### 3.4 Phase→axis / axis→session mapping fragmentation

Il concetto "quale axis si testa in quale phase" è **replicato in 3 posti**:

1. `_PHASE_TEST_MAP` (planner_v2.py:79-105) — fonte autoritativa, dict phase_id → {axis: bool}.
2. `_test_type_map` (planner_v2.py:1267-1269) — inline dict inside `generate_phase_week`, session_id → axis_name.
3. Comparisons letterali `if test_type == "finger"` sparsi (linee 1306, 1316, ...).

**Rischio**: se si rinomina "finger" → "hangboard", tre punti separati devono essere aggiornati. Nessun controllo di consistenza a import time.

### 3.5 Dead code

- `generate_test_week()` (planner_v2.py:1504) — **non è dead code**: 13 caller nei test (test_test_week.py, test_b101_*.py, test_planner_v2.py). Tuttavia **zero caller di produzione** (no router, no engine). Funzione tenuta viva solo dai test.
- `check_load_coherence()` (progression_v1.py:496) — **dead in produzione**: solo 3 caller nei test (test_load_transfer.py). Helper diagnostico.

---

## §4 — Vocabolario vs codice

### 4.1 Termini in codice ma non in `docs/vocabulary_v1.md`

- Campo `source` su baseline: il vocab menziona `source` solo dentro §2.10.2 (contesto pulling) ma non lo definisce formalmente come campo standard.
- Valori `estimated_from_grade`, `estimated_from_pullup`, `grade_fallback`, `test_session`: usati in codice (progression_v1.py) ma **assenti dal vocab**.
- Chiavi `assessment.tests.weighted_pullup_2rm_total_kg` e `weighted_pullup_1rm_estimated_kg`: introdotte da D84, mai aggiunte al vocab.

### 4.2 Termini ambigui

- **hangboard vs finger**: data layer usa `hangboard` (baseline key, equipment); axis layer usa `finger_strength` (assessment axis, weakness); preference usa `finger_training_device`. Coerente ma richiede awareness multi-layer.
- **repeater vs power_endurance vs endurance**: `power_endurance` è phase + domain; `repeater_strength_endurance` è test metric. Non sinonimi, facile confondersi.
- **pulling vs pulling_strength**: `pulling` è data layer, `pulling_strength` è domain/axis. Coerente ma contesto-dipendente.

### 4.3 Migration tag nei commenti

15 reference a brief ID nei commenti di `backend/engine/progression_v1.py`, `resolve_session.py`, `api/routers/week.py`:

| Tag | Count | Tema |
|---|---|---|
| B121 | 5 | Pulling baseline system (refactor centrale) |
| D85 | 1 | Max hang 7s primary test |
| D84 / D84b | 2 | Weighted pullup 2RM + bodyweight |
| B191 | 1 | Finding-A asymmetric estimated_at fallback |
| B133 | 1 | Test feedback: completed_reps vs completed_sets |
| B-HORST-INTENSITY | 1 | Baseline protocol field population |
| D35 | 2 | Hangboard experience gate |

Nessun `TODO` o `FIXME` trovato in codice baseline-related — le criticità sono "nascoste" in commenti descrittivi.

---

## §5 — Remediation scope

### 5.1 Checklist di completezza

- [x] Writer list (progression_v1.py, assessment_v1, week.py)
- [x] Reader list (11 reader baseline-side, 3 source-aware, 5 source-blind)
- [x] Onboarding input mapping table (28 righe)
- [x] Dispatch table test_max_hang_* (11 + 2 occorrenze documentate)
- [x] Conferma `generate_test_week` is NOT dead (tested, no prod callers)
- [x] 15+ magic number documentati
- [x] 6+ asimmetrie per axis (hangboard vs pulling vs repeater)

### 5.2 Finding severity summary

| Severity | Count | Categorie |
|---|---|---|
| **BLOCKER** | 3 | RC1 (test_max_hang_7s orphan), RC2 (estimated_at fallback), axis dispatch fragmentation |
| **HIGH** | 3 | Phase test map + test type map + freshness logic axis-name replicati 3 posti; intensity fallback mismatch (catalog vs progression_v1) |
| **MEDIUM** | 11 | Magic number non-named (2, 15, 50, 0.90), dict duplicati, scalar test senza `source`, vocabulary gap |
| **LOW** | 5 | Named constants OK, evening bonus, intensity order |
| **COSMETIC** | 3 | Naming multi-layer (hangboard/finger), source value strings diverse (`estimated_from_*` vs `assessment`) |

### 5.3 Remediation bundle

#### Bundle A — **Minimum fix** (sblocca utenti nuovi, ~2 giorni)

Obiettivo: nuovi utenti ricevono test_max_hang nella test week. Niente refactor strutturale.

1. **B(next): wire test_max_hang_7s nel planner**
   - Sostituire `"test_max_hang_5s"` con `"test_max_hang_7s"` in planner_v2.py:1276, 1555
   - Aggiornare `_SESSION_META[:53]` con l'entry `test_max_hang_7s` (mantenere `test_max_hang_5s` come alias per storico)
   - Aggiornare `_test_type_map` (:1267)
   - Verificare che i test esistenti passino (attesi ~3 test da aggiornare)

2. **B(next+1): drop `estimated_at` fallback nella freshness check finger**
   - week.py:326 → `_hb_baselines[0].get("updated_at")` (senza OR estimated_at)
   - Allinea il comportamento di finger a pulling
   - Rischio: alcuni utenti con solo stima onboarding riceveranno il test anche prima dei 42gg. **Desiderato** — è l'obiettivo.

**Esito Bundle A**: chiude RC1 + RC2. Non tocca vocabulary, non tocca axis asymmetry, non tocca hardcoding structural. **2 brief B-type, ~2 giorni.**

#### Bundle B — **Recommended** (Bundle A + consolidation, ~5-6 giorni)

Aggiunge a Bundle A:

3. **D(next): audit follow-up + vocabulary update**
   - Aggiornare `docs/vocabulary_v1.md` §2.10.x con definizione formale campo `source` e suoi valori canonici.
   - Aggiungere `source` field su scalar `assessment.tests.*` (`"self_reported"` se da onboarding, `"measured"` se da test in-app). Migration script retrofit per utenti esistenti.
   - Distinguibilità restored.

4. **B(next+2): consolidare axis dispatch**
   - Estrarre `_test_type_map` (planner_v2.py:1267) in costante module-level a fianco di `_PHASE_TEST_MAP`.
   - Aggiungere assert-time check: ogni axis_name in `_PHASE_TEST_MAP` deve esistere in `_test_type_map.values()`, e viceversa.
   - Non cambia runtime behaviour — solo evita fragmentation future.

5. **B(next+3): resolver fallback chain symmetry**
   - Aggiungere fallback `baselines.pulling` → `assessment.tests.weighted_pullup_1rm_total_kg` in resolve_session, simmetrico al fallback hangboard → max_hang_20mm_7s.
   - Sblocca utenti che hanno il test scalar ma non il baseline (edge case post-retrofit).

**Esito Bundle B**: RC1+RC2 risolti, vocabulary allineato, axis dispatch resiliente, resolver simmetrico. **2 B + 1 D + 1 B + 1 B, ~5-6 giorni.**

#### Bundle C — **Ambitious** (Bundle B + structural refactor, ~10-14 giorni)

Aggiunge a Bundle B:

6. **B(next+4): introdurre `baselines.power_endurance`**
   - Simmetrizza con hangboard/pulling.
   - Writer: `_estimate_power_endurance_baseline(state, assessment)` da `repeater_7_3_max_sets_20mm`.
   - Reader: freshness check usa baseline invece di history tail.
   - Breaking change contenuto: retrofit script leggibile.

7. **D(next+1): extraction static policy dict → JSON catalog**
   - Spostare `_PHASE_TEST_MAP`, `_BASE_DURATIONS`, `_WEAKNESS_ADJUSTMENTS` in `backend/catalog/policy/v1/*.json`.
   - Loader on import, validation via Pydantic.
   - Rende config modificabile senza redeploy.

8. **B(next+5): test → baseline writer unified**
   - Introdurre funzione `write_baseline_from_test(axis, test_result, state)` unica.
   - Sostituisce i writer sparsi in progression_v1.py:1120, 1157, 1251.
   - Normalizza `source` values (`"test"` per tutti).

9. **D(next+2): dead code archival**
   - `check_load_coherence` → spostare in `_archive/diagnostics/` o promuovere a CLI tool.
   - `generate_test_week` → valutare rimozione (non usata in prod); se conservata, aggiungere docstring "TEST-ONLY".

**Esito Bundle C**: modello baseline uniforme su 3 axis, config dichiarativa, zero source-blind readers. **3 B + 2 D, ~10-14 giorni.**

### 5.4 Raccomandazione

**Procedere con Bundle A immediatamente** (2 brief, 2 giorni) per sbloccare pre-paid-launch. RC1+RC2 sono attivi in produzione OGGI — nuovi utenti registrati post-Stripe non ricevono il test hangboard.

**Valutare Bundle B in parallelo/sequenza** se c'è buffer prima del lancio paid. La vocabulary update (finding #3) è low-risk e high-clarity.

**Rinviare Bundle C post-launch**. Il refactor structural vale la pena solo quando il volume utenti è sufficiente per beneficiare di config modificabile senza redeploy. Pre-launch, il ritorno è teorico.

---

## §6 — Parcheggi

Findings noti ma **non remediation candidate** in questo ciclo:

- **Naming multi-layer** (hangboard vs finger, pulling vs pulling_strength): creerebbe churn massiccio per zero benefit utente. Conservare, documentare in vocabulary.
- **Magic number `15`** (pullup BW gate): valore derivato da letteratura (Hörst). Hardcoded OK.
- **Hangboard intensity `0.90` duplicata** tra progression_v1.py e exercise catalog: richiederebbe `intensity_pct` come source unico. Candidato Bundle C/futuro.
- **Evening slot bonus `+10`**: cosmetic, LOW priority.

---

## Appendice — File investigati

### Code
- backend/engine/planner_v2.py
- backend/engine/macrocycle_v1.py
- backend/engine/progression_v1.py
- backend/engine/resolve_session.py
- backend/engine/assessment_v1.py
- backend/api/routers/onboarding.py
- backend/api/routers/week.py
- backend/api/routers/feedback.py

### Catalog
- backend/catalog/sessions/v1/test_max_hang_{5s,7s}.json
- backend/catalog/sessions/v1/test_lp_{max_5s,repeater}.json
- backend/catalog/sessions/v1/test_repeater_7_3.json
- backend/catalog/sessions/v1/test_{max_weighted_pullup,pullup_bw}.json

### Docs
- docs/vocabulary_v1.md (§1.2, 1.3, 2.2, 2.10.2, 3.0, 5.9)
- docs/briefs/D-TESTWEEK-AUDIT_report.md (predecessore diretto)

### Production data
- Supabase `users.state` (daniele.somensi@ferrero.com, UUID 98f77487-...) — 3 week plans (2026-04-20, 04-27, 05-04), nessun `test_max_hang*` schedulato → conferma empirica RC1+RC2.

---

**Report end.** Decisione di scoping a Daniele.
