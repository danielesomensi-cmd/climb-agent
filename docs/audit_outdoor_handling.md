# D247 — Outdoor Handling Audit (READ-ONLY)

**Type:** D (audit / read-only) · **Risk:** reads high-risk modules, no writes · **Date:** 2026-06-19

Mappa precisa di come "outdoor" è gestito oggi attraverso engine, data model, planner e frontend, con riferimenti `file:line`. **Nessuna modifica effettuata.** Questo è lo step di discovery prima di progettare un'esperienza outdoor dedicata.

---

## 1. Representation & data model

### Due rappresentazioni distinte e parallele (punto chiave)

Outdoor vive in **due posti scollegati**:

1. **`outdoor_slot` / campi `outdoor_*` a livello di giorno** nel week plan → "c'è un giorno outdoor pianificato"
2. **`outdoor_logs` (JSONL/Supabase) + log dettagliato delle vie** → "cosa ho effettivamente scalato"

Più una **terza copia parziale**: `state.outdoor_log[]` (mirror B116, solo metadati di carico).

### 1a. Come il planner segna un giorno come outdoor

Outdoor NON è una sessione né una entry di catalogo. È un **flag a livello di giorno** derivato dalla preferenza di location degli slot:

`backend/engine/planner_v2.py:767-778`
```python
# Check if ALL available slots on this day are outdoor-only
available_slots = [s for s in SLOTS if day_avail[s]["available"]]
if available_slots:
    all_outdoor = all(
        day_avail[s].get("preferred_location") == "outdoor"
        or day_avail[s].get("locations") == ["outdoor"]
        for s in available_slots
    )
    if all_outdoor:
        day_is_outdoor[offset] = True
        day_has_available_slot.append(False)  # skip for session assignment
```

E l'output del giorno: `backend/engine/planner_v2.py:1404-1405`
```python
if day_is_outdoor[offset]:
    day_entry["outdoor_slot"] = True
```

> ⚠️ **Violazione esplicita del principio "equipment-based, not location-based".** La discriminazione outdoor/indoor qui è **interamente location-based** (`preferred_location == "outdoor"`). Non c'è alcun `required_equipment` coinvolto: il giorno outdoor è gated sulla location dello slot, non sull'equipaggiamento. Questo è coerente con la natura "outdoor" (per definizione fuori dalla palestra) ma è formalmente un'eccezione al principio del progetto, da tenere a mente.

### 1b. Campi `outdoor_*` a livello di giorno (week plan)

Definiti come campi day-level preservati attraverso la rigenerazione — `backend/engine/replanner_v1.py:637-643`:
```python
_DAY_LEVEL_FIELDS = (
    "outdoor_spot_name", "outdoor_spot_id", "outdoor_discipline",
    "outdoor_session_status", "other_activity", ...
)
```
Più `outdoor_slot` (bool) e `outdoor_load_score` (int, settato al completamento — `replanner_v1.py:976`).

Stati possibili di `outdoor_session_status`: `"planned"` → `"done"` → (`"skipped"` riconosciuto in report). Settato a `planned` da `add_outdoor`/override (`replanner_v1.py:966,1501`), a `done` da `complete_outdoor` (`replanner_v1.py:972`).

### 1c. Spots (setup base)

`state.outdoor_spots[]` — schema in `backend/data/user_state.json:276` (`"outdoor_spots": []`).
Modello: `backend/api/models.py:173-179`:
```python
class OutdoorSpotCreate(BaseModel):
    id: Optional[str] = None
    name: str
    discipline: Literal["lead", "boulder", "both"]
    typical_days: Optional[List[str]] = None
    notes: Optional[str] = None
```
> Nessun campo "caratteristiche del progetto" (angolo parete, lunghezza, stile). Lo spot è solo nome + disciplina + note libere.

### 1d. Dove sono salvati i dati delle vie/send

Tabella/log **dedicato e separato** dal week plan: `outdoor_logs`.

- **Supabase** (prod): tabella `outdoor_logs` con colonne `user_id`, `session_date`, `entry` (JSONB) — `backend/engine/storage_supabase.py:278-282`. UNIQUE su `(user_id, session_date)` → upsert per data, no dedup necessario.
- **File** (pytest/dev): JSONL annuale per utente — `backend/engine/storage_file.py:259-277`.

