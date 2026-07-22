# D259 — Audit: `load_model` Mistag Scan (READ-ONLY)

**Type:** D (audit / read-only) · **Risk:** LOW · **Status:** ✅ Findings delivered — no code/catalog changes.
**Root case:** kg-log field entirely absent for **Bulgarian Split Squat** e **Cossack Squat** nel guided player di una sessione adhoc "Legs @ Work".

---

## 1. I due casi noti — confermati

| id | name | `load_model` | equipment_required | `attributes.allow_load_logging` |
|----|------|-------------|--------------------|--------------------------------|
| `bulgarian_split_squat` | Bulgarian Split Squat | `bodyweight_only` | — | (assente) |
| `cossack_squat` | Cossack Squat | `bodyweight_only` | — | (assente) |

Entrambi sono taggati `bodyweight_only`, **nessun** campo `equipment_required`, **nessun** `attributes.allow_load_logging`. Nel testo compaiono solo "weight"/"load" in senso metaforico ("all weight on the front leg", "psoas load") — **non** un'istruzione "add a dumbbell". Ma sono movimenti universalmente caricati (goblet/manubri): il tag è corretto come *forma di default* ma blocca l'utente dal loggare un carico realmente usato.

### Tie-back alla regola di render B298
Il campo kg nel guided player è governato da (identico in `guided-exercise-step.tsx:194` e `feedback-items.ts:47`):

```
hasLoadField = isKgLoadable(load_model ∈ {external_load, total_load})
               || !!exercise.allowLoadLogging      // ← attributes.allow_load_logging
```

`bodyweight_only` + flag assente ⇒ **entrambi i termini falsi** ⇒ campo kg soppresso. Causa confermata. **Non** è un bug B298 e **non** è il tema anchor di A253: è metadata di catalog + un buco di propagazione (§4).

---

## 2. Sweep catalog-wide — 254 esercizi

Distribuzione `load_model`: `bodyweight_only` 146 · `external_load` 45 · `grade_relative` 40 · `total_load` 23.

I mismatch reali si dividono in **due meccanismi di fix diversi**, guidati dal precedente **A229** (che superò A228: pallof passò a `external_load` e il flag `allow_load_logging` fu rimosso — oggi **zero** esercizi lo usano, ma il frontend lo onora ancora).

### Tier 1 — vero mistag di `load_model` → `external_load`
La forma **primaria/obbligatoria** usa carico esterno (dumbbell in `equipment_required`). Come pallof in A229, vanno a `external_load` (avranno anche una prescrizione/suggested load).

| id | name | attuale | equipment_required | suggerito | evidenza |
|----|------|---------|--------------------|-----------|----------|
| `elbow_wrist_extensor_eccentric` | Wrist Extensor Eccentrics | `bodyweight_only` | `[dumbbell]` | **`external_load`** | dumbbell obbligatorio; l'eccentrica *è* il caricamento |
| `stick_pronation_supination_eccentric` | Stick Pronation/Supination Eccentrics | `bodyweight_only` | `[dumbbell]` | **`external_load`** | "Hold a light dumbbell or hammer…"; leva = carico |

### Tier 2 — bodyweight-first, comunemente caricati → `attributes.allow_load_logging: true`
Prescrizione a corpo libero **corretta** (il planner non deve pretendere un carico), ma l'utente deve poter **loggare** i kg usati. È esattamente la classe del bug segnalato. Fix = il flag dormiente (record-only), **non** cambio di `load_model`.

| id | name | `load_model` | evidenza di caricabilità |
|----|------|-------------|--------------------------|
| `bulgarian_split_squat` ⭐ | Bulgarian Split Squat | `bodyweight_only` | goblet/manubri standard (caso segnalato) |
| `cossack_squat` ⭐ | Cossack Squat | `bodyweight_only` | goblet/kettlebell standard (caso segnalato) |
| `reverse_lunge` | Reverse Lunge | `bodyweight_only` | cue esplicito: "hold dumbbells (5–15 kg) or use a barbell" |
| `single_leg_rdl` | Single-Leg Romanian Deadlift | `bodyweight_only` | cue: "hold a dumbbell in the opposite hand" |
| `glute_bridge` | Glute Bridge | `bodyweight_only` | cue: "place dumbbell or plate across hip crease" |
| `single_leg_glute_bridge` | Single-Leg Glute Bridge | `bodyweight_only` | fratello di glute_bridge, stesso caricamento |
| `hip_flexor_strengthening` | Hip Flexor Strengthening | `bodyweight_only` | cue: "place a light dumbbell on the thigh (2–5 kg)" |
| `seated_leg_raise_hip_flexor` | Seated Leg Raise (Hip Flexor) | `bodyweight_only` | cue: "adding a light ankle weight (1–2 kg)" |
| `side_lying_hip_abduction` | Side-Lying Hip Abduction | `bodyweight_only` | cue: "adding an ankle weight (1–3 kg)" |
| `single_leg_calf_raise` | Single Leg Calf Raise | `bodyweight_only` | calf raise caricato = standard (goblet/manubrio) |
| `pistol_squat_progression` | Pistol Squat Progression | `bodyweight_only` | contrappeso goblet frequente — *confidenza minore* |

