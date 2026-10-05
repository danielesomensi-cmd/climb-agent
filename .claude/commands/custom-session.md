---
description: Componi una sessione custom per Daniele (o "fammi un allenamento", "sessione su misura", "mettila nell'app") partendo dallo stato live — mai a memoria.
---

# /custom-session — sessione su misura per Daniele

Questa è la **fonte unica** delle regole per comporre le sessioni custom di Daniele.

- Le costanti (gap dita, blocchi dei test, tetto della tirata pesante) **non si ricopiano qui**: le stampa lo script, importandole da `backend/engine/athlete_context.py`.
- Il programma (obiettivo, limitatori, scale, try-hard, settimane tipo, tasche, progetto corrente) sta in `docs/training/athlete_plan.md`.
- Le scale (16 famiglie a corpo libero, PIEDI / POSIZIONI / CADUTE) e i protocolli (`limit_weak_style`, `template_warmup`, `outdoor_technique_day`, `pocket_warmup`) stanno in `backend/catalog/progressions/v1/bw_ladders.json` (C272).

Richiesta dell'utente: $ARGUMENTS

## 1. Leggi lo stato live, SEMPRE prima di proporre

```bash
source .venv/bin/activate && python scripts/athlete_context.py            # oggi
python scripts/athlete_context.py --date YYYY-MM-DD                        # se la sessione è per un altro giorno
```

- Legge Supabase in sola lettura, a ogni lancio, e stampa l'età dello stato.
- Se fallisce, **ti fermi** e lo dici: non componi a memoria.
- Leggi anche `docs/training/athlete_plan.md` (almeno §2-§5). Il blocco «Note atleta» con i livelli delle scale e le tasche lo stampa già lo script.

## 2. Decidi COSA fare, prima del come

- **Sessioni chiave della settimana** (sezione dello script):
  - se manca uno stimolo chiave, proponi di farlo **dentro una sessione esistente** (per esempio 3 hang in testa al limit dello stesso giorno: dita prima, poi il limit), oppure **al posto** di una sessione a priorità più bassa;
  - mai aggiungere un giorno dita in più;
  - mai riportare debito dalle settimane passate: uno stimolo saltato la settimana scorsa è perso;
  - mai risolvere un conflitto togliendo la sessione chiave.
- **Guardie** (sezione «Guardie», giorno per giorno). Ogni riga deve rispettare:
  - `NO dita max` → niente hang massimali, limit, campus o tasche dure quel giorno. Lavoro dita solo se il giorno è **già** dita-hard e la riga va dentro quella seduta. La riga tiene conto anche dello spacing del replanner (sessioni con tag dita entro `ceil(recovery_multiplier)` giorni, finger_maintenance compresa), del cap hard della settimana e del deload;
  - `NO tirata ≥85%` → niente trazione zavorrata pesante né front lever (finestra mobile di 7 giorni, giorni già pianificati compresi; vale anche il giorno prima di limit/strength_long);
  - `NO HIIT` → niente HIIT lo stesso giorno o il giorno prima di una sessione max;
  - giorni hard della settimana rispetto al cap (in deload il cap può essere 0).
  - Avvisi `HIIT_ON_GUARD_DAY` / `WORK_RECURRENCE_PHASE_CHANGE`: le ricorrenze «Work —» di Daniele vanno riviste (spostate o rese Z2) e proposte a lui, non ignorate.
- Uno stimolo chiave `NOT_DUE` (per esempio il limit in PE dentro il gap di 12 giorni) **non** si aggiunge.
- **Retest:** decide la retest policy (sezione «Retest»). Non si sposta e non si aggiunge un test a mano. Si riporta la riga «ufficiale / lavoro / prossimo test».
- **Ogni sessione non di puro recupero** contiene un **blocco tecnica** (piedi o posizione, drill id + livello di scala) **oppure** un **blocco try-hard**, con **UN target misurabile** nelle note. I drill e la loro misura li stampa lo script («Libreria tecnica / try-hard»); il livello di scala corrente sta nelle «Note atleta». Esempi: «campione ≤1 aggiustamento», «hover 2 s 4/5», «non-send chiusi in FALL», «F2, paura ≤3». La tecnica va fatta da freschi, a inizio seduta, vicino al limite (flash..RP-2): mai dopo il limit, mai 6b+/6C.
- **La forza continua a progredire:** non togliere né ridurre finger_max, pulling_max e limit per far posto ad altro. Tecnica e try-hard sostituiscono volume.

## 3. Componi

