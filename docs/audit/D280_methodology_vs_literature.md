# D280 — La metodologia di climb-agent contro la letteratura 2022-2026 e contro il piano reale

**Data:** 2026-08-30 · **Tipo:** D (audit read-only) · **Stato:** chiuso

## Metodo

Workflow multi-agente a 4 fasi, 15 agenti, ~1,95 M token:

1. **Ricerca** — 4 agenti su WebSearch/WebFetch: forza dita/hangboard, resistenza e sistemi
   energetici, periodizzazione, tecnica/infortuni. Finestra privilegiata 2023-2026.
2. **Motore** — 3 agenti in audit read-only: macrocycle+planner, progression+closed-loop,
   assessment+resolver+catalogo.
3. **Confronto** — 3 agenti: motore vs letteratura, piano reale di Daniele vs letteratura,
   integrità del closed loop. **36 finding** prodotti.
4. **Verifica avversariale** — 5 agenti istruiti a *confutare* i 5 finding più gravi, con
   obbligo di riaprire codice e fonti. Esito: **2 scartati, 2 declassati, 1 confermato con
   correzioni**.

Sopra il workflow ho poi verificato **a mano**, eseguendo il codice e con grep mirati, i nove
punti riportati nella Parte A. Tutto ciò che in questo documento è marcato *verificato* è stato
riprodotto direttamente; il resto è marcato *non verificato* e va trattato come ipotesi.

**Lezione di metodo emersa dal round avversariale:** gli agenti di confronto hanno prodotto
citazioni misattribuite (un paper 2024 sul finger loading attribuito all'autore sbagliato, una
review sulla popolazione generale usata per sostenere una tesi sul mantenimento della forza,
una review sui determinanti di performance usata per un'affermazione sugli orizzonti temporali
che non contiene) e affermazioni di codice smentite dall'esecuzione. **Nessun finding di questo
tipo di audit va accettato senza riaprire la fonte e il file.**

---

## Verdetto in una riga

Il modello metodologico su carta è solido e in linea con la letteratura. Il problema non è
*cosa* il motore prescrive, ma che **diversi anelli del ciclo chiuso sono scritti e mai letti**:
tre campi di stato senza consumatori, una coda di re-test che sbocca solo nel planner legacy,
i pesi di dominio personalizzati e poi ignorati dal planner. Il sistema è più deterministico di
quanto sia adattivo.

---

## Parte A — Errori confermati nel codice (verificati direttamente)

### A1. ⚠️ ~~`step_grade` collassa i mezzi gradi~~ — **in gran parte errato, corretto da [[B344]] (2026-08-30)**

> **Rettifica.** La tesi centrale di questo finding è **sbagliata**. `vocabulary §2.10.1`
> documenta esplicitamente la scala a gradi interi **anche per il lead** (`lead_max_os=7c`,
> offset −2 → **7a**), la scala a lettere è condivisa fra Font e francese
> (`6a/6b/6c/7a` ≡ `6A/6B/6C/7A`), e un test blinda l'assenza del `+` in output.
> **L'aritmetica è corretta**: 7a+ → 7a → −1 → 6c è un grado intero sotto l'onsight,
> cioè l'intento documentato. Non ci sono "4 mezzi gradi" di errore.
>
> Avevo verificato l'**output** del codice ma non l'**intento** — esattamente l'errore
> contro cui questo stesso audit metteva in guardia due paragrafi sopra.
>
> **Cosa era vero e B344 ha chiuso:** il *casing*. L'output arriva alla UI in maiuscolo
> Font (`Grade: 6C` in `exercise-detail-sheet.tsx:121`, senza conversione) su una sessione
> di corda, e `6C` maiuscolo si legge come Font boulder ≈ 7a+ francese. Ora `inject_targets`
> emette `suggested.grade_scale` e il client rende con `displayPrescribedGrade`.
>
> **Cosa resta, come decisione e non come bug:** lo strip del `+` arrotonda in giù di mezzo
> grado chi ha un `+` nel grado di riferimento (7a+ → 6c invece di 6c+). Comportamento
> dichiarato dalla spec. Tracciato come `B-LEAD-HALF-GRADE-ROUNDING`.

Il testo originale del finding è conservato qui sotto perché è la prova di come si sbaglia
questo tipo di audit — non perché sia da implementare.

**Severità dichiarata all'epoca: alta · sforzo S**

```
step_grade('7a+', -1) → '6C'      step_grade('7a+', -2) → '6B'      step_grade('7a+', -5) → '5B'
step_grade('7a',  -1) → '6C'      step_grade('8a',  -1) → '7C'
```

`progression_v1.py:22-27` e `:335-346` lavorano su una scala Font a gradi **interi**, rimuovono
il `+` e ripiegano su `6C` per input non riconosciuti. La funzione è applicata anche agli
esercizi ancorati a `lead_max_os` (`:1055-1068`): `threshold_climbing` e `route_intervals`
(offset −1) e `arc_training` (offset −5).

Per Daniele (onsight 7a+) il motore prescrive quindi gli intervalli di soglia a **"6C"** —
una stringa in scala boulder, che letta come 6c francese è ~4 mezzi gradi sotto il target
inteso. Le sessioni di continuità su corda escono sistematicamente troppo facili.

