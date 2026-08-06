# A271 — Assi non misurati e pesi di dominio

> **Tipo:** A (feature, correzione metodologica) · **Origine:** i due residui che il property test di [[A270]] ha trovato e fissato · chiude l'ultimo pezzo di [[D260]] issue #7
> **Moduli:** `assessment_v1.py` **e** `macrocycle_v1.py` (⚠️ entrambi sulla lista STOP di CLAUDE.md) + nuova migrazione `m003`
> **Dipende da:** [[A269]] (il campo `profile_source`) e [[A270]] (la demozione del gap), entrambi in produzione.
>
> ⛔ **STOP gate.** Serve OK esplicito di Daniele, **e** una scelta fra i due framing del §3.

---

## 1. Il difetto, misurato

[[A270]] ha introdotto il property test che [[D260]] avrebbe voluto: *nessun singolo input auto-dichiarato può muovere un peso di dominio di più di 2 punti percentuali*. Nello scope di A270 il risultato non è «sotto 2 pp», è **zero**. Fuori da quello scope, il test ha trovato due perdite, entrambe già inchiodate da un test:

| # | percorso | entità | chi tocca |
|---|---|---|---|
| 1 | `cant_manage_rests` → penalità sull'asse `endurance` → attraversa la soglia `< 50` → `volume_climbing` | **3,5 pp** | chiunque dichiari quella debolezza |
| 2 | Utente **senza alcun test**: gli assi forza ripiegano su `_grade_ratio_score` **più** `_weakness_penalty`, e `endurance` porta la sua → un peso di deload si muove | **8,3 pp** | **8 profili su 18** |

Il secondo è **più grande dei 7,5 pp che [[D260]] §5 chiamava «la distorsione più grande del motore»**. La differenza è che quello passava per la tecnica ed era visibile; questo passa per il ramo di fallback e non lo aveva mai guardato nessuno.

Il punto non è la dimensione: è che una tendina compilata durante l'onboarding riscrive i pesi di un macrociclo di 12 settimane, sugli assi dove il motore ha **meno** informazione, non di più.

---

## 2. ⚠️ Prerequisito bloccante — `profile_source` oggi è cieco per 4 utenti su 18

Qualunque regola che condizioni una decisione di pianificazione a `profile_source` eredita l'affidabilità di `assessment.tests_source`. **Oggi non è sufficiente.**

- Solo **7 profili su 18** hanno un `tests_source` non vuoto.
- **4 su 18** — `f49678eb`, `d7f6083e`, `79fadc50`, `22080848` — hanno **un numero dita reale a referto** (max hang o loading pin) e `tests_source` **vuoto**. La loro provenienza dice `estimated` mentre il dato è misurato.

Sono utenti che hanno fatto l'onboarding **prima di [[D214]]**, quando `_build_tests_source` non esisteva ancora. `m001` non li copre: quella migrazione inferisce la provenienza dalla *storia append-only* (`tests.max_strength`, `tests.repeater_strength_endurance`, …), che si popola solo quando un test viene completato **dentro l'app**. Chi ha digitato i numeri nel wizard e non ha mai eseguito una sessione di test non ha nessuna storia da cui inferire.

**Se A271 partisse così, punirebbe 4 utenti per un buco contabile, non per un'assenza di dati.**

### 2.1 La migrazione `m003` che lo chiude

Regola proposta: **un valore presente in `assessment.tests` è stato digitato da un umano, quindi è `measured`.**

Verificato: nessun percorso scrive una stima dentro `assessment.tests`.

| scrittore | cosa fa |
|---|---|
| `onboarding._build_user_state_from_onboarding` | scrive ciò che l'utente ha digitato, e da [[D214]] stampa già `tests_source` |
| `progression_v1:1290+` | percorso di completamento test — scrive valore **e** `tests_source` insieme (`at_src = assessment.setdefault("tests_source", {})`) |
| `public_assessment.py:149` | costruisce un dict **locale**, non persiste niente ([[A262]]) |
| `settings/profile-assessment-editor` | modifica manuale dell'utente |

Le stime derivate dal grado vivono in `baselines` (`estimate_missing_baselines`), **mai** in `assessment.tests`. Quindi la regola è sana — ma **va ri-verificata come primo passo del brief**, non assunta: se un solo percorso scrivesse una stima lì dentro, `m003` marcherebbe misurato un dato inventato, che è il contrario del punto di [[A269]].

