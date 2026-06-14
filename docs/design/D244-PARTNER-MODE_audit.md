# D244 — Design Audit: Partner Training Mode + Surface Preference + Extensible Modifier Architecture

> **Tipo**: D (design audit, read-only) · **Brief ID**: D244
> **Origin**: Daniele 2026-05-21 (pain point: scalare in coppia con Sandra) · predecessore A219
> **Stato**: ✅ Completo (Phase 1-6). Decisioni D-PARTNER-03/05/11 confermate da Daniele 2026-06-14.
> **No code changes**: solo questo documento + ROADMAP/CLAUDE update

---

## §0 — Findings di Phase 1: divergenze dalle assunzioni del brief

L'audit del codebase ha rivelato che **diverse assunzioni del brief originale sono superate dallo stato attuale del codice**. Questo è il valore principale dell'audit: senza, le implementazioni sarebbero partite su premesse sbagliate.

### F1 — La "Surface Preference" esiste GIÀ (A210 "Boulder only")

Il brief tratta `prefer_routes` / `prefer_boulder` come feature nuova. In realtà **A210 ha già implementato il forcing di superficie** (direzione boulder), end-to-end:

- **Backend**: `resolve_session(..., equipment_override=[...])` (`resolve_session.py:1373-1377`) ri-risolve la stessa sessione rimuovendo `gym_routes`. Esposto via `/api/session/resolve` (`routers/session.py:78`).
- **Frontend**: stato effimero in `session-card.tsx:706-842` — banner ambra + badge "Boulder only" + pulsante Undo. Due meccanismi: (A) se la sessione ha `boulder_fallback`, swap alla sessione boulder dedicata; (B) altrimenti `equipment_override` che strippa `gym_routes`.
- **Catalog**: `boulder_fallback` già presente su 12 sessioni (mappa route→boulder: `route_endurance_gym→boulder_circuit_gym`, `route_projecting_gym→limit_boulder_gym`, `endurance_aerobic_gym→boulder_circuit_gym`).

➡️ **Conseguenza**: il Surface Preference Modifier **non è greenfield**. È: (1) generalizzare A210 alla direzione opposta (`prefer_routes`), (2) opzionalmente persisterlo come modifier (oggi A210 è volutamente effimero, mai persistito). L'effort del brief #7 (A-SURFACE-PREF) scende da S a XS-S.

### F2 — Gli esercizi NON hanno un campo `surfaces`

Il brief (Phase 3.3 / 4.1) assume `exercises[].surfaces: [gym_routes|gym_boulder]`. **Non esiste.** La superficie è modellata come equipment:

- **Esercizio**: `equipment_required` (hard, subset) + `equipment_required_any` (hard, intersection). Valori superficie: `gym_routes` (7 hard + 9 any), `gym_boulder` (1 hard + 32 any), `spraywall`, `board_*`, `homewall`.
- **Sessione**: `required_equipment: [gym_routes|gym_boulder|...]` (30/35 sessioni) + filtro soft block-level in `pick_best_exercise_p0` Stage 2b (`resolve_session.py:411-417`).

➡️ **Conseguenza**: il catalog enrichment per surface pref (brief Phase 4.1, campo `surfaces`) è **non necessario** — i dati esistono già come equipment. La surface pref si implementa via `equipment_override` (riuso A210), NON via un nuovo campo né via "bias +30% score" (il resolver filtra, non scora, per superficie).

### F3 — Non esiste `user_state.schema.json`

`user_state` è JSON schemaless (nessun file di schema in `backend/data/`). Aggiungere `session.modifiers: []` **non richiede migration** — è additivo e i consumer leggono con `.get()`.

➡️ **Conseguenza**: il brief #4 (B-MODIFIER-SCHEMA) si riduce a "documentare la convenzione + eventuale default `[]` nei punti di scrittura". Effort XS → quasi no-op. Possibile assorbirlo dentro A-MODIFIER-CORE.

### F4 — UX: nessun menu 3-dot; esiste un edit Drawer