L'ancoraggio all'onsight è la scelta *corretta*; è l'aritmetica che la tradisce.
`outdoor_pitch_ladder._shift` lavora già su `GRADE_ORDER` a mezzi gradi e si comporta bene —
è la funzione da riusare.

### A2. `freshness_policy` è scritta su ogni test e non letta da nessuno
**Severità: alta · sforzo M**

`{"stale_after_days": 90}` viene scritto in `progression_v1.py:1318, :1356, :1391, :1446`.
Grep su `backend/engine`, `backend/api`, `frontend/src`: **zero letture**. `confidence: "high"`
è hardcoded alla scrittura e mai rivisto.

Conseguenza su Daniele: i suoi 4 test hanno 100-166 giorni, tutti oltre la soglia dichiarata
nel dato stesso, e le prescrizioni continuano a derivarne al 100% senza alcun declassamento,
avviso o richiesta di re-test.

### A3. `test_queue` sbocca solo nel planner legacy, che non è importato da nessuno
**Severità: alta · sforzo M**

`_enqueue_test` (`progression_v1.py:1215-1224, :1528`) accoda un re-test dopo due feedback
consecutivi `hard`/`very_hard` (o `easy`/`very_easy`) sul max hang. L'unico consumatore è
`_test_candidates` / `generate_week_plan` in **`planner_v1.py:245-318`** — e `planner_v1` non
è importato da alcun modulo di `backend/engine`, `backend/api` o `frontend/src`. `planner_v2`
non legge mai `test_queue`.

L'unico meccanismo di auto-correzione che il motore ha (rimisurare quando il carico non torna)
scrive in un canale senza sbocco.

### A4. Zero è uno stato assorbente nella progressione dei carichi
**Severità: media · sforzo S**

`progression_v1.py` (ramo `external_load` bilaterale, ~:1608):

```python
base = float(used_load)
pct  = _rule_midpoint_pct(updated, feedback_label)
next_load = _round_half_step(base * (1.0 + pct))
```

Con `base = 0.0` **ogni** etichetta produce `0.0`, `very_easy` compreso. In lettura il guard è
`is not None`, non truthy, quindi lo zero si propaga invece di ricadere su un fallback.

È esattamente il `back_squat` di Daniele: `last_external_load_kg 0.0`, feedback `very_easy`,
`next_external_load_kg 0.0`, fermo dal 2026-07-30. Colpisce in particolare la famiglia prehab,
cioè l'unica con evidenza preventiva decente — un prehab che non progredisce per anni non
è prevenzione.

Nota: B288 ha reso *legittimo* uno 0 kg in input ("l'ho fatto a corpo libero"), che è giusto;
manca il caso simmetrico in uscita.

### A5. `ok` vale +2,5% per sessione ed è il default a input zero
**Severità: alta · sforzo M** — *unico finding sopravvissuto al round avversariale, con correzioni*

`DEFAULT_ADJUSTMENT_POLICY` (`progression_v1.py:167-173`) + `_rule_midpoint_pct` (`:1181-1187`)
applicano il **punto medio** del range: `very_easy` +15%, `easy` +7,5%, **`ok` +2,5%**,
`hard` −2,5%, `very_hard` −10%. Sul modello `total_load` la percentuale si applica al carico
totale peso corporeo incluso (`:1546-1559`): a 76 kg di BW e ~33 kg esterni, un +2,5% nominale
è **+8,3% reale** sul carico appeso. `inject_targets` (`:964-972`, `:1136-1150`) sovrascrive
incondizionatamente il target ancorato a `baselines.hangboard`. L'unico clamp in tutto il modulo
è `max(0.0, …)` a `:997`.

Il round avversariale ha aggiunto l'aggravante che il finding originale non vedeva:
**`ok` è il valore di default a input zero.** `frontend/src/components/training/feedback-dialog.tsx:118`
dichiara "Unrated exercises default to Ok" e `buildDialogFeedbackItems` invia
`feedback_label ?? "ok"`, `completed: true` hardcoded e il campo kg precompilato col carico
suggerito. Chi chiude la sessione senza toccare nulla firma un +2,5% su ogni carico.
Con 2 sessioni dita/settimana in `strength_power` fa **+5%/settimana composto**, contro un
tasso di adattamento osservato di ~2%/settimana (Devise 2022, 4 settimane).

E ha corretto tre punti del finding originale, da non ripetere:
- **Esistono** due mitigazioni: gate di freschezza a 60 giorni in `_best_entry` (`:555-580`) e
  `_enqueue_test` dopo 2 feedback `hard` (`:1741-1757`). Non è vero che "la correzione arriva
  solo dopo un fallimento".
- Il cap proposto contro `baselines.hangboard.max_total_load_kg` **non va implementato**: non
  morderebbe mai sugli esercizi submassimali (`HANGBOARD_DEFAULT_INTENSITY_PCT`: repeaters 0,65,
  density hangs 0,75) e quel baseline è spesso esso stesso stimato (`estimate_missing_baselines`,
  fallback 1,10×BW) — capperebbe carichi reali contro un massimale inventato.