`m003` va in `backend/engine/migrations/`, pigra su lettura come `m001`/`m002`, idempotente, **prima di `m002`** nella catena di `load_state` (m002 deriva da `tests_source`, quindi deve trovarlo già completo). Dopo `m003`, `m002` va rieseguito su chi ha già un `profile_source` scritto da una provenienza cieca — quindi `m002` deve **ricalcolare** invece di limitarsi a riempire quando `m003` ha mutato lo stato in quel giro.

---

## 3. I due framing — è qui che serve la decisione

Entrambi chiudono le due perdite del §1. Sono molto diversi per ciò che tolgono.

### Framing A — «un asse non misurato non pesa»

Un asse la cui provenienza è `estimated` o `self_reported` viene **saltato** in `_adjust_domain_weights` (niente bump, niente taglio) e nella tupla di `_find_weakest_axis`.

Controfattuale calcolato sui 18 profili reali (con la provenienza **corretta** da `m003`, altrimenti i numeri sono peggiori e falsi):

- **14 utenti su 18** hanno almeno un peso mosso; massimo **13,5 pp**.
- **12 utenti su 18** finiscono con **tutti e quattro** gli assi che pesano esclusi → ricevono **i pesi di default della fase, senza nessuna personalizzazione**.

- ✅ È la posizione onesta in senso stretto: se non abbiamo misurato, non adattiamo.
- ✅ Crea un incentivo fortissimo a fare i test.
- ❌ **Due terzi degli utenti perdono la personalizzazione**, cioè la proposta di valore del prodotto. Per un'app a pagamento pre-massa critica è un prezzo molto alto.
- ❌ Butta via anche il segnale **derivato dal grado**, che non è un'auto-diagnosi: che un 6c che punta a 7b abbia dita più deboli di un 8a è un'inferenza grezza ma non infondata. Non è la stessa classe epistemica di «sento che la mia tecnica è scarsa».

### Framing B — «un'auto-dichiarazione non pesa» — **RACCOMANDATO**

`_weakness_penalty` non viene applicata a un asse la cui provenienza è `estimated`. Gli assi non misurati restano nei pesi, ma **puramente derivati dal grado**: nessun input soggettivo li tocca.

Controfattuale sui 18 profili:

- **8 utenti su 18** hanno almeno un peso mosso; massimo **9,7 pp**.
- Nessuno perde la personalizzazione: gli assi continuano a rispondere ai gradi dichiarati.

- ✅ Colpisce **esattamente** il difetto che il property test ha trovato, e lo azzera: dopo A271 il bound diventa **0 pp** in tutti i casi, non solo in quelli misurati.
- ✅ Chirurgico. La penalità self-eval per dita e tirata esiste **solo** nel ramo di fallback (`_compute_finger_strength`/`_compute_pulling_strength`, ramo `else`), quindi sparisce del tutto e in modo pulito. PE è già conforme dopo [[A270]] (50 secco senza repeater). Resta da gatare solo `endurance`.
- ✅ Compatibile con Framing A dopo: quando i test saranno diffusi, passare ad A sarà un cambiamento piccolo.
- ❌ Un asse stimato continua a muovere il piano. È un compromesso, e va detto: la stima da grado è un segnale debole, non una misura.

**Raccomandazione: B.** Framing A è la posizione giusta il giorno in cui la maggioranza degli utenti ha dei test; oggi spegnerebbe la personalizzazione per due terzi della base per una purezza che non produce un piano migliore — produce **il piano di default**. B toglie ciò che è davvero indifendibile (una tendina che riscrive dodici settimane) e lascia in piedi ciò che è debole ma fondato.

### 3.1 Cosa NON è un'opzione

Ridurre l'influenza degli assi stimati a metà, o mettere un cap. È lo stesso costante inventato che [[D272]] ha scartato per l'opzione (a) della tecnica e che [[D260]] §7 criticava: un numero scelto per essere piccolo non è una calibrazione.

---

## 4. Superficie della modifica (Framing B)

