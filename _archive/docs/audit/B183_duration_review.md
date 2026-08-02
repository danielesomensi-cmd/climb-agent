# B183 Duration Review — Session Quality Audit

> Generated: 2026-04-02  
> Based on: all 35 sessions in `backend/catalog/sessions/v1/`  
> Resolved with: full equipment set (no user-specific constraints)  
> Formula: sets × (reps × sec/rep OR work_seconds) + (sets−1) × rest + 30s transition/exercise  
> Alt_sides: raddoppia i set effettivi (es. pistol squat 3×6 → 6 set effettivi)  

---

## Parte 1 — Tabella completa

**Legenda delta:** `+` = formula > target (formula più alta del dichiarato), `−` = formula < target

| session_id | target_min | formula_min | n_ex | proposed_min | notes |
|---|---|---|---|---|---|
| `boulder_circuit_gym` | 85 | 73.5 | 12 | **85** | Formula -12: bouldering principale è instruction-only (non in exercise_instances). Target cattura il tempo di climbing reale. Tieni. |
| `complementary_conditioning` | 35 | 47.3 | 8 | **35** | Formula +12: TGU/carries/crawls sono instruction-only, formula conta solo ab_wheel+core_hollow. Il target riflette l'intera sessione incluso il contenuto non risolto. Tieni. |
| `core_training` | 25 | 38.0 | 6 | **40** | Formula +13: 3 core + 3 cooldown timed. Target=25 **stale** — nessun warmup, 3 cooldown timed (hip_pigeon=60s×4 set = 8 min da solo). Proponi 40. |
| `deload_recovery` | 30 | 30.1 | 4 | **30** | Match perfetto (delta +0.1). Tieni. |
| `easy_climbing_deload` | 70 | 66.0 | 11 | **70** | Delta -4, buon match. Il climbing è instruction-only. Tieni. |
| `endurance_aerobic_gym` | 80 | 78.8 | 13 | **80** | Match eccellente (delta -1). Tieni. |
| `finger_aerobic_base` | 40 | 60.0 | 10 | **40** | Formula +20: il lavoro hangboard aerobico (repeaters/intervals) è instruction-only. Formula conta solo dip+ab_wheel + pesante rest da prehab. Target=40 cattura l'intera sessione. Tieni. |
| `finger_endurance_short` | 40 | 60.0 | 10 | **40** | Identico a finger_aerobic_base. Tieni. |
| `finger_maintenance_gym` | 65 | 94.4 | 16 | **65** | Formula +29: il lavoro hangboard principale è instruction-only. Formula accumula ~30 min di rest da 4 prehab × rest lungo. Target=65 è il riferimento umano validato. Tieni. |
| `finger_maintenance_home` | 30 | 51.7 | 9 | **30** | Formula +22: stesso problema — hang content instruction-only, 4 cooldown timed inflazionano la formula. Tieni. |
| `finger_strength_home` | 35 | 51.7 | 9 | **35** | Identico a finger_maintenance_home. Tieni. |
| `flexibility_full` | 35 | 18.5 | 2 | **35** | Formula -17: risolve solo 2 esercizi. Tutto il contenuto flessibilità (pigeon, couch stretch, ecc.) è instruction-only. Target=35 è accurato. Vedi Parte 2. |
| `handstand_practice` | 25 | 30.6 | 3 | **25** | Formula +6, entro margine. Tieni. |
| `heavy_conditioning_gym` | 70 | 81.5 | 16 | **80** | Formula +12: 9 esercizi di lavoro reale. Target=70 **stale**. Proponi 80. |
| `legs_strength` | 30 | 44.6 | 6 | **45** | Formula +15: target=30 **stale** — solo 2 work + no warmup. Con alt_sides pistol squat da solo ~9 min reali. Proponi 45. Vedi Parte 2. |
| `limit_boulder_gym` | 85 | 82.3 | 13 | **85** | Delta -3, match ottimo. Tieni. |
| `lower_body_gym` | 60 | 80.8 | 11 | **75** | Formula +21: target=60 **stale post-B183** — aggiunti reverse_lunge + single_leg_calf_raise. 5 work con alt_sides = ~40 min solo lavoro+rest. Proponi 75 (conservativo: rest tra set unilaterali si sovrappone parzialmente). |
| `power_contact_gym` | 100 | 82.3 | 13 | **100** | Formula -18: campus + climbing sono instruction-only. Target=100 giustificato. Tieni. |
| `power_endurance_gym` | 90 | 85.7 | 14 | **90** | Delta -4, buon match. Il climbing principale è instruction-only. Tieni. |
| `prehab_maintenance` | 18 | 19.5 | 4 | **20** | Match eccellente (delta +2). Arrotonda a 20. |
| `pulling_strength_gym` | 80 | 78.6 | 12 | **80** | Match eccellente (delta -1). Tieni. |
| `regeneration_easy` | 50 | 42.9 | 5 | **50** | Formula -7: easy climbing è instruction-only. Target cattura il climbing. Tieni. |
| `route_endurance_gym` | 100 | 78.8 | 13 | **100** | Formula -21: route endurance (linked routes, laps) instruction-only. Ogni via 5-15 min. Target=100 è l'unico valore affidabile. Tieni. |
| `route_projecting_gym` | 100 | 78.3 | 13 | **100** | Identico a route_endurance_gym. Tieni. |
| `strength_long` | 90 | 97.8 | 16 | **90** | Formula +8, entro margine. Rest hangboard (3-5 min/set) realistici ma target=90 è valore storico validato. Tieni. |
| `technique_focus_gym` | 90 | 89.5 | 15 | **90** | Match quasi perfetto (delta -0.5). Tieni. |
| `test_lp_max_5s` | 40 | 24.4 | 8 | **40** | Test session — formula -16: calibrazione LP + carico/scarico pesi non catturati. Tieni. |
| `test_lp_repeater` | 45 | 21.8 | 6 | **45** | Test session — formula -23: 1 work exercise ma sessione include setup LP, warmup specifico, recupero esteso tra tentativi. Tieni. |
| `test_max_hang_5s` | 40 | 36.9 | 8 | **40** | Test session — delta -3, buon match. Tieni. |
| `test_max_hang_7s` | 40 | 36.9 | 8 | **40** | Test session — identico a test_max_hang_5s. Tieni. |
| `test_max_weighted_pullup` | 45 | 53.3 | 8 | **45** | Test session — delta +8, entro margine. Tieni. |
| `test_pullup_bw` | 30 | 40.1 | 7 | **30** | Test session — delta +10. Formula infla il cooldown timed. Tieni. |
| `test_repeater_7_3` | 45 | 21.8 | 6 | **45** | Test session — identico a test_lp_repeater. Tieni. |
| `upper_body_weights` | 30 | 42.9 | 7 | **40** | Formula +13: target=30 **stale** — 3 push work + cooldown timed. Nessun warmup. Proponi 40. Vedi Parte 2. |
| `yoga_recovery` | 25 | 17.5 | 1 | **25** | Formula -8: yoga flow instruction-only, risolve solo active_hip_mobility. Target=25 corretto. Tieni. |