- Mundry 2021 aggiunge +1,25 kg **a settimana dalla terza**, non per sessione, con n=8 nel
  braccio: base sottile per farne una regola generale.

**Intervento con il miglior rapporto valore/rischio:** portare `ok` a `pct_range [0.00, 0.00]`
(una riga) e introdurre un rate-limit **settimanale**, non per sessione.

### A6. I `domain_weights` sono personalizzati, mostrati e mai consumati dal planner
**Severità: alta · sforzo L**

`_adjust_domain_weights` (`macrocycle_v1.py:429`, chiamata a `:718`) modula davvero i pesi sul
profilo assessment, e `/plan` li mostra all'utente (`plan/page.tsx:326-332`). Ma in
`planner_v2.py` la variabile compare **solo** nella firma (`:635`), nel docstring (`:669`) e
nella scrittura dello snapshot di settimana (`:1666`): **non entra in alcuna decisione di
selezione**. Un commento nel file lo ammette: *"a domain weight does not guarantee a dose"*.

Precisazione doverosa: il profilo *influenza comunque* il piano attraverso la composizione del
pool (`_build_session_pool`), quindi la personalizzazione non è nulla — ma i pesi numerici che
l'utente vede sono metadato di display, non un vincolo.

### A7. Le sessioni custom e quelle del coach nascono con i tag di sicurezza a `False`
**Severità: alta · sforzo M**

`add_custom_session` (`replanner_v1.py:1491-1495`) costruisce la sessione con
`"intensity": "medium"` e `"tags": {"hard": False, "finger": False}` **hardcoded**, qualunque
cosa contenga. Il coach ad-hoc passa esattamente da lì.

I tre enforcement di sicurezza del planner — gap 48h dita, divieto di giorni hard consecutivi,
cap sui giorni hard — leggono solo quei tag. Una sessione di max hang inserita dal coach è
quindi **invisibile al gap dita**.

### A8. `recent_sessions` non ha alcun writer
**Severità: media · sforzo S**

