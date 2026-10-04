# Piano di miglioramento — Daniele

> **Cos'è.** È il piano generale di Daniele verso l'8b, scritto per Claude Code: lo legge prima di comporre una sessione su misura (`/custom-session`).
> **Come si usa.** I dati del giorno (fase, massimali, carichi ancorati, sessioni chiave, guardie) **non stanno qui**: li stampa `python scripts/athlete_context.py`, che legge lo stato live. Questo file contiene le regole, il programma e i livelli delle scale.
> **Aggiornamento.** Lo aggiorna Claude, nello stesso brief o su richiesta di Daniele, quando un criterio di scala è raggiunto. Lo dice a Daniele e scrive la data.
> **Fonti.** Analisi del 2026-10-04: `TECH` (tecnica e try-hard), `BW` (corpo libero), `NIKITA` (progetto corrente), decisioni vincolanti in `docs/audit/D282_train_harder_phase1.md`. Le dosi senza una fonte pubblicata sono **ENGINEERING CONSTANT**.

Ultimo aggiornamento: 2026-10-04 (A293).

---

## 1. Obiettivo e limitatori

- **Obiettivo:** migliorare come scalatore, cioè chiudere l'**8b RP** oppure scalare l'**8a con margine**. Nell'engine c'è «8b RP entro il 2026-12-06». TECH propone un obiettivo a breve («un 8a chiuso in 1-3 sessioni») e l'8b in primavera 2027. È solo una proposta da fare a Daniele: la data **non si cambia senza il suo sì**.
- **Livello misurato** (i numeri del giorno li stampa lo script):
  - RP lead 8a+;
  - onsight reale 7b (Kalymnos 25-27/08: Blue Moon, Ataraxia e Meraki 7b a vista);
  - dita circa 1,49× il peso corporeo (max hang 7" su 20 mm, test del 24/09);
  - trazione circa 1,58× il peso corporeo (2RM, test del 24/09).
- **Limitatori dichiarati da Daniele, in ordine:**
  1. **tecnica di piedi**: precisione e pressione sugli appoggi piccoli;
  2. **posizionamento del corpo**: anche, flag, drop-knee, twist-lock, posizioni economiche;
  3. **try-hard**: spesso si ferma molto prima del 100%, sia per non voler cadere sia per mancanza di aggressività («rabbia»).
- **La forza continua a progredire**, anche se non è il limitatore principale. Questo prevale su NIKITA.json («solo mantenimento»): dita e trazione si allenano per diventare più forti, con i carichi ancorati e i tetti di B364. Tecnica e try-hard **sostituiscono volume**, non le chiavi di forza.

## 2. Forza: regole di progressione

**Massimale ufficiale e carico di lavoro sono due numeri diversi.**

| | Massimale ufficiale | Carico di lavoro |
|---|---|---|
| Da dove viene | `tests.*` / `baselines` | `working_loads` |
| Chi lo scrive | solo un test | il feedback |
| Cosa fa | definisce i tetti | si muove a passi di kg dentro i tetti |

Un'etichetta di feedback non tocca mai il massimale e non programma mai un test.

**Un'unica fonte per i carichi:** `anchored_load` (B364) per weighted_pullup, weighted_chinup, max_hang_5s e max_hang_7s. Lo script stampa il numero del giorno, già con tetto, pavimento, rampa di rientro, guardie, dolore e fatica.
- **Mai** copiare `working_loads` grezzi.
- **Mai** usare il 2RM come carico (errore del 04/10: 4×3 a +45 kg).
- **Mai** scrivere «oppure» fra due carichi.

**Tetti** (ENGINEERING CONSTANT):
- **Trazione:** fascia di Prilepin e (r+2)RM:
  - 4×3 non oltre circa l'85% del 1RM;
  - per lavorare al 90% cambia lo schema (3-4×2): il tetto del 4×3 non sale.
- **Sospensioni:** il tetto è il carico che si tiene per (secondi prescritti + 3 s), con un tetto di fase:
  - SP e performance 0,95;
  - PE 0,90;
  - base 0,85;
  - deload 0,70.
  Il 100% compare solo nei test.

**Rampa di rientro:** dopo uno stacco di 14 giorni o più, fattore sul tetto:
- 1ª esposizione 0,90;
- 2ª esposizione 0,95;
- dalla 3ª 1,0.

Il test conta come esposizione. Durante il rientro, max hang al massimo 5 serie.

**Passi delle etichette** (Daniele fa esattamente le ripetizioni prescritte, quindi «easy» è un segnale vero). Sempre dentro il tetto:

| Esercizio | very_easy | easy | ok | hard | very_hard |
|---|---|---|---|---|---|
| Trazione / chin-up zavorrati | +5 kg | +2,5 kg | tiene | −2,5% | −7,5% |
| Max hang | +4 kg | +2 kg | tiene | −2 kg | −4 kg |
| Accessori senza misura | +10% | +5% | — | — | — |

- **Limiti di escalation:** trazione ≤ +5 kg a seduta; dita ≤ +5% del massimale ufficiale in 7 giorni.
- **Tetto raggiunto + easy:** «sei al tetto del massimale testato, il prossimo retest lo alzerà».

**Retest:** solo la retest policy programma i test (A289).
- **Retest anticipato:** solo verso l'alto, misurato e due volte. Ultima serie di trazione con e1RM sopra il 1RM ufficiale, oppure sospensione tenuta oltre target+5 s al ≥90%.
- **Blocchi:**
  - test dita entro 72 h da un giorno dita-hard;
  - test trazione entro 48 h da una seduta di tirata pesante;
  - very_hard negli ultimi 3 giorni;
  - fase performance o deload;
  - 10 giorni o meno prima di un viaggio.

**Esercizi principali fissi per fase** (A290). In SP: max_hang_7s su 20 mm mezza arcuata e weighted_pullup. Si progredisce il carico; ruotano solo accessori e core (A/B, mai lo stesso esercizio in due sedute consecutive dello stesso tipo).

**Tirata pesante:**
- al massimo 2 sedute a ≥85% in 7 giorni, chin-up compreso;
- niente trazione ≥85% e niente front lever nelle 24 h prima di limit o strength_long.

**Più duro, in quest'ordine:** intensità (RIR 1-2) → densità → frequenza → volume.
- Mai a cedimento sulle dita.
- Al massimo 1 blocco a RIR 1.
- Domanda sul dolore a fine seduta (scala 0-3 per zona: 2 → −10% per 7 giorni, 3 → 14 giorni e proposta di limitazione).

**Fatica:** 3 sedute hard in 14 giorni → pavimento più avviso.

### Dita a tasca e mono

- Sul **mono** usa il **medio sinistro**. Con la **mano destra** tira molto **bidito e tridito**.
- **Riscaldamento specifico** prima di limit e outdoor (in testa alla seduta dita):
  - carico progressivo del medio sinistro e delle tasche a 2-3 dita della destra;
  - su tasca di trave, 3-4 sospensioni progressive (50% → 70-80%);
  - id catalogo: `hang_rampup_progressive`, poi le tasche nelle note.
- **Lavoro su tasca solo submassimale e solo su una tasca di hangboard.** Mai un mono in palestra (il simulatore è un buco a 2 dita).
- **Sorvegliare puleggia e lombricali** di quelle dita. Un fastidio alla puleggia chiude la giornata. Circa 6 carichi veri del mono per giornata outdoor (ENGINEERING CONSTANT).

## 3. Tecnica: piedi e posizione

**Principi:**
- La tecnica si allena **vicino al limite**: da flash a RP-2. A 7b a vista gli errori di piede e di posizione escono solo lì.
- Il riscaldamento non è lo stimolo tecnico.
- Mai 6b+/6C come blocco tecnico. Mai più volume come leva.
- **Una leva per volta:** piedi più piccoli → meno aggiustamenti → più ripido o posizione meno ovvia → fatica → roccia.
- Sempre **da freschi, a inizio seduta**: precisione e glued_feet mai dopo il limit.
- Circa 70% problemi nuovi o varianti, 30% ripetizione.

**Il modo preferito: il limit nello stile debole.**
- Nella chiave LIMIT, 4 problemi (o sezioni di 3-5 movimenti): 2 di potenza come sempre, e 2 scelti perché il crux è di **piedi** o di **posizione**, a RP-1/RP-2 (circa 7B+/7C).
- Sui 2 problemi tecnici vale un vincolo dichiarato prima di partire: «piede piazzato una volta sola» oppure «posizione X sul crux».
- La tecnica entra nel limit **senza aggiungere un giorno dita**.

**Drill disponibili nel catalogo oggi:**

| Blocco | Id catalogo | Dose / note |
|---|---|---|
| Riscaldamento a costo zero | `silent_feet_drill`, `foothold_stare`, `straight_arms`, `hip_rotation_drill`, `flag_practice` | 3-4 boulder in salita fino a flash −1, un focus ciascuno |
| Precisione di piedi (scala PIEDI) | `no_readjust_drill`, `sticky_feet`, `tech_hard_target`, `tech_five_step`, `tap_and_place` | 4 problemi × 2 giri a flash −1/flash; un aggiustamento = si ripete |
| Posizione (scala POSIZIONI) | `twist_lock_drill`, `flag_practice`, `tech_barn_door_2000`, `tech_hips_first`, `freeze_drill` | board 40-45° a 7A+/7B, ogni sezione in 3 modi (frontale, flag, twist/drop-knee) |
| Varianti / adattabilità | `tech_contrast_bouldering`, `three_limb_drill`, `one_hand_climbing`, `tech_single_leg_climbing` | 3 problemi àncora a flash in 4 versioni |
| Tallone | `heel_hook_specific_drill` | 2 settimane su prese grandi; stop al primo fastidio dietro il ginocchio |
| Lettura | `timed_route_preview` | Beta Forecast: 2' di lettura, sequenza ad alta voce, poi «previsto sì/no» |
| Pacing / lento | `slow_climbing`, `tech_smooth_is_fast` | deload: chiave tecnica a severità bassa |
| Limit | `limit_bouldering`, `board_limit_boulders`, `system_board_limit`, `spray_wall_limit` | il limit nello stile debole (vedi sopra) |
| Forza del piede | `single_leg_calf_raise` | 3×8-10 sul bordo, 2 volte a settimana dopo una seduta qualsiasi |

**Drill proposti ma NON ancora in catalogo** (arrivano con C271): `glued_feet_board`, `position_menu_3way`, `variant_ladder_board`, `lead_technique_under_pump`, `rest_and_clip_drill`, `vertical_small_feet_limit`, `lead_precision_feet_above_bolt`, `three_attempt_comp`, `no_take_lead_onsight`, `toe_flexor_isometric`, `edge_calf_raise_bigtoe`, `technique_benchmark_test`, `pre_attempt_routine`.

Finché non esistono:
- si usa l'id esistente più vicino;
- la regola specifica va nelle `notes` della riga. Esempio: `no_readjust_drill` con la nota «glued feet: un piede che si stacca annulla il tentativo, Kilter 40°, 3 tentativi».

**Tecnica da 8b:** riposi (kneebar, scuotere, scaricare le braccia), rinvio a braccio teso e anca dentro, ritmo costante sulla resistenza, link dal basso.
- Nelle settimane senza roccia: seduta lead in palestra con 1 regola tecnica dichiarata per via.
- Nel weekend outdoor: la regola si applica sulle vie di riscaldamento.

**Il weekend outdoor è la seduta tecnica principale:**
- riscaldamento con regola piedi (ogni piede caricato 3 s prima di muovere una mano);
- 1-2 onsight 7b-7c con Beta Forecast;
- il progetto con la mappa dei punti di impegno.

A Berdorf: volume verticale 7a-7c su piedi piccoli, scarpetta annotata, scivolate di piede per giro; solo **≥ 24 h dopo la pioggia**.

### Scale tracciate (livello corrente nel blocco note, §9)

- **PIEDI:**
  - P1: flash −1 con 1 piazzamento e 0 rumore (board 7A, verticale 7A+);
  - P2: la stessa regola a flash (7A+/7B), più glued_feet a 40°;
  - P3: la regola dentro il limit nello stile debole (RP-1/RP-2, piede tenuto al primo piazzamento sul crux);
  - P4: sotto fatica e su roccia (lead precision a OS, scivolate sul progetto).
  - **Avanza** con 2 sedute di fila a ≤ 1 aggiustamento sul problema campione. **Regredisce** con ≥ 3 aggiustamenti per 2 sedute.
- **POSIZIONI:**
  - Q1: board 40-45° a 7A+/7B con il menu a 3 versioni;
  - Q2: il menu sui crux di posizione del limit;
  - Q3: lead, rinvio a braccio teso e riposi trovati sotto pump;
  - Q4: posizione decisa a vista su roccia.
  - **Avanza** con hover di 2 s sul crux in ≥ 4 tentativi su 5 per 2 sedute (oppure regola lead rispettata su 2 vie su 2). **Regredisce** sotto il 50%.
- **CADUTE:**
  - F1: rinvio ai piedi;
  - F2: 1-2 m sopra il rinvio;
  - F3: caduta in movimento sul crux.
  - **Avanza** con paura ≤ 3 per 2 sedute. **Regredisce** dopo una caduta a paura ≥ 7.
  - Abilita il no-take da F2 e la caduta deliberata al punto di impegno da F3.

## 4. Try-hard

- **Routine fissa di 30-45 s** prima di ogni tentativo chiave (limit, gara, no-take, progetto): suole pulite → 2 respiri lenti → sequenza mimata → **una parola chiave** ad alta voce, scelta per quel crux («tallone basso», «prendilo») → «vado». Dal «vado» non si rinegozia fino al riposo successivo. Cambia la parola, non il rituale.
- **Budget di 5 tentativi per problema.** Un LET_GO (mollare) consuma un tentativo: mollare ha un costo. 3' tra i tentativi, 5' tra i problemi.
- **Regola «a oltranza»:** si scende solo cadendo in movimento. Power exhale sui movimenti duri. «One more move» solo dove la caduta è pulita sul materasso, mai sulle prese alte di Kilter/Moon, in uscita, capovolti o in torsione con una mano.
- **Nucleo settimanale** (tutte le fasi tranne il deload), un formato a scelta:
  - gara a 3 tentativi: 6-8 problemi appena sopra il flash, 2' di lettura, massimo 3 tentativi;
  - no-take: 2-3 vie da OS a OS+1, vietato chiedere corda, solo con fall ladder ≥ F2 e assicuratore abituale;
  - il limit con budget di tentativi.
  Nella settimana vanno anche le cadute (`fall_practice`, fall ladder): fase intensiva per 4-6 settimane, poi 2-3 cadute a inizio di ogni giornata lead.
- **Misura primaria = l'esito:** % di non-send chiusi in FALL rispetto a TAKE+LET_GO, più i movimenti provati dopo il punto in cui volevi fermarti. Lo sforzo 0-3 è secondario e facoltativo.
- **Se l'esito è piatto da 3 settimane:** grado −1 su gara e no-take, fall ladder giù di un gradino. Il problema è la paura, non la difficoltà. Né più volume né più grado.

## 5. Settimana tipo per fase

**Regole comuni:**
- almeno **2 giorni di riposo veri**;
- nessuna settimana con più di 3 stimoli dita-hard più l'outdoor duro;
- il riscaldamento tecnico è ovunque e non costa tempo.

La chiave TECNICA della settimana si soddisfa con una di queste:
- limit nello stile debole;
- seduta tecnica su board ≥ 30' a flash o oltre;
- giornata outdoor con le regole tecniche;
- lead con regola tecnica sotto pump.

**Base.** Seduta tecnica su board di 75' (la chiave), più la chiave di forza della fase, più gara a 3 tentativi o lead con cadute e no-take, più outdoor. Riposo martedì e venerdì.

**Strength & Power** (settimana con roccia nel weekend):

| Giorno | Contenuto |
|---|---|
| Lun | LIMIT + TECNICA (dita-hard): glued_feet 15' in apertura, 4 problemi (2 potenza + 2 stile debole), budget 5 tentativi |
| Mar | riposo |
| Mer | FINGER_MAX + PULLING_MAX a casa, 60' (lunedì sera → mercoledì sera = 48 h) |
| Gio | facoltativo: tecnica corta 40' a flash/flash+1, senza problemi ≥ RP-2 (quindi non dita-hard), più forza del piede |
| Ven | riposo |
| Sab | outdoor tecnico: riscaldamento con regola piedi, cadute di mantenimento, progetto con mappa dei punti di impegno. È il try-hard della settimana |
| Dom | outdoor leggero (verticale 7a-7b, onsight con Beta Forecast) oppure riposo |

Senza roccia: giovedì lead in palestra (cadute 10', 2 vie con regola tecnica, no-take su 2-3 vie), sabato gara a 3 tentativi.

**Power Endurance.**
- Chiave tecnica: lead con regole tecniche sotto pump vero; nei 4×4, 1 regola tecnica per serie.
- Try-hard: limit nello stile debole quando lo chiede il gap di 12 giorni, altrimenti gara a 3 tentativi; no-take ogni settimana.
- Mantenimento dita: max_hang_7s per al massimo 3 serie all'85-90%, nella stessa seduta del limit quando c'è.

**Performance.**
- Chiave tecnica: outdoor o onsight in palestra con Beta Forecast a 1-2'. Niente drill nuovi, solo applicazione.
- Chiave progetto: mappa dei punti di impegno, routine, 2-3 cadute a inizio giornata.

**Deload.** Riscaldamento tecnico e 20' di `slow_climbing` / hover a flash −2. Niente try-hard e niente cadute oltre il mantenimento.

## 6. Corpo libero e core (scale BW)

Per un atleta col suo livello, un esercizio a corpo libero a due braccia è **troppo facile**: va reso unilaterale, assistito o zavorrato. Le scale complete (con i livelli NEW) arrivano con il brief di catalogo. Qui sotto, solo gli id **già in catalogo** e il punto di partenza consigliato da BW:

| Famiglia | Livelli esistenti (dal più facile) | Partenza per Daniele |
|---|---|---|
| Compressione a terra | `core_l_sit` | L-sit 60 s misurato: straddle L-sit 3×20 s (NEW) al posto di `core_l_sit` 5×15 s |
| Compressione appesi | `hanging_leg_raise` → `knees_to_elbows` → `toes_to_bar` → `weighted_hanging_leg_raise` | `toes_to_bar` 3×6 con eccentrica di 3 s, poi 5 s, poi +1 kg alle caviglie |
| Rollout | `ab_wheel_rollout` (in ginocchio) | già oltre il criterio: ring fallout (NEW) 3×6; in piedi solo manuale (zona lombare) |
| Front lever | `front_lever_tuck` → `front_lever_one_leg` → `front_lever_straddle` | straddle 4×10 s. **Mai** nelle 24 h prima di limit/strength_long; conta come tirata pesante |
| Laterale | `side_plank` → `copenhagen_plank` | copenhagen: 2 sedute in versione corta, poi lunga 3×10 s |
| Rotazione | `windshield_wipers` | 2-3×6-12 |
| Spinta | `pushup`, `ring_pushup`, `pike_pushup`, `handstand_pushup_wall` | `ring_pushup` 3×8 |
| Femorali | `nordic_curl` | 2×4-8 |

**Budget per seduta:** al massimo `toes_to_bar` **oppure** front lever, più rollout oppure dragon flag, più eventualmente copenhagen. Non tutte le famiglie insieme. Con 2 esercizi di compressione serve un esercizio di catena posteriore (`back_extension`).

`dead_bug`, `plank`, `core_hollow_hold`, `pallof_press` e `plank_shoulder_tap` restano **solo come attivazione** e mai come blocco principale, quando esiste un'alternativa.

## 7. Registro (cosa scrivere nelle note)

- **Per tentativo chiave** (limit, gara, no-take, progetto): `T1 M7 FALL +1`, cioè tentativo, punto più alto, esito ∈ SEND | FALL | TAKE | LET_GO e movimenti provati dopo lo «stop». Lo script conta gli esiti dalle note degli outdoor delle ultime 4 settimane, finché A296 non porta il limit log.
- **Per seduta tecnica:** un solo numero, gli aggiustamenti di piede su **1 problema campione** oppure l'hover x/5 sul crux, più il livello di scala.
- **Fall ladder:** gradino F1-F3, numero di cadute, paura massima 0-10 (una volta per seduta).
- **Outdoor / progetto:** scivolate di piede per giro, scarpetta usata, esito al punto di impegno.
- Nessuna debt card per un log mancante: solo per una chiave non fatta. I log passati non si toccano.

## 8. Progetto corrente — Cima Nikita (8a, Berdorf)

È **un** progetto dentro il programma, non il suo asse. **Non si pianifica attorno alle giornate Nikita.** Non ci sono «settimane Nikita», né restrizioni di 72 h prima di Nikita, né un template settimanale dedicato. Le giornate outdoor seguono le regole outdoor generiche: outdoor-hard (tentativo ≥ RP−2 = giorno dita-hard) e condizioni (≥ 24 h dopo la pioggia).

- **Limitatori dichiarati su Nikita:** pressione sui **piedi piccoli** e la **testa**, cioè impegnarsi e provare fino in fondo.
- **Beta del 21/07:**

| Movimento | Cosa |
|---|---|
| M1 | incrocio al bidito |
| M2 | piede destro nel buco destro (di punta) |
| M3 | la sinistra aggiusta |
| M4 | piede sinistro basso al centro |
| M5 | piede destro |
| M6 | piede sinistro sul nottolino, spinta laterale |
| M7 | mono (medio sinistro) |
| M8 | piede sinistro aperto e basso, in contropressione («tiro e spingo») |
| M9 | chiusura |
| M10 | catena |

- **Sequenza piedi M2-M8** provata sulla via a corda tesa, col mono solo sfiorato. Suole pulite prima di ogni tentativo (zerbino alla base). A/B di scarpette: morbida da buco/spalmo contro rigida da tacca.
- **Registro per tentativo** (4 campi più il video): `T1 M7 piede R✓ I2 | T2 M8 mov R✓ I3`.
  - Punto più alto M1-M10 o spit.
  - Tipo di caduta: mov (in movimento) | mollato | piede | mano.
  - Routine fatta R✓/R✗.
  - Impegno I0-I3.
  Per lo script vale anche il formato generico `T1 M7 FALL +1`.
- **Sicurezza:**
  - circa 6 carichi veri del mono per giornata;
  - cadute «in lancio» solo con lo spit alla vita o sopra;
  - occhio alla caviglia in uscita da M8;
  - solo spazzole morbide;
  - segni di gesso tolti a fine giornata.

## 9. Blocco note per lo script

Il testo fra i due marcatori qui sotto è stampato da `scripts/athlete_context.py` in «Note atleta». Tienilo corto e aggiornato.

<!-- athlete-context:notes -->
Livelli scale (aggiornati 2026-10-04, partenza consigliata — da confermare alla prima seduta tracciata):
- PIEDI: P2 (flash 7A+/7B, 1 piazzamento, 0 rumore; glued_feet a 40° quando arriva C271)
- POSIZIONI: Q1 (board 40-45° a 7A+/7B, menu a 3 versioni)
- CADUTE: da valutare (prima seduta di fall_practice: F1 → F2 se paura ≤3)
Limitatori: 1) piedi 2) posizione 3) try-hard. Ogni custom non di recupero ha un blocco tecnica o try-hard con UN target misurabile.
Forza: continua a progredire (carichi SOLO da anchored_load, mai working_loads grezzi, mai il 2RM).
Tasche: mono = medio SINISTRO; bi/tridito con la DESTRA. Riscaldamento specifico su tasca di trave prima di limit/outdoor; tasche solo submassimali su hangboard, mai mono in palestra; attenzione a pulegge/lombricali.
Core: niente dead_bug/plank/plank_shoulder_tap/pallof come blocco principale; front lever mai nelle 24 h prima di limit/strength_long.
Progetto corrente: Cima Nikita 8a (Berdorf) — NON si pianifica attorno a Nikita; registro «T1 M7 piede R✓ I2».
Berdorf: solo ≥24 h dopo la pioggia.
<!-- /athlete-context:notes -->
