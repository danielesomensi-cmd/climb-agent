# D238 — Audit: test_max_hang_7s suggerisce 90 % MVC invece di 100 %

**Tipo:** D (audit, read-only)
**Data:** 2026-05-18
**Modello:** Opus 4.7 (1M context)
**Utente analizzato:** `7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e` (Daniele)
**Backend persistenza:** Supabase (produzione) — letto via `GET /api/state` con `X-Admin-Key`

---

## §1 — Riproduzione del bug

**Contesto**
- Macrocycle generato il 2026-05-17, start_date 2026-05-18 (lunedì = oggi).
- Fase week 1 = `base`, settimana 1 di 12.
- Test session schedulata su **martedì 2026-05-19**, `session_id = "test_max_hang_7s"`.

**Dati utente (snapshot da `/api/state` reale, non da fixture)**

| Campo | Valore |
|---|---|
| `bodyweight_kg` | **77** (non 76 come nel brief) |
| `assessment.tests.max_hang_20mm_7s_total_kg` | **120** |
| `assessment.tests.max_hang_20mm_5s_total_kg` | 120 |
| `assessment.tests_source` | `{}` (sidecar vuoto — nessun test marcato "measured") |
| `baselines.hangboard[0]` | `max_total_load_kg=120`, `edge_mm=20`, `grip="half_crimp"`, `hang_seconds=7`, `source="test"`, `updated_at="2026-03-17"` |
| `tests.max_strength[0]` | `total_load_kg=120`, `external_load_kg=43`, `date=2026-03-17`, `exercise_id=max_hang_5s`, `freshness_policy.stale_after_days=90` |
| `working_loads.entries[max_hang_5s]` | `last_total_load_kg=120`, `next_total_load_kg=123` (progression target dopo test, non usato) |
| `working_loads.entries[max_hang_7s]` | **assente** |

**Sessione risolta (output reale di `POST /api/session/resolve`)**

Il blocco main del template `finger_max_strength_test` restituisce per `max_hang_7s`:

```json
"suggested": {
  "baseline_id": null,
  "protocol_version": "max_hang_5s.v1",
  "based_on": { "max_total_load_kg": 120.0, "bodyweight_kg": 77.0 },
  "setup": { "edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight" },
  "intensity_pct_of_total_load": 0.9,
  "target_total_load_kg": 108.0,
  "added_weight_kg": 31.0,
  "assistance_kg": 0.0,
  "rationale": "target_total_load = intensity_pct * max_total_load; added = target_total - bodyweight; rounded to 0.5kg",
  "schema_version": "progression_targets.v1",
  "suggested_total_load_kg": 108.0,
  "suggested_external_load_kg": 31.0,
  "suggested_rep_scheme": "5x7s"
}
```

Coerente con quanto Daniele vede in UI:
- "Suggested: **+31 kg** (total: **108 kg**)"
- "5 × 7s, rest 3:00"
- Note: "Test protocol: find your 7s max hang total load on 20mm (MVC-7). Rest fully between sets."

