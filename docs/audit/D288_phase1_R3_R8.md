# D288 — Fase 1: R3 (deload con una dose per stimolo chiave) e R8 (tecnica outdoor solo con target registrato)

> **Data:** 2026-11-13 · **Tipo:** D (analisi di Fase 1, sola lettura: nessun codice cambiato, nessuna scrittura in prod)
> **Fonte:** `docs/audit/D288_kb_research_r1_r8.md` §Q3 e §Q8; decisioni di Daniele del 2026-11-13; codice di `origin/main` (worktree `climb-agent-d288`, HEAD `f1a01baa`); stato di prod dal mirror del 13/11 (`climb-state-mirror/data/*_latest.json`), letto e simulato **in memoria** (storage sostituito, nessuna scrittura; script nello scratchpad della sessione, non committati).
> **Stato:** **STOP.** R3 tocca `planner_v2.py` e `macrocycle_v1.py`, più il ciclo chiuso dei carichi ancorati (`anchored_load.py`, B364: non è nell'elenco di CLAUDE.md, ma scrive `working_loads` e lo tratto come STOP). La Fase 2 parte solo dopo l'OK di Daniele. R8 non tocca moduli STOP, ma cambia lo schema del log outdoor.
> **Decisioni applicate (Daniele, 13/11):**
> - **R3 accettata:** il deload tiene un'esposizione a basso volume per ogni stimolo chiave, invece di togliere tutto il lavoro duro. La forma:
>   - stessi giorni di arrampicata;
>   - serie × 0,5;
>   - un'esposizione dita di 2-3 serie al carico di lavoro di fase −10 %, con ≥ 3 s di riserva;
>   - una seduta corta di limit o di tecnica a livello flash;
>   - niente PE, test o cedimento;
>   - nessuno scarico a calendario dentro il ciclo; la settimana ridotta su trigger va proposta come avviso, mai applicata da sola (A301/B369).
> - **R8 accettata:** un giorno outdoor conta per la chiave tecnica **solo** con un target tecnico misurabile registrato.
> - Dove questo file e le decisioni non sono d'accordo, vincono le decisioni.

## 0. In breve

- **Il deload oggi è il modello «stop al lavoro duro».** Nella settimana di deload entrano solo sessioni `low`:
  - hard cap 0;
  - `apply_deload_week` toglie tutto ciò che è `hard` e tiene al massimo 5 sedute;
  - a Daniele restano **2 sere di arrampicata su 6**: una facile e una di rigenerazione.
- **Il tetto deload dei max hang (0,70) è incompatibile con R3.**
  - Per Daniele il «carico di fase −10 %» vale **99 kg (+21 kg)**.
  - Oggi in deload il tetto lo porterebbe a 81 kg (+3 kg).
  - R3 supera la tabella dei tetti di D282 §6 per il deload.
- **La forma va scritta nel codice del planner, non nel pool del macrociclo.**
  - `session_pool` e `intensity_cap: low` sono salvati dentro `user_state.macrocycle.phases[]`, e il router passa quella copia.
  - Una modifica a `_SESSION_POOL["deload"]` o a `PHASE_INTENSITY_CAP` non raggiungerebbe il macrociclo di Daniele.
- **La settimana del 30/11 di Daniele non cambia da sola.** È in cache (rev. 6, generata il 04/11).
  - La simulazione col codice attuale dà la stessa settimana.
  - R3 si vede solo se quella settimana viene rigenerata: script una tantum, con dry run e OK.
- **Il trigger della settimana ridotta per Daniele non sarebbe mai scattato:** 0 `very_hard` su 175 sedute registrate, nessun blocco dolore. L'avviso costa poco ma parlerà di rado.
- **R8 è piccola:**
  - un campo facoltativo `technique_target` nel log outdoor;
  - nessun endpoint nuovo;
  - una regola in `key_sessions_v1`, che ha già il ramo `outdoor_counts`, oggi morto perché nessuna riga del catalogo lo usa.
  - Il coach può scriverlo subito, con il `POST`/`PUT /api/outdoor/log` che usa già; la UI è un passo separato con preview Vercel.

---

## 1. R3 — il deload

### 1.1 Dove vive oggi

| Pezzo | Dove | Cosa fa oggi |
|---|---|---|
| Fase terminale unica | `macrocycle_v1.py:19` (`PHASE_ORDER`) | Il deload è sempre l'ultima fase. |
| Durata del deload | `macrocycle_v1.py:259-270` (lead), `:304-315` (boulder) | Default 1 settimana, minimo 1, massimo 2: il surplus può dargli la seconda (`:283-285`, `:318-320`). |
| Pool di sessioni | `macrocycle_v1.py:144-152` (lead), `:224-232` (boulder) | `regeneration_easy`, `flexibility_full`, `yoga_recovery`, `prehab_maintenance` primary; `easy_climbing_deload`, `deload_recovery`, `finger_aerobic_base` available. |
| Tetto d'intensità | `macrocycle_v1.py:50` | `PHASE_INTENSITY_CAP["deload"] = "low"`. |
| Copia salvata nel macrociclo | `macrocycle_v1.py:822-833` | `generate_macrocycle` copia pool e tetto dentro `phases[]`. |
| Lettura della copia | `deps.py:649-651` → `week.py:872-882` | Il router passa **la copia salvata** al planner. |
| Note e costante di pool | `macrocycle_v1.py:880`, `:889` | La nota «Volume -50%… easy climbing only»; `DELOAD_SESSION_POOL` lo legge solo un test. |
| `apply_deload_week` | `macrocycle_v1.py:892-926` | Scorre i giorni e toglie ogni sessione con `tags.hard` (`:913-914`). Tiene le prime 5 delle altre (B160c, `:911-912`). Imposta `phase = deload` e `targets = {hard_days: 0, finger_days: 0}` (`:924`). Non sostituisce niente: la docstring dice il contrario. |
| Planner: tetti e passate di riempimento | `planner_v2.py:1533-1534`, `:1536-1544`, `:1954-2090`, `:2200-2249` | Hard cap 0. Il filtro d'intensità lascia passare solo `low`. PASS 1 piazza l'unica sessione di arrampicata `low`, `easy_climbing_deload`, con `max_per_week` = 1 di default (`:70`, `:1993-1996`). PASS 2 riempie i giorni target con sedute di recupero. |
| Planner: passate disattivate in deload | `planner_v2.py:2537`, `:2593-2595`, `:981-982`, `:128-132` | Pavimento dita (PASS 2.5) e pavimento tirata (PASS 2.6) spenti; nessun pavimento chiave (PASS 2.7); nessun test (`_PHASE_TEST_MAP`). |
| Planner: trasformazione finale | `planner_v2.py:3664-3679` | `apply_deload_week` e riepilogo del carico. |
| Planner: pranzi | `planner_v2.py:3681-3703`, `complementary_v1.py:91-92` | I pranzi A300 si aggiungono dopo la trasformazione; HIIT → Z2. |
| Resolver: serie | `resolve_session.py:78-108`, `:1508-1519` | `deload_sets` (A312) esiste solo su 20 blocchi di 5 pranzi: è l'unico «meno serie» del deload. |
| Resolver: campo morto | `resolve_session.py:2490-2494` | `force_deload_reason` (B38) viene scritto e nessuno lo legge. |
| Scale corpo libero | `bw_progression.py:71-74` | Congelate: una serie in meno (minimo 2), niente promozioni. |
| Carichi ancorati: costanti | `anchored_load.py:119-133` | Max hang in deload: tetto 0,70, pavimento 0,60, % di fase 0,65 (tabella vincolante di D282 §6). |
| Carichi ancorati: lettura | `anchored_load.py:613-615`, `:617-624` | Il carico di lavoro si converte col rapporto fra le % di fase; poi il target a freddo. |
| Carichi ancorati: scrittura del feedback | `anchored_load.py:1158`, `:1191` | Il feedback scrive `phase_id_at_log` = fase corrente; `hang_write_cap` usa il tetto di fase. |
| Tirata in deload | `progression_v1.py:142-144` | `PULLING_1RM_PCT` 0,525: percorso morto, perché in deload non entra nessuna sessione di tirata (D280 D2). |
| Test | `retest_policy.py:123`, `:127` | `RETEST_BLOCKED_PHASES` e `REQUEST_BLOCKED_PHASES` comprendono il deload. |
| Chiavi | `key_stimuli.json:109-111` | Deload = solo `technique`, priorità 3, severità `info`. `key_sessions_v1.py:974-980` propone anche sessioni fuori dal pool. |
| Guardie | `guards_v1.py:121`, `:126-128` | `REST_DAY_SESSION_IDS` comprende `deload_recovery` e `regeneration_easy`: un giorno con solo quelle è un riposo vero (`MIN_REST_DAYS` 2). |
| Contesto atleta | `athlete_context.py:755-757`, `:1465-1466` | «fase deload: niente massimali» blocca le righe max delle custom; il composer le esclude con la stessa guardia (`session_composer.py:292-294`). |
| Ordine degli esercizi | `exercise_ordering.py:254` | In deload `strength_neural`, cioè i max hang, va in posizione 6: dopo aerobico, tecnica, core e prehab. |
| Fatica | `adaptive_replan.py:1-13`, `:229-251` | B369: «2 very_hard in 3 giorni → giorno di recupero» è solo un suggerimento, mai applicato. |

### 1.2 Verifiche sui dati

- **Un solo deload, terminale: confermato.** Dentro il ciclo l'unica riduzione è legata ai viaggi, e c'è il suggerimento B369 (D280 B10 lo diceva già). Il taper A281 viaggio:
  - volume × 0,6 e poi × 0,4 nelle due settimane prima della partenza;
  - 3 giorni senza lavoro duro (`macrocycle_v1.py:982-1035`);
  - il moltiplicatore è stampato sul giorno (`planner_v2.py:3576-3578`) e applicato in `week.py:66-106`, `:210-217`.
- **Il macrociclo di Daniele.**
  - 13 settimane, dal 2026-09-07 al 2026-12-06: base 2, SP 4, PE 3, performance 3, deload 1.
  - Deload dal 30/11 al 06/12, in cache (`week_plans["2026-11-30"]`, rev. 6, generata il 04/11), con pool salvato e `intensity_cap: low`.
- **Simulazione col codice attuale** (rigenerazione forzata della settimana 13 sul mirror, in memoria):
  - stesse sessioni della cache;
  - 2 sere di arrampicata su 6 disponibili (`easy_climbing_deload` lunedì, `regeneration_easy` giovedì), contro 6 su 6 nelle settimane di performance del 16 e del 23/11;
  - chiave tecnica `missing` (`info`).
- **Carichi di Daniele (lettura in memoria, data 02/12):**

  | Voce | Valore |
  |---|---|
  | Massimale ufficiale | max hang 7" 116 kg (test del 24/09); peso 78 kg |
  | Carico di lavoro salvato | 107 kg, scritto in fase PE il 02/11 |
  | Ancorato in performance (intensità hard) | **110 kg (+32)**: è il tetto 0,95 |
  | Ancorato in deload oggi | **81 kg (+3)**: è il tetto 0,70 |
  | Forma R3 | 110 × 0,90 = **99 kg (+21)**, cioè l'85,3 % del massimale |
  | Tetto con 3 s di riserva | 111 kg: la riserva è rispettata con ampio margine |

  Con la lettura «grezza» del carico salvato in PE si avrebbe 107 × 0,90 = 96,5 kg. Il design usa la funzione unica (§1.3).
- **Dati per il trigger.**
  - `session_completion_log`: 175 righe, **0** `very_hard` (104 ok, 54 senza voto, 10 easy, 6 hard, 1 very_easy).
  - Nessun blocco dolore: solo 3 righe di dolore, tutte a 0.
  - `feedback_log` tiene 7 voci (`adaptive_replan.append_feedback_log`): non copre 7 giorni, quindi non è la fonte giusta.

### 1.3 Design proposto (R3-a: il deload terminale)

**Dove vive la forma.**
- Una costante `DELOAD_FORM` in `macrocycle_v1.py`, accanto ad `apply_deload_week`. Contiene le sessioni della forma, i limiti settimanali dei riempitivi e il fattore di carico.
- `planner_v2` la legge quando `phase_id == "deload"`, **indipendentemente dal pool e dal tetto salvati**: raggiunge il macrociclo esistente di Daniele senza `generate_macrocycle` e senza `from_phase`.
- `_SESSION_POOL["deload"]` si aggiorna lo stesso, per coerenza nei macrocicli nuovi e per la logica A326 del cambio sede.

| Elemento R3 | Dove nel codice | Proposta |
|---|---|---|
| **Stessi giorni di arrampicata** | `planner_v2.py:1536-1544`, PASS 1 `:1954-2090`, `apply_deload_week` | In deload il planner riempie gli stessi giorni di una settimana normale: i giorni target con una sede da arrampicata. Nessuna lettura della settimana precedente: dipende solo da disponibilità e target, quindi è deterministico. <br>Pool di PASS 1 in deload: tecnica ×1, seduta dita ×1, poi `easy_climbing_deload` / `regeneration_easy` come riempitivi, con un limite settimanale valido solo in deload (il `max_per_week` globale resta, perché vale anche per il fallback PASS 1.5, `:2151`). <br>Via il tetto di 5 sedute di `apply_deload_week`. Per Daniele: 6 sere. <br>Un prototipo grezzo in memoria (pool e tetto allargati) ne mette 4 su 6: lo limitano il budget di PASS 1 (`:1957`, `2 × len(primary_pool)`) e una seduta dita solo-casa. La Fase 2 deve coprire entrambi i punti. |
| **Serie × 0,5** | catalogo + A312 (`resolve_session.py:78-108`) | Nel deload terminale passa dalle dosi di catalogo: <br>• `deload_sets` (A312) sui blocchi drill di `technique_focus_gym`; <br>• la seduta dita ha 3 serie (5 × 0,5 arrotondato per eccesso); <br>• le sessioni native del deload tengono le loro dosi, già leggere; <br>• i pranzi tengono A312: nessun secondo taglio, il golden `b413_lunch_golden_cases` deve restare identico; <br>• le scale BW tengono «−1 serie». <br>Un moltiplicatore generico × 0,5 per sessione, sul modello di A281, serve solo a R3-c (§1.4). |
| **Un'esposizione dita, 2-3 serie a carico di fase −10 %, ≥ 3 s di riserva** | sessione di catalogo nuova (C), `_SESSION_META`, `stimulus.SESSION_FALLBACK_STIMULI` (`stimulus.py:167-182`), `anchored_load.py` | **Sessione** (nome da fissare, p. es. `deload_finger_touch`): <br>• riscaldamento dita; <br>• `max_hang_7s` fissato a 3 × 7" (20 mm, mezza arcuata, come l'ancora di fase); <br>• blocco facoltativo di arrampicata facile in palestra; <br>• prehab. <br>Sede palestra **e** casa, richiede la trave; meta `hard: False, finger: True, intensity: medium`. Niente blocco di tirata (vedi domanda 1). <br>**Carico:** in deload `anchored_load` = `anchored_load(stessa data, phase_id = ultima fase non deload, intensity="hard")` × 0,90 (`DELOAD_LOAD_FACTOR`, ENGINEERING CONSTANT), poi il tetto strutturale dei 3 s (`RESERVE_S`). Il tetto deload 0,70 non vale più per le sospensioni. <br>**Ciclo chiuso:** in deload il feedback **non riscrive** il carico di lavoro (congelato come le scale BW); `hard`/`very_hard` e dolore contano come oggi. Senza questo, un carico scritto con fase `deload` (% 0,65) verrebbe convertito × 1,23 nella base successiva (0,80/0,65). <br>**Posizione:** ≥ 48 h dall'ultimo giorno dita-hard (anche della settimana prima, B161); mai negli ultimi 3 giorni (`KEY_PASS_PRE_TEST_DAYS`, `planner_v2.py:166`: le 72 h prima di un test d'apertura del ciclo nuovo); primo giorno valido da lunedì. **Solo per gli atleti testati** (D282, regole globali: le ancore valgono solo con un massimale testato); per gli altri niente esposizione dita, come oggi. `finger_aerobic_base` esce dai riempitivi quando la seduta dita c'è. |
| **Una seduta corta di limit o di tecnica a livello flash** | `technique_focus_gym` + `deload_sets` | Il motore sceglie la **tecnica**: <br>• non è hard, quindi l'hard cap resta 0; <br>• è il limitatore n. 1 di Daniele; <br>• non aggiunge un secondo giorno dita-hard all'esposizione. <br>Il limit corto resta una scelta dell'atleta (custom o coach); il planner non lo mette. |
| **Niente PE, test, cedimento** | già così | PE esclusi dal tetto `low` (`power_endurance_gym` è `high`). Test bloccati (`retest_policy.py:123/127`, `planner_v2.py:128-132`). HIIT → Z2; pranzi a RIR 3; scale BW congelate. La lista consentita aggiunge solo le 2 sessioni R3: il tetto `low` resta per tutto il resto (D280 D2 respingeva il tetto `high`: non serve toccarlo). |
| **Un'esposizione per stimolo chiave** | `key_stimuli.json:109-111` | Righe deload: <br>• `finger_maintenance` (target 1, priorità 2, `info`, con `propose: ["deload_finger_touch"]` e `why` sovrascritti a livello di riga: il catalogo lo consente, `key_sessions_v1.py:195`); <br>• `technique` (`info`). <br>Nessuna card critica in deload. |
| `apply_deload_week` | `macrocycle_v1.py:892-926` | Continua a togliere ogni `hard` (rete di sicurezza). Toglie il tetto di 5. `targets = {hard_days: 0, finger_days: <contate>}`. Docstring corretta. |
| Ordine degli esercizi | `exercise_ordering.py:254` | In deload `strength_neural` passa a 1, subito dopo il riscaldamento: le sospensioni si fanno da freschi. `test_a121:244-255` resta valido. |
| Contesto e coach | `athlete_context.py:755-757`, `:1465-1466` | Testo nuovo: «deload: una sola esposizione dita (3 serie a −10 %), la mette il piano». Le righe max nelle custom restano bloccate: l'esposizione la dà il motore. |
| Cambio sede (A326) | `replanner_v1.py:247-250` | `in_cap` deve accettare la lista consentita del deload, altrimenti spostare la seduta dita la perde. |

