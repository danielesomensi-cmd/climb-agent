# A258 — Pool di fase condizionato al profilo (Fase 1: analisi)

> **Tipo:** A (feature) · **Origine:** [[D263]] punto 4, severità CRITICO dal KB · **Modulo:** `macrocycle_v1.py` (⚠️ lista STOP di CLAUDE.md)
>
> ⛔ **FASE 1 — ANALISI. Nessuna riga scritta. Serve OK esplicito di Daniele prima della Fase 2.**

---

## 1. Il difetto

**I pesi di dominio si adattano al profilo, l'appartenenza al pool di sessioni no.** Uno scalatore con `pulling_strength` a 20/100 riceve **la stessa dose quasi nulla** di Daniele che è a 100/100. È il difetto più grave isolato da [[D263]]: il sistema non risponde al profilo proprio dove servirebbe di più.

Sintomo concreto: `pulling_strength_gym` — l'unica sessione con tre blocchi dedicati (trazione zavorrata, bloccaggio, typewriter) — non è nel pool di **nessuna** fase, per nessun profilo.

## 2. Perché il fix è architetturalmente naturale

Le due funzioni sono **già affiancate**, nella stessa funzione, con il profilo già in scope — `macrocycle_v1.py:625-627`:

```python
base_weights   = weights_map[phase_id]
domain_weights = _adjust_domain_weights(base_weights, assessment_profile)   # ← profilo GIÀ usato
session_pool   = _build_session_pool(phase_id, discipline=discipline)       # ← profilo IGNORATO
```

La modifica è **simmetrica a qualcosa che il progetto fa già**: passare `assessment_profile` anche alla seconda. Nessuna nuova fonte di verità, nessun nuovo stato.

## 3. Il fatto architetturale decisivo: il pool è congelato

`generate_macrocycle` **memorizza** il pool dentro la fase (`phase["session_pool"] = session_pool`, riga 644), e `api/deps.py:581` lo rilegge da lì (`phase.get("session_pool", [])`) invece di ricalcolarlo.

Tre conseguenze, tutte da mettere in chiaro **prima** di decidere:

1. **Nessuna mutazione retroattiva.** I macrocicli già generati conservano il loro pool: la modifica vale solo per i **nuovi** cicli (o dopo una rigenerazione esplicita). Ottimo per l'immutabilità, ma significa che **Daniele non vedrà nulla cambiare** finché non inizia un ciclo nuovo (il suo finisce il 2026-08-09).
2. **Il pool non segue il profilo che cambia.** Se la tirata di un utente migliora a metà ciclo, il pool resta quello scelto alla generazione. È **esattamente il comportamento attuale di `domain_weights`**, quindi coerente col progetto — ma va detto, non scoperto dopo.
3. **La soglia va valutata su un dato che oggi si perde.** Il punteggio d'asse **satura a 100** ed è **relativo all'obiettivo**: Daniele è a 1.01× il benchmark 8a+ (grezzo 100.6). Una regola «attiva se asse < 50» funziona per il caso debole, ma il clamp impedisce di distinguere "esattamente al requisito" da "ampiamente oltre". Se in futuro servirà un **pavimento di mantenimento** (raccomandazione 3a del KB), andrà costruito sul **ratio grezzo**, che è disponibile in `baselines.pulling.pulling_ratio_pct`, non sul punteggio clampato.

## 4. Cosa cambierebbe

- `_build_session_pool(phase_id, discipline, assessment_profile=None)` — parametro **opzionale**, default `None` = comportamento identico a oggi (i ~25 file di test che la chiamano senza profilo restano validi).
- Regola condizionale, secondo la risposta del KB: `pulling_strength_gym` entra nel pool **se** `assessment_profile["pulling_strength"] < 50` **e** `phase_id in ("base", "strength_power")`.
- **"In sostituzione, non in aggiunta"**: il KB è esplicito. Entra come `available`, non `primary`, così compete per uno slot invece di aggiungersi al carico. Da verificare in Fase 3 che il conteggio di giorni duri non salga.

**Sulla capienza settimanale.** Il KB assumeva 3-4 giorni allenabili e tetto 2; Daniele ne ha **7 e 4**. La condizione dovrebbe quindi includere anche la capienza reale — ma `_build_session_pool` **non conosce** l'availability dell'utente, che vive nel planner. Due opzioni:
- (i) condizione solo sul profilo qui, e lasciare al planner il compito di non sforare il tetto (che già fa);
- (ii) passare anche la capienza, allargando la firma.
**Propendo per (i)**: il tetto giorni duri è già rispettato a valle, e caricare `_build_session_pool` di conoscenza sull'availability le farebbe fare due lavori.

## 5. Superficie d'impatto

**Call site di produzione (5):**

| chiamante | effetto della modifica |
|---|---|
| `macrocycle_v1.py:627` (in `generate_macrocycle`) | **il punto della modifica** — profilo in scope |
| `replanner_v1.py:250` | fallback quando `session_pool` è None → resterebbe senza profilo |
| `replanner_v1.py:1364` | rigenerazione dopo replan → **ha accesso al profilo?** da verificare |
| `api/routers/replanner.py:304` | override → idem |
| `planner_v2.py:28` | solo import |

⚠️ **Punto di attenzione — VERIFICATO, ed è un problema reale.** `replanner_v1.py:1364` (percorso `set_availability`) legge i `domain_weights` dallo **snapshot** ma **ricostruisce il pool da zero** con solo `phase_id + discipline`:

