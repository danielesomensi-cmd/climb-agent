# D287 — Audit del planner e delle correzioni manuali via coach

> **Data:** 2026-11-13 · **Tipo:** D (audit + correzioni libere) · **Base:** main `aa70dc82`
> **Richiesta (Daniele, 2026-11-11):** «Fai una verifica ben fatta di come funziona il planner e di come ho richiesto spesso modifiche manuali usando climb coach via Telegram per migliorare il planner. Verifica anche il progetto climbing knowledge su claude.ai […] Proponi miglioramenti in modo super conciso e fai i miglioramenti ovvi in autonomia!»
> **Fonti:** trascrizioni del coach Telegram 06/10 → 11/11 (115 richieste classificate), mirror notturno di prod (`climb-state-mirror`, 27 snapshot, settimane 14/09 → 09/11), codice di main, KB del repo (`docs/research_kb/`) e testo del progetto claude.ai «climb-agent Knowledge Base».
> **Metodo:** raccolta delle evidenze (12 lettori) → **verifica avversariale di 42 claim** eseguendo il motore reale su copie in memoria dello stato mirror (nessuna scrittura in prod, nessun repo toccato) → implementazione delle sole correzioni libere → revisione avversariale del diff.
> **Allegato:** [`D287_verification_appendix.md`](D287_verification_appendix.md) — evidenza, effetto su Daniele, fix minimo e analisi di Fase 1 di ogni claim. **I claim smentiti o «decisi diversamente» là elencati non vanno riaperti.**

## 1. I numeri

- **8 sessioni su 33** generate dal planner sono state eseguite così come generate (le 3 settimane con un piano originale intatto nel mirror: 19/10, 26/10, 02/11). Serali 3/18, pranzi 5/15.
- **37 delle 54 sessioni indoor fatte** in 8 settimane sono custom (69%), più 8 giornate outdoor.
- **~23 modifiche strutturali a mano per settimana** (161 in 7 settimane: 65 custom inserite, 66 rimozioni, 15 spostamenti, 10 sostituzioni di catalogo). La libreria custom è passata da 37 a 71 voci in 27 giorni.
- **16 custom serali su 18 nascono entro un giorno dalla seduta:** il lavoro manuale è ricomposizione del giorno, non della settimana.
- **La forma è giusta, il contenuto no:** settimane generate ed eseguite hanno entrambe ~11 sessioni su 6-7 giorni con 3-4 giorni duri; ~20 delle 23 rimozioni sono state rimpiazzate nello stesso slot.
- Richieste al coach (115): sostituire una sessione 15, cambiare un esercizio 13, recupero 10, lamentele sul piano 10, bug dell'app 9, spostare 8, outdoor 7, durata/intensità 7, palestra/attrezzi 6, togliere 6, carico 6, altro 18. **78 su 115 sistematiche** (si ripetono, non sono episodi).

## 2. Le cause, in ordine di peso

1. **La sede della sera non è il default del giorno.** Il default è giusto in al massimo 8 sere su 22; almeno 11 serali su 25 si sono svolte in una sede o in uno slot che la disponibilità non descrive. Lo strumento c'è (`change_gym` con `slot`, riletto dal planner), ma quando la sessione non entra nella nuova sede (corda → boulder, qualunque → casa) degrada a condizionamento invece di cercare una sessione che dia lo stesso stimolo. → E1/E2/E3.
2. **Contenuto dello slot.** PE in palestra piazzata 5 volte ed eseguita 0; mantenimento dita della domenica tolto 3 volte su 3; `technique_focus_gym` è la sessione più rimossa (6); 11 drill di tecnica/try-hard usati nelle custom non vengono mai risolti dal catalogo; nessuna rampa di sospensioni prima del limit. → K1/K2/K3, G4/G5.
3. **Il motore non vede bene le custom.** Il seed della settimana precedente le salta (C1); i pavimenti dita/trazioni non vedono né le sessioni fatte né quelle dell'utente (C2: falso «non c'è posto» già comparso nelle settimane del 12/10 e del 27/07); due esercizi di core «high» rendono dura una custom (T1, bug-inbox 07/11).
4. **Regole ancora applicate a mano nel coach** (repo `climb-coach`), alcune ormai sbagliate rispetto al motore (§7).
5. **Il progetto KB su claude.ai è fermo al 12/05** (1232 commit fa) e non può ragionare sul motore di oggi (§6).