### 1.4 Il trigger: un avviso (R3-b) e la settimana ridotta a richiesta (R3-c, facoltativa)

**R3-b — solo un avviso, non un modulo STOP.**
- Un modulo puro nuovo, `backend/engine/reduced_week.py`: `suggestion(state, today) → {suggested, week_start, reasons[], skipped}`. Niente orologio, niente scritture.
- **Motivi:**
  - `very_hard_7d`: ≥ 2 sedute con `difficulty: very_hard` in `session_completion_log` nei 7 giorni fino a oggi. Non `feedback_log`, che tiene solo 7 voci.
  - `pain_block`: un blocco in `progression_counters.pain_blocks` attivo oggi con punteggio ≥ 2, su qualunque zona. È la stessa lettura di `anchored_load.pain_for`.
- **Quando tace:**
  - `recent_taper`: una finestra taper A281 [T−14, T−1] cade negli ultimi 35 giorni;
  - `deload_soon`: questa settimana o la prossima è il deload terminale.
- «Lo chiede l'atleta» non è un motivo dell'avviso: è il percorso a richiesta (R3-c).
- **Dove si vede** (solo backend):
  - `athlete_context`, cioè lo script che il coach Telegram legge ogni volta;
  - il prompt del coach in-app (blocco A297);
  - un campo fratello in `GET /api/week`, come `key_status` e le guardie, per una card futura (frontend → preview Vercel).
