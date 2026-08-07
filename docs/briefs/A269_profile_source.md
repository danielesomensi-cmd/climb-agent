# A269 — `profile_source` e `profile_scoring_version`

> **Tipo:** A (feature, fondamento) · **Origine:** [[D260]] §3.6 finding #7 · [[D271]] §3.3 · [[D272]] §7
> **Moduli:** `assessment_v1.py` (⚠️ lista STOP di CLAUDE.md), `api/deps.py`, `api/routers/{onboarding,assessment,macrocycle}.py`, nuova migrazione `m002`
> **Prerequisito di:** [[A270]] (demozione del gap) e di [[D271]] (test endurance). Da fare **per primo**.
>
> ⛔ **STOP gate.** Analisi già fatta ([[D271]] §3.3, [[D272]] §7). Serve OK esplicito di Daniele prima di scrivere codice.

---

## 1. Il difetto

**Il motore non registra da dove viene un punteggio d'asse.** [[D260]] §3.6 lo chiama «il problema del 50»: `50` è emesso come default silenzioso da almeno quattro percorsi diversi — gradi mancanti in PE e tecnica, il ramo `else` di dita/tirata quando `target_idx = 0`, e `profile.get(axis, 50)` dentro `_find_weakest_axis` e `_adjust_domain_weights` — e a valle **una media vera e un «non lo sappiamo» sono indistinguibili**.

Non è teorico. Su 18 profili in produzione:

- **8 non hanno né max hang né loading pin**: il loro `finger_strength` è stimato dal grado, e nessun campo lo dice.
- **15 non hanno un repeater**: il loro `power_endurance` è per il 60% il gap RP−OS più l'auto-valutazione.
- **`endurance` non ha un test dedicato per nessuno** — è `0.8 × PE` per tutti e 18.

Il radar mostra cinque numeri con la stessa grafica, il coach li legge tutti come misure, e i pesi di dominio li usano tutti allo stesso modo.

**L'idea esiste già, ma solo dove non serviva persistere.** [[A262]]/[[A263]] l'hanno fatta per l'endpoint pubblico: la risposta di `/api/public/assessment` porta `measured_axes[]` ed `estimated` — «detto ad alta voce nel payload, non solo nella copy della pagina». Questo brief fa la stessa cosa per lo stato salvato.

**Il precedente architetturale c'è già anche lato dati.** [[D214]] ha introdotto `assessment.tests_source` (`{chiave_test: "measured"}`, chiave assente ⇒ `"estimated"`), e [[B253]] ha aggiunto la migrazione pigra `m001_backfill_tests_source`. `profile_source` è la stessa cosa un livello più su: da *quali input sono misurati* a *quali assi lo sono*.

## 2. Cosa NON fa questo brief

Elenco esplicito, perché è il punto di tutta la sicurezza di A269:

- ❌ **Nessuna formula cambia.** `compute_assessment_profile` restituisce esattamente gli stessi cinque interi di oggi, per ogni input.
- ❌ **Nessun peso di dominio, nessuna durata di fase cambia.** `_adjust_domain_weights` e `_find_weakest_axis` non vengono toccate.
- ❌ **Nessun punteggio storico viene ricalcolato con regole nuove** (vincolo globale: mai rescoring retroattivo).
- ❌ **Nessun cambiamento visivo.** Il radar resta identico. La resa grafica di un asse `estimated` è una decisione separata, deliberatamente rinviata: grigiare tecnica, PE ed endurance insieme lascerebbe un iscritto nuovo con **due soli assi vivi** sulla pagina pubblica di acquisizione, e [[A267]] sotto i tre vertici disegna raggi invece di un poligono. Prima il dato, poi la grafica.

Se al termine del brief un qualsiasi punteggio d'asse è diverso da prima per un qualsiasi utente, **il brief è sbagliato**, non i dati.

## 3. Il modello dati

### 3.1 `assessment.profile_source`