## 3. Fatto in D287

- **Documentazione riallineata al codice:** `docs/ENGINE_ARCHITECTURE.md` §3 Macrocycle e §4 Weekly Planner (tabella dei 12 stadi; ordine reale dei pass 1 → 1.5 → 2 → 2.2 → 2.5 → 2.6 → 3a → 3 → 2.7 → sweep no-hard → deload → complementari; gap in giorni di calendario, non 48 h; taper A281; deload reale; limiti di `total_weeks` per scope; vincolo 6 dell'ordinamento); `CLAUDE.md` e guida utente («multi-pass», non «3-pass»).
- **`athlete_context` d287.1:** lo spacing dita dice che è **solo un alert** (A301: nulla viene spostato né declassato); nuova sezione `stale_weeks` con avviso `STALE_WEEK` per le settimane dei prossimi 14 giorni marcate `_stale` — sostituisce il ricontrollo a mano dei 14 giorni dopo ogni rigenerazione (regola del coach).
- **Catalogo:**
  - pranzo braccia/spalle v1.2: **verticale in fondo** (Daniele 25/10, «Handstand solo alla fine, non mi piace farla quando c'è troppa gente»), con ripresa dei polsi prima della verticale e regole di stop a spalle stanche;
  - `toe_flexor_isometric`: setup da seduti con tallone a terra, variante senza bilancia, lettura mensile per piede;
  - `treadmill_incline_walk`: comanda la fascia cardiaca, pendenza e velocità sono solo le leve;
  - HIIT 4x4: «mai nelle 24 h prima» di una sessione massimale (B405), non «il giorno prima»;
  - nota Z2: tenere la fascia, non la velocità.
- **Test:** `test_d287_athlete_context_alerts.py`, `test_a318_arms_shoulders_lunch.py` riscritto (ordine per ogni livello di core); golden rigenerati solo per le chiavi del pranzo braccia (solo ordine).
- **Effetto noto:** un pranzo braccia **passato**, pianificato e mai fatto, viene ri-risolto alla lettura e mostra il nuovo ordine (`week._auto_resolve`, lacuna già nota da B414). Le sessioni fatte restano intatte.

## 4. Decisioni che servono a Daniele

Niente di questo è stato toccato.

| # | Decisione | Perché | Costo |
|---|---|---|---|
| 1 | **Pranzo braccia: lento avanti 3° dei 4 sollevamenti** | Il «verticale in fondo» fatto solo da catalogo ordina i quattro lift per id (curl, alzate laterali, lento, tricipiti). Per avere lento primo *e* verticale in fondo serve un valore `"order": "last"` in `resolve_session.py` + `exercise_ordering.py`. | S, ma `resolve_session` è da STOP |
| 2 | **Z2 a pranzo con core** (35' di camminata + hollow + arch hold) | Richiesto il 13/10 e il 28/10, ma C279 (30/10) ha fissato lo Z2 a 45' di camminata dopo quelle richieste. Patch pronta. | S, catalogo |
| 3 | **Panca col bilanciere al pranzo push** | Ribalta B381 (manubri, approvato il 17/10); serve anche il carico: 5×6 a 80 kg non è mai stato registrato. | S, catalogo + golden |
| 4 | **Regola dei tag: core/gambe/verticale «high» non fanno giorno duro** (front lever e trazioni pesanti sì) | T1/T2: oggi `toes_to_bar` + `half_windshield_wiper` = custom dura; la settimana del 02/11 è arrivata a 5/5 giorni duri con `hard_back_to_back`. | S, `session_tags.py`; dopo il deploy riallineamento B395 |
| 5 | **Brief planner C1+C2+C3** (Fase 1 nell'allegato) | Le custom e le sessioni fatte entrano nel seed e nei pavimenti: niente falso «non c'è posto», niente dose dita doppia. | M, `planner_v2` (STOP) |
| 6 | **Brief cambio sede E1/E2** | Cambiare sede conserva lo stimolo; a casa dita/forza prima del condizionamento. 8 custom serali su 18 non sarebbero servite. | M, replanner (STOP) |
| 7 | **Contenuto delle sessioni chiave K1/K3** | Un drill di tecnica fisso nelle sessioni limit/PE/circuito (la tua regola del 04/10) e la rampa di sospensioni prima del limit. | M, catalogo; golden si muovono |
| 8 | **Pulizia prod: 3 custom gambe con back squat** (19/11, 26/11, 01/12) | Ridondanti da B414 (il pranzo gambe di catalogo fa già back squat) e bloccano quello del motore. | dry run + OK |
| 9 | **KB su claude.ai: aggiornare e fare la sessione di ricerca** | §6. | upload (OK) |
| 10 | **Repo coach: righe vecchie** | §7. | altro repo |

## 5. Tutti i claim verificati

Verdetti: 12 confermati, 21 parziali, 5 decisi diversamente, 2 smentiti, 2 già coperti. Classi: 24 da STOP, 16 liberi, 2 nell'altro repo.

| Claim | Area | Verdetto | Classe | Effort | In una riga |
|---|---|---|---|---|---|
| P1a | Planner PASS 1 | confermato | STOP | S | Vero ma raro: scatta solo con un giorno «solo casa» prima di un giorno palestra; le tue settimane 10–13 non cambiano; correzione di tre righe. |
| P1b | Planner PASS 1 | confermato | STOP | L | Vero: il distacco conta giorni di calendario e non ore; a te non cambia nulla, hai solo serate; nessuna correzione consigliata da sola. |
| P1c | Planner PASS 1 | parziale | STOP | M | Vero nella sostanza: l'ordine alfabetico decide i giorni e il tuo lunedì al Bkl riceve sempre tecnica; settimane 10–12 identiche, solo due giorni duri. |
| P1d | Planner PASS 1 | confermato | STOP | M | Vero: con più giorni liberi dell'obiettivo l'allenamento si ammassa da lunedì; a te non succede, hai sei giorni su sei. |
| C1 | Custom nel planner | confermato | STOP | S | Nel seed B161 leggere i tag propri dei custom della settimana prima, così il lunedì non piazza dita o duro dopo un custom domenicale. |
| C2 | Custom nel planner | confermato | STOP | M | Far vedere ai floor dita/trazioni le sessioni tue e quelle già fatte nella settimana: niente doppia dose né avvisi «non c'è stato posto» falsi. |
| C3 | Custom nel planner | parziale | STOP | S | Bug reale ma quasi irraggiungibile e mai sul tuo profilo: tre righe da accodare al brief di C1/C2, non da fare da solo. |
| C4 | Custom nel planner | smentito | libero | — | Nessun intervento: il planner non legge stimulus_recency; la divergenza del contatore è già la voce aperta STIMULUS-RECENCY-DIVERGENCE. |
| C5 | Custom nel planner | parziale | libero | S | Non toccare: è l'effetto di due tue decisioni (B390 e A301) e col tetto a 5 non scatta; eventuale allineamento solo nell'avviso. |
| T1 | Tag hard/finger | confermato | libero | S | Confermato: due esercizi di core alti rendono «hard» la custom; proposta: non contarli, salvo front lever e trazioni pesanti. |
| T2 | Tag hard/finger | parziale | libero | S | Tecnica su board e gara a 3 tentativi sono taggate giuste; resta il riscaldamento tasche che dà «dita» a una custom di tecnica. |
| L1 | Pranzi / catalogo | confermato | libero | M | Handstand in fondo si può fare solo da catalogo, ma il lento avanti scende dopo curl e alzate laterali: decidi se va bene. |
| L2 | Pranzi / catalogo | parziale | libero | M | Z2 senza core è vero; aggiungerlo è solo catalogo, ma la camminata scende da 45' a 35': serve un tuo sì. |
| L3 | Pranzi / catalogo | deciso diversamente | libero | S | La panca col bilanciere di default ribalta B381 che hai approvato il 17/10: serve il tuo sì esplicito, per ora resta ai manubri. |
| L4 | Pranzi / catalogo | parziale | libero | S | Toe flexor: testo del catalogo da riscrivere (posizione, senza bilancia), gratis; il disegno è già in lista C285 e richiede preview. |
| L5 | Pranzi / catalogo | confermato | libero | S | Nel testo Z2 comanda la FC: pendenza e velocità diventano solo un punto di partenza; salvare velocità/pendenza dell'HIIT è una feature a parte. |
| L6 | Pranzi / catalogo | smentito | STOP | S | Nessun doppione da rotazione nei tuoi pranzi: hai 5 famiglie; i due Z2 del 2-3/12 sono lo scarico (HIIT→Z2), deciso il 5/10. |
| L7 | Pranzi / catalogo | parziale | altro repo | S | HIIT a pranzo prima del limit serale va bene (30 h, B405): correggere la regola vecchia nel repo del coach, non il piano. |
| G1 | Palestra / outdoor | parziale | STOP | S | Slot palestra senza gym_id: cercare l'attrezzatura in tutte le palestre, non solo nella prima; Daniele non è toccato, priorità bassa. |
| G2 | Palestra / outdoor | parziale | STOP | S | Rinviare la PE verso la palestra con le vie solo se quel giorno la può ospitare; oggi Daniele non è toccato. |
| G3 | Palestra / outdoor | deciso diversamente | STOP | — | Non toccare: per scelta (B372) solo la falesia dichiarata sul piano fa da ancora, ed è così che Daniele la dichiara. |
| G4 | Palestra / outdoor | parziale | STOP | S | In PASS 2.7 piazzare prima una seduta per ogni chiave, poi la seconda PE: con weekend in falesia il limit non salta più. |
| G5 | Palestra / outdoor | confermato | libero | — | Nessun fix di piazzamento: B414 ha già chiuso il contenuto PE; valutare con Daniele max hang d'apertura nella seduta limit. |
| R1 | Replanner | parziale | STOP | S | Vero nel codice ma senza effetto sulle settimane reali di Daniele: con tetto 5 le liste suggerite non cambiano; correzione di una riga, bassa priorita. |
| R2 | Replanner | confermato | libero | S | Confermato: i suggerimenti del quick-add usano sempre la settimana corrente; 22 liste su 56 sbagliate nelle settimane future, tutta la settimana di scarico. |
| R3 | Replanner | confermato | STOP | S | Confermato: un add_custom_session con id o data sbagliati risponde 200 senza aggiungere nulla e alza la revisione; i tipi sconosciuti vengono accettati e loggati. |
| R4 | Replanner | deciso diversamente | libero | S | Deciso cosi con A301 e fissato da un test; l'app offre solo slot liberi, nei dati reali 4 sostituzioni su 51 e nessuna custom persa. |
| R5 | Replanner | parziale | STOP | M | Vero che lo spostamento conserva la palestra, ma ricalcolarla dallo slot sbaglierebbe 2 spostamenti reali su 3: serve una sede scelta, non dedotta. |
| R6 | Replanner | deciso diversamente | libero | S | Comportamento reale ma voluto: le modifiche esplicite sul passato sono l'eccezione ammessa, le sessioni fatte restano protette e il coach ci conta. |
| R7 | Replanner | già coperto | altro repo | S | Confermato ma gia in roadmap (B369-P6-residui 3): le mosse via PUT non hanno marker, la rigenerazione le annulla; va corretto il runbook del coach. |
| R8 | Replanner | confermato | STOP | M | Confermato: 66 rimozioni e 65 inserimenti in 7 settimane, nessun evento unico di sostituzione e nessun legame tra custom e sessione sostituita. |
| R9 | Replanner | deciso diversamente | STOP | S | Comportamento voluto e fissato da test: la falesia convive con le sessioni indoor; costa 37 rimozioni in piu, risolvibili con un'opzione facoltativa. |
| E1 | Sede della sera | parziale | STOP | M | Cambio sede: degrada a condizionamento solo corda→boulder e tutto→casa; in 8 custom serali su 18 la sessione sarebbe rimasta. |
| E2 | Sede della sera | parziale | STOP | S | A casa i fallback deterministici esistono (dita, forza lunga), ma spostare una serata a casa non li sceglie mai. |
| E3 | Sede della sera | parziale | STOP | — | Confermato: 16 custom serali su 18 nascono entro un giorno; ma la leva giornaliera esiste già, va solo resa consapevole dello stimolo. |
| E4 | Sede della sera | parziale | STOP | M | B414 ha tolto il blocco boulder dalla PE su corda; restano 5-6 blocchi a terra che Daniele toglie a mano. |
| E5 | Sede della sera | già coperto | STOP | — | Già risolto da B405 il 27/10: l'ancora PE è il grado a vista (7b → 7A), resta solo un commento vecchio. |
| K1 | Sessioni chiave | parziale | libero | S | Tecnica solo come sessione a sé, tolta 6 volte; un blocco drill nelle sessioni di limite e PE è solo catalogo. |
| K2 | Sessioni chiave | parziale | STOP | M | Mantenimento dita piazzato la domenica e tolto 3 volte su 3; la soglia dei 4 set non lo riguarda. |
| K3 | Sessioni chiave | parziale | libero | S | Manca la rampa di sospensioni prima del limite e il pushup serale è fisso; il core serale segue già la scala. |
| K4 | Sessioni chiave | parziale | STOP | S | Dita max e trazioni senza pavimento in forza: il debito silenzioso esce solo con poche sere libere, non nelle sue settimane. |
| K5 | Sessioni chiave | parziale | libero | S | Il debito non passa alla settimana dopo ed è una scelta di progetto; basta dirlo in lettura, senza spostare nulla. |

Lato motore, fuori dai claim: PASS 2 piazza sessioni complementari con tag dita senza alcun controllo di gap (18 settimane fuzz su 2994 hanno dita in giorni consecutivi); è legato ad A-FINGER-LOAD-TIERS.

## 6. KB su claude.ai

**Cosa è vecchio nel progetto:**
- durate delle fasi: la base è 4 settimane per il lead (2 con override) e 2 per il boulder, non ≥ 6; forza 2-4 / 2-5, performance 2-3;
- focus corrente «Coach KB preparation (Phase 3.5)»: il coach è in produzione e dal 17/10 vive in `~/Projects/climb-coach`;
- deload adattivo e finestra pre-trip di 5 giorni: non esistono più (A218; taper A281 di 14 giorni).

**Cosa gli manca:** tutto ciò che decide la settimana di oggi:
- sessioni chiave con debito e risoluzione (A294/A305/A315), pavimenti di qualità (A282), slot pranzo complementari (A300/C274/C279), guard come soli alert (A301);
- base sbloccabile (A284), retest (A289/A319/A320), `anchored_load` (B364), falesia come giorno duro + dita (B372/B382), user-owned come ancore (B414);
- `docs/training/athlete_plan.md` e i finding aperti di D280.

Delle 24 decisioni KB sulla costruzione della settimana: 6 implementate, 4 parziali, 10 mancanti, 4 contraddette (frequenza dita e carico dita basso, D83 parte da 50 anni e non da 40, deload, minimi di fase D21/D44).

**File da caricare (serve il tuo OK):** `docs/ENGINE_ARCHITECTURE.md`, `backend/catalog/key_stimuli/v1/key_stimuli.json`, `docs/training/athlete_plan.md`, `docs/audit/D280_methodology_vs_literature.md`, questo file; il mirror del 12/05 va sostituito.

**Prompt per la sessione di ricerca** (da incollare nel progetto dopo l'upload):

```text
The attached files describe the climb-agent engine as of 2026-11-13. Your engine mirror from 2026-05-12 is outdated: where they disagree, the attached files win.
For each question give (1) the best evidence from 2020-2026 with full citation and what was actually measured, (2) one rule the engine could apply, with numbers and units, (3) confidence (high / medium / low) and what would change it. Write "no evidence" when there is none; flag any rule that rests on a single small study.
1. Finger-load tiers: minimum spacing between low-load finger work (aerobic hangs, IntHangs, maintenance) and max hangs / limit bouldering; how many finger-hard stimuli per week, crag days included.
2. Crag days: does a day of outdoor limit climbing count as finger-hard and against the hard-day cap; how much recovery after a 2-3 day trip.
3. Deload: is an unload needed inside an 11-14 week cycle and at what cadence; keep intensity and cut volume, or remove hard work.
4. Concurrent lunch training: interference of HIIT 4x4, Zone 2, legs and upper-push sessions with evening climbing and next-day max strength; minimum hours before a max session; should HIIT count as a hard day.
5. Hard-day cap and rest days for an advanced lead climber (8a+ redpoint) with 6-7 available days: is "max 3 hard days, at least 2 true rest days" evidence-based?
6. Age 40-49: which modifiers apply (frequency of maximal stimuli, progression rate, tendon recovery)?
7. Limit bouldering, try-hard and fall practice: weekly dose by phase; maintenance gap for limit work during the power-endurance phase.
8. Technique for a feet/positioning limiter: minutes or drills per week, and whether an outdoor day can count.
```

## 7. Repo `climb-coach` (altro repo: solo proposte)

- `regole.md:49-50`, `CLAUDE.md:51`: HIIT «mai il giorno prima» → «mai nelle 24 h prima» di una sessione massimale (B405; pranzo del giorno prima di una serale = 30 h, va bene).
- `runbook/scrivere-in-app.md:51`, `runbook/leggere-prod.md:89`: carichi da `state["working_loads"]` → solo da `anchored_load`, come dicono le regole del coach stesso.
- Runbook, riga 9: spostare/aggiungere sessioni solo via `/api/replanner/events` (dry run, `session_ref`, protezione 409), mai via `PUT /api/state`: quelle mosse non hanno marker e la rigenerazione le annulla (R7, già in roadmap come B369-P6-residui 3).
- `profilo/atleta.md`: pranzi 45' → 55' (:25); palestre senza Eifelblock, D-Summit e casa (:11); «venerdì sera riposo» (:24) contro il piano.
- `bug-inbox.md`: intestazione «Aperti (2026-10-18)»; `REENTRY_MAX_HANG_SETS` (:20) è già chiuso; i 3 aperti sono ora in roadmap (sezione D287).

## 8. Limiti di questa analisi

- Nel mirror non c'è un piano originale prima del 19/10: le settimane precedenti sono ricostruite solo dai log.
- Gli eventi non hanno timestamp né autore; il motivo di una sostituzione si deduce solo dal nome della custom.
- I verificatori non hanno eseguito pytest (vincolo di sola lettura): i test sono stati eseguiti dopo l'implementazione (suite completa verde).
- Dati di salute deliberatamente esclusi.
