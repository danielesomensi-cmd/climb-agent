# D278 — Code review

**Tipo:** D (review, read-only sul codice) · **Data:** 2026-08-17 · **Precedente:** [D254](D254_full_repo_review.md) (2026-07-20)

---

## Copertura — leggere questo prima dei finding

Dal 20 luglio il repo ha accumulato **419 commit, 320 file, +34.433 / −3.346 righe**.
Una lettura riga per riga di quel delta con una qualità utile non è una cosa che si fa in
una passata, e dichiarare il contrario renderebbe inutile anche la parte fatta bene.

Questa è quindi una review **mirata al rischio**, non una sweep uniforme. Ho ispezionato in
profondità le superfici dove un difetto costa di più:

| Superficie | Perché | Esito |
|---|---|---|
| Confine LLM (`coach/session_composer.py`) | è **l'unica eccezione delimitata** al principio «nessun LLM tocca il piano»: se cede, cede la garanzia centrale del prodotto | **1 finding Alto** |
| Guardia abbonamento su tutti gli endpoint di scrittura | fail-closed dichiarato, Stripe LIVE | 1 osservazione |
| Webhook Stripe | è il percorso del denaro | solido |
| Immutabilità delle sessioni passate | pilastro non negoziabile | guardie presenti e deliberate |
| Cache settimana lato client (`week-cache.ts`, nuovo) | l'invalidazione sbagliata mostra all'atleta un piano che non esiste | solido |

**Non coperto:** il catalogo esercizi (+2.003 righe, è dato non logica), la suite di test
(+~4.000 righe), l'engine di assessment (`assessment_v1.py` +432 righe — ma è il modulo più
testato del repo, 3 brief consecutivi con fixture sui 18 profili reali), e la maggior parte
del frontend, che [D254](D254_full_repo_review.md) aveva già esaminato a fondo un mese fa.

---

## F1 — Il pool del coach è troncato in silenzio, e in ordine alfabetico (ALTO)

`backend/coach/session_composer.py:234`

```python
    pool.sort(key=lambda e: str(e.get("id")))
    return pool[:MAX_POOL]          # MAX_POOL = 120
```

Il pool è la lista di esercizi che l'engine costruisce e dentro la quale il modello **può**
scegliere: è il meccanismo che rende sicura l'eccezione A259. Viene ordinato per `id` e poi
tagliato a 120.

**Il taglio morde, in tutte e tre le modalità.** Misurato sul catalogo reale (263 esercizi):

| Modalità | Ammissibili dopo i filtri P0 | Visibili al modello | **Invisibili** |
|---|---|---|---|
| `home` | 162 | 120 | **42** |
| `gym` (Work) | 139 | 120 | **19** |
| `bodyweight` | 162 | 120 | **42** |

Poiché il taglio segue l'ordinamento alfabetico, **non è un campione: è la coda
dell'alfabeto**, sempre la stessa. Esercizi che il coach non può proporre a casa, mai:

`side_plank`, `v_up`, `toes_to_bar`, `windshield_wipers`, `weighted_pullup`,
`wall_handstand_hold`, `treadmill_incline_walk`, `stationary_bike_zone2`,
`romanian_deadlift`, `scapular_pullup`, `split_squat`, `turkish_getup`, `wrist_curl`, …

**Tre conseguenze concrete:**

1. **Chiedere «core a casa» non può restituire il core.** `side_plank`, `v_up`,
   `toes_to_bar` e `windshield_wipers` stanno tutti oltre il taglio.
2. **C266 è stato in buona parte annullato senza che nessuno se ne accorgesse.** Quel brief
   ha aggiunto il cardio steady-state al catalogo proprio perché non c'era
   (`treadmill_incline_walk`, `stationary_bike_zone2`, `easy_run_zone2`): due dei tre
   cadono oltre il 120° posto, quindi «fammi del cardio» non può proporli.
3. `wall_handstand_hold` è invisibile in **entrambe** le modalità — ed è l'esercizio con
   cui l'autore chiude abitualmente le sedute.

**Ed è muto.** Il codice guarda il limite inferiore e non quello superiore:

```python
    if len(pool) < MIN_EXERCISES:
        logger.warning("composer: pool too small (%d) — falling back", len(pool))
```

Non esiste il ramo simmetrico. Nei log una composizione impoverita dal taglio è
indistinguibile da una composizione normale.

**Il contrasto che rende il difetto evidente:** lo stesso sottosistema, nello stesso mese,
ha fatto la cosa giusta. `prompt_builder.py:519` (B328) tronca le vie outdoor **e lo
dichiara**:

```python
        hidden = len(rendered) - len(shown)
        if hidden:
            climbs += f", (+{hidden} more routes not shown)"
```