Shape della `entry` (validato in `outdoor_log.py:16,75-116`, modello `models.py:197-208`):
```python
{
  "log_version": "outdoor.v1",        # required
  "date": "YYYY-MM-DD",               # required
  "spot_id": "spot_xxx" | None,
  "spot_name": "Arco",                # required
  "discipline": "lead|boulder|both",  # required
  "duration_minutes": 120,            # required, int >= 1
  "conditions": {...} | None,         # libero, MAI usato/letto altrove
  "routes": [                         # required (lista, può essere vuota)
    {
      "name": "...",                  # required per via
      "grade": "7a",                  # required per via (Font per boulder, French per lead)
      "discipline": "lead|boulder|both" | None,
      "style": "onsight|flash|redpoint|project" | None,
      "attempts": [                   # non-empty list
        {"result": "sent|fell|topped_out", "notes": str|None}
      ]
    }
  ],
  "notes": str | None,
  "energy_level": str | None,         # accettato dal modello, MAI usato
  "overall_feeling": str | None       # accettato dal modello, MAI usato
}
```

> **Implicazione per la feature:** il modello `OutdoorSessionLog` ha già 3 campi opzionali "soft" inutilizzati (`conditions`, `energy_level`, `overall_feeling`). `conditions: Dict[str,Any]` è un contenitore JSONB libero perfetto per ospitare day-type / caratteristiche progetto / strategia senza migrazione schema. La degradazione graceful è già strutturalmente possibile: quasi tutto è `Optional`, solo `name`/`grade` per via e i 6 top-level required sono obbligatori.

---

## 2. Planner integration

### Il planner NON pianifica sessioni outdoor — le **esclude**

`planner_v2` tratta i giorni outdoor come **buchi**: li marca `outdoor_slot=True` e li salta nell'assegnazione sessioni (`planner_v2.py:776-777`, `day_has_available_slot.append(False)`). Verificato anche per il passaggio finger-maintenance: `planner_v2.py:1206-1207` (`if day_is_outdoor[offset]: continue`).

I giorni outdoor **non contano nel budget** di `target_training_days_per_week` — confermato dal test `test_outdoor_slot_not_counted_in_budget` (`test_outdoor.py:348`).

### Outdoor NON passa per resolve / progression / closed-loop

- `resolve_session.py` — **zero** occorrenze di "outdoor" (grep vuoto). I giorni outdoor non hanno sessioni da risolvere.
- `progression_v1.py` — zero occorrenze.
- `closed_loop_v1.py` / `backend/engine/adaptation/` — zero occorrenze.
- `macrocycle_v1.py` — una sola menzione testuale in una descrizione di fase (`macrocycle_v1.py:692`, "projecting, outdoor"). Il macrociclo **non genera** giorni outdoor.

### Come nasce un giorno outdoor

Due strade, entrambe **user-driven**, mai dal macrociclo:

1. **Disponibilità onboarding/weekly-override**: l'utente segna uno slot come `preferred_location="outdoor"` → il planner lo rileva (vedi §1a). Mappatura in `weekly_override.py:20` (`"outdoor": ["outdoor"]`).
2. **Replanner override / quick-add**: intent outdoor (vedi §3) → `replanner_v1.py:1482-1510` marca il giorno outdoor e **azzera le sessioni indoor** (`location == "outdoor"`).

> Le sessioni outdoor sono **"free"/manuali**: nessun esercizio assegnato, nessun set/rep/load prescritto. Sono solo un contenitore per il log.

---

## 3. Current outdoor "report" / logging

### Tutti i campi salvati: vedi §1d (shape `entry` completo).

### Endpoints (router `backend/api/routers/outdoor.py`)

| Metodo | Path | Funzione | Note |
|--------|------|----------|------|
| GET | `/api/outdoor/spots` | `get_outdoor_spots` (`:31`) | da `state.outdoor_spots` |
| POST | `/api/outdoor/spots` | `add_outdoor_spot` (`:38`) | |
| DELETE | `/api/outdoor/spots/{id}` | `delete_outdoor_spot` (`:65`) | |
| POST | `/api/outdoor/log` | `post_outdoor_log` (`:82`) | **subscription-gated** |
| GET | `/api/outdoor/log/{date}` | `get_outdoor_log_by_date` (`:116`) | arricchisce con `load_score` |
| PUT | `/api/outdoor/log` | `put_outdoor_log` (`:128`) | sync `state.outdoor_log[]` |
| DELETE | `/api/outdoor/log/{date}` | `delete_outdoor_log` (`:160`) | sync `state.outdoor_log[]` |
| GET | `/api/outdoor/sessions` | `get_outdoor_sessions` (`:186`) | |
| GET | `/api/outdoor/stats` | `get_outdoor_stats` (`:196`) | |
| POST | `/api/outdoor/convert-slot` | `convert_outdoor_slot` (`:206`) | subscription-gated |