**Verità attesa (per Daniele):** una test session a giorno 1 del macrocycle dovrebbe suggerire **MVC-7 = 120 kg total = +43 kg added** (l'ultimo massimo registrato come target da confermare/superare), non 108 kg.

**Discrepanza:** 108 / 120 = 0.900 → applicato il moltiplicatore di intensità training (90 %) al posto del valore raw (100 %).

---

## §2 — Percorso codice tracciato

### 2.1 — Sorgente del moltiplicatore 0.9

Il moltiplicatore vive nel catalogo esercizi, **non** nel template di sessione:

**`backend/catalog/exercises/v1/exercises.json:311-342`**

```json
{
  "id": "max_hang_7s",
  "role": ["main", "test"],
  "pattern": "isometric_hang",
  "attributes": {
    "edge_mm": 20,
    "grip": "half_crimp",
    "intensity_pct": 0.9
  },
  "load_model": "total_load",
  ...
}
```

Lo stesso identificativo esercizio (`max_hang_7s`) è usato sia come `main` in sessioni di training (`finger_max_strength.json` ecc.) sia come `main` in sessioni di test (`finger_max_strength_test.json`). L'attributo `intensity_pct=0.9` è pensato per il contesto di **training**, ma viene applicato anche al contesto di **test** perché nessun altro layer lo override.

### 2.2 — Template del test che embed l'esercizio

**`backend/catalog/templates/v1/finger_max_strength_test.json:30-41`**

```json
{
  "block_id": "main",
  "type": "main_set",
  "exercise_id": "max_hang_7s",
  "prescription": {
    "sets": 5,
    "work_seconds": 7,
    "rest_between_sets_seconds": 180,
    "notes": "Test protocol: find your 7s max hang total load on 20mm (MVC-7). Rest fully between sets."
  },
  "role": ["main"],
  "domain": ["finger_strength"]
}
```

⚠️ Il template definisce `role: ["main"]` (non `["test"]`) e **non** include `intensity_pct_of_total_load`, quindi la prescription non override il default 0.9 dell'esercizio.

### 2.3 — Risolutore: `suggest_max_hang_load()`

**`backend/engine/resolve_session.py:140-199`** — funzione che produce il blocco `suggested`.

Snippet rilevanti:

```python
# line 152-156: priorità all'override di prescription, fallback ad attributes
intensity = prescription.get("intensity_pct_of_total_load")
if intensity is None:
    intensity = attrs.get("intensity_pct")
if intensity is None:
    return None
```

```python
# line 163-171: prima cerca un baseline matched, poi fallback a assessment.tests
b = _pick_hangboard_baseline(user_state, edge_mm=20, grip="half_crimp", hang_seconds=hang_seconds)
if not b:
    tests = (user_state.get("assessment") or {}).get("tests") or {}
    test_total = tests.get("max_hang_20mm_7s_total_kg") or tests.get("max_hang_20mm_5s_total_kg")
    if test_total is not None:
        b = {"max_total_load_kg": float(test_total), ...}
```

```python
# line 177-178: il calcolo che produce 108/31
target_total = float(intensity) * float(max_total)
added = target_total - float(bw)
```

Per Daniele:
- `_pick_hangboard_baseline()` matcha `baselines.hangboard[0]` (edge=20, grip=half_crimp, hang_seconds=7) → ritorna `max_total_load_kg=120`.
- `intensity=0.9` (da `attributes.intensity_pct`, perché la prescription del template non lo override).
- `target_total = 0.9 × 120 = 108.0`.
- `added = 108 − 77 = 31.0`.

### 2.4 — Siti di chiamata

`suggest_max_hang_load()` viene invocata **incondizionalmente** ogni volta che l'esercizio ha `intensity_pct`:

- **`backend/engine/resolve_session.py:1165-1168`** — path "explicit_exercise_id" (template fissi):
  ```python
  if ex_attrs.get("intensity_pct") is not None:
      sug = suggest_max_hang_load(user_state, merged, exercise_attrs=ex_attrs)
      if sug:
          inst["suggested"] = sug
  ```
- **`backend/engine/resolve_session.py:1634-1637`** — path generico di selezione candidati: stesso pattern.
- **`backend/engine/body_part_picker.py:608-617`** — picker on-the-fly: usa la funzione solo se `working_loads` non ha un'entry per quell'esercizio.

Nessuno dei tre call site distingue test session da training session.

### 2.5 — Merge della prescription (priorità)

**`backend/engine/resolve_session.py:1122-1129`**

```python
merged: Dict[str, Any] = {}
if isinstance(ex_defaults, dict):
    merged.update(ex_defaults)               # 1° exercise.prescription_defaults
if isinstance(prescription, dict):
    merged.update(prescription)              # 2° template.block.prescription
if isinstance(primary_overrides, dict):
    merged.update(primary_overrides)         # 3° selection override (B174)
```

→ Se il template del test mettesse `intensity_pct_of_total_load: 1.0` nella prescription del block main, lo step 2 sovrascriverebbe il default 0.9 dell'esercizio. **Non lo fa.**

---

## §3 — Aritmetica esatta

```
Source          : baselines.hangboard[0].max_total_load_kg = 120.0
                  (matched by _pick_hangboard_baseline: edge=20, grip=half_crimp, hang_s=7)
                  fallback would have used assessment.tests.max_hang_20mm_7s_total_kg = 120.0

Multiplier      : exercises[max_hang_7s].attributes.intensity_pct = 0.9
                  (no override in template prescription)

Body weight     : user_state.bodyweight_kg = 77

target_total    = 0.9 × 120.0          = 108.0 kg
added_weight    = 108.0 − 77.0         = 31.0 kg

Rounded to 0.5  : 108.0, 31.0 (already at half-step grid)
```

**Verifica:** lo `suggested` object restituito dall'API contiene esattamente questi numeri. La UI li mostra come "+31 kg (total: 108 kg)". ✅

---

## §4 — Stato del branch test-session

### 4.1 — Dove il codice riconosce "test session"

| Modulo | Cosa fa con i test | Influenza il load? |
|---|---|---|
| `planner_v2.py:1156-1334` (`_run_pass3`) | Schedule test sessions, bypass intensity cap di fase, freshness 42 gg | ❌ no — solo placement |
| `planner_v2.py:1306-1313` | Phase-gate per axis test (D92/B191) | ❌ no |
| `progression_v1.py:1156` | `test_sessions = [s for s in planned if session_id.startswith("test_") or tags.test]` | ✅ ma solo **dopo** la sessione, per leggere i risultati e aggiornare `assessment.tests` / `baselines` |
| `progression_v1.py:1181-1216` | `if exercise_id == "max_hang_7s": ...` → scrive il nuovo MVC | ✅ **dopo** completion |
| `resolve_session.py` (intero file) | nessuna ricerca | ❌ **nessun branch** |
| `resolve_session.py:140-199` `suggest_max_hang_load` | nessuna ricerca | ❌ **nessun branch** |

### 4.2 — Cosa il template segnala (e che nessuno legge)

**Catalogo session** (`test_max_hang_7s.json:38-41`):
```json
"tags": { "test": true },
"test_id": "max_hang_7s_total_load"
```

Questi due campi vengono inseriti in:
- `planner_v2` plan output → `day.sessions[i].tags.test = true` e `day.sessions[i].test_id = "..."` (line 1306-1313)
- `resolve_session` output → `resolved.session.tags = session.tags` (line 1718) → **propagato** ma **non consumato** dal calcolo del load.

Il flag è "in chiaro" lungo tutta la pipeline ma nessun consumer downstream lo usa per modulare `intensity`.

### 4.3 — Differenza tra training e test (oggi)

Per `max_hang_7s` (stesso `exercise_id`):
- Sessione `finger_max_strength` (training): block prescription = `{ sets: 5, work_seconds: 7, rest: 180, ... }` → `intensity = 0.9 × MVC` ✅ corretto per training
- Sessione `test_max_hang_7s` (test): block prescription IDENTICA + `tags.test=true` a livello sessione → `intensity = 0.9 × MVC` ❌ dovrebbe essere `1.0 × MVC`

**Il bug**: nessun layer (template, esercizio, risolutore) sa che siamo nel ramo "test".

---

## §5 — Blast radius

### 5.1 — Test session catalog inventario

| Session catalog | Module → exercise | `intensity_pct` esercizio | Restituisce `suggested`? | Affetto dal bug 90 % |
|---|---|---|---|---|
| `test_max_hang_7s` | `finger_max_strength_test` → `max_hang_7s` | **0.9** | ✅ sì | **🟥 SÌ — caso di Daniele** |
| `test_max_hang_5s` | `finger_max_strength_test` → `max_hang_7s` (sì, lo stesso esercizio!) | **0.9** | ✅ sì | **🟥 SÌ — stesso bug** |
| `test_lp_max_5s` | `finger_max_strength_test_lp` → `lp_max_test_5s` | `null` | ❌ no | 🟡 nessun suggerimento (separato — vedi §5.3) |
| `test_lp_repeater` | `finger_strength_endurance_test_lp` → `lp_repeater_test` | **0.6** | ✅ sì | ⚠️ verificare (probabilmente intensità "di setup" per test a esaurimento) |
| `test_repeater_7_3` | `finger_strength_endurance_test` → `test_repeater_7_3_to_failure` | **0.6** | ✅ sì | ⚠️ verificare (vedi nota) |
| `test_max_weighted_pullup` | `pulling_strength_test` → `weighted_pullup` | `null` | ❌ no | 🟡 nessun suggerimento |
| `test_pullup_bw` | `pulling_strength_test_bw` → `test_max_pullup_bw` | `null` | ❌ no | 🟡 nessun suggerimento (BW-only) |

### 5.2 — Anomalia secondaria nel catalogo

`test_max_hang_5s.json` e `test_max_hang_7s.json` usano **entrambi** il template `finger_max_strength_test` che contiene `exercise_id: max_hang_7s`. Quindi `test_max_hang_5s` in pratica suggerisce un protocollo 7s, non 5s. Inoltre entrambi i session catalog dichiarano `test_id: "max_hang_7s_total_load"`. **Bug separato** (D85 legacy?) ma da segnalare.

### 5.3 — Test sessions che NON suggeriscono load (intentional?)

- `test_max_weighted_pullup`: usa `weighted_pullup` (no `intensity_pct`). L'utente non ha un target di carico → deve "trovarlo" durante il test. Concettualmente è corretto (è un 1RM/2RM test), ma significa che **il sistema non guida l'utente verso il proprio massimo precedente**. Possibile UX gap, fuori scope.
- `test_lp_max_5s`: simmetrico al weighted_pullup.

### 5.4 — Test con `intensity_pct = 0.6` (`test_repeater_7_3_to_failure`, `lp_repeater_test`)

Il valore 0.6 è inferiore a un training (training repeater è tipicamente 80-90 % MVC), quindi probabilmente rappresenta il **carico di setup** per un test "a esaurimento" — l'utente carica al 60 % MVC e fa più reps possibili. Non è il bug di Daniele, ma **sospetto consigliato** per audit separato: il fatto che il dato non sia documentato nel codice è un brutto segnale.

### 5.5 — Bug terziari osservati durante l'audit

1. **`resolve_session.py:182`** — `protocol_version` ritorna `"max_hang_5s.v1"` come default anche quando il baseline è per `max_hang_7s`. Solo etichetta, ma confusionario in `feedback_log`/`tests` history.
2. **`resolve_session.py:181`** — `baseline_id: null` nello `suggested` di Daniele anche se il `baselines.hangboard[0]` matcha; il baseline non porta un proprio `baseline_id`. Solo telemetria/debug.
3. **`assessment.tests_source = {}` per Daniele** — sidecar vuoto nonostante test del 2026-03-17 in `tests.max_strength[0]`. La policy D214 ("solo scalari measured popolano `_recent_test_dates`") quindi non scatta → il planner schedula correttamente il retest a settimana 1. ✅ Effetto desiderato in questo caso, ma il sidecar dovrebbe popolarsi quando l'utente completa un test in-app.

---

## §6 — Raccomandazione (opinione)

### 6.1 — È un bug? Sì.

Il prompt visualizzato in UI dice testualmente "Test protocol: find your 7s max hang total load on 20mm (MVC-7)" — **trovare** il massimo. Suggerire 90 % MVC come target è incoerente con quel prompt: l'utente che parte da +31 kg non sta "trovando" il proprio massimo, sta confermando un sub-massimale e, peggio, **abbassando** il proprio MVC nel sistema (vedi §6.2).

Non vedo una motivazione fisiologica difendibile per suggerire 90 % invece di 100 % in un test. Una sicurezza/ramp-up viene già coperta dal warm-up specifico (`dead_hang_easy 3 × 10s`) prima del main block. Le 5 serie da 7s a 180s di riposo sono il protocollo MaxHangs standard di Hörst/López — pensato per testare il massimo, non per allenarlo (per il training c'è la sessione separata `finger_max_strength`).

### 6.2 — Perché è dannoso (oltre l'estetica)

Closed-loop negativo dimostrabile:

1. Utente vede suggested +31 kg → carica i pesi proposti → completa 5 × 7s a 108 kg ("ok" o "easy").
2. Logga `used_total_load_kg = 108`.
3. `progression_v1.update_test_results_from_log` (line 1181-1216) scrive:
   ```
   assessment.tests.max_hang_20mm_7s_total_kg = 108
   baselines.hangboard[0].max_total_load_kg = 108
   ```
4. **Il nuovo MVC del sistema è 108 kg, non 120 kg.** L'utente ha *silenziosamente regresso* del 10 %.
5. Tutte le sessioni di training della fase successiva derivano dal nuovo MVC 108 → 90 % × 108 = **97 kg** target → ulteriore regresso → spirale verso il basso.

Il bug ha un effetto compounding: ogni ciclo di test sotto-stima il massimo e l'errore si amplifica nei training successivi.

### 6.3 — Forma del fix (opinione)

Tre opzioni, in ordine di preferenza:

**Opzione A — Catalog-only (preferita): aggiungere `intensity_pct_of_total_load: 1.0` nel template del test**

`backend/catalog/templates/v1/finger_max_strength_test.json` block main:
```json
"prescription": {
  "sets": 5,
  "work_seconds": 7,
  "rest_between_sets_seconds": 180,
  "intensity_pct_of_total_load": 1.0,
  "notes": "Test protocol: find your 7s max hang total load on 20mm (MVC-7). Rest fully between sets."
}
```

Pro:
- **Zero rischio** sul motore. Il resolver line 152 legge prima `prescription.intensity_pct_of_total_load` e solo dopo cade su `attributes.intensity_pct`. Già supportato dal codice.
- Esplicito: il template del test dichiara la propria intensità.
- Coerente con i template di training futuri che potrebbero voler usare un'intensità diversa dal default esercizio (es. deload week → 0.8).
- Test catalog facile da scrivere.

Contro:
- Soluzione "per file": va replicata sul template LP (`finger_max_strength_test_lp.json`) — ma sono comunque solo 2 file.
- Non protegge da futuri test session che dimenticano di settare l'override.

**Opzione B — Resolver branch: rendere `suggest_max_hang_load` test-aware**

Passare un flag `is_test: bool` (o `session_role: "test" | "training"`) al risolutore e, in caso di test, forzare `intensity = 1.0` ignorando il default esercizio.

Pro:
- Difesa in profondità: anche un template non aggiornato si comporta correttamente.
- Coerente con il fatto che il planner già sa che è una test session (line 1156 `tags.test` o `session_id.startswith("test_")`).

Contro:
- Tocca `resolve_session.py` (modulo high-risk per CLAUDE.md — richiede analisi prima dell'implementazione).
- Richiede di propagare il flag fino al call site (line 1166, 1635) — diff non banale.
- Magic behavior: la stessa exercise definition produce risultati diversi a seconda del wrapper della sessione, meno leggibile.

**Opzione C — Marcare i test exercise nel catalog**

Tipo: creare un esercizio separato `max_hang_7s_test` con `intensity_pct: 1.0`, e aggiornare il template a puntarci.

Pro:
- Massima separazione data/logic.

Contro:
- Duplica una exercise definition quasi identica.
- Inquina il catalog con varianti "marketing-only" (test vs training).
- Più code paths da mantenere.

### 6.4 — Raccomandazione finale

**Opzione A** — fix catalog-only su `finger_max_strength_test.json` e `finger_max_strength_test_lp.json`, più una nota nei test esistenti `backend/tests/` per asserire che il blocco main di una test session restituisce `intensity_pct_of_total_load == 1.0` nel `merged`. Aggiungere un'asserzione UI/integration test che `target_total_load_kg == max_total_load_kg` per test session di finger strength.

Effort: **XS** (1 file template + 1 file template LP + 1-2 test pytest).
Rischio: **Basso** — change tutto entro catalog, motore intatto.
Blast radius: 2 session catalog (`test_max_hang_5s`, `test_max_hang_7s`) + 1 (`test_lp_max_5s` se applicabile — verificare attributo `intensity_pct` su `lp_max_test_5s` perché ora è null, quindi forse il fix LP è diverso).

Audit separato consigliato (NON parte di questo fix):
1. **`test_max_hang_5s` punta al template `finger_max_strength_test` che usa `max_hang_7s`** — apparente errore di catalog. Rinominare uno dei due o creare un template dedicato.
2. **`test_repeater_7_3_to_failure` e `lp_repeater_test` con `intensity_pct=0.6`** — verificare semantica (probabilmente carico di setup, non target), documentare nel JSON.
3. **`test_max_weighted_pullup` non suggerisce alcun carico** — UX gap: l'utente non ha riferimento al proprio massimo precedente. Considerare un suggested totale = `weighted_pullup_1rm_total_kg` da `baselines.pulling`.

---

## Appendice — file/line di riferimento

| File | Linee | Cosa |
|---|---|---|
| `backend/catalog/exercises/v1/exercises.json` | 311-365 | Definizione `max_hang_7s`, `intensity_pct=0.9` |
| `backend/catalog/sessions/v1/test_max_hang_7s.json` | 24-41 | Session catalog del test, `tags.test=true` |
| `backend/catalog/templates/v1/finger_max_strength_test.json` | 30-41 | Template del block main del test |
| `backend/engine/resolve_session.py` | 140-199 | `suggest_max_hang_load` — il calcolo |
| `backend/engine/resolve_session.py` | 152-156 | Priority lookup `prescription` → `attributes` |
| `backend/engine/resolve_session.py` | 167-171 | Fallback baseline da `assessment.tests` |
| `backend/engine/resolve_session.py` | 177-178 | `target = intensity × max_total`; `added = target − bw` |
| `backend/engine/resolve_session.py` | 1122-1133 | Merge precedence (defaults → prescription → overrides) |
| `backend/engine/resolve_session.py` | 1165-1168 | Call site #1 (explicit_exercise_id) |
| `backend/engine/resolve_session.py` | 1634-1637 | Call site #2 (generic selection) |
| `backend/engine/resolve_session.py` | 1718 | `tags` propagato in output (non consumato) |
| `backend/engine/progression_v1.py` | 1156-1216 | Closed-loop update post-test → scrive il nuovo MVC |
| `backend/engine/planner_v2.py` | 1262-1334 | Pass3 placement test sessions (freshness/phase gate) |
| `backend/engine/body_part_picker.py` | 540-621 | Path alternativo (`apply_resolver_light`) — fuori dal flow del test |