La regola è già nota alla codebase; qui non è stata applicata.

**Perché non è un finding cosmetico.** Un pool troncato non produce un errore: produce una
sessione *plausibile e più povera*, che è esattamente il modo di sbagliare più difficile da
notare. E il fallback deterministico non scatta, perché il pool resta ben sopra
`MIN_EXERCISES`: il sistema si comporta come se fosse tutto a posto.

**Rimedio, con il costo misurato.** Il tetto esiste per contenere il prompt. Includere
**tutti** i 162 ammissibili costa **~1.300 token di input in più** (pool completo ≈ 5.080
token contro ≈ 3.800 di oggi) — trascurabile contro un `COACH_MAX_TOKENS` di 2.048 in
uscita e con il prompt caching attivo. Tre strade, in ordine di preferenza:

1. **Alzare `MAX_POOL` sopra il massimo ammissibile** (≥ 170). Un tetto che non si raggiunge
   mai smette di essere una politica implicita.
2. Se il tetto deve restare, **ordinare per pertinenza all'intent** (dominio / parte del
   corpo richiesta) prima di tagliare, invece che per `id`.
3. **In ogni caso, loggare il taglio** (`pool truncated: N of M`), come fa B328.

---

## F2 — `PUT /api/outdoor/log` non è gated ma scrive sul piano (BASSO)

`backend/api/routers/outdoor.py:258`

`POST /api/outdoor/log` porta `dependencies=[Depends(require_active_subscription)]`; `PUT`,
`DELETE /log/{date}` e i due endpoint su `/spots` no.

**Non è un bypass di creazione** — l'ho verificato: `update_outdoor_session` solleva
«No outdoor session found» → 404 se la data non esiste già, quindi con il PUT non si crea
nulla che il POST avrebbe rifiutato. E lasciare che un abbonamento scaduto possa
**modificare e cancellare** i propri dati è una politica difendibile, probabilmente voluta.

Quello che stona è un effetto collaterale: il PUT chiama `_sync_plan_after_outdoor_log`
(B277), che **muta il week plan** — marca il giorno `done`, scrive il carico, applica il
ripple. Quindi un utente senza abbonamento attivo, modificando un log esistente, provoca
comunque una scrittura sul piano, che è la risorsa che la guardia protegge.

Impatto pratico ridotto (serve un log preesistente, e il piano è comunque suo). Da decidere
esplicitamente più che da correggere di corsa: o la guardia va anche sul PUT, o si scrive
nel codice perché la modifica dei propri dati storici resta libera per progetto.

---

## Verificato solido (nessuna azione)

- **Validazione del composer** (`validate()`, righe 245-314). Fa tutto quello che il
  contratto di `CLAUDE.md` promette: appartenenza al pool obbligatoria, dedup, clamp su
  serie/rep/lavoro/riposo, scarto motivato in `dropped[]` invece di riparazione silenziosa,
  taglio sul budget di tempo dalla coda. **I carichi non arrivano mai dal modello**
  (`_decorate_engine_fields` li legge da `working_loads` e dall'ancora A253, e lascia `0`
  quando non sa) e neppure la lateralità (`alt_sides` dal catalogo, B324). Il fallback su
  `adhoc_builder` scatta sia con pool piccolo sia con troppe righe scartate.
- **`build_pool`**: filtri P0 tutti presenti e nell'ordine giusto — esclusioni dell'utente,
  `_is_active`, `_is_spine_safe`, compatibilità equipaggiamento, e i test esclusi dal pool
  (un protocollo di misura non è un esercizio da infilare in una seduta ad hoc).
- **Webhook Stripe**: dedup LRU su `event.id` (1024), eccezioni che risalgono come 500 così
  Stripe ritenta, alert fondatore in fire-and-forget che non può far fallire la risposta.
- **Immutabilità**: guardie esplicite e commentate in `replanner_v1.py` (merge dei giorni
  passati dal piano precedente, rifiuto di eventi su giorni chiusi).
- **`week-cache.ts`**: gestisce il doppio alias `week(0)` / `week(N)` con la cautela giusta —
  rispecchia solo se l'altra entry esiste già, per non inventare una settimana che nessuno
  ha caricato.
- **Guardia abbonamento**: nessun endpoint di scrittura risulta scoperto per errore. Gli
  scoperti sono tutti deliberati (onboarding, checkout, assessment pubblico, admin con
  chiave propria, editing dello stato, tips/milestones cosmetici).

---

## Raccomandazione

**F1 merita un brief B a sé** — è un difetto di correttezza su una feature dichiarata come
l'eccezione controllata al principio deterministico, ha una riparazione da poche righe e un
costo misurato. F2 è una decisione di prodotto da mettere per iscritto, non un'urgenza.