| dove | cosa |
|---|---|
| `assessment_v1._compute_finger_strength` | il ramo `else` perde `+= _weakness_penalty(...)`. Diventa la stima pura da grado |
| `assessment_v1._compute_pulling_strength` | idem |
| `assessment_v1._compute_endurance` | `_weakness_penalty(self_eval, "endurance")` applicata **solo** quando l'asse è `partial` (repeater o durata misurati) |
| `assessment_v1._compute_power_endurance` | **già conforme** dopo [[A270]] |
| `assessment_v1._compute_technique` | invariato: è `self_reported`, non pesa niente ([[A270]]) |
| `PROFILE_SCORING_VERSION` | → `profile_v3_self_report_unweighted` |
| `migrations/m003_backfill_tests_source_from_values.py` | nuova, §2.1 |
| `deps.load_state` | catena `m001` → `m003` → `m002`, con `m002` che ricalcola se `m003` ha mutato |

**Nota di progettazione.** Le funzioni `_compute_*` oggi non conoscono la provenienza — la calcola `compute_profile_source` a parte, sullo stesso `assessment`. Serve calcolarla **prima** e passarla, oppure far calcolare a ciascuna `_compute_*` il proprio flag dalle stesse chiavi. La prima è più pulita e mette la regola in un posto solo; comporta un piccolo riordino di `compute_assessment_profile`.

---

## 5. Test

- **Il property test di [[A270]] passa a zero, senza esclusioni.** Oggi esclude le debolezze che mappano su `endurance` (`_ENDURANCE_WEAKNESSES`); quell'esclusione va **rimossa**, e il bound diventa `worst == 0.0` su tutte le debolezze, tutte le fasi, entrambe le discipline. È la definizione di fatto del brief.
- **I due test di residuo di [[A270]] vanno invertiti**, non cancellati:
  `test_known_residual_a_self_reported_endurance_weakness_still_moves_a_weight` e
  `test_known_residual_self_report_leaks_through_the_grade_estimate_fallback` diventano asserzioni che la perdita è **chiusa** (delta esattamente 0), e conservano nel docstring il numero che era (3,5 pp e 8,3 pp).
- **`m003`**: idempotente; non fa downgrade; un valore in `tests` senza `tests_source` diventa `measured`; uno stato senza `tests` non muta; l'ordine `m001` → `m003` → `m002` è fissato leggendo il sorgente di `load_state`, come già fa il test di `m002`.
- **I 4 utenti con provenienza cieca**: fixture di regressione che dopo `m003` la loro `finger_strength` risulta `measured`, e che **il loro punteggio non cambia** (m003 tocca la provenienza, mai un valore).
- **Corpus dei 18**: `expected_profile_v3` nella fixture, più il test «quali assi si muovono e per chi» sul modello di [[A270]].
- **Invarianti**: sessioni passate immutabili; snapshot vs live; `is_macrocycle_stale` diventerà `True` per gli 8 utenti colpiti — comportamento voluto, da asserire.

---

## 6. Cosa questo brief non fa

- ❌ Non tocca le soglie a scalino `< 35 / < 50 / > 75` né la loro fragilità ([[D260]] issue #5). Restano aperte.
- ❌ Non tocca `_PE_REPEATER_BENCHMARK`, tuttora privo di fonte ([[D260]] §7) e ora più importante di prima, perché [[A270]] ha smesso di diluirlo.
- ❌ Non re-ancora dita e tirata ([[D260]]-P2): quello invalida gli score storici ed è una decisione di prodotto a sé.
- ❌ Non grigia niente sul radar. La resa grafica degli assi `estimated`/`self_reported` resta la decisione separata rinviata da [[A270]] §1.

---

## 7. Domande aperte per Daniele

1. **Framing A o B?** Raccomandato B. A è la posizione giusta più avanti, quando i test saranno diffusi.
2. **La regola di `m003` — «un valore in `tests` è stato digitato, quindi è misurato» — è accettabile?** È solida contro il codice di oggi, ma è un'inferenza su dati storici di cui non abbiamo il log. L'alternativa conservativa è lasciare quei 4 utenti `estimated` e accettare che il brief li penalizzi.
3. **Il banner di ricalcolo, di nuovo.** [[A270]] lo ha già fatto comparire a tutti e 18 due giorni fa. A271 lo farebbe comparire a 8 di loro una seconda volta. Vale la pena aspettare e unire questo brief a un altro cambiamento di scoring, invece di far lampeggiare «il tuo profilo è cambiato» due volte in una settimana?

---

*Brief pronto. Nessuna riga scritta. Serve OK di Daniele e la scelta del §3.*