### Riepilogo proposte di modifica a target_duration_min

| Sessione | target attuale | proposed | motivazione |
|---|---|---|---|
| `core_training` | 25 | **40** | target stale, formula=38 più accurata |
| `heavy_conditioning_gym` | 70 | **80** | target stale, 9 esercizi reali, formula=81 |
| `legs_strength` | 30 | **45** | target stale, formula=45, no warmup |
| `lower_body_gym` | 60 | **75** | stale post-B183, formula=81 (conservativo per alt_sides) |
| `prehab_maintenance` | 18 | **20** | arrotondamento a 5, match formula |
| `upper_body_weights` | 30 | **40** | target stale, formula=43, no warmup |

**6 sessioni con target stale. 29 sessioni OK.**

---

## Parte 2 — Sessioni sospettamente corte o sottili

### Sessioni con meno di 5 exercise_instances risolte

#### `flexibility_full` — 2 esercizi ⚠️ GAP DI TEMPLATE

- **Risolve:** `active_hip_mobility` + `cooldown_deep_squat_hold`
- **Dovrebbe avere:** pigeon pose, couch stretch, pancake, hamstring fold, thoracic rotation — tutto instruction-only nonostante gli esercizi esistano nel catalog (`hip_flexor_couch_stretch`, `flexibility_cossack_squat`, `flexibility_active_leg_raise`, `flexibility_ninety_ninety`)
- **Intenzionale?** NO — gap di template. Il catalog ora ha gli esercizi ma il template non è stato aggiornato per selezionarli.
- **Fix suggerito:** aggiungere 4-5 blocchi di selezione con `pattern: flexibility_passive` e `pattern: flexibility_active`.
- **Impatto:** formula inutilizzabile (18 min), ma target=35 è corretto.