Eventi replanner correlati (`replanner_v1.py`): `add_outdoor` (`:957`), `complete_outdoor` (`:968`), `undo_outdoor` (`:1032`), `remove_outdoor` (`:1037`).

### Frontend

- **Form di log**: `frontend/src/components/training/OutdoorLogForm.tsx` (unico componente di compilazione). Campi esposti all'utente: **Date, Spot (select+free text), Discipline (boulder/lead/both), Duration (default 120), Routes[] (name/grade/style/attempts a badge ciclabile Sent→Fell→remove), Notes**. NON espone `conditions`, `energy_level`, `overall_feeling`.
- **Pagina dedicata**: `frontend/src/app/(main)/outdoor/page.tsx` (history, stats, grade histogram). Voce in bottom-nav: `bottom-nav.tsx:63` (`href: "/outdoor"`).
- Hook: `use-outdoor.ts` (queries), `use-outdoor-mutations.ts`.
- Form invocato anche da `/today` (`today/page.tsx:25`) e `/week` (`week/page.tsx`) tramite dialog.

### Il dato loggato è riusato?

**Parzialmente, ma in catene separate:**
- **Load / report**: SÌ. `report_engine.py` carica le sessioni outdoor (`load_outdoor_sessions`, `report_engine.py:981`), somma il loro `compute_outdoor_load_score` nel carico settimanale/mensile (`:271-273`), costruisce una sezione outdoor (`_build_outdoor`, `:479`) e merge nei giorni (`:595-616`).
- **Ripple immediato**: SÌ ma **solo via day-level `outdoor_load_score`**, non leggendo le vie. Vedi §5.
- **Closed loop / progression / assessment**: **NO**. Le vie scalate outdoor (grade, send) **non aggiornano** il profilo a 5 assi, né la progressione, né i moltiplicatori adattivi. Il log delle vie è isolato dall'engine deterministico.
- I campi `conditions`/`energy_level`/`overall_feeling` non sono letti **da nessuna parte**.

---

## 4. Frontend surfaces

Pagine/componenti che toccano outdoor:

| File | Ruolo |
|------|-------|
| `app/(main)/outdoor/page.tsx` | Pagina dedicata: history + stats + histogram |
| `components/training/OutdoorLogForm.tsx` | Form di log/edit (unico) |
| `app/(main)/today/page.tsx` | Dialog log outdoor dal "today" |
| `app/(main)/week/page.tsx` | Quick-add outdoor + fetch routes per giorni done |
| `components/training/day-card.tsx` | Render outdoor nel week/day grid (vedi sotto) |
| `app/(main)/reports/weekly/page.tsx` | Sezione outdoor nel report |
| `components/training/replan-dialog.tsx`, `quick-add-dialog.tsx` | Intent outdoor nel replan |
| `components/training/weekly-checkin-*.tsx` | Check-in |
| `app/(main)/settings/page.tsx` | Gestione spots |
| `app/onboarding/{locations,availability,trips}/page.tsx` | Setup disponibilità outdoor + trips |
| `components/layout/bottom-nav.tsx` | Voce nav `/outdoor` |
| `lib/{types,api,query-keys,invalidation}.ts`, `lib/hooks/...outdoor...` | Tipi + data layer |

### Come appare un giorno outdoor nel week view

`day-card.tsx`:
- `day.outdoor_spot_name` presente → card con nome spot + disciplina (`:389-401`).
- Se `done`: mostra `N routes/problems · M min` + `Load: X` (`:410-425`); espandibile per dettaglio vie (`:490-535`). `routeLabel` = "problems" se boulder, "routes" altrimenti (`:164`).
- Se `outdoor_slot` ma senza spot_name (giorno outdoor pianificato vuoto): branch dedicato `:535`.
- Le routes vengono fetchate separatamente per i giorni `done` (`week/page.tsx:126-154`) e passate come props (`outdoorRoutes`, `outdoorDurationMinutes`, `outdoorLoadScore` — `day-card.tsx:39-41`).

### Esiste già un session timer riutilizzabile?

**SÌ — pattern `startedAt` + tick a 1s, banale da riusare:**
- `components/guided/session-timer.tsx` (intero file, 39 righe): prende `startedAt: string`, calcola `elapsed` con `setInterval(tick, 1000)`, formatta `h:mm:ss`. **Componente generico, drop-in.**
- Backend precedente per il pattern "timer di sessione": `free_session.py` salva `started_at` all'avvio (`:212`) e calcola `duration_minutes` al finish da `(now - started)` (`:300-301`). Questo è esattamente il modello "start timer → durata calcolata server-side" che servirebbe per la sessione outdoor.
- Altri timer (countdown esercizio, rest, circuit, tabata): `guided/exercise-timer.tsx`, `free-session/rest-timer.tsx`, `circuit/CircuitTimer.tsx`, `session-play/custom-rest-timer.tsx` — countdown, meno pertinenti di `session-timer.tsx`.