- Mai salvato, mai applicato (A301/B369).
- Per Daniele, nel suo storico, non sarebbe mai comparso.

**R3-c — settimana ridotta a richiesta (STOP, facoltativa).**
- `planning_prefs.reduced_weeks: [lunedì]`, scritto da un'azione esplicita: il coach con `PUT /api/state`, dry run e OK; più avanti un bottone sulla card dell'avviso.
- `mark_weeks_stale(only=…)` marca la settimana.
- Il planner applica la stessa forma alla settimana di fase:
  - stessi giorni;
  - serie × 0,5 con un moltiplicatore per sessione sul modello di A281, mai sulle custom né sulle sessioni native del deload;
  - la chiave dita della fase diventa l'esposizione a −10 %;
  - il limit diventa corto, oppure tecnica;
  - PE → facile;
  - test bloccati quella settimana dalla retest policy.
- Tocca `planner_v2`, `week.py`, `retest_policy` e `anchored_load`.
- **Consiglio:** non ora (domanda 3).

### 1.5 Consumatori e test

**Cosa cambia in R3-a.**
- `macrocycle_v1.py`:
  - `:144-152` e `:224-232` (pool);
  - `:880` (nota);
  - `:889-926` (`DELOAD_FORM`, `apply_deload_week`).
- `planner_v2.py`:
  - `_SESSION_META` della sessione nuova;
  - `:1533-1544` (lista consentita);
  - PASS 1 in deload (pool, riempitivi, budget);
  - posizione della seduta dita;
  - `:3664-3679` (riepilogo con `finger_days`).