#### `yoga_recovery` — 1 esercizio — BORDERLINE INTENZIONALE

- Yoga flow per natura difficile da codificare come esercizi discreti. Non critico.

#### `handstand_practice` — 3 esercizi — BORDERLINE

- 1 skill exercise + 1 prehab + 1 cooldown. Manca warmup specifico (shoulder prep, wall kicks).

#### `deload_recovery` — 4 esercizi — ✅ INTENZIONALE

- Sessione deload corretta. Poca intensità = pochi esercizi.

### Il pattern "lower_body_gym" — sessioni con nome forte ma contenuto sottile

#### `legs_strength` — ⚠️ STESSA SITUAZIONE DI lower_body_gym PRE-B183

- **Nome:** "Legs Strength (Unilateral Focus)"
- **Work exercises:** `glute_bridge` + `pistol_squat_progression` (solo 2)
- **Problemi:**
  1. **Nessun warmup** — nessun `warmup_strength` block nel template
  2. Solo 2 esercizi di lavoro per una sessione dedicata al lower body
  3. Nessun blocco lunge, nessun blocco calf
  4. `nordic_curl` finisce in prehab per il suo role, non in work
- **Context:** sessione home (equipment=[]), quindi no dumbbell/barbell. Ma potrebbe avere: `reverse_lunge` (no equipment), `single_leg_calf_raise` (step edge), step_ups
- **Fix suggerito:** identico a lower_body_gym — aggiungere `warmup_strength` + `accessory_lunge` (pattern=lunge) + `accessory_calf` (pattern=calf_raise). Aggiornare `time_budget` a 45 min.

#### `complementary_conditioning` — ⚠️ CONTENUTO NON RISOLTO

- **Nome:** "Carries + Crawls + TGU" — signature exercises non vengono selezionate
- **Work exercises:** `ab_wheel_rollout` + `core_hollow_hold` (solo 2)
- **Problema:** `turkish_getup` è nel catalog ma non viene selezionato. `carries` e `crawls` probabilmente instruction-only.
- **Fix suggerito:** verificare filtri di selezione per `turkish_getup` (category=conditioning, role=accessory, domain=strength_general, pattern=carry). Se i filtri del template non matchano questo esercizio, correggerli.

#### `regeneration_easy` — ⚠️ MOLTO THIN

- **Work exercises:** solo `archer_pullup` (1)
- Il climbing easy è instruction-only e costituisce il cuore della sessione — quindi non è un gap critico. Ma 1 esercizio + 2 warmup + 1 cooldown + 1 prehab è squilibrato.

---

## Parte 3 — Ratio warmup+cooldown vs lavoro reale