> **Implicazione:** un timer di sessione outdoor (start → durata) può riusare `session-timer.tsx` (UI) + il pattern `started_at`/finish di `free_session.py` (persistenza). Oggi però l'outdoor log compila `duration_minutes` a mano (default 120 nel form, `OutdoorLogForm.tsx:37`); non c'è cronometro live per outdoor.

---

## 5. Feedback & immutability

### Outdoor genera feedback per il closed loop?

**No — è isolato dal closed loop.** L'unico effetto "adattivo" è il **ripple immediato day-level** nel replanner, basato sul `outdoor_load_score` aggregato (non sulle singole vie):

`replanner_v1.py:974-1024` (evento `complete_outdoor`):
```python
outdoor_load = event.get("outdoor_load_score", 0)
day["outdoor_load_score"] = outdoor_load
if outdoor_load >= OUTDOOR_RIPPLE_THRESHOLD:   # soglia = 65 (:123)
    # ... declassa sessioni hard→medium, medium→low nei giorni successivi
    "explain": [f"hard→medium after outdoor load={outdoor_load}"]
```
Test: `test_high_load_triggers_ripple` (`test_outdoor.py:407`), `test_low_load_no_ripple` (`:420`).

Questo è un **adattamento locale e immediato** (riduce intensità nei giorni vicini per recupero), **non** un feedback al motore deterministico: non tocca `closed_loop_v1`, `progression_v1`, né l'assessment. `feedback.py` non ha alcun riferimento outdoor (grep vuoto).

### Immutabilità delle sessioni outdoor passate

**Rispettata, su due livelli:**

1. **Replanner non può modificare un outdoor completato:**
   - `remove_outdoor` solleva errore se `done`: `replanner_v1.py:1039-1040` (`raise ValueError("Cannot remove a completed outdoor session")`).
   - Override outdoor su un giorno con sessione completata è bloccato: `replanner_v1.py:1495` (`Cannot override day ... with outdoor`).

2. **Rigenerazione preserva il giorno outdoor done wholesale:**
   - `merge_prev_week`: se il giorno preserve ha `outdoor_session_status == "done"` → copia l'intero giorno (`replanner_v1.py:589-594`).
   - `regenerate_preserving_completed`: stessa logica (`replanner_v1.py:692-695`).
   - I campi `outdoor_*` sono in `_DAY_LEVEL_FIELDS` e quindi preservati nel merge (`replanner_v1.py:620-621`, `:637-643`).

3. **Il log stesso è append/upsert per data:** lo storage è separato dal week plan, quindi rigenerazioni/cambi-device/cambi-equipment del piano **non toccano** la tabella `outdoor_logs`. L'unica via di modifica è l'edit esplicito utente (`PUT /api/outdoor/log`, che valida e rimpiazza per data).

> **Nota/gap:** l'immutabilità è verificata a livello di week-plan e di blocco-remove, ma NON esiste un guard che impedisca a un `PUT`/`update_outdoor_session` di modificare un log di una data passata — è progettato come "edit utente esplicito" (coerente con l'eccezione "pencil icon" del principio di immutabilità). Da confermare in design se l'edit di sessioni passate vada limitato.

---

## 6. Catalog pattern

### Esiste un catalogo outdoor?

**No.** `find backend/catalog -iname "*outdoor*"` → vuoto. Nessun pool `outdoor/*`. Outdoor non ha esercizi, template o sessioni catalogate, perché è trattato come "free day" senza prescrizione.

### Come sono catalogate le superfici/sessioni non-standard (precedenti utili)

Il precedente più vicino per "strategia/contenuto deterministico parametrizzato" è il sistema **free-session presets**:
- `GET /api/free-session/presets` restituisce preset per superficie con **grades personalizzati e phase tips** (`free_session.py` — preset con `duration_min/max`, tips di fase). È rule-based, deterministico, parametrizzato per superficie e fase. **Questo è il pattern naturale su cui modellare un catalogo deterministico di strategia/nutrizione outdoor.**
- Altri precedenti di contenuto deterministico parametrizzato: `phase-rationales.ts` (frontend), `backend/catalog/cues/v1/process_cues.json` (cues testuali catalogati). `process_cues.json` è l'unico file catalog che assomiglia a "consigli testuali deterministici".
- `body-part-picker` genera sessioni on-the-fly da catalogo esercizi senza persistenza (preview) — pattern utile per "genera suggerimento, opzionalmente persisti".