```jsonc
"profile_source": {
  "finger_strength":  "measured",   // ogni input dell'asse è un test misurato
  "pulling_strength": "measured",
  "power_endurance":  "partial",    // almeno un input misurato + termini derivati/soggettivi
  "technique":        "estimated",  // nessun input misurato
  "endurance":        "estimated"
}
```

**Tre valori, e descrivono da cosa deriva l'asse — non quanto è buono:**

| valore | significato |
|---|---|
| `measured` | tutti gli input che concorrono all'asse vengono da un test registrato come `measured` in `tests_source` |
| `partial` | almeno un input misurato, più termini derivati (gradi) o soggettivi (self-eval) |
| `estimated` | nessun input misurato: l'asse è inferito da gradi, tenure e auto-valutazione |

[[A270]] aggiungerà un quarto valore, `self_reported`, per un asse che deriva da **un solo** input soggettivo e da nessun test. Non introdurlo qui.

**Convenzione di assenza, identica a `tests_source`:** chiave mancante ⇒ `"estimated"`. Un lettore non deve mai poter interpretare l'assenza come una misura. Documentarlo nel docstring, come fa `_build_tests_source`.

### 3.2 Regole per asse

Da derivare da `assessment.tests_source`, **non** dalla presenza dei valori in `assessment.tests` (un valore stimato dall'onboarding è presente ma non misurato — è esattamente la distinzione che [[D214]] ha introdotto).

| asse | `measured` se | `partial` se | altrimenti |
|---|---|---|---|
| `finger_strength` | uno fra `max_hang_20mm_{5,7}s_total_kg`, `lp_max_lift_5s_{left,right}_kg` è `measured` | — | `estimated` |
| `pulling_strength` | `weighted_pullup_1rm_total_kg` misurato, **oppure** la coppia submassimale `pullup_submaximal_{reps,load_kg}` misurata (stima Brzycki, [[D38]]) | — | `estimated` |
| `power_endurance` | — | `repeater_7_3_max_sets_20mm` misurato (pesa 40%, il resto è gap + self-eval) | `estimated` |
| `technique` | — | — | **sempre** `estimated` (nessun test lo alimenta) |
| `endurance` | — | `max_hang_duration_20mm_seconds` misurato (è un modificatore, non la base) | `estimated` |

⚠️ **Nota di onestà su `finger_strength`:** con `LP_ONE_ARM_TO_TWO_HAND` ([[A266]]) l'asse è misurato ma **convertito**. Resta `measured` — la conversione è documentata e verificata contro tre fonti — ma il campo `tests_source` dice già quale chiave era la sorgente, quindi l'informazione non si perde.

### 3.3 `assessment.profile_scoring_version`

Stringa singola a livello di profilo, non per asse.

- Valore introdotto da questo brief: **`"profile_v1"`** — le regole di scoring di oggi.
- [[A270]] lo porterà a `"profile_v2_gap_demoted"`.
- [[D271]] Stage 2 a `"profile_v3_endurance_measured"`.
- **Mai retroattivo.** Un profilo salvato conserva la sua versione e i suoi numeri; una versione nuova vale dalla prossima valutazione o dalla prossima rigenerazione esplicita.

Un solo campo condiviso, non uno per brief: [[D272]] §7 lo chiede esplicitamente, perché «quali regole hanno prodotto questo radar» deve avere **una** risposta.

## 4. Dove scrivere

`assessment["profile"]` viene assegnato in **quattro** punti. Tutti e quattro devono scrivere anche `profile_source` e `profile_scoring_version`, nella stessa operazione:

| # | file:riga | contesto |
|---|---|---|
| 1 | `api/deps.py:274` | `_recompute_profile_if_needed`, ricalcolo pigro al salvataggio ([[B127]]) |
| 2 | `api/routers/assessment.py:34` | `POST /api/assessment/compute` |
| 3 | `api/routers/onboarding.py:473` | `POST /api/onboarding/complete` |
| 4 | `api/routers/macrocycle.py:266` | `POST /api/macrocycle/start-new-cycle` |

**Non duplicare la logica in quattro posti.** `compute_assessment_profile` deve restituire anche la provenienza. Due modi:

- **(a) Firma nuova**: `compute_assessment_profile_with_source(assessment, goal) -> (profile, source)`, e `compute_assessment_profile` resta un wrapper che restituisce solo il profilo. ✅ **Raccomandato**: i ~30 file di test che chiamano la funzione esistente non si toccano, e il percorso pubblico (`public_assessment.py:160`) che non persiste nulla continua a usare il wrapper.
- (b) Cambiare il tipo di ritorno di `compute_assessment_profile`. Rompe ogni chiamante, incluso l'endpoint pubblico. Scartare.

**Percorso pubblico — non toccare.** `public_assessment.py` non persiste niente e ha già `measured_axes` + `estimated` nella risposta. Se si vuole allinearlo, è un brief separato; qui rischia solo di rompere l'unica superficie di acquisizione.

## 5. Il fingerprint — l'unico punto delicato

> ⚠️ **§5 è stato SUPERATO in implementazione (06/08). La modifica proposta qui NON è stata fatta.**
> Il ricalcolo forzato che comportava non è il no-op che questo paragrafo assumeva: sul corpus di
> produzione **tre profili loading-pin** sono stati salvati prima di [[A266]] e un ricalcolo li
> sposterebbe (`e60d7a0c` 51→100, `d7f6083e` 51→69, `79fadc50` 54→71). Il primo è l'utente il cui
> ricalcolo Daniele ha **esplicitamente sospeso** ([[A266-P1]]): una migrazione non può ribaltare una
> decisione di prodotto. E non serviva: `m002` gira a ogni lettura subito dopo `m001`, quindi la
> provenienza è derivata dal sidecar già popolato al primo caricamento. Il buco descritto sotto è
> chiuso dalla migrazione, non dal fingerprint. Dettaglio in
> `test_three_loading_pin_profiles_are_already_drifted_from_A266`.

*Ragionamento originale, conservato perché il buco che descrive è reale — ha solo un'altra soluzione:*

`_recompute_profile_if_needed` (`deps.py:258-277`) salta il ricalcolo quando l'hash degli input non è cambiato:

```python
inputs = json.dumps({"grades": …, "tests": …, "self_eval": …, "experience": …,
                     "target_grade": …, "current_grade": …}, sort_keys=True)
if assessment.get("_profile_fingerprint") == fingerprint: return
```

`tests_source` **non è nel fingerprint**, ma la provenienza dipende da lui. Caso reale che rompe: la migrazione `m001` aggiunge `tests_source` a un utente legacy **senza toccare `tests`** → il fingerprint non cambia → `profile_source` non verrebbe mai ricalcolato.

**Decisione: aggiungere `tests_source` agli input del fingerprint.** Conseguenza: un ricalcolo una tantum per ogni utente esistente. È sicuro **solo perché A269 non cambia nessuna formula** — e va dimostrato, non assunto: vedi il test §7.1.

## 6. Migrazione `m002`

Modellata su `m001_backfill_tests_source.py`: modulo in `backend/engine/migrations/`, funzione `migrate(state) -> bool`, invocata pigramente da `deps.load_state`, **idempotente**, mai un downgrade di un valore esistente.

```python
# backend/engine/migrations/m002_backfill_profile_source.py
def migrate(state): ...
```

- Se `assessment.profile` esiste e `profile_source` no → derivarlo dalle regole §3.2 sul `tests_source` corrente.
- Se `profile_scoring_version` manca → `"profile_v1"`.
- **Ordine:** deve girare **dopo** `m001` in `load_state`, altrimenti deriva la provenienza da un `tests_source` non ancora popolato per gli utenti legacy.
- Se `assessment.profile` non esiste → non fare nulla (utente senza profilo).

## 7. Test

### 7.1 Il test che rende il brief sicuro

**Corpus di regressione sui 18 profili di produzione.** Salvare i 18 `assessment` + `goal` reali come fixture (anonimizzati: solo i campi che entrano nello scoring) e asserire che `compute_assessment_profile` restituisca **esattamente gli stessi cinque interi** prima e dopo il brief, per tutti e 18. È la garanzia che il ricalcolo forzato dal fingerprint (§5) sia un no-op.

Precedente: [[B321]] ha usato il payload di produzione esatto come fixture, ed è così che il bug è stato inchiodato.

### 7.2 Provenienza

- Un asse senza alcun input misurato → `estimated`, **mai** assente e mai `measured`.
- `tests` popolato ma `tests_source` vuoto (il caso legacy pre-D214) → `estimated`. È il test che distingue «valore presente» da «valore misurato».
- Utente loading-pin ([[A266]]) → `finger_strength: "measured"`.
- Utente con stima Brzycki da reps submassimali → `pulling_strength: "measured"`.
- Repeater presente → `power_endurance: "partial"`, mai `measured`.
- `technique` → `estimated` per **ogni** input possibile.
- Chiave assente letta da un consumatore ⇒ `estimated` (test sulla convenzione, non sul dizionario).

### 7.3 Migrazione

- Idempotente: due giri consecutivi, il secondo restituisce `False` e non muta.
- Non fa downgrade di un `profile_source` già presente.
- Gira dopo `m001`: un utente legacy con `tests.max_strength` popolato e `tests_source` vuoto finisce `measured` sulle dita, non `estimated`.
- Stato senza `assessment.profile` → nessuna mutazione.

### 7.4 Invarianti

- **Sessioni passate immutabili** (regola globale): generare un piano, completare sessioni, salvare lo stato (che innesca il ricalcolo del §5), rigenerare → `session_completion_log`, `feedback_log`, `week_plans` passati e `working_loads` byte-identici.
- **`is_macrocycle_stale` resta `False`.** I punteggi non si muovono, quindi nessun banner deve comparire a nessun utente. Asserirlo sui 18 profili: se anche uno solo diventa stale, una formula è cambiata.
- Pesi di dominio e durate di fase identici a prima per tutti e 18 i profili.

## 8. Superficie da aggiornare, oltre al motore

| dove | cosa |
|---|---|
| `coach/prompt_builder.py:140-145` | la riga `- Assessment (5-axis): …` deve marcare gli assi non misurati, altrimenti il coach parla di misure che non esistono — la stessa classe di fabbricazione che [[B305]] ha chiuso. Formato suggerito: `technique 30/100 (estimated)` |
| `frontend/src/lib/types.ts` | `UserState.assessment` guadagna `profile_source?` e `profile_scoring_version?`. Solo tipi, nessun render |
| `docs/vocabulary_v1.md` | nuova sezione con i tre valori e la convenzione di assenza |
| `CLAUDE.md` | nessuna riga della tabella endpoint cambia (nessun endpoint nuovo) |

**Non aggiornare la guida utente in questo brief**: non cambia niente di visibile. Toccherà al brief che decide la grafica.

## 9. Definizione di fatto

- [ ] I 18 profili di produzione producono punteggi identici (§7.1)
- [ ] `profile_source` e `profile_scoring_version` scritti da tutti e quattro i punti di §4
- [ ] `m002` idempotente e ordinata dopo `m001`
- [ ] `is_macrocycle_stale` resta `False` per tutti
- [ ] Il coach dichiara gli assi stimati
- [ ] Suite backend verde, `scripts/sync_status.py` eseguito
- [ ] `docs/ROADMAP_CURRENT.md` aggiornato nello stesso commit

---

*✅ **Consegnato il 2026-08-06** (commit `5ea8eda`). Il §5 è stato superato in implementazione — vedi il riquadro lì.*