Inizializzato a `[]` in `deps.py:42` e `onboarding.py:351`, mai scritto. Due lettori:
`adhoc_builder.py:416` (`_harmonization_note`, che emette *"You trained fingers recently — this
keeps finger load low"* e quindi **non scatta mai**) e `body_part_picker.py:453`.

La salvaguardia interna del compositore ad-hoc è scritta e inerte. È peggio di non averla:
dà falsa sicurezza a chi legge il codice.

### A9. `taper` non esiste nel motore
**Severità: alta · sforzo L**

Grep su `backend/engine`, `backend/api`: nessuna occorrenza (solo due stringhe descrittive nel
catalogo esercizi). L'unico meccanismo legato ai viaggi è `compute_pretrip_dates`
(`macrocycle_v1.py:862-890`), che marca 6 giorni `[start−5, start]` e serve al planner
(`planner_v2.py:940-941`) solo per **escludere** le sessioni hard. `trip.end_date`,
`trip.priority` e `trip.discipline` non sono letti da nessuna parte.

Contro Bosquet et al. 2007 (meta-analisi, Med Sci Sports Exerc): il taper efficace è ~2 settimane
con riduzione **esponenziale del volume del 41-60%** e **intensità e frequenza invariate**
(ES 0,72 ± 0,36). Il motore fa l'opposto: toglie intensità e lascia il volume.

---

## Parte B — Lacune metodologiche rispetto alla letteratura (non verificate a mano)

Ordinate per forza dell'evidenza. Tutte da riaprire prima di aprire un brief.

### B1. L'autoregolazione è il braccio con l'evidenza più forte, e il motore usa quello che vince meno
Network meta-analysis 2025 (J Exerc Sci Fit): sulla forza massima l'autoregolazione batte in modo
consistente il carico a percentuale fissa — SUCRA back squat **APRE 93,0% · RPE 66,8% ·
VBRT 27,0% · PBRT 13,2%**; bench press APRE 97,1% vs PBRT 15,9%.

Il motore prescrive esclusivamente percentuali fisse di un massimale registrato
(`PULLING_1RM_PCT`, `HANGBOARD_DEFAULT_INTENSITY_PCT`, `intensity_pct × max_total_load_kg`).

**APRE è essa stessa deterministica** — il carico della serie N+1 è funzione delle ripetizioni
della serie N secondo una tabella fissa — quindi è compatibile col vincolo di determinismo del
progetto. È probabilmente il singolo miglioramento metodologico con il rapporto
evidenza/compatibilità più alto disponibile.

### B2. Il carico dita a bassa intensità e alta frequenza non è modellabile: il gap 48h è binario
Gilmore, Klimek, Abrahamsson & Baar 2024 (coorte retrospettiva n=526, Sports Med Open,
10.1186/s40798-024-00793-7): il carico frequente a ~40% del massimo (piedi a terra, ~10 min di
tempo appeso, ≥3 sessioni/settimana, ≥6 h fra le sessioni) dà **+2,5%** strength:weight contro
**+3,2%** dei max hangs — e **chi fa entrambi ottiene +5,8% (d=0,79, p=0,0081)**, effetto quasi
additivo. Il gruppo che solo arrampicava: **0%**.

In `_SESSION_META` (`planner_v2.py:38-74`) il carico dita è un booleano e
`finger_gap_days = ceil(1 × recovery_multiplier)` applica le stesse 48h a `finger_aerobic_base`
(low) e a `limit_boulder_gym` (max). La combinazione meglio supportata dalla letteratura recente
è quindi **strutturalmente non pianificabile**.

Rimedio: sostituire il flag con `finger_load: high | low`, gap 48h solo fra `high`, minimo 6 h
altrove. Limite dello studio: retrospettivo, non randomizzato, carico Abrahangs non misurato,
solo 21 donne su 526.

### B3. L'intensità hangboard determina *quale* qualità migliora, e il motore ha un default unico
Devise et al. 2022 (RCT a 4 bracci, n=54, Front Sports Act Living, 10.3389/fspor.2022.862782),
4 settimane, 2 sessioni/settimana, edge 12 mm:

| intensità | protocollo | forza | stamina | endurance |
|---|---|---|---|---|
| 100% MFS | 2×6 hang da 6 s, 3 min tra hang | **+14,3%** | ns | ns |
| 80% MFS | 3× max 12 rip 10 s/6 s, 8 min tra serie | +5,9% | **+105%** | **+25%** |
| 60% MFS | 2×24 rip 10 s/6 s, 6 min tra serie | ns | +64% | +19% |

L'80% è l'opzione a spettro largo, da preferire quando il profilo è piatto o il tempo scarseggia.
La scelta dovrebbe derivare da fase × asse debole, non da un default.

**Corollario importante per la progressione (A5):** nello stesso studio il guadagno correla
**negativamente** con il livello di partenza — r = −0,56, p < 0,001, r² = 0,32 (n=42, i tre
bracci di training). Per un atleta a 1,60× BW un ciclo con +2-3% è un successo, non uno stallo.
*(Attenzione: lo studio dura 4 settimane; qualunque proiezione a 8-10 settimane è un'estrapolazione
non contenuta nel paper.)*

### B4. L'ARC promette un meccanismo che la letteratura recente non sostiene
`arc_training` (`exercises.json:2773`) prescrive 2×1200 s continui con il cue *"no rests, no
shaking out"* e la descrizione *"Primary adaptation target is capillary density and forearm
aerobic enzyme activity"*. "capillarization/capillary density" compare in 3 descrizioni
user-facing (righe 1015, 2773, 10740).

Bioengineering 2024 (n=32, NIRS + diffuse correlation spectroscopy, PMC11048441): l'adattamento
dell'avambraccio nei climber è di **delivery/riperfusione** (slope del flusso iperemico p=0,043;
picco di ossiemoglobina p=0,001, d=1,263), con **nessuna differenza nel consumo di O₂ sotto
occlusione**. Il meccanismo dichiarato è quello sbagliato, e il protocollo *senza rilascio* è
proprio quello che non allena la riperfusione.

Minimo indispensabile: riscrivere le tre descrizioni togliendo il claim di meccanismo.

### B5. La critical force non è misurata né modellata
`HANGBOARD_DEFAULT_INTENSITY_PCT` ancora ogni protocollo di resistenza a una % del max hang
(repeater 7:3 → 0,70; repeater 15:15 → 0,65; long duration → 0,55; density → 0,75). Grep su
`critical_force|w_prime|end_force`: nulla.