Il brief D-PARTNER-10 raccomanda un "menu contestuale 3-dot". **Non esiste.** Le azioni sessione vivono in un **Drawer (bottom sheet)** aperto dall'icona matita su `session-card.tsx:1217-1326`, con voci: Add exercise, Modify session (Replan), **Boulder only (today)** (A210), Move, Remove, Undo.

➡️ **Conseguenza**: i toggle modifier vanno **nello stesso Drawer**, accanto a "Boulder only (today)" — riuso del pattern già familiare all'utente. D-PARTNER-10 va riscritta.

### F5 — A210 applica SENZA preview (apply + undo)

Il brief D-PARTNER-11 raccomanda "preview sempre". Ma il precedente shippato (A210) **non fa preview**: applica direttamente, mostra banner + Undo. `replan-dialog.tsx` non ha step before/after.

➡️ **Conseguenza**: c'è una tensione reale tra "preview always" (brief) e "apply+undo" (pattern esistente). Vedi decisione D-PARTNER-11 rivista.

### F6 — `injured` overlappa col sistema limitations esistente

Il brief (D-PARTNER-12) elenca `injured_<body_part>` tra i modifier futuri. Ma esiste già `normalize_limitations()` + `limitation_map` + filtro contraindications (`resolve_session.py:270-563`): zone elbow/finger/shoulder/wrist con severità monitor/active/severe. `injured` come modifier sarebbe un override temporaneo sopra questo sistema, non greenfield.

### F7 — Numeri reali (vs brief)

| Brief dice | Reale |
|---|---|
| 218 esercizi | **225** esercizi (`exercises.json`, `version 2.1`) |
| 35 sessioni | 35 in `_SESSION_META`, 36 file (1 = `_archive`) |
| `partner_compatibility` ~30-50 solo_only | da mappare in C-brief; nessun flag partner esiste oggi |

---

## §1 — Hook points (dove agganciare i modifier)