1. **Carichi degli esercizi ancorati** (weighted_pullup, weighted_chinup, max_hang_5s/7s):
   - la sezione «Carichi ancorati oggi» vale **solo per lo schema che stampa** (serie×ripetizioni del catalogo, per esempio 4×3 trazioni, 5 hang);
   - con un altro schema (3×5, 3×2, 4 hang...) il carico è diverso: lancia la simulazione (§4) e prendi il numero dalla riga **«carico al play»**, che lo ricalcola sullo schema della bozza;
   - nota di calcolo nella riga, copiata dalla riga «carico al play» (o dalla sezione, se lo schema è lo stesso): «+X kg = Y% di Z kg (1RM/massimale), test gg/mm, rientro n/N». Mai un numero che il player non prescriverebbe;
   - nel payload: `load_kg` = carico **aggiunto** ≥ 0 (per l'assistito 0 + nota) e `load_mode` lasciato `anchored`, così il player ricalcola il giorno in cui si gioca;
   - mai `working_loads` grezzi, mai il 2RM, mai «oppure».
2. **Gli anchor entrano in una custom solo se tutte e tre:**
   - (a) lo stimolo non è già fatto nella settimana;
   - (b) le guardie lo permettono;
   - (c) nessuna sessione di catalogo pianificata nella settimana porta lo stesso stimolo.
   Altrimenti la custom resta senza dita e senza tirata massimale.
3. **Per ogni riga** controlla nel catalogo (`backend/catalog/exercises/v1/exercises.json`) `description`, `cues`, `load_model` e `prescription_defaults`. Le tue note non li contraddicono. Calibra sul suo livello misurato: un esercizio a corpo libero a due braccia per lui è troppo facile, quindi lo rendi unilaterale, assistito o zavorrato.
4. **Solo id esistenti nel catalogo.** Dal C272 ci sono anche gli id con role `library` (drill tecnica / try-hard / tasche: `glued_feet_board`, `position_menu_3way`, `three_attempt_comp`, `fall_ladder`, `pocket_rampup_hangboard`…) e `ladder` (livelli delle scale a corpo libero): il motore non li sceglie mai da solo, ma in una custom si usano come qualsiasi altro id. Per un drill con `grade_ref` il grado lo calcola il player; la regola specifica (vincolo, target) va nelle `notes`.
5. **Più duro, in quest'ordine:** intensità (RIR 1-2) → densità → frequenza → volume. Mai a cedimento sulle dita, al massimo 1 blocco a RIR 1, domanda sul dolore (0-3 per zona) a fine seduta.
6. **Core e corpo libero dalla scala:** per ogni famiglia usa il **livello e la dose** della sezione «Scale corpo libero» dello script (seed in sola lettura: storico −1 passo, oppure test L-sit). Se la riga dice «IN CIMA ALLA BANDA», proponi a Daniele il passo terminale o il livello successivo, non decidere da solo. «SOLO MANUALE» = livello lombare, solo se lo chiede lui. Atleta non testato o famiglia senza dati: dose del catalogo.
   - Il front lever solo senza tirata massimale nelle 24 h dopo.
   - `dead_bug`, `plank`, `plank_shoulder_tap`, `pallof_press`, `core_hollow_hold` al massimo come attivazione.
   - Budget: `toes_to_bar` **oppure** front lever, più rollout, più eventualmente copenhagen.
7. **Accessori a rotazione A/B:** guarda «Varietà» e ruota fuori i gruppi «usati troppo».
8. **Struttura:**
   - riscaldamento specifico 10-12', con riscaldamento tasche prima di limit o outdoor (protocollo `pocket_warmup`: `hang_rampup_progressive` → `pocket_rampup_hangboard` bi/tridito destra → `single_finger_pocket_rampup` medio sinistro, piedi appoggiati);
   - 1-2 blocchi principali;
   - ≤ 2 accessori;
   - 3' di chiusura.
   Con falesia il giorno dopo si tagliano le serie, non l'intensità.
9. **Vincoli del payload** (`CustomSessionExerciseEntry`): ≤ 30 esercizi, `sets` 1-20, `reps` 1-100, `work_seconds` 1-3600, `load_kg` 0-200, `notes` ≤ 1000 caratteri (in italiano). Il catalogo resta in inglese.

## 4. Simula, mostra l'anteprima, aspetta l'OK

```bash
python scripts/athlete_context.py --simulate bozza.json --target-date YYYY-MM-DD --slot evening [--replace]
```

`bozza.json` = il body di `POST /api/custom-session` (`{"name": ..., "exercises": [...]}`), salvato nello scratchpad.

- Se una sessione **CHIAVE** viene declassata, cambi giorno o contenuto e risimuli. Non si scrive.
- Una collisione di slot si risolve con `--replace`, solo su una sessione non chiave.
- Mostra a Daniele l'anteprima: righe, carichi con nota di calcolo, target misurabile, cosa cambia nel piano. **Aspetta l'OK esplicito**, anche se ha detto «mettila nell'app».

## 5. Scrivi (solo dopo l'OK)

1. `POST /api/custom-session` risponde **201**: non rilanciare, duplicheresti la sessione.
2. In una chiamata **separata**: `POST /api/replanner/events` con `remove_session` (se serve) + `add_custom_session`. Il router legge `custom_sessions` prima degli eventi.
3. Auth: Clerk prod (memoria `reference_prod_user_debug`). Il JWT dura circa 60 s: rigeneralo ogni circa 12 chiamate.
4. Mai `add_generated_session` per esercizi del catalogo. Mai usarlo per spostare un test: per quello si usa `PUT /api/state` sul `week_plans[<lunedì>]`.
5. Rileggi il piano (rilancia lo script): le sessioni chiave ci sono ancora, la custom è dove deve essere.

## Errori già fatti (non ripeterli)

- 30/09: Minimum Edge Hang con zavorra. È a corpo libero sulla tacca minima.
- 02/10: bloccaggi a due braccia a corpo libero, troppo facili, e a braccio chiuso, che il catalogo vieta.
- 04/10: trazioni 4×3 a +45 kg = il suo 2RM. Il carico va solo da `anchored_load`.