Esiste un mismatch documentato fra MVC e CF: allo stesso 40% MVC alcuni atleti sono sotto la
propria critical force (sostenibile) e altri sopra (esaurimento in minuti) — prescrivere la
resistenza in %MVC è fisiologicamente scorretto a livello individuale. Su corda la CF spiega da
sola ~61% della varianza del livello (CF+W' ~66%), contro il ~34% che W' spiega sul boulder.

Proposta: test all-out 4 min (7 s:3 s, edge 20 mm, half-crimp), archiviando **end-force** (media
degli ultimi 30 s), gated su redpoint ≥7a perché sotto quel livello il plateau non arriva.

### B6. La tirata in fase base è prescritta sotto la soglia di mantenimento
`PULLING_1RM_PCT[("base", …)]` = **0,55 / 0,625 / 0,70**, mentre il blocco `pulling_maintenance`
di `finger_maintenance_home.json` prescrive 2×4 con la nota *"Low volume, high intensity"* e
*"If the hangs left you tired, drop a rep — never the load"*. Il 62,5% dell'1RM a 4 ripetizioni
lascia 8-10 ripetizioni di buffer: è volume basso a intensità **bassa**, cioè né mantenimento né
stimolo. Il codice contraddice il proprio catalogo.

*Cautela:* la soglia "≥80% 1RM per mantenere" va ri-ancorata a una fonte corretta sul
mantenimento (Spiering et al. 2021) — la review 2024 sulla dose minima citata dagli agenti
riguarda la popolazione generale e l'*aumento*, non il mantenimento. Item già tracciato in
roadmap come `BASE-PULLING-INTENSITY-CAP`.

### B7. `energy_system` e `intensity_level` sono dichiarati, non derivati
`threshold_climbing` (`exercises.json:2731`) e `threshold_long_intervals` (`:2789`) hanno
**prescription_defaults identici** — 6×120 s di lavoro, 60 s di riposo, `lead_max_os` offset −1 —
ma il primo è `power_endurance` / `intensity_level: medium` e il secondo `aerobic_capacity` /
`low`. `intensity_level` è un filtro P0: due esercizi identici vengono ammessi in fasi diverse.

Baláš et al. 2021-2022 (Front Physiol, PMC8819085): il contributo dei sistemi energetici è
determinato dalla **struttura lavoro/riposo**, non dall'etichetta — test intermittente
59,9 ± 12,0% aerobico vs test continuo 28,1 ± 15,6% vs all-out 19,4 ± 8,1%.

Rimedio: derivare `energy_system` dai parametri reali con una regola esplicita e aggiungere un
test di catalogo che fallisca sulle incoerenze.

### B8. Nessun modificatore di età
Grep su `age|birth` in `progression_v1.py` e `assessment_v1.py`: nessun uso. L'unico gate
anagrafico nel planner è `target_days = min(target_days, 4)` per gli under-18.

Sopra i 40 il vincolo che conta non è ridurre il volume ma limitare il **rate** di progressione
del carico e diluire la frequenza degli stimoli massimali: il muscolo guadagna forza in 6-8
settimane, il tendine si rimodella in mesi. Da marcare esplicitamente in codice come **euristica
a evidenza debole** — su questo la letteratura specifica per arrampicatori master è sottile.

### B9. L'infortunio pregresso non è persistito
`normalize_limitations` (`resolve_session.py:337-379`) costruisce una mappa `{zona: severità}`
dallo stato **corrente** su 4 zone. Non esiste `injury_history[]`: nessuna data di esordio, di
risoluzione, nessuna persistenza. Alla risoluzione tutti gli esercizi si riaprono in blocco.

Systematic review 2023 (PMC10756908, 34 studi) e 2025 (PMC12821603): l'infortunio pregresso è
un predittore forte, con **probabilità media di re-infortunio del 63%** su 3 studi prospettici;
il **93% degli infortuni è da sovraccarico**.

### B10. Il deload non ha cadenza intra-ciclo, e `deload_factor` è dead code
*(residuo di un finding originariamente marcato "critico" e declassato a **bassa** dal round
avversariale — vedi Parte D2)*

`PHASE_ORDER` colloca un unico blocco deload terminale: lead@16 → 14 settimane di carico
consecutive; boulder@16 → 15. L'unico scarico non terminale è il pre-trip a 5 giorni;
`should_trigger_adaptive_deload` è stato rimosso da A218. `deload_factor: 0.5`
(`macrocycle_v1.py:827`, `planner_v2.py:1693`) è **scritto e mai letto** — nessun consumatore in
engine, api o frontend.

Ma: l'evidenza a favore di una cadenza 4:1 è **solo** un sondaggio di pratica auto-riportata su
powerlifter (Sports Med Open 2024, n=246), mentre le due fonti sperimentali disponibili trovano
che inserire o omettere lo scarico non cambia gli adattamenti. **Nota di roadmap, non intervento
urgente.** Il dead code va rimosso o reso effettivo in ogni caso.

---

## Parte C — Il piano reale di Daniele (stato prod, 2026-08-30)

### C1. Il livello dichiarato non è corroborato da nessun dato nell'app — *severità media*
`goal`: `current_grade 8a+ → target 8b redpoint`. `performance.current_level.sport.worked = 8a+`
(updated_at 2026-08-01).

Nei **46 log outdoor** (2026-03-15 → 2026-08-29, 5 mesi e mezzo, tutti lead) il send più duro è
un **7b+ singolo** (28/06, Berdorf) più sette 7b. Nessun send a 7c o superiore. L'8a risulta
tentato e non chiuso **26 volte** da inizio luglio; un progetto 7c+ è aperto con 16 tentativi
falliti da marzo.

Limite dell'inferenza, da rispettare: i log coprono 5,5 mesi. Il dato smentisce la **forma
attuale**, non necessariamente un 8a+ fatto in stagioni precedenti. L'affermazione difendibile è
*"grado dichiarato ≠ grado confermato dai log"*, non *"il grado dichiarato è falso"*.

Difetto di sistema, ristretto e reale: `_validate_goal` (`macrocycle_v1.py:597-629`) valida solo
il gap target−current (warning se >8 mezzi gradi; qui il gap è 1) e **nessun modulo di
assessment/macrociclo/planner legge mai `outdoor_log`**. L'engine non ha modo di accorgersene.

**Ciò che il round avversariale ha smentito, e che non va ripetuto:** l'idea che il target 8b
gonfi l'assessment. Ricalcolando `compute_assessment_profile` sui dati reali variando il target,
`finger_strength = 100` con 8b, 8a+, 8a, 7c+ **e** 7c: l'asse è saturo a prescindere. Il
meccanismo è invertito — un target più alto alza il benchmark e *abbassa* il punteggio;
correggere a 8a porterebbe pulling 96→100 e PE 70→79. E rigenerando il macrociclo con goal
8a/7c invece di 8b/8a+ la **struttura delle fasi è identica** e i `domain_weights` cambiano di
~1 punto percentuale. Il piano è di fatto insensibile alla correzione.

Azione proporzionata: allineare il dato o separare esplicitamente "dichiarato" e "confermato dai
log", per onestà del report — **non** aspettandosi che cambi il piano generato.

### C2. Il trip a Kalymnos: nessun taper, nessun mantenimento, nessun rientro — *severità alta*
Trip 2026-08-20 → 2026-09-06, priority high, lead. I week plan del 24/08 e 31/08 hanno
`load 0, hard_days 0, recovery_days 7` con un solo `flexibility_full` mai svolto. Nel frattempo
i log mostrano **7 giornate di falesia in 10 giorni** (21-22-23 consecutivi, 25-26-27
consecutivi, 29) con 7a/7a+/7b sent e tentativi su 8a.

Un giorno i cui slot sono tutti `outdoor` diventa `day_has_available_slot=False`
(`planner_v2.py:830-840`) ed è emesso con `sessions: []`. Il riepilogo poi conta
`recovery_days_count` come *"giorno senza sessioni o tutte low"* (`:1652-1655`): **un giorno di
falesia conta come giorno di recupero.**

Precisazione dal round avversariale: l'outdoor **non** è del tutto invisibile —
`_sync_plan_after_outdoor_log` (B273/B343) marca il giorno `done` via evento `complete_outdoor`,
scrive `outdoor_load_score` e applica il ripple sul giorno dopo, e `report_engine.py:281-282`
somma quel carico nel report settimanale. Quello che l'outdoor **non** fa è alimentare
`stimulus_recency`, `working_loads` e i gap di sicurezza dita.

Cosa manca, con numeri: taper 2 settimane pre-trip (volume ×0,6 poi ×0,4, intensità e giorni
invariati); mantenimento in trip senza attrezzatura (Javorský & Saeterbakken 2023, crossover
n=13, 5 settimane: 2 sessioni/settimana non esaustive, 6×6 rip in 7 s:3 s a ~60% MVC,
36-72 contrazioni/settimana bastano a mantenere MVC, critical force e impulso di forza);
rientro con volume ridotto e re-test.

### C3. Tutti e 4 i test scaduti, prescrizioni invariate — *severità alta*
max hang 5 s 2026-03-17 (166 gg), repeater 7:3 2026-03-19 (164 gg), max hang 7 s 2026-05-19
(103 gg), weighted pullup 2RM 2026-05-22 (100 gg). Tutti oltre i 90 giorni dichiarati nel dato.
Conseguenza diretta di **A2**: la soglia esiste solo come stringa.

### C4. Metà del peso della fase di forza va agli assi saturi — *severità alta, non verificato*
Profilo: finger 100, pulling 96, PE 53, endurance 51, technique 30. La fase `strength_power`
assegna finger .294 + pull .202 = **0,496**. In numeri reali: max hang 122 kg / 76 = **1,61× BW**;
weighted pull-up 1RM 127,8 / 76 = **1,68× BW**.

Su corda il discriminante è la soglia metabolica, non il picco (CF ~61% della varianza del
livello su via). Per un obiettivo di resistenza tipo Kalymnos, forza dita e tirata andrebbero in
**mantenimento** (dose minima: 1 sessione/settimana, 1-2 serie pesanti per pattern) liberando
peso per PE e volume su corda.

⚠️ **Ma questo finding è in larga parte neutralizzato da A6**: i `domain_weights` non sono letti
dal planner. Riequilibrarli non cambierebbe nulla finché non diventano un vincolo effettivo.
L'ordine corretto degli interventi è **prima A6, poi C4**.

### C5. Struttura settimanale: 7 sere su 7 e nessun riposo imposto — *non verificato*
Disponibilità 7/7 evening. Il planner cappa a 4 giorni e 3 hard, ma ordina i giorni in PASS 1
mettendo prima quelli con palestra, non cronologicamente, e i controlli di gap in PASS 1
userebbero una differenza **con segno** sull'ultimo offset invece di `abs()`. Da verificare
prima di aprire un brief.

Osservazione fattuale indipendente dal codice: 12-13-14 agosto, **tre giorni consecutivi** di
vie lunghe, 7 tiri e 480 min al giorno. Nessun meccanismo del sistema può accorgersene, perché
il carico outdoor non alimenta né recency né fatica.

### C6. Età 40 — vedi B8
Il parametro da cambiare è il rate di progressione e la spaziatura, non il volume.

---

## Parte D — Finding scartati o ridimensionati (da NON riaprire)

Questa sezione esiste per evitare re-investigazione. Sono tutte tesi che un agente ha prodotto
con sicurezza e che la verifica ha demolito.

### D1. ❌ "Il macrociclo finisce il 06/09 ma la deadline è il 24/10: 7 settimane di picco perse" — **SCARTATO**
`goal.deadline` **non è una data-evento**: è un campo **derivato**. L'utente non inserisce mai
una data, inserisce una durata. `deadline-weeks-selector.tsx` è uno slider *"Plan duration
(weeks)"* con `computeEndDateIso(weeks) = today + weeks*7`. `goal-editor.tsx:150-153` porta il
commento letterale *"A218: total_weeks is the source of truth; deadline is a derived display
string"*.

Aritmetica che chiude il caso: `goal.total_weeks = 12`; 2026-10-24 − 12 settimane =
**2026-08-01**, esattamente `performance.current_level.updated_at`. Il 1° agosto Daniele ha
mosso lo slider su 12 settimane e l'app ha scritto "deadline 24 ottobre". Non esiste alcun
obiettivo il 24/10: nessun trip, nessuna gara.

Il meccanismo per gli eventi reali è `trips[]`, e **ha funzionato**: PE alle settimane 7-9
(06/07→26/07), performance alle 10-12 (27/07→16/08), `macrocycle.end_date` = **2026-09-06** =
ultimo giorno di Kalymnos.

**Residuo reale, severità bassa (igiene del dato):** `goal.total_weeks` = 12 contro
`macrocycle.total_weeks` = 16, perché `/api/macrocycle/generate` con `from_phase="current"`
rilegge `old_mc["total_weeks"]` (`macrocycle.py:91`) — cioè lo slider "Plan duration" **non ha
effetto sul ciclo in corso**, e `/settings` mostra una "deadline" che non corrisponde a nulla.
Rimedio: rinominare in `plan_end_date` e far sì che modificare `total_weeks` o rigeneri davvero
o dica che non lo farà.

### D2. ❌ "Il deload azzera l'intensità e fa perdere forza" — **declassato da critica a bassa**
Da ritirare: *"tirata al 52,5% dell'1RM in deload"* — **non accade mai**. In una settimana di
deload non entra alcuna sessione di tirata: `planner_v2.py:1338-1340` esenta esplicitamente il
deload dalla garanzia pulling (*"KB: zero pulling in a deload week is correct"*).
`PULLING_1RM_PCT[("deload", …)] = 0,525` è codice morto su quel percorso.

Da ritirare anche: *"il pool si riduce a regeneration/flexibility/yoga/prehab"* — sono 7 sessioni
(incluse `easy_climbing_deload` e `finger_aerobic_base`), e la settimana generata dà 4 sessioni
su 4 giorni distinti: la frequenza **non** collassa.

Da respingere la raccomandazione di alzare `PHASE_INTENSITY_CAP['deload']` a `'high'`:
contraddice la fonte principale del finding stesso (83,7% degli atleti riduce l'intensità sui
multiarticolari in scarico) e si appoggiava a una citazione mal attribuita.

Residuo → **B10**.

### D3. ❌ "L'aderenza al piano è di fatto zero" — **falso**
`session_completion_log`: **87 done, 11 skipped** su 98. Dal 30/06: **23 done, 8 skipped**. Il
blocco di skip è concentrato in **una settimana** (24-29 luglio), non due mesi. Giugno è quasi
interamente `done` (route_endurance, limit_boulder, power_contact, technique_focus,
finger_strength_home).

### D4. ❌ "Solo 7 feedback su 98 completamenti" — **misread**
`feedback_log` è un **buffer rotante di 7 per design**: `append_feedback_log`
(`adaptive_replan.py:150`) fa `feedback_log.sort(...); del feedback_log[7:]`. Il conteggio non
dice nulla sulla frequenza dei feedback.

*(Nota: entrambe queste due cifre erano finite nel mio riassunto di scouting prima della verifica.
Sono sbagliate.)*

### D5. ⚠️ "fatigue_proxy e stimulus_recency sono campi morti" — **vero, ma impatto molto minore**
Confermato: `apply_day_result_to_user_state` (`closed_loop_v1.py:117`) ha un unico call site
(`feedback.py:221`) dietro il gate `if req.resolved_day …`, e **nessun client invia
`resolved_day`** (verificato su tutto `frontend/src`).

Ma nessun modulo del motore li legge: grep su `planner_v2`, `progression_v1`, `resolve_session`,
`replanner_v1`, `macrocycle_v1` → **zero occorrenze**. Gli unici consumatori sono
`report_engine._build_stimulus_balance` (il campo `days_since_last` resta `null`, quindi la riga
"Nd since last" del report non compare mai) e `body_part_picker._recent_recency_groups` (inerte
su dict vuoto). **Nessuna progressione, nessun carico e nessun piano sono compromessi.**

Osservazione collaterale: `unmet_stimulus` (`planner_v2.py:1703`) non è consumato da alcun
componente frontend — segnale calcolato e mai mostrato.

Azione proporzionata: o si collega il writer a un percorso che gira davvero, o si **rimuove** il
campo morto. Lasciarlo è la scelta peggiore: la doc dichiara "closed-loop" come principio non
negoziabile mentre due dei suoi contatori non si scrivono mai.

---

## Parte E — Brief proposti, in ordine

| # | Brief | Contenuto | Sforzo |
|---|---|---|---|
| 1 | **B: `ok` neutro + rate-limit** | `ok` → `[0.00, 0.00]`; rate-limit settimanale sul totale per esercizio dita; rivedere `completed: true` hardcoded in `buildDialogFeedbackItems`. **Non** implementare il cap contro `baselines.hangboard`. (A5) | S/M |
| 2 | **B: `step_grade` a mezzi gradi** | `step_lead_grade` sulla scala francese per tutti gli esercizi `grade_ref` lead, riusando `outdoor_pitch_ladder._shift`. (A1) | S |
| 3 | **B: zero assorbente** | `max(step_minimo, base × pct)`; `base == 0` → nessuna memoria utilizzabile, non propagare lo zero. Test: da 0 kg con `very_easy` il carico **deve** salire. (A4) | S |
| 4 | **B: tag di sicurezza sulle custom** | Derivare `tags.hard/finger` e `intensity` dal contenuto della sessione all'inserimento. (A7) | M |
| 5 | **B: canali morti** | Rendere operativa `freshness_policy` (declassare confidence, marcare `load_source: stale_baseline`, sospendere la progressione); far leggere `test_queue` a `planner_v2` PASS 3 **o** eliminare `_enqueue_test`; decidere su `recent_sessions`, `fatigue_proxy`/`stimulus_recency`, `unmet_stimulus`, `deload_factor` — collegare o rimuovere. (A2, A3, A8, D5, B10) | M |
| 6 | **A: trip di prima classe** | Leggere `end_date` e `priority`; taper 2 settimane (volume ×0,6/×0,4, intensità invariata); sessione di mantenimento in trip senza attrezzatura; non contare un `outdoor_slot` come `recovery_day`; `logged_load` distinto da `planned_load`. (A9, C2) | L |
| 7 | **A: domain_weights come vincolo** | Da metadato a validazione post-generazione: distribuzione entro ±0,10 dai pesi di fase, e nessuna delle tre qualità a zero in una settimana. Prerequisito di C4. (A6) | L |
| 8 | **A: autoregolazione APRE** | Tabella APRE deterministica al posto della % fissa sul massimale. Il singolo cambiamento metodologico con l'evidenza più forte. (B1) | L |
| 9 | **C: catalogo** | Togliere il claim "capillary density" dalle 3 descrizioni; derivare `energy_system` dai parametri con test di coerenza; aggiungere il blocco low-load/high-frequency dita. (B2, B4, B7) | M |

Prima di aprire 6-9: riverificare le fonti. Il round avversariale ha trovato citazioni
misattribuite in tre finding su cinque.

---

## Fonti principali raccolte (da riverificare individualmente)

- Gilmore, Klimek, Abrahamsson & Baar 2024 — *Effects of Different Loading Programs on Finger
  Strength in Rock Climbers*, Sports Medicine - Open, 10.1186/s40798-024-00793-7 (n=526,
  retrospettivo)
- Devise et al. 2022 — *Effects of Different Hangboard Training Intensities…*, Front Sports Act
  Living, 10.3389/fspor.2022.862782 (RCT n=54, 4 settimane)
- Mundry, Steinmetz, Schöffl, Saul 2021 — *Hangboard training in advanced climbers*, Sci Rep
  11:13530 (RCT n=27, 8 settimane)
- Hermans, Saeterbakken, Vereide, Stien, Andersen 2022 — *The Effects of 10 Weeks Hangboard
  Training…* (RCT n=35)
- Saeterbakken et al. 2024 — Front Physiol 10.3389/fphys.2024.1461820 (RCT n=31, forza dinamica
  dita, nessun transfer su performance boulder)
- Javorský & Saeterbakken 2023 — mantenimento con 2 sessioni/settimana non esaustive
  (crossover n=13)
- Baláš et al. 2021-2022 — Front Physiol PMC8819085 (contributo dei sistemi energetici per
  struttura lavoro/riposo)
- Bioengineering 2024 — PMC11048441 (NIRS + DCS, n=32: delivery/riperfusione, non consumo di O₂)
- Bosquet et al. 2007 — Med Sci Sports Exerc, meta-analisi taper (27/182 studi)
- Network meta-analysis 2025 — J Exerc Sci Fit, PubMed 40791980 (APRE vs PBRT)
- Pérez-Cordero et al. 2025 — review sistematica affidabilità test dita (15 studi, 747
  partecipanti; ICC mediano 0,86)
- Systematic review 2023 PMC10756908 / 2025 PMC12821603 — epidemiologia infortuni, 93% da
  sovraccarico, re-infortunio 63%
- Bell et al. 2024 — Sports Medicine - Open 10.1186/s40798-024-00691-y (sondaggio deload, n=246
  — **evidenza livello 5, non arrampicatori**)

**Da NON citare** (misattribuite dagli agenti e corrette in verifica): Faggian 2025 per gli
orizzonti temporali di intervento (la review riguarda determinanti di performance e validità dei
test); PMC11127831 per il mantenimento della forza (è sulla popolazione generale e sull'*aumento*);
Kaufmann et al. 2024 PLOS ONE per la superiorità dell'on-the-wall (conclude l'opposto: *"climbers
should rely on personal training preferences"*).