| # | Hook | File · funzione/linea | Modifier-aware oggi? | Note di aggancio |
|---|------|----------------------|---------------------|------------------|
| H1 | Resolver — P0 filter superficie | `resolve_session.py:411-417` (Stage 2b `required_equipment` soft) | NO (ma c'è `equipment_override` a riga 1373-1377) | Surface pref → **riusa `equipment_override`**, non toccare lo scoring. Già il punto più pronto. |
| H2 | Resolver — selezione esercizio | `pick_best_exercise_p0` (`resolve_session.py:351`) | NO | Per partner mode L1 NON serve toccarlo (si swappa la sessione, non gli esercizi). Per L2 (futuro) qui si aggiungerebbe filtro `partner_compatibility`. |
| H3 | Replanner — trasformazione giorno | `apply_day_override` (`replanner_v1.py:1458`) | NO | Partner mode = nuovo tipo di trasformazione. Ortogonale all'intent (vedi D-PARTNER-04). Possibile nuovo `apply_modifier` separato anziché estendere override. |
| H4 | Replanner — intent map | `INTENT_TO_SESSION` (`replanner_v1.py:84`) | N/A | **NON** aggiungere `partner_mode` qui — gli intent sono "cosa fai", i modifier "come". Conferma D-PARTNER-04. |
| H5 | Catalog — surface fallback sessione | `boulder_fallback` su 12 sessioni | PARZIALE | Già mappa route→boulder. Substrato per partner mode su sessioni route. Eventuale `partner_variant_id` per casi non coperti. |
| H6 | Catalog — compatibilità partner esercizio | `exercises.json` schema | NO | Nuovo campo `partner_compatibility: parallel|rotation|solo_only` (C-brief). Serve solo per L2/badge, non per L1. |
| H7 | User state — modifier persistiti | `week_plans[wk].weeks[].days[].sessions[]` | NO | Nuovo campo `session.modifiers: []`. **Nessuna migration** (F3). Snapshot reversibilità in `session.pre_modifier_snapshot`. |
| H8 | Immutabilità — guard done/skipped | già presente ovunque (`status in ("done","skipped")`) | SÌ | I modifier DEVONO riusare lo stesso guard. Vedi vincolo immutabilità. |
| H9 | Closed-loop | sessioni `is_custom`/`custom_build` skippano progression | PARZIALE | Se partner mode swappa a sessione diversa, decidere se feedback alimenta progression (vedi nota §2 D-PARTNER-05). |
| H10 | FE — toggle modifier | edit Drawer `session-card.tsx:1217-1326` | PARZIALE (A210 lì dentro) | Aggiungere voci accanto a "Boulder only (today)". |
| H11 | FE — banner/badge stato | `session-card.tsx:824-842` (banner) + `866-871` (badge) | SÌ (per boulder) | Generalizzare il pattern banner+badge+undo già esistente. |
| H12 | FE — preview (se scelto) | `replan-dialog.tsx` (oggi senza preview) | NO | Net-new se D-PARTNER-11 sceglie preview. |
| H13 | FE — pill su session detail | `session/[id]/page.tsx:60-66` + `top-bar.tsx` | NO | Aggiungere slot pill/rightContent al TopBar. |

**Decisione architetturale confermata**: i modifier sono **ortogonali agli intent**. L'intent definisce *quale* sessione (→ `session_id`); il modifier *trasforma* quella sessione (swap o ri-resolve). Mescolarli in `INTENT_TO_SESSION` porterebbe a esplosione combinatoria (15 intent × N modifier). Il campo `session.modifiers: []` è additivo e componibile.

---

## §2 — Decisioni di design (tabella ufficiale, raccomandazioni RIVISTE post-findings)

> ⚠️ Raccomandazioni in **grassetto** dove i findings di §0 hanno modificato la proposta del brief originale.

| ID | Domanda | Raccomandazione (rivista) | Rationale |
|----|---------|---------------------------|-----------|
| **D-PARTNER-01** | Granularità durata | (a) one-shot su singola sessione [MVP] + (b) flag settimanale [post-MVP] | Invariato dal brief. Caso 80% = "oggi scalo con Sandra". |
| **D-PARTNER-02** | Livelli trasformazione | L1 (swap sessione) in MVP; L2 (hint rotation/parallel per esercizio) v2; L3 (ricalcolo rest belay) mai | Invariato. L1 risolve il pain point con riuso `boulder_fallback`. |
| **D-PARTNER-03** | Scope Surface Pref | (b) modifier indipendente, **generalizzazione di A210, non greenfield**. ✅ **DECISA: effimero** (vedi D-PARTNER-05) | F1: A210 fa già boulder-forcing. Surface pref = aggiungere `prefer_routes`, riusando il pattern effimero A210. |
| **D-PARTNER-04** | Architettura | (b) **modifier ortogonale** (`session.modifiers: []`) | Confermato da H3/H4: intent=cosa, modifier=come. Decisione cardine. |
| **D-PARTNER-05** | Persistenza | ✅ **DECISA (Daniele 2026-06-14)**: snapshot persistente per **partner mode**; **surface pref EFFIMERO come A210** (solo-FE, no persistenza) | Partner mode cambia molto la sessione e deve sopravvivere a regen → persiste in `session.modifiers`. Surface pref resta leggero/effimero come A210 (meno codice, coerente con shippato). |
| **D-PARTNER-06** | Reversibilità | (a) sì sempre. Partner mode: `pre_modifier_snapshot`. Surface pred: Undo come A210 | ~1KB/sessione. `past_sessions_immutable` già protegge le done. |
| **D-PARTNER-07** | Sessioni full-solo (hangboard puro) | (b) modifier disponibile + helper text | Rest naturali 2-3 min → partner fa il suo. Non penalizzare. |
| **D-PARTNER-08** | Outdoor partner mode | (b) diverso, **fuori scope MVP** | Outdoor in coppia è già nativo (lead alternato). Documentare per v2. |
| **D-PARTNER-09** | Mappa fase→trasformazione | Vedi §3.2 (post-OK). Substrato: `boulder_fallback` esistente | Da letteratura + discussione 2026-05-20. |
| **D-PARTNER-10** | UX: dove vive il toggle | **(rivista) edit Drawer esistente** (`session-card.tsx:1217-1326`), accanto a "Boulder only (today)" | F4: non esiste menu 3-dot. Riuso pattern Drawer già familiare. |
| **D-PARTNER-11** | UX: preview prima di applicare | ✅ **DECISA (Daniele 2026-06-14)**: preview SOLO per partner mode; surface pref usa apply+undo stile A210 | F5: A210 non fa preview e funziona. Preview giustificato solo dove la trasformazione è significativa (ARC→boulder volume). |
| **D-PARTNER-12** | Modifier futuri | Documentare `energy_low`, `time_constrained_X`, `weather_bad`. **`injured` = override sopra il sistema limitations esistente (F6), non greenfield** | Tutti riducibili a "filtro esercizi + trasformazione sessione". `injured` riusa `limitation_map`. |

### Note estese sulle decisioni che cambiano per i findings

**D-PARTNER-03 + D-PARTNER-05 (Surface Pref):** la scelta vera che ti chiedo è: il surface preference deve **persistere** (diventare un `session.modifiers` salvato, sopravvive a regen) o restare **effimero come A210** (solo per la visualizzazione di oggi, si perde a refresh)? Il brief assumeva persistente. A210 ha scelto effimero di proposito. Persistere ha senso se vuoi "questa settimana preferisco corda" come stato stabile; effimero basta se è solo "oggi mostrami la versione boulder".

**D-PARTNER-11 (Preview):** la scelta vera è se uniformare a "preview sempre" (più lavoro FE net-new, H12) oppure adottare il pattern A210 già shippato (apply+undo) per il surface pref e tenere il preview solo per il partner mode. Io raccomando il secondo (meno codice, coerente con ciò che già esiste).

**D-PARTNER-04 (Architettura):** è la decisione che, se cambi idea, fa rifare tutto il resto (come nota il brief). Confermo fortemente `modifier ortogonale`: il codice mostra che gli intent sono già un mapping rigido intent→session_id e che `equipment_override` è già un "modificatore" applicato a valle del resolve. Un modifier system è l'astrazione naturale di ciò che A210 ha fatto ad-hoc.

---

## §3 — Spec architettura modifier (estendibile)

### 3.1 Modifier schema generico

I modifier sono ortogonali agli intent (D-PARTNER-04). **Solo i modifier persistenti** (partner mode) vivono in `session.modifiers`; i modifier effimeri (surface pref) restano stato frontend come oggi A210.

```jsonc
// session.modifiers: ModifierSpec[]  — SOLO per modifier persistenti (partner_mode)
{
  "type": "partner_mode",          // ModifierType
  "params": { "partner_level": "similar" },   // opzionale, type-specific
  "applied_at": "2026-06-14T18:30:00",
  "pre_modifier_snapshot": { /* sessione pre-trasformazione, per Undo (D-PARTNER-06) */ }
}
```

```typescript
type ModifierType =
  | "partner_mode"      // PERSISTENTE → session.modifiers
  // Surface pref: EFFIMERO (D-PARTNER-05), NON entra in session.modifiers.
  //   Resta stato FE come A210 (equipment_override / boulder_fallback swap).
  //   "prefer_boulder" = A210 attuale; "prefer_routes" = direzione nuova da aggiungere.
  // --- Placeholders v2 (NON implementati ora) ---
  | "energy_low"
  | "time_constrained"      // params: { minutes: number }
  | "weather_bad"           // nasconde outdoor
  | "injured";              // override sopra limitation_map esistente (F6)
```

**Regola di estendibilità**: ogni modifier futuro si riduce a una di queste due primitive, entrambe già presenti nel codice:
1. **Ri-resolve con vincolo equipment** (`equipment_override` — A210) → surface pref, time-constrained (sottinsieme moduli).
2. **Swap sessione** (`boulder_fallback` / `partner_variant_id`) → partner mode, energy_low (→ deload variant).

Un terzo livello (filtro esercizi `partner_compatibility` / `injured` su `limitation_map`) è opzionale e riservato a L2/v2.

### 3.2 Mappa fase → trasformazione partner mode (D-PARTNER-09)

L1 = swap sessione. Dove esiste `boulder_fallback` (H5) lo si riusa; altrimenti `partner_variant_id` nuovo o "nessuna trasformazione" (sessione già partner-friendly).

| Fase | Sessione tipica | Trasformazione partner (L1) | Meccanismo | Rationale |
|------|-----------------|-----------------------------|------------|-----------|
| **Base / ARC** | `route_endurance_gym`, `endurance_aerobic_gym` | → `boulder_circuit_gym` (volume in parallelo) | **`boulder_fallback` esistente** | ARC continuativo 25-40 min ostico in coppia; boulder volume mantiene stimolo aerobico parallelizzabile. |
| **Strength & Power (finger)** | `strength_long`, `finger_*`, hangboard | → **invariato** (rest 2-3 min coprono rotation) | nessuna | Stimolo strength è solo, partner-compatible nativamente. Helper text: "partner fa il suo durante i rest". |
| **Strength & Power (climb)** | `limit_boulder_gym`, `power_contact_gym` | → **invariato**, rotation esplicita (uno scala/uno spotta) | nessuna | Boulder limit è già rotation-based. |
| **Power Endurance (boulder)** | `power_endurance_gym` | → **invariato**, 4×4 alternato sullo stesso problema | nessuna (helper text) | Rest 4 min tra round → rotation perfetta. |
| **Power Endurance (route)** | `route_endurance_gym` (PE module) | → `boulder_circuit_gym` se vie troppo lunghe | `boulder_fallback` | TR alternato funziona solo se vie brevi; altrimenti boulder. |
| **Performance** | `route_projecting_gym`, `route_redpoint` | → **invariato** (lead/TR alternato è nativo) | nessuna | Performance lead è ideale in coppia. |
| **Tecnica** | `technique_focus_gym` | → **invariato**, drills paralleli + coaching reciproco | nessuna (helper text) | Drills = solo movimento, parallelizzabili al 100%. |
| **Deload** | `deload_recovery`, `regeneration_easy`, `yoga_recovery` | → **invariato**, mobility parallela | nessuna | Low-intensity, già parallelizzabile. |

➡️ **Conclusione chiave**: per la maggioranza delle fasi la trasformazione L1 è **"nessuna" + helper text** (la sessione è già partner-friendly). Lo swap reale serve quasi solo per ARC/endurance route, e lì **`boulder_fallback` esiste già**. Questo riduce drasticamente lo scope catalog (vedi §4).

### 3.3 Surface preference (EFFIMERO — riuso A210)

| Modifier | Effetto | Meccanismo (esistente) |
|----------|---------|------------------------|
| `prefer_boulder` | sessione route → boulder | **già A210**: `boulder_fallback` swap, oppure `equipment_override` strip `gym_routes` |
| `prefer_routes` | sessione boulder → route (NUOVO) | speculare: `equipment_override` strip `gym_boulder`/board surfaces, oppure nuovo `routes_fallback` su sessioni boulder |

**Vincoli (non-negoziabili)**:
- NON bypassa il P0 filter su `required_equipment` reale: `prefer_routes` su utente senza `gym_routes` → **no-op silenzioso** con warning UX ("la tua palestra non ha vie").
- NON è uno scoring bias (+30%): il resolver **filtra** per superficie (Stage 2/2b), non scora. Si forza via `equipment_override`.
- `prefer_routes` richiede di mappare un `routes_fallback` solo se vogliamo lo swap a sessione dedicata; altrimenti basta `equipment_override` che fa ri-risolvere la stessa sessione su esercizi route-compatibili.

---

## §4 — Spec catalog enrichment (RIDOTTA dai findings)

### 4.1 Exercises — `partner_compatibility` (C-brief, solo per L2/badge)

Campo nuovo, **NON necessario per L1** (L1 swappa la sessione, non filtra esercizi). Serve solo se/quando si fa L2 (hint per-esercizio) o si vuole greyare il toggle su sessioni full-solo (D-PARTNER-07).

```jsonc
{ "id": "max_hang_7s", "partner_compatibility": "rotation" }  // parallel | rotation | solo_only
```

Distribution attesa su 225 esercizi: ~60% `parallel` (mobility, core, drills, easy boulder), ~30% `rotation` (hangboard, weighted pullup, limit boulder, 4×4), ~10% `solo_only` (campus max, finger overload).

➡️ **Declassato a opzionale/post-MVP.** Non è prerequisito di A-PARTNER-MODE L1.

### 4.2 Sessions — `partner_variant_id` (solo dove `boulder_fallback` non basta)

Dalla mappa §3.2, le uniche trasformazioni reali sono ARC/endurance route → boulder, **già coperte da `boulder_fallback`**. Quindi `partner_variant_id` serve solo se vogliamo varianti *dedicate* al partner (es. `arc_intervals_partner` con belay rotation strutturata) diverse dal semplice fallback boulder.

➡️ **Opzionale.** MVP può usare solo `boulder_fallback` + "nessuna trasformazione + helper text".

### 4.3 Nuove session (C-brief, opzionale)

| Session ID | Necessità |
|-----------|-----------|
| `arc_intervals_partner` | OPZIONALE — solo se la trasformazione "ARC → boulder_circuit" non soddisfa; variante con 2 blocchi 15 min + belay rotation. |
| `boulder_volume_circuit_easy_partner` | OPZIONALE — `boulder_circuit_gym` con flag parallel + selettore grado per mismatch di livello partner. |

### 4.4 Surface pref — catalog enrichment: **NON necessario** (F2)

I dati superficie esistono già come `equipment_required`/`required_equipment`. Nessun campo `surfaces` da aggiungere. Eventuale `routes_fallback` su sessioni boulder solo se si sceglie lo swap a sessione dedicata invece di `equipment_override`.

---

## §5 — Spec UX

### 5.1 Punti di interazione (riuso pattern A210)

**Edit Drawer** (`session-card.tsx:1217-1326`) — accanto a "Boulder only (today)" (A210):
- Nuova voce **"Partner mode"** (toggle) → se preview attiva (D-PARTNER-11), apre modal anteprima; altrimenti applica + banner + undo.
- Surface pref: **estendere** il toggle A210 esistente da mono-direzione ("Boulder only") a bi-direzione ("Boulder only" / "Routes only") quando la palestra ha entrambe le superfici. Nessun nuovo entry point — si riusa lo stesso bottone/pattern.

**Banner + badge** (`session-card.tsx:824-842` + `866-871`):
- Generalizzare il banner ambra esistente: "Partner mode — sessione adattata" / "Boulder only" / "Routes only".
- Badge in card header (icona: 2 omini per partner, corda/montagna per surface).
- Undo sempre presente quando un modifier è attivo.

**Session detail header** (`session/[id]/page.tsx:60-66` + `top-bar.tsx`):
- Aggiungere slot `rightContent`/`pills` al `TopBar` → pill "Partner mode" + "Ripristina originale".

### 5.2 Modal preview — SOLO partner mode (D-PARTNER-11)

```
┌─────────────────────────────────────────┐
│ Partner mode — "ARC Endurance"          │
├─────────────────────────────────────────┤
│ Anteprima trasformazione:               │
│  PRIMA:                  DOPO:           │
│  ARC 30 min continuo  →  Boulder volume  │
│  downclimb 6a            circuit 6a/6b   │
│                          15-20 problemi  │
│  Esercizi: 4 → 6        Durata: ~ stessa │
├─────────────────────────────────────────┤
│ [Annulla]              [Applica]        │
└─────────────────────────────────────────┘
```

Per le fasi con trasformazione "nessuna" (§3.2), il modal mostra invece l'helper text ("Questa sessione è già adatta alla coppia: alternatevi durante i rest") senza before/after.

Surface pref: **nessun modal** — apply diretto + banner + undo (come A210 oggi).

### 5.3 Indicatori visivi

- Badge "Partner" (2 omini) / "Boulder only" / "Routes only".
- Tooltip al tap: spiega cosa fa il modifier.
- Toggle greyed + helper se non applicabile (es. surface pref su palestra mono-superficie; partner mode su sessione full-solo → mostra comunque con helper, D-PARTNER-07).

### 5.4 Vincolo immutabilità (H8, non-negoziabile)

Il toggle modifier è disponibile SOLO per sessioni con `status not in ("done","skipped")` e `date >= today`. Riusa lo stesso guard già presente in `apply_day_override`/`apply_events`. Da testare esplicitamente in A-PARTNER-MODE.

---

## §6 — Piano brief successivi (RIVISTO dai findings)

### Brief seriali

| # | Brief ID | Tipo | Effort (rivisto) | Dipende da | Note |
|---|----------|------|------------------|-----------|------|
| 1 | `C-PARTNER-CATALOG` | C | S (era M) | — | `partner_compatibility` su 225 esercizi. **Declassato a OPZIONALE/post-MVP** — non serve per L1. |
| 2 | `B-MODIFIER-SCHEMA` | B | XS→quasi no-op | — | `session.modifiers: []` convenzione. **Nessuna migration** (F3). Possibile assorbire in #4. |
| 3 | `A-MODIFIER-CORE` | A | S-M (era M) | #2 | **HIGH RISK** (`replanner_v1.py`): nuovo `apply_modifier`/estensione + reversibilità snapshot. **Mandatory analysis + STOP gate.** `resolve_session.py` NON serve toccarlo per L1 (riusa `equipment_override` + swap). Suggerisci `/model opus` per Phase 1. |
| 4 | `A-SURFACE-PREF` | A | XS-S (era S) | parz. #3 | **Generalizza A210**: aggiunge `prefer_routes`, estende toggle FE bi-direzionale. EFFIMERO (no persistenza). Frontend branch + Vercel preview obbligatori. Quasi indipendente da #3 (riusa A210). |
| 5 | `A-PARTNER-MODE` | A | M | #3 | Partner mode L1 via modifier system: swap `boulder_fallback`/helper-text per fase (§3.2), preview modal, banner/badge/undo, persistenza + immutabilità. Frontend branch + preview obbligatori. |

**Cambiamenti vs piano brief originale (7 brief → 5):**
- Eliminati `C-PARTNER-CATALOG-02/03` (nuove session + `partner_variant_id`): coperti da `boulder_fallback` esistente, opzionali.
- `A-SURFACE-PREF` non dipende più da un core greenfield: riusa A210 → può andare anche prima/parallelo.
- `A-MODIFIER-CORE` non tocca `resolve_session.py` per L1 (riduce rischio).

**Ordine consigliato**: #4 (A-SURFACE-PREF, valore rapido riusando A210) → #3 (A-MODIFIER-CORE) → #5 (A-PARTNER-MODE). #1/#2 opzionali/assorbiti.

### Brief opzionali (v2)

- `A-MODIFIER-ENERGY` (`energy_low` → swap a deload variant)
- `A-MODIFIER-TIME` (`time_constrained_X` → ri-resolve con sottoinsieme moduli)
- `A-MODIFIER-INJURY` (`injured_<zone>` → override su `limitation_map` esistente, F6)
- `A-PARTNER-MODE-L2` (hint rotation/parallel per esercizio — richiede `partner_compatibility` di #1)
- `A-PARTNER-OUTDOOR` (D-PARTNER-08)

### STOP gate ricordati per i brief implementativi

`A-MODIFIER-CORE` (#3) tocca `replanner_v1.py` → **mandatory analysis phase + STOP** prima dell'implementazione (CLAUDE.md). `A-PARTNER-MODE` (#5) e `A-SURFACE-PREF` (#4) toccano `frontend/` → **branch `brief/...` + Vercel preview + OK Daniele** prima del merge.

---

## §7 — Blockers e prerequisiti

Nessun blocker tecnico hard. Note:

- **B-MODIFIER-SCHEMA quasi no-op** (F3): nessuno schema da migrare. Valutare se assorbirlo in A-MODIFIER-CORE.
- **Closed-loop + session swap** (H9): se partner mode swappa la sessione (es. ARC route → boulder volume), il feedback alimenta `progression_v1` sulla sessione *nuova* o no? Le custom/generated bypassano progression. Decisione da prendere in A-PARTNER-MODE — documentata qui come prerequisito.
- **Determinismo**: ogni trasformazione modifier deve restare deterministica (stesso stato+input → stesso output). Lo swap via `boulder_fallback` lo è; un'eventuale selezione "miglior surrogato" va resa deterministica (tie-break su id).