- `anchored_load.py`:
  - `:119-133` (costanti);
  - `:547-626` (ramo deload della lettura);
  - `:945-1164` (congelamento in scrittura);
  - `:1167-1192` (`hang_write_cap`).
- `stimulus.py:167-182`.
- `key_stimuli.json:109-111`.
- `exercise_ordering.py:254`.
- `athlete_context.py:755-757`, `:1465-1466`.
- `replanner_v1.py:247-250`.
- Catalogo:
  - la sessione nuova;
  - `deload_sets` su `technique_focus_gym`.
- Documenti:
  - `ENGINE_ARCHITECTURE.md` §Deload (`:190-197`) e il filtro d'intensità (`:239-240`);
  - `user_guide_v1.md` «Deload (1 week)» (`:138-146`);
  - `athlete_plan.md` §2 (riga «deload 0,70») e §5 «Deload»;
  - `vocabulary_v1.md`;
  - una nota «superato il 13/11» sulla tabella dei tetti di D282 §6.

**Invariati, verificati:**
- `complementary_v1` (HIIT → Z2);
- `retest_policy`;
- `bw_progression`;
- `guards_v1`;
- il codice di `key_sessions_v1`: le righe nuove arrivano dal catalogo;
- il composer del coach.

**Test da riscrivere:**
- `test_planner_v2.py:160-165` `test_deload_only_low_intensity` → «solo `low`, tranne la lista consentita R3».
- `test_planner_v2.py:776-783` `test_deload_week_low_load` (≤ 20 × 5 sedute) → giorni e carico della forma R3.
- `test_a282_quality_floors.py:121-128` `test_deload_is_exempt` («una settimana di deload senza lavoro dita è corretta») → esattamente 1 esposizione dita non hard per un atleta testato, 0 per un non testato.
- `test_a294_key_sessions.py:160-164` (`keys("deload") == ["technique"]`) → aggiungere la riga dita.
- `test_a293_athlete_context.py:322-323` (`key_requirements_for("deload")`) e `:608-613` (testo della guardia deload).