| session_id | warmup | cooldown | prehab | work | W+C | flag |
|---|---|---|---|---|---|---|
| `boulder_circuit_gym` | 3 | 4 | 2 | 3 | 7>3 | ⚠️ climbing instruction-only (giustificato) |
| `complementary_conditioning` | 2 | 3 | 1 | 2 | 5>2 | ⚠️ TGU/carries instruction-only |
| `core_training` | 0 | 3 | 0 | 3 | 3=3 | ⚠️ no warmup |
| `deload_recovery` | 0 | 1 | 2 | 1 | 1=1 | ✅ deload intenzionale |
| `easy_climbing_deload` | 3 | 4 | 2 | 2 | 7>2 | ✅ deload intenzionale |
| `endurance_aerobic_gym` | 3 | 4 | 2 | 4 | 7>4 | ⚠️ climbing instruction-only (giustificato) |
| `finger_aerobic_base` | 3 | 3 | 2 | 2 | 6>2 | ⚠️ hangboard instruction-only (giustificato) |
| `finger_endurance_short` | 3 | 3 | 2 | 2 | 6>2 | ⚠️ hangboard instruction-only (giustificato) |
| `finger_maintenance_gym` | 4 | 4 | 4 | 4 | 8=4 | ⚠️ 2:1 ratio (giustificato) |
| `finger_maintenance_home` | 1 | 4 | 2 | 2 | 5>2 | ⚠️ hangboard instruction-only (giustificato) |
| `finger_strength_home` | 1 | 4 | 2 | 2 | 5>2 | ⚠️ hangboard instruction-only (giustificato) |
| `flexibility_full` | 0 | 2 | 0 | 0 | 2>0 | 🔴 zero work — gap di template |
| `handstand_practice` | 0 | 1 | 1 | 1 | 1=1 | ⚠️ no warmup |
| `heavy_conditioning_gym` | 3 | 3 | 1 | 9 | 6<9 | ✅ work domina — ottimo |
| `legs_strength` | 0 | 3 | 1 | 2 | 3>2 | 🔴 no warmup + cooldown > work |
| `limit_boulder_gym` | 3 | 4 | 2 | 4 | 7>4 | ⚠️ bouldering instruction-only (giustificato) |
| `lower_body_gym` | 3 | 3 | 0 | 5 | 6>5 | ✅ quasi bilanciato post-B183 |
| `power_contact_gym` | 3 | 4 | 2 | 4 | 7>4 | ⚠️ campus/climbing instruction-only (giustificato) |
| `power_endurance_gym` | 3 | 4 | 2 | 5 | 7>5 | ⚠️ climbing instruction-only (giustificato) |
| `prehab_maintenance` | 0 | 1 | 3 | 0 | 1>0 | ✅ il prehab è il lavoro |
| `pulling_strength_gym` | 3 | 3 | 1 | 5 | 6>5 | ✅ quasi bilanciato |
| `regeneration_easy` | 2 | 1 | 1 | 1 | 3>1 | ⚠️ 1 solo work exercise |
| `route_endurance_gym` | 3 | 4 | 2 | 4 | 7>4 | ⚠️ route climbing instruction-only (giustificato) |
| `route_projecting_gym` | 3 | 4 | 2 | 4 | 7>4 | ⚠️ route climbing instruction-only (giustificato) |
| `strength_long` | 4 | 4 | 3 | 5 | 8>5 | ⚠️ hangboard instruction-only (giustificato) |
| `technique_focus_gym` | 3 | 4 | 2 | 6 | 7>6 | ✅ quasi bilanciato |
| `test_lp_max_5s` | 3 | 0 | 2 | 3 | 3=3 | ✅ test |
| `test_lp_repeater` | 3 | 0 | 2 | 1 | 3>1 | ✅ test intenzionale |
| `test_max_hang_5s` | 3 | 0 | 2 | 3 | 3=3 | ✅ test |
| `test_max_hang_7s` | 3 | 0 | 2 | 3 | 3=3 | ✅ test |
| `test_max_weighted_pullup` | 2 | 3 | 1 | 2 | 5>2 | ✅ test session |
| `test_pullup_bw` | 2 | 3 | 1 | 1 | 5>1 | ✅ test session |
| `test_repeater_7_3` | 3 | 0 | 2 | 1 | 3>1 | ✅ test intenzionale |
| `upper_body_weights` | 0 | 3 | 1 | 3 | 3=3 | ⚠️ no warmup |
| `yoga_recovery` | 0 | 1 | 0 | 0 | 1>0 | ✅ recovery flow instruction-only |

### Spiegazione strutturale del ratio sbilanciato

La maggior parte delle sessioni ha W+C > work **non perché i template siano sbagliati**, ma perché il contenuto principale (bouldering, vie, hangboard) è in instruction-only blocks. Questo è una scelta architettuale corretta: l'arrampicata non si presta a sets/reps discreti.

### Sessioni con problemi reali (non giustificati dall'architettura)

| Sessione | Problema | Priorità |
|---|---|---|
| `flexibility_full` | 0 work — exercises in catalog ma non collegati al template | MEDIA |
| `legs_strength` | No warmup + 2 work per sessione "Strength" | ALTA |
| `upper_body_weights` | No warmup | MEDIA |
| `core_training` | No warmup + target stale | BASSA |
| `complementary_conditioning` | TGU in catalog ma non selezionato | MEDIA |

---

## Conclusione — `target_duration_min` come proxy UI

**La formula non può sostituire `target_duration_min`** per le sessioni di arrampicata e hangboard (54% del catalog), perché il contenuto principale è instruction-only e la formula calcola solo gli esercizi accessori.

**Strategia corretta:** aggiornare i 6 target stale identificati, poi continuare a mostrare `target_duration_min` nel badge `~XX min`. Il badge è utile e accurato — basta mantenere i valori aggiornati ad ogni arricchimento di template.

**Domanda per Daniele:** vuoi che procedessi con i fix (aggiornamento target stale + legs_strength template)? Oppure solo `lower_body_gym.json` target_duration_min (75) come fix immediato di B183?