### Tier 3 — calisthenics zavorrabile con fratello già caricabile → **lasciare `bodyweight_only`**
Famiglia pull-up (`pullup`, `chinup`, `eccentric_pullup`, `power_pullups_explosive`, `frenchies`, `archer_pullup`, `l_sit_pullup`, `typewriter_pullup`, `uneven_grip_pullup`, `lock_off_isometric`) e push (`pushup`, `incline_pushup`, `pike_pushup`, `handstand_pushup_wall`, `dip`, `ring_pushup`). Chi vuole zavorrare logga la variante dedicata già `external_load` (`weighted_pullup`/`weighted_chinup`/`weighted_dip`). Tag corretto — *fuori scope*, al più `dip` opzionale.

### Falsi positivi esclusi (correttamente non-caricabili)
Dita/hang deliberatamente a corpo libero o assistiti (`min_edge_hang` "no added load", `active_finger_curls`, `finger_recruitment_pulls`, `hang_rampup_progressive`, `test_max_hang_duration_20mm`) · drill su parete/board (`foothold_stare`, `straight_arms`, `tap_and_place`, `hip_rotation_drill`, `tech_applied_strength`, `easy_route_laps`, `campus_*`, `breathing_awareness`) · mobilità/stretch (`cooldown_*`, `foam_rolling_general`, `lat_overhead_stretch`, `flexibility_*`) · core skill/isometrico (`ab_wheel_rollout`, `core_l_sit`, `plank_shoulder_tap`, `v_up`, `knees_to_elbows`, `toes_to_bar`, `hanging_leg_raise`, `copenhagen_adductor_plank`) · band/eccentrica a corpo libero (`clamshell`, `standing_hip_adduction_band`, `band_pull_apart`, `nordic_curl`, `*_assisted_pullup`). "load"/"weight" nel testo = metafora, non kg esterni.

---

## 3. Cross-check batch di authoring

- **Tier 1** — i due mistag `dumbbell` sono **vecchi** e isolati: `elbow_wrist_extensor_eccentric` dal restructure iniziale (`15ee847`), `stick_pronation_supination_eccentric` dal primo batch hangboard (`756d18a`). Non un difetto di un batch recente.
- **Tier 2** — cluster parziale in **C209** ("KB-validated catalog expansion — 6 exercises hips/glutes/legs") che introdusse `bulgarian_split_squat`, `cossack_squat`, `single_leg_rdl` tutti `bodyweight_only`; il resto è sparso (`reverse_lunge` B183, `glute_bridge` B83).
- **Root cause reale**: non un singolo default recente sbagliato, ma un'**abitudine di authoring ricorrente** — gli accessori gamba/anca *opzionalmente* caricati vengono taggati `bodyweight_only` e il flag `allow_load_logging` non viene mai applicato. Poiché A229 rimosse l'unico utente del flag, **oggi nessun `bodyweight_only` è loggabile**: l'intera classe "accessorio opzionalmente caricato" è uniformemente non-loggabile.

---

## 4. ⚠️ Reperto oltre il catalog: la propagazione `attributes` è rotta nel path adhoc/custom

Il campo `hasLoadField` legge `attributes.allow_load_logging`, ma **`attributes` non arriva** al guided player quando la sessione è adhoc/custom — esattamente lo scenario del bug:

- `resolve_session.py` (piano standard) → propaga `attributes` ✅ (righe 1287/1403/1791)
- `body_part_picker.py` → propaga `attributes` ✅
- **`adhoc_builder.py::_to_custom_exercise`** → emette solo `load_model` (B298), **NON** `attributes` ❌
- **`custom_session.py::_enrich_exercise_display`** (path di persist su "Add to today & run") → re-deriva da catalog `name/cues/load_model/category/video_url` ma **NON `attributes`** ❌ (riga 90)

**Conseguenza:** anche se il Brief C mette `attributes.allow_load_logging: true` in catalog su `bulgarian_split_squat`, il campo kg resterebbe **assente** nel guided player adhoc (il caso reale). Il solo cambio di catalog è **necessario ma non sufficiente** per le sessioni adhoc/custom.

---

## 5. Raccomandazione — scoping del follow-up

Il follow-up **non è puro Brief C**: è **misto catalog + codice** (tocca `frontend/`? no — solo backend `adhoc_builder.py`/`custom_session.py`; ma resta backend-only → push diretto a main OK, con test).

**Catalog (~13 esercizi):**
1. Tier 1 (2): `load_model` → `external_load`.
2. Tier 2 (11, o 10 se si esclude `pistol_squat_progression`): aggiungere `attributes.allow_load_logging: true` (mantenendo `bodyweight_only`).

**Codice (obbligatorio per far funzionare il caso adhoc segnalato):**
3. `custom_session.py::_enrich_exercise_display` — propagare `attributes` (o almeno `allow_load_logging`) dal catalog sull'istanza persistita.
4. `adhoc_builder.py::_to_custom_exercise` — emettere `attributes`/`allow_load_logging` per coerenza della preview pre-persist.

**Test:**
5. Guided player mostra il campo kg per un Tier-2 in (a) sessione pianificata **e** (b) sessione adhoc/custom persistita.
6. Tier-1 riceve `load_model=external_load` + suggested load via progression.
7. Invariante immutabilità: past/completed non modificati dal re-tag.

**Fuori scope:** Tier 3 (già coperti dalle varianti `weighted_*`). Nota B298: anche dopo il re-tag, i Tier-2 mostrano un campo kg **vuoto** finché l'utente non logga una volta — comportamento corretto (bucket VUOTO), l'obiettivo è rendere il campo **presente e loggabile**, non pre-riempito.