**Test che devono restare identici:**
- `test_b308` (niente tirata in deload);
- `test_a305:67-68`, `:194-196` (PASS 2.7 non tocca il deload);
- `test_a300:231` (HIIT → Z2);
- `test_a312_deload_sets.py`;
- **`b413_lunch_golden_cases.py:116`, `:205-208`**: i pranzi del deload al 01/12, cioè la guardia contro il doppio taglio;
- `test_a326:275-277`, `test_a319:1160-1168`, `test_b414_do_the_test.py:100`, `test_a121:244-255`;
- `test_planner_v2.py:108-131`, `:445-447`: nessun hard, tag di fase, nessun test;
- `test_resolver_enhancements.py:139-151`.

I golden `a290_untested_cases`, `b364_untested_cases` e `c272` non hanno date di deload: restano invariati.

**Test nuovi** (`test_d288_r3_deload_form.py`):
- giorni di arrampicata uguali a quelli della stessa disponibilità in una fase normale;
- 1 sola seduta dita (testato), 0 (non testato), mai `hard`;
- seduta dita ≥ 48 h dall'ultimo giorno dita-hard della settimana prima e mai negli ultimi 3 giorni;
- 1 tecnica; nessun limit, PE o test;
- `targets` = `{0, 1}`;
- carico = ancorato della fase precedente × 0,90, entro il tetto dei 3 s;
- il feedback in deload non muove `working_loads`;
- funziona con un macrociclo salvato con pool vecchio e `intensity_cap: low`, come quello di Daniele;
- determinismo;
- **sessioni passate e dell'utente intatte attraverso la rigenerazione** (fusione B369: regola di CLAUDE.md per ogni modifica che rigenera il piano).

**R3-b, test:**
- scatta con 2 `very_hard` in 7 giorni e con un blocco dolore attivo; tace con 1;
- tace dopo un taper e nella settimana prima del deload;
- non scrive niente;
- testo in `athlete_context`.

### 1.6 La settimana di Daniele dal 30/11

Tabella indicativa: i giorni esatti li dà il planner in Fase 2. Valgono le regole del §1.3: seduta dita ≥ 48 h dopo il progetto di sabato 28/11, mai negli ultimi 3 giorni, tecnica dove c'è il boulder.