> **Implicazione:** un catalogo `outdoor/strategy_v1.json` + `outdoor/nutrition_v1.json` indicizzato per (day_type × wall_angle × length × style × phase) si innesterebbe pulito seguendo il pattern free-session presets / process_cues — JSON-data separato dalla logica, lookup deterministico, zero LLM. Nessuna struttura esistente va estesa: sarebbe additiva.

---

## Riepilogo dello stato attuale (un paragrafo)

Oggi "outdoor" è gestito come un **giorno-contenitore location-based** completamente fuori dal motore deterministico: il planner riconosce i giorni outdoor solo per **escluderli** (`day_is_outdoor` → nessuna sessione, non conta nel budget), non li genera mai dal macrociclo, e non li fa passare per resolve/progression/closed-loop. La rappresentazione è frammentata su tre livelli scollegati — flag/campi `outdoor_*` nel week plan, log dettagliato delle vie nella tabella dedicata `outdoor_logs` (JSONB `entry`, schema `outdoor.v1`), e un mirror parziale `state.outdoor_log[]` per il carico. Il log delle vie alimenta **solo** report e un **ripple di intensità immediato** (soglia load 65) nei giorni vicini, ma **non** chiude il loop sull'assessment/progressione. L'immutabilità delle sessioni passate è correttamente garantita (replanner blocca remove/override di outdoor done, la rigenerazione copia wholesale, lo storage è separato dal piano), con l'unica via di modifica l'edit utente esplicito. Esistono già le primitive riusabili per la feature: un `session-timer.tsx` generico, il pattern `started_at`→durata di `free_session.py`, contenitori opzionali `conditions`/`energy_level`/`overall_feeling` mai usati, e il pattern free-session-presets per cataloghi deterministici parametrizzati. Manca del tutto: catalogo outdoor, concetto di "day type"/caratteristiche progetto, cronometro outdoor, e qualunque suggerimento deterministico di strategia/nutrizione.

## Decisioni da prendere in fase di design

- **Dove vivono day-type + caratteristiche progetto (overhang/vertical/slab, short/long, power/endurance)?** Riusare il contenitore `conditions` JSONB già esistente nell'entry (zero migrazione) vs nuovi campi top-level vs estendere lo `spot` (`OutdoorSpotCreate`). I primi due sono per-sessione, lo spot è persistente.
- **Cronometro outdoor: stato server o solo client?** Riusare il pattern `started_at`/finish di `free_session.py` (durata calcolata server-side, coerente, ma richiede sessione "attiva" persistita) vs timer puramente client che precompila `duration_minutes` nel form attuale.
- **Sessione outdoor "attiva" come nuova entità?** Oggi outdoor è un log a posteriori. Una sessione con timer live + logging incrementale delle vie implica un concetto di "active outdoor session" (come `free_session` ha `started_at`/`log-climb`/`finish`). Decidere se outdoor diventa un sotto-caso di free-session o resta separato.
- **Catalogo strategia/nutrizione: granularità della chiave di lookup.** Quali assi indicizzano i suggerimenti (day_type × wall_angle × length × style × fase macrociclo × disciplina)? Modellare su free-session presets / `process_cues.json`.
- **Graceful degradation: regole di fallback.** Con input parziale (es. solo day_type, nessuna caratteristica progetto), quale suggerimento esce? Definire la gerarchia di default deterministici.
- **Il closed loop deve restare isolato?** Decidere se le vie outdoor (grade massimo mandato) debbano alimentare l'assessment/progressione, o restare puramente descrittive come oggi. Impatta i principi "closed-loop" e "deterministic".
- **Edit di sessioni passate.** Confermare se `PUT /api/outdoor/log` su date passate vada limitato o resta "edit esplicito utente" (eccezione pencil-icon).
- **Friction UX del form attuale.** `duration` default 120 hardcoded, nessun cronometro, 3 campi soft non esposti, spot senza caratteristiche: decidere cosa diventa progressive-disclosure vs cosa resta opzionale-nascosto.
- **Principio location-based vs equipment-based.** Il gating outdoor è oggi location-based (`preferred_location == "outdoor"`): confermare che resti l'eccezione accettata o se introdurre un marcatore equipment-based (es. `outdoor` come pseudo-equipment).