```python
domain_weights = snapshot.get("domain_weights", base_weights)   # ← dallo snapshot
session_pool   = _build_session_pool(phase_id, discipline=discipline)  # ← ricostruito
```

E il `profile_snapshot` salvato nei week_plans **non contiene il profilo d'assessment** — solo `phase_id, intensity_cap, domain_weights, allowed_locations, hard_cap_per_week, recovery_multiplier` (verificato sui piani reali di Daniele).

**Conseguenza se non gestito:** un utente con tirata debole genera il ciclo e ottiene `pulling_strength_gym` nel pool; poi modifica la disponibilità → il replanner ricostruisce il pool **senza profilo** → la sessione **sparisce** dal piano rigenerato. Incoerenza silenziosa fra piano generato e replanificato.

**Soluzione raccomandata: memorizzare il pool in `profile_snapshot`** — vedi §7.3 per la motivazione completa e per l'opzione che ho dovuto scartare dopo la verifica (leggere dalla fase del macrociclo **non è praticabile**: `apply_events` non riceve né `user_state` né macrociclo).

**Test:** ~25 file chiamano `_build_session_pool`. Con il parametro opzionale e default `None` dovrebbero restare tutti verdi; i più esposti sono `test_macrocycle_v1.py`, `test_discipline_all_round.py`, `test_macrocycle_boulder.py`, `test_b287_replanner_immutability.py`.

## 6. Invarianti da preservare (verifica obbligatoria in Fase 3)

- **Sessioni passate immutabili**: il pool cambia solo per cicli nuovi. Da testare che rigenerare un macrociclo con `from_phase="current"` non tocchi le settimane concluse.
- **`from_phase="current"`**: CLAUDE.md lo segnala esplicitamente per ogni funzione che chiama `generate_macrocycle`. Da riverificare su tutti i call site.
- **Determinismo**: stesso stato + stesso profilo → stesso pool.
- **Boulder e all_round**: la regola va decisa anche per `_SESSION_POOL_BOULDER`, oppure limitata esplicitamente a lead con motivazione.
- **Nessun aumento del carico**: la sessione entra come `available`, il conteggio giorni duri non deve salire.

## 7. Raccomandazioni

**1. Soglia a 50 — SÌ.** Coincide con la soglia `< 50` che `_adjust_domain_weights` usa già per definire "asse debole". Riusarla significa **una sola definizione di debolezza** in tutto il motore: se un domani si sposta, si sposta in un punto solo. Inventare una seconda soglia qui creerebbe due nozioni di "debole" che divergono silenziosamente.

**2. Anche boulder — SÌ, e non è un di più: il buco è identico.** Verificato sul pool boulder:

| fase (boulder) | peso `pulling_strength` | sessioni che lo coprono |
|---|---|---|
| base | 0.15 | 1 (`complementary_conditioning`, solo `available`) |
| strength_power | 0.25 | 4 |
| **power_endurance** | **0.15** | **0** ⚠️ |
| performance | 0.10 | 2 |
| deload | 0.05 | 0 (benigno) |

In `power_endurance` il boulder ha peso **0.15** contro lo 0.10 del lead, quindi il buco è **più grave**. Limitare la regola al lead lascerebbe scoperto proprio il caso peggiore.

**3. Divergenza del replanner — RACCOMANDAZIONE CORRETTA dopo verifica: memorizzare il pool in `profile_snapshot`.**

Nel brief avevo proposto di leggere il pool dalla fase del macrociclo. **Non è praticabile**: `apply_events` (`replanner_v1.py:971`) riceve solo `plan, events, availability, planning_prefs, gyms, custom_sessions` — **nessun `user_state`, nessun macrociclo**. Leggerlo lì richiederebbe di allargare la firma di una funzione pubblica con molti chiamanti.

La soluzione pulita è **simmetrica a quella che il progetto usa già**: `profile_snapshot` porta `domain_weights` esattamente perché il replanner non debba ricalcolarli. Aggiungere `session_pool` allo snapshot lo fa seguire lo stesso schema, con lo stesso fallback:

```python
domain_weights = snapshot.get("domain_weights", base_weights)          # oggi
session_pool   = snapshot.get("session_pool") or _build_session_pool(...)  # proposto
```

Il fallback copre i piani già salvati, che il campo non ce l'hanno. Beneficio collaterale: elimina la ricostruzione che in B287/R-3 aveva già perso la disciplina.

**4. Partire dal solo caso tirata — SÌ.** Verificato cosa allenano le altre 4 sessioni orfane: `heavy_conditioning_gym`, `legs_strength`, `lower_body_gym`, `upper_body_weights` dichiarano **tutte** un solo dominio, `strength_general`, che nell'assessment **non è un asse**. Non esiste un punteggio "forza generale" su cui condizionare: servirebbe prima decidere *quale* asse le governa, cioè una domanda di training design che al KB non abbiamo posto. La tirata invece ha un asse proprio, un test dedicato e una risposta del KB già in mano. **Generalizzare adesso significherebbe impacchettare una decisione non istruita dentro una istruita.**

## 8. Ordine consigliato

[[B308]] (frequenza garantita) e questo brief sono **complementari, non alternativi**: B308 garantisce il mantenimento *per tutti*, A258 dà una dose di *sviluppo* a chi ha la tirata debole. Ordine: azione 2 del KB (blocco tirata in `base`/`power_endurance`, catalogo) → **B308** → **A258**.

---

⛔ **STOP — Fase 1 completa. In attesa di OK esplicito prima di scrivere codice.**