| Giorno | Oggi (cache = rigenerazione col codice attuale) | Con R3, dopo una rigenerazione |
|---|---|---|
| Lun 30/11 | pranzo braccia (A312) · sera `easy_climbing_deload` (Bkl) | pranzo braccia (A312) · sera **tecnica** `technique_focus_gym` a dosi di scarico |
| Mar 01/12 | pranzo custom gambe (sua) · sera flessibilità | pranzo custom (resta) · sera **dita**: 3 × 7" a **99 kg (+21)** + arrampicata facile (Cocque, trave) |
| Mer 02/12 | Z2 · prehab | Z2 · arrampicata facile |
| Gio 03/12 | Z2 · `regeneration_easy` | Z2 · arrampicata facile |
| Ven 04/12 | pranzo spinta (A312) | invariato (resta l'unico riposo vero, come nelle settimane normali) |
| Sab 05/12 | `deload_recovery` (casa) | arrampicata facile |
| Dom 06/12 | — | arrampicata facile |
| Chiavi | tecnica `missing` (`info`) | dita e tecnica pianificate (`info`) |

**Condizioni perché si veda:**
1. R3-a in prod entro **giovedì 26/11**.
2. Poi la settimana va rigenerata. La cache non cambia da sola: `week.py:711-753` serve la copia salvata se non è forzata o `_stale`, e D282 vieta di rigenerare le settimane in cache senza una migrazione con dry run.
3. Lo strumento: uno script una tantum `mark_weeks_stale(only="2026-11-30")` con `--dry-run`, lanciato dal loop principale dopo il deploy e dopo l'OK di Daniele.
4. La fusione B369 conserva la custom di martedì e la rimozione del pranzo gambe (`adaptations` della settimana).

**Senza rigenerazione non cambia niente di visibile:**
- nessuna sessione in cache porta un max hang;
- la custom di martedì è gambe, senza righe ancorate;
- se R3-a non arriva in tempo, vale dal prossimo deload.

**Dopo il 06/12** (`END-OF-CYCLE-STUCK-IN-DELOAD`, roadmap: accettato da Daniele il 07/11): finché non avvia il ciclo nuovo, ogni settimana resta deload. Con R3 diventa un mantenimento, con un'esposizione dita e una tecnica a settimana, invece di zero. Con R1 adottata, l'85,3 % sarebbe uno stimolo dita «alto»: uno solo a settimana, dentro il tetto di 3.

---

## 2. R8 — tecnica outdoor solo con target registrato

### 2.1 Oggi

**Catalogo e motore.**
- `key_stimuli.json:64-72`: la tecnica conta per `session_ids` (`technique_focus_gym`) o per ≥ 2 drill piedi/posizione. Nessun `outdoor_counts`: la review di A294 l'ha tolto (`_doc`, riga 3). Progetto e try-hard hanno `outdoor_hard_counts` (`:60`, `:78`).
- `key_sessions_v1.py:562-574`: `_outdoor_any` (qualunque log outdoor, con o senza vie) alimenta due cose.
  - Il ramo `outdoor_counts`: `_phase_history` `:627-628` e `compute_key_status` `:1456-1461`, con evidenza «outdoor (regole tecniche non verificabili)». Nessuna riga lo usa: è un ramo morto.
  - L'esclusione dei giorni outdoor dalle proposte (`_propose_for` `:1007`), che deve restare.
- Chi legge lo stato chiave riceve le righe `outdoor_logs` con l'entry completa: `backend/api/key_status.py:35-62`, `:118`, `athlete_context` live, il prompt del coach. Le righe di riepilogo `state.outdoor_log` (B116) non portano l'entry.

**Schema e vincoli.**
- `backend/data/schemas/outdoor_session_entry.v1.json` ha `additionalProperties: false` e nessun campo target.
- I modelli di richiesta, `models.py:360-396` e `:408-425`, sono Pydantic con `extra` di default: **un campo sconosciuto viene scartato in silenzio**, senza 422.
- `outdoor_log.validate_outdoor_entry` (`:338-431`) non rifiuta chiavi sconosciute.
- `test_a324_rope_role_aid.py:602-606` impone `model_fields ⊆ schema.properties`.

**Scritture.**
- `POST /api/outdoor/log` (`outdoor.py:309-357`).
- `PUT` (`:375-456`): A324 riporta le chiavi non inviate (`:401`), tranne `outdoor_log.py:457-459`.
- `finish` della seduta guidata (`:783`, `model_dump` a `:808`).
- Fusione B412: `_MERGE_OWNED`, `outdoor_log.py:584-587`.
- Impronta: `:597-606`.

**Dati.**
- 61 log outdoor di Daniele: nessuno porta un numero tecnico, neanche nelle note. L'abitudine non c'è ancora.
- Le misure esistono già nel catalogo:
  - protocollo `outdoor_technique_day` (`bw_ladders.json`: «Foot slips per go on the project»);
  - misura della scala PIEDI («Foot readjustments on ONE sample problem»), campo A298 `sample_readjust`, 0-30 (`bw_progression.py:109`).

### 2.2 Il dato

Un campo facoltativo di primo livello nell'entry outdoor, uno per falesia:

```json
"technique_target": {
  "metric": "foot_slips_per_go | sample_readjust",
  "value": 2,
  "sample": "Isatis L1"
}
```

- **Metrica.** `metric` usa i nomi del catalogo e di A298:
  - `foot_slips_per_go` = scivolate di piede per giro (`athlete_plan.md` §7);
  - `sample_readjust` = aggiustamenti di piede sul tiro campione.
- **Valore.** `value` è un numero da 0 a 30: le scivolate per giro possono essere una media decimale, gli aggiustamenti sono interi.
- **Tiro misurato.** `sample` è facoltativo (≤ 80 caratteri): la via o il tiro misurato.
- **Quando conta.** Con metrica valida e valore nel range: conta il numero registrato, non che sia «buono». La chiave è lo stimolo, non il risultato; la domanda è la verificabilità (D288 §Q8).
- **Falesie multiple.** Un giorno con più falesie conta una volta.
- **Schema.** La proprietà nuova ha il suo `additionalProperties: false`. Il contratto con climb-watch non cambia: il campo è facoltativo.
- **Un solo validatore.** `outdoor_log.technique_target_of(entry)`, usato da `validate_outdoor_entry` (stesso schema di A324 per gli import da script) e da `key_sessions_v1`.
- **Scala PIEDI.** Il numero outdoor **non** muove la scala PIEDI (A298) in questo passo. Potrebbe farlo in seguito, come evidenza del livello P4 «su roccia».

### 2.3 Chi lo scrive

**API.**
- Un modello `OutdoorTechniqueTarget` e il campo su `OutdoorSessionLog`: `POST` e, per ereditarietà, `PUT`.
- Lo stesso campo su `OutdoorSessionFinishRequest`, per la seduta guidata.
- Nessun endpoint nuovo.
- `PUT`: se il campo non viene inviato, resta quello salvato (A324); `null` lo cancella.
- B412: una seconda seduta sulla stessa falesia, lo stesso giorno, non sovrascrive il target salvato. È una chiave non posseduta dalla fusione: resta il valore salvato, riempito solo se manca. Una correzione passa dal `PUT`.

**Prima il coach.**
- Il coach Telegram registra già le giornate outdoor con `POST /api/outdoor/log` (runbook `scrivere-in-app.md` del workspace del coach).
- Dopo la giornata chiede il numero e lo mette nello stesso `POST`.
- Oppure lo aggiunge dopo con un `PUT`, che richiede già di leggere il giorno, mandare vie e note complete, mostrare l'anteprima e avere l'OK.
- Dopo il deploy serve una riga nel runbook e in `app.md` del coach (workspace del coach, non questo repo).

**UI e ordine.**
- La UI non serve perché il credito compaia: la card chiave già mostra «fatto» dal backend.
- Serve solo per registrare il numero senza il coach: è R8-b.
- Ordine obbligato: prima il backend, perché Pydantic scarta in silenzio un campo che non conosce.

### 2.4 La modifica in `key_sessions_v1`

- **Catalogo.** `key_stimuli.json`, voce `technique`: `"outdoor_target_counts": true`; si aggiornano `_doc` e `why`.
- **Funzione nuova.** `_outdoor_technique_days(state, rows, since, until)`: legge le righe come `_outdoor_any` e tiene i giorni con un target valido. Restituisce una riga per data, con metrica, valore e tiro.
- **Dove entra.**
  - Sostituisce il ramo `outdoor_counts` in `compute_key_status` (`:1456-1461`), con un'evidenza del tipo «outdoor: 2 scivolate/giro (Isatis L1)».
  - Entra anche in `_phase_history` (`:627-628`): una settimana con un target outdoor non è «vuota» per l'escalation a critico.
  - `_outdoor_any` resta per `_propose_for` (`:1007`).
- **A325.** Un giorno outdoor con target chiude la chiave: niente top-up.
- **Effetto sui consumatori,** tutti dalla stessa funzione:
  - `athlete_context` (anche `--simulate`);
  - il prompt del coach;
  - la card di `/api/week`;
  - `check_insertion`: niente `key_removed` se la tecnica è già fatta da un target outdoor.
- **Planner.** PASS 2.7 resta invariato: non può conoscere un log futuro. Un giorno outdoor pianificato conta solo quando il numero è registrato, come da decisione.
- **Dati mancanti.** Senza righe outdoor (lettura fallita → `None`) niente credito: è la direzione prudente.

### 2.5 Test

**`test_a294_key_sessions.py`:**
- `:263` resta: un outdoor senza target non chiude la tecnica, il try-hard sì.
- Nuovi:
  - outdoor con target valido → tecnica fatta, con l'evidenza;
  - metrica sconosciuta, valore negativo o non numerico → non conta;
  - giorno con due falesie → conta una volta;
  - target in una settimana passata → conta in `_phase_history`;
  - outdoor pianificato senza log → non conta;
  - try-hard invariato;
  - `check_insertion` senza `key_removed` quando la tecnica è chiusa da un target.

**`test_a324_rope_role_aid.py`:**
- l'allineamento schema ↔ modelli resta verde con la proprietà nuova;
- casi `jsonschema` validi e non validi.

**Nuovo `test_d288_r8_outdoor_technique_target.py`:**
- `POST` salva il campo;
- `PUT` senza campo lo conserva;
- `PUT` con `null` lo cancella;
- `finish` lo salva;
- `validate_outdoor_entry` rifiuta una metrica sbagliata;
- la fusione B412 tiene il valore salvato;
- un replay identico non cambia niente.

**`test_a293_athlete_context.py`:** l'evidenza outdoor compare nella riga tecnica.

### 2.6 Frontend: passo separato (preview Vercel + OK di Daniele)

- **File da toccare:**
  - `OutdoorLogForm.tsx`, che copre log manuale, modifica con la matita e chiusura guidata via `onSubmit` (`:124-130`, `:279-311`);
  - `lib/types.ts`;
  - `lib/api.ts:858-876`, `:954`.
- **Interfaccia.** Un riquadro «Tecnica (vale per la chiave)»: metrica, numero, tiro facoltativo.
- **Payload.** Il campo si invia solo se compilato. In modifica il form mostra il valore salvato e manda `null` per cancellarlo.
- **Test.** vitest sul payload.
- **Workflow.** Tocca `frontend/`: branch, preview testata, OK esplicito prima del merge (CLAUDE.md).

---

## 3. Rischi, sforzo, ordine

| # | Passo | Moduli | STOP | Sforzo | Quando |
|---|---|---|---|---|---|
| 1 | **R3-a** deload terminale | `macrocycle_v1`, `planner_v2`, `anchored_load` (lettura + congelamento), catalogo (sessione nuova, `technique_focus_gym`), `key_stimuli`, `stimulus`, `exercise_ordering`, `athlete_context`, `replanner_v1` (A326), documenti | sì | M (circa 1 giorno + review) | subito dopo l'OK: in prod entro **gio 26/11** |
| 2 | Rigenerare la settimana del 30/11 | script una tantum `mark_weeks_stale(only=…)`, `--dry-run` | scrittura prod | XS | dopo il deploy, con l'OK |
| 3 | **R8-a** backend | schema, `models`, `outdoor_log`, `key_stimuli`, `key_sessions_v1`, documenti; riga nel runbook del coach | no | S (½ giorno) | dopo 1 (stesso `key_stimuli.json`) |
| 4 | **R3-b** avviso | `reduced_week.py`, `athlete_context`, prompt del coach, campo in `/api/week` | no | S (½ giorno) | dopo 1 |
| 5 | **R8-b** UI | `OutdoorLogForm`, `types`, `api`, vitest | preview + OK | S | dopo 3 |
| 6 | **R3-c** settimana ridotta a richiesta | `planner_v2`, `week.py`, `retest_policy`, `anchored_load`, `planning_prefs` | sì | M | solo se Daniele lo vuole |

D288-R1 e R2 toccano anch'essi `planner_v2`: vanno serializzati. R3-a prima, per la scadenza del 30/11.

**Rischi R3:**
1. **Pool salvato.** Una forma messa nel pool salvato non arriverebbe ai macrocicli esistenti; per questo vive nel codice del planner. Restano due sorgenti (pool salvato + forma), da documentare.
2. **Settimane in cache.** Non cambiano da sole: lo stale una tantum con dry run fa parte del rilascio.
3. **Ciclo chiuso.** Senza il congelamento in scrittura, il carico del deload gonfia la base successiva (× 1,23). Il congelamento è parte del passo, non un'opzione.
4. **Posizione della seduta dita.** 48 h dopo il progetto di sabato 28/11; 72 h prima di un test d'apertura del ciclo nuovo.
5. **D282.** La tabella vincolante dei tetti (D282 §6, deload 0,70) cambia per le sospensioni: va annotata come superata dalla decisione del 13/11.
6. **Altri utenti.** Anche il loro deload cambia (giorni di arrampicata, tecnica), ma senza esposizione dita se non sono testati.
7. **Test.** Circa 6 test da riscrivere. Il golden dei pranzi `b413` deve restare identico byte per byte.
8. **Registro delle esposizioni.** L'esposizione del deload entra nel registro: la confidenza del test d'apertura del ciclo nuovo sale. È voluto.

**Rischi R8:**
1. **Campo scartato.** Pydantic scarta in silenzio i campi sconosciuti: va in prod prima il backend, poi il coach o la UI.
2. **Il `PUT` del coach.** Sostituisce vie e note: il coach deve mandarle complete, come prevede già il runbook (il `PUT` non ha dry run).
3. **Fusione B412.** Vince il primo target salvato; la correzione passa dal `PUT`.
4. **Righe outdoor non disponibili.** Niente credito, per scelta prudente.
5. **Autodichiarazione.** Il numero è dichiarato, come ogni log.

## 4. Domande aperte (serve la parola di Daniele)

1. **Tirata nel deload.**
   - La forma accettata elenca dita e tecnica/limit; la tirata pesante resta fuori (oggi «zero tirata in scarico», B308 / D280 D2).
   - Raccomandazione: fuori.
   - In alternativa: 2 serie di trazione zavorrata a −10 % nella stessa seduta dita.
2. **Settimana del 30/11.**
   - Dopo il deploy di R3-a (entro il 26/11), la rigenero con uno stale solo su quella settimana? Prima il dry run; la custom di martedì resta.
   - Raccomandazione: sì. Senza, il 30/11 resta com'è oggi.
3. **Settimana ridotta a richiesta (R3-c).**
   - Nel tuo storico il trigger non sarebbe mai scattato.
   - Faccio solo l'avviso (R3-b), lasciando la richiesta al coach a mano, o vuoi anche il percorso in-app (STOP)?
   - Raccomandazione: solo l'avviso, per ora.
