# D288 — Fase 1 di R1 e R2: carico dita a due livelli, tetto settimanale, blocchi di falesia

> **Data:** 2026-11-13 · **Tipo:** D (analisi di Fase 1, sola lettura — protocollo ad alto rischio di CLAUDE.md) · **Codice letto:** worktree `climb-agent-d288` = origin/main @ f1a01ba
> **Fonte:** `D288_kb_research_r1_r8.md` (Q1, Q2, Q5), roadmap `A-FINGER-LOAD-TIERS`, il codice riga per riga, simulazioni in memoria sul mirror di prod del 13/11 (`climb-state-mirror/data`, nessuna scrittura, nessun pytest).
> **Stato:** **STOP.** Tocca `planner_v2.py` (e, per un campo additivo, `progression_v1.py`): niente codice prima dell'OK di Daniele.

## 0. Decisioni applicate (Daniele, 2026-11-13)

1. Il giorno duro in falesia sta **dentro** il tetto di 3 esposizioni dita-high.
2. HIIT e gambe a pranzo **non** rompono il riposo vero: resta la definizione di oggi (`guards_v1.is_rest_day_session` / `_low_rest_days`).
3. Tutto ciò che segue un'azione dell'utente resta **alert**, mai rifiuto né riscrittura (A301). Le restrizioni nuove valgono solo per i piazzamenti dell'engine.

Corollari che l'analisi ne ricava:
- **Composer e /custom-session.** Le ragioni nuove (tetto, blocco falesia) vanno in una lista di avvisi, **mai** in `finger_max_ok`. Oggi `finger_max_ok = False` toglie gli esercizi dita-hard dal pool del composer: `athlete_context.py:2487-2508` → `session_composer.py:540` e `:294`. Lì diventerebbero un rifiuto.
- R1 ed R2 restano **ENGINEERING CONSTANT**: la ricerca dà confidenza bassa (6 h, tetto 3, 72 h).

## 1. Dove vive oggi la regola dita

### 1.1 I predicati

| Predicato | Definizione | Chi lo usa |
|---|---|---|
| `finger` (booleano) | `_SESSION_META[sid]["finger"]` per il catalogo, `tags.finger` salvato per custom e generate. Lettura unica `stimulus.session_flag` (`stimulus.py:464-470`: i tag propri vincono, poi il meta) | spacing di 48 h: planner, `guards_v1`, `athlete_context`, `suggest_sessions` |
| `is_finger_hard_session` | `stimulus.py:473-491`. Vale per la sessione finger ∧ hard, oppure con famiglia finger_max / limit_power, oppure con `FINGER_FATIGUE_EXTRA_IDS` / `FINGER_HARD_LIBRARY_IDS` (`:134-155`) | blocco di 72 h prima del test dita, key sessions, composer, `finger_hard_days` |
| `finger_hard_days` | `stimulus.py:988-1049`, definizione unica A288 di «giorno dita-hard»: sessioni finger-hard + `outdoor_hard` + `free_limit` | retest policy, key sessions, guardie di `athlete_context` |
| giorno di falesia | planner: **dichiarato** = hard + dita (B382(b), `planner_v2.py:1777-1806`). Alert: **dal log** (B372 `outdoor_fatigue_days`, `stimulus.py:1119-1212`) | planner e alert, con due letture diverse |
| gap | `ceil(1 × recovery_multiplier)` **giorni di calendario**, calcolato due volte: `planner_v2.py:1580-1581` e `replanner_v1._recovery_gap` (`replanner_v1.py:35-43`), letto da `guards_v1.py:656`, `key_sessions_v1.py:682-685`, `athlete_context.py:579-587` e `replanner_v1.py:637` / `:647`. `FINGER_GAP_H = 48` (`retest_policy.py:108-109` → `athlete_context.py:109`) è solo documentale: nessun calcolo lo legge | — |

### 1.2 Ogni copia della regola

**`planner_v2.py`** — undici siti di piazzamento, ciascuno con il proprio confronto:

| Riga | Cosa |
|---|---|
| 38-101 | `_SESSION_META`: `finger` su 15 sessioni (5 di trave: `finger_strength_home`, `finger_maintenance_home` / `_gym`, `finger_aerobic_base`, `finger_endurance_short`; i 6 test dita; `strength_long`, `power_contact_gym`, `limit_boulder_gym`, `route_projecting_gym`) |
| 810 | `_make_session_entry`: copia `tags.finger` dal meta sul piano |
| 1699-1718 | B161: semina dalla settimana precedente (meta + tag; le custom via `session_flag`) |
| 1777-1806, 2183-2189 | B382(b): giorni di falesia dichiarati, aggiunti a `finger_day_offsets` dopo PASS 1.5 |
| 1819-1845 | B390: giorni vissuti (`session_flag` finger) |
| 1865-1897 | B414: `_user_finger` e `_near_anchor` (± gap, stesso giorno incluso) |
| 2011-2020, 2087-2088 | PASS 1: guarda all'indietro, solo l'ultimo elemento, più `_near_anchor`; poi registra il giorno |
| 2155-2157, 2175-2176 | PASS 1.5 |
| **2200-2249** | **PASS 2: nessun controllo dita, nessuna registrazione** (§1.3) |
| 2310-2313, 2344-2345 | PASS 2.2 (slot extra) |
| 2401-2404, 2442-2443 | cascata dei pavimenti (`_place_quality_floor._try`) |
| 2498-2508, 2536-2575 | PASS 2.5: presenza (`_week_carries("finger")`, qualunque dito) |
| 2622-2625, 2665-2666 | PASS 2.6 |
| 2761, 2776-2778, 2841-2879, 3036-3051, 3178-3182 | PASS 3a: 72 h finger-hard con `is_finger_hard_session`, 48 h con `session_flag(finger)`, sostituire una dita è neutro, registrazione |
| 3316, 3347-3352, 3390-3394, 3418-3419, 3444-3453, 3476-3477 | PASS 3 legacy |
| 1136-1139, 1206-1211, 1226-1253, 1379-1382, **1302** | PASS 2.7: `_has`, «unico portatore di dita», gap, registrazione. **1302: rifiuta ogni piazzamento che aggiunge un alert di `guards_v1`** |
| 3586, 3635-3638 | `targets.finger_days` (riassunto) |
| 3712-3793, 3828 | `generate_test_week`: due test dita a 48 h |

**`replanner_v1.py`:**
- `:35-43` `_recovery_gap`.
- `:220-235` `_stimulus_replacement`: «stesso carico» = (hard, finger).
- Tag dal meta in sei punti: `:520` (annulla skip), `:574` (riempimento), `:780` (quick-add), `:1822` (change_gym), `:2003-2004` (key re-schedule), `:2460` (override).
- `:539-544` `_meta_for`: default `finger: False` per le custom.
- `:627-680` `suggest_sessions`: −1000 a una sessione dita accanto a un giorno dita.
- `:1286-1395` `_seed_finger_date`, `_enforce_no_consecutive_finger`, `_reconcile`: nessun chiamante dell'engine dopo A301/B414, tenuti in vita dai test b287 / b165b / b367.
- `:1811-1812`, `:2488` `lost_finger`.
- `:1917-1938` `add_custom_session`: tag derivati una volta all'inserimento (B345).
- `:2113-2121` `add_generated_session`: merge dichiarato ↑ derivato.

**`guards_v1.py`:**
- `:284-323` `_finger_gap`: `session_flag` finger, gap da `_recovery_gap`, falesia su entrambi i lati.
- `:330-365` `_finger_test`: 72 h, finger-hard.
- `:438-467` `_hard_cap`: la falesia conta come giorno hard; non esiste un tetto sulle dita.
- `:493-511` `_post_outdoor`: hard **o finger** il giorno dopo la falesia.
- `:519-557` `_hard_back_to_back`: a `:552` esclude le sessioni finger, «sono di finger_gap».
- `:560-613` `is_rest_day_session` / `_low_rest_days`.
- `:132` `_COUNT_CODES`.

**`key_sessions_v1.py`:**
- `:673-679` `_finger_hard_map`.
- `:1003-1062` proposte: finger = meta o `req.finger_hard`, gap su una timeline unificata.
- **`:1100-1118` una proposta che aggiunge un alert di `guards_v1` viene scartata** (escluso `low_rest_days`).
- `:1845-1876` conflitto `finger_gap` della key.
- `:2050-2086` `check_insertion` (`finger_gap` + `added_guard_warnings`).
- `:2135-2227` `finger_key_guard` / `composer_guard`.

**`athlete_context.py`:**
- `:106-109` `FINGER_GAP_H`.
- `:401-415` `_session_view` (finger, finger_hard).
- `:428-466` B395 `_stale_custom_tags` (`_DERIVED_TAG_KEYS = hard, finger`).
- `:590-806` `_guards`: `finger_tagged` con la falesia a `:632-646`, le ragioni dita a `:709-733`, il cap hard comune a `:751-767`.
- `:1936-1943` testi EN.
- `:2451-2508` `composer_guard_view` (§0).

**`session_tags.py`:**
- `:121-140` pattern e domini dita.
- `:151-184` B414 E2: le sospensioni sub-max dopo intervalli PE non contano.
- `:189-210` B392: i warm-up leggeri non contano.
- `:237-304` `derive_session_tags`: il booleano.
- `:307-330` merge, solo verso l'alto.

**Altri moduli:**
- **`complementary_v1.py:101-121`.** Unico orologio a slot: mattina 08, pranzo 13, sera 19; `OUTDOOR_START_HOUR` 8; `hiit_too_close`. Nessuna logica dita.
- **`retest_policy.py`.** Costanti a `:108-114`; `_external_blockers` (`finger_hard_dates`) a `:1570-1602`.
- **`phase_anchor.py:26-33`, `:665-688`.** Step-down a sub-max del blocco max hang entro 72 h da un'esposizione finger_max. È nel resolver e R1 non lo tocca.
- **Lettori del solo booleano:**
  - `api/routers/session.py:335-355`;
  - `closed_loop_v1.py:150`, `:158`, `:226`;
  - `adhoc_builder.py:518`;
  - `body_part_picker.py:871`;
  - frontend: `session-card.tsx:563-564` e `:839-849` (badge), `week-alerts.ts:54-65` (titoli), `types.ts:289-297` (`GuardCode`).

### 1.3 Cosa non va già oggi (trovato leggendo e simulando)

1. **PASS 2 piazza sessioni dita senza gap e senza registrarle** (`planner_v2.py:2200-2249`).
   - Su 640 settimane sintetiche: 30 piazzamenti dita da PASS 2 (`finger_aerobic_base`, `finger_endurance_short`).
   - In 2 casi su 120 (solo casa, base lead, 6-7 giorni) l'engine mette due giorni dita consecutivi: aerobic venerdì ed endurance_short sabato. Oggi questo fa scattare `finger_gap` sulla settimana generata dall'engine stesso. Il buco va chiuso comunque; con R1 quella coppia diventa legale (low–high).
2. **La prima clausola di `is_finger_hard_session` (finger ∧ hard) sbaglia sulle custom miste.** Una custom con solo ramp-up dita più trazioni zavorrate risulta finger-hard: blocca il test 72 h e mette «NO dita max» sui giorni vicini.
3. **Il booleano non distingue i carichi.** `finger_aerobic_base` (≤ 50 %), le ripetute di `finger_maintenance_*` / `finger_endurance_short` (70-80 %) e `limit_boulder_gym` hanno lo stesso gap. L'allowlist `KNOWN` di `test_b414_session_tags_pe.py:110-115` esiste proprio perché un blocco secondario sub-max non è esprimibile.
4. **Due letture della falesia.** Il 31/10 e l'1/11 (Vercors, massimo 7b+ contro la soglia 7c+): per il log sono giornate facili; per il planner sono hard.
5. **La falesia non marca stale nessuna settimana.** Nessun router outdoor o replanner chiama `deps.mark_weeks_stale`, né direttamente né via `invalidate_week_cache`: lo fanno solo impostazioni, override, macrociclo e retest. B382(b), e qualsiasi ancora R2, agiscono solo se la settimana dopo viene generata **dopo** la falesia. Le settimane di Daniele si generano in anticipo (11/16 il 04/11, 09/28 il 05/09).

## 2. Design proposto

### 2.1 Tre concetti, di cui due esistono già

| Concetto | Valori / definizione | Serve a | Stato |
|---|---|---|---|
| `finger_load` | `high` \| `low` \| `None` | lo **spacing** | **nuovo** |
| giorno dita-hard | `finger_hard_days` (A288) + falesia dura | il tetto settimanale **≤ 3** | esiste |
| giorno max-hang | famiglia `finger_max` (`session_stimuli`, test compresi via `SESSION_FALLBACK_STIMULI`) | il tetto **≤ 2** | esiste |

Lettura di R1 adottata: «il sub-massimale a cedimento conta high **per lo spacing**». Le ripetute al 60-80 % stanno quindi nel livello `high` (48 h), ma il tetto di 3 conta le esposizioni dita-hard: max / test ≥ 85 %, limit / board / campus, `three_attempt_comp`, falesia dura. È la definizione A288. Se Daniele intende altro → domanda 2.

### 2.2 Da dove viene `finger_load`

- **Esercizi (dato, C).** Nuovo campo `finger_load: high|low` in `exercises.json` su ogni esercizio che oggi conta come dito per `session_tags` (55 voci).
  - **Regola pinnata da un test:** `low` solo con `intensity_level` ≤ medium, `stress_tags.fingers` ≠ high, niente ruolo `test`, fuori da `FINGER_HARD_IDS` e dalle famiglie finger_max / limit_power, TUT di `prescription_defaults` ≤ 600 s.
  - **Lista low proposta:** `hang_rampup_progressive`, `pocket_rampup_hangboard`, `single_finger_pocket_rampup`, `dead_hang_easy`, `warmup_repeaters_large`, `finger_warmup_generic`, `finger_recruitment_pulls`, `sub_max_capacity_hang` (40-50 %), `bar_dead_hang`, `hangboard_moving_hangs` (piedi a terra), `long_duration_hang`.
  - **Al limite (45-55 %):** `long_interval_repeaters` e `repeater_sub_max_endurance` → low solo con le note portate a ≤ 50 %.
  - **Restano high:** `intermittent_dead_hangs` (55-65 %), `repeater_15_15`, `lopez_subhangs`, `density_hangs`, tutte le 7/3.
- **Sessioni di catalogo.** `_SESSION_META[sid]["finger_load"]` sulle 15 voci dita, con `finger == (finger_load is not None)` pinnato da un test.
  - **high:** `strength_long`, `power_contact_gym`, `limit_boulder_gym`, `finger_strength_home` (in PE è il 3 × 7 s), `route_projecting_gym`, `finger_maintenance_home` / `_gym` e `finger_endurance_short` (ripetute), i 6 test dita.
  - **low:** `finger_aerobic_base`.
  - **Pin di coerenza.** Riuso dell'infrastruttura di `test_b414_session_tags_pe.py`: per ogni sessione risolta su profili, palestre e fasi, il livello derivato dagli esercizi deve essere ≤ quello dichiarato (None < low < high), con gli stessi `KNOWN`.
  - **`finger_aerobic_base` va reso onesto (C):** il template `finger_aerobic_endurance` può pescare `intermittent_dead_hangs` al 55-65 % → escluderlo. Nei golden oggi si risolve in `bar_dead_hang` e ramp-up, quindi nessuna chiave si muove.
- **Custom e generate.** Nuova `session_tags.derive_finger_load(exercises)`; `derive_session_tags` resta invariata.
  - Ignora i warm-up leggeri (B392) e le sospensioni sub-max dopo intervalli PE (B414 E2).
  - Gli id di `FINGER_HARD_IDS` → high; per il resto il massimo dei `finger_load`; un esercizio dita senza campo → high.
  - Salvato in `tags.finger_load` all'inserimento (`replanner_v1.py:1917`, `:2113-2121`), solo se la sessione carica le dita.
  - `session_tags` legge il catalogo dalla proiezione `progression_v1._load_catalog_cache` (`progression_v1.py:770-800`): serve un campo additivo, come fece B345. È un modulo STOP, coperto dallo STOP di questo brief.
- **Una sola lettura: `stimulus.finger_load_of(s)`**, nell'ordine:
  1. `tags.finger_load` salvato;
  2. altrimenti, se `tags.finger` non è un `False` esplicito, il valore di `_SESSION_META` per id;
  3. altrimenti `tags.finger` True → **high** (i tag vecchi valgono high, come chiesto);
  4. altrimenti esercizi finger-hard → high (tag stantii, per esempio la custom del 26/10);
  5. altrimenti `None`.
- **Le voci di catalogo nel piano non ricevono il campo**: il livello si legge per id, quindi il golden a300 non cambia per la sola rappresentazione.
- **`is_finger_hard_session`**: la prima clausola diventa finger ∧ hard ∧ `finger_load_of ≠ low` (corregge §1.3-2).

### 2.3 Spacing in ore

- **Orologio unico.** `complementary_v1.SLOT_HOUR` (08 / 13 / 19), già usato da `guards_v1._clock` e da `hiit_too_close`; sessione senza slot → 19.
- **high–high:** invariato, calendario, |Δgiorni| ≤ `ceil(1 × mult)` (decisione: «mai giorni consecutivi»).
- **low–high (in entrambi gli ordini) e low–low:** ≥ 6 h × `recovery_multiplier` sull'orologio; al massimo 2 low al giorno. Con tre slot è vietata solo la coppia mattina + pranzo (5 h); pranzo → sera fa 6 h ed è ammessa.
- **Falesia = high su [08:00, 18:00] del suo giorno.** `OUTDOOR_START_HOUR` esiste già; `OUTDOOR_END_HOUR = 18` è nuovo, ENGINEERING CONSTANT. Ne segue: nessuna sessione dita il giorno stesso; la sera prima e la mattina dopo vanno bene per una low.
- **Costanti nuove accanto a `FINGER_GAP_H`** (`retest_policy`): `FINGER_LOW_GAP_H` 6, `FINGER_LOW_MAX_PER_DAY` 2, `FINGER_HARD_WEEKLY_MAX` 3, `MAX_HANG_WEEKLY_MAX` 2, `CRAG_BLOCK_MIN_DAYS` 2, `CRAG_BLOCK_FINGER_H` 72.

### 2.4 Planner: tetto e max-hang, solo sui piazzamenti dell'engine

- **Un solo gate**, `_finger_ok(offset, slot, sid)`, al posto delle undici copie di §1.2. `finger_day_offsets` diventa «giorni high» (per i high, stessa semantica di oggi); in più `finger_low_slots: [(offset, ora)]`. PASS 2 entra nel gate e registra (§1.3-1).
- **Tetto.** Si contano i giorni dita-hard della settimana di calendario (lun-dom, come il cap hard):
  - le sessioni dell'engine;
  - i giorni vissuti (B390);
  - le sessioni dell'utente (B414);
  - la falesia della settimana.

  Un piazzamento dita-hard su un giorno nuovo richiede `< 3` giorni già contati; un max-hang richiede `< 2`. Sostituire una sessione dita-hard non aggiunge giorni: stessa logica di `_hard_ok` (`:2881-2899`), così il test che prende il posto del limit resta ammesso.
- **Le sessioni dell'utente contano e non si spostano mai.** Se superano già il tetto, l'engine non aggiunge dita-hard; lo dicono `unmet_stimulus` e il debito A294.
- **Ultimo slot disponibile.** Oggi decide l'ordine del pool: nella simulazione SP vince il limit. Proposta: vince la key a priorità più alta; finger_max e limit sono entrambe priorità 1 → domanda 1.
- **Invariati di proposito:** `targets.finger_days` conta high + low (il digest non si muove); la presenza di PASS 2.5 resta «qualunque dito».

### 2.5 R2: ancora del planner e alert

- **Quali giorni sono falesia dura.** Nuovo input opzionale di `generate_phase_week`, `crag_hard_dates`, calcolato in `week.py:855-919` con `outdoor_fatigue_days`: è dal log, la stessa lista degli alert. Con `None` il planner usa la lettura dichiarata di B382(b); test e script restano invariati.
- **Ancora.** Un run è una sequenza di ≥ 2 giorni di falesia dura consecutivi, anche a cavallo della settimana (offset negativi); `c` è l'ultimo giorno.
  - **c+1:** riposo vero. Escluso dai giorni dell'engine prima del pruning, come un giorno outdoor; i pranzi complementari restano (decisione 2).
  - **c+2:** niente hard. Si riusa `day_intensity_reduced`, già letto da PASS 1, 2.7 e 3a; va aggiunto a 2.5, 2.6 e PASS 3 legacy.
  - **dita-high** solo con `t ≥ c·24 + 18 + 72`, cioè dalla **sera di c+3**: dopo un sabato-domenica, mercoledì sera sì, mercoledì a pranzo no.
- **Alert `crag_block` in `guards_v1`**, sulla stessa `tl.outdoor` (B372). `detail` vale `rest_day`, `no_hard` o `finger_72h`; `with` contiene i giorni del run. `post_outdoor` lascia il giorno c+1 a `crag_block` (un alert per sessione).

### 2.6 Alert (tutto ciò che segue l'utente)

| Codice | Regola | Nuovo |
|---|---|---|
| `finger_gap` | solo high–high (il titolo FE «Finger gap under 48 h» resta vero) | ristretto |
| `finger_low_gap` | low–high / low–low < 6 h, oppure più di 2 low al giorno | sì |
| `finger_hard_cap` | > 3 giorni dita-hard nella settimana, falesia B372 compresa; segnala le ultime sessioni oltre il tetto (in `_COUNT_CODES`, come `hard_cap`) | sì |
| `max_hang_cap` | > 2 giorni max-hang (`_COUNT_CODES`) | sì |
| `crag_block` | R2 (§2.5) | sì |

Ritocchi agli alert esistenti:
- `_post_outdoor`: hard **o finger-high** (una low il giorno dopo la falesia non scatta più).
- `_hard_back_to_back:552`: esclude solo le finger-high; altrimenti una hard con dita leggere il giorno prima della falesia non avrebbe alcun alert.
- In `athlete_context` le ragioni nuove vanno in `finger_warnings` / `day_warnings`, mai in `finger_codes` (§0).

**Effetto voluto, gratis.** PASS 2.7 (`planner_v2.py:1302`) e le proposte A294 (`key_sessions_v1.py:1100-1118`) scartano già ogni piazzamento che aggiunge un alert. Appena gli alert esistono, quei due percorsi dell'engine rispettano tetto e R2 senza codice nel planner.

## 3. Consumatori e test che si muovono

### 3.1 Consumatori

| File | Cambia | Passo |
|---|---|---|
| `guards_v1.py` | `finger_gap` ristretto; quattro codici nuovi; `_post_outdoor`, `_hard_back_to_back:552` | A, C |
| `athlete_context.py` | spacing solo high; avvisi tetto / R2 fuori da `finger_max_ok`; `_session_view` + `finger_load`; B395 confronta anche `finger_load` (assente con finger True = high, quindi niente falsi stale); testi IT / EN | A, C |
| `stimulus.py` | `finger_load_of`, `is_max_hang_session`, clausola di `is_finger_hard_session` | C |
| `session_tags.py`, `progression_v1.py:770-800` | `derive_finger_load`; campo additivo nella proiezione | C |
| `replanner_v1.py` | salvataggio a `:1917` e `:2113-2121`; `suggest_sessions` (−1000 solo high accanto a high); `_stimulus_replacement` confronta (hard, livello). Il codice morto `:1286-1395` resta | C |
| `key_sessions_v1.py` | `:1046` finger → high; nient'altro (`finger_hard_days` invariato) | C |
| `planner_v2.py` | `_SESSION_META.finger_load`; il gate; PASS 2; tetti; R2; input `crag_hard_dates` | C, D |
| `api/routers/week.py:855-919` | calcola e passa `crag_hard_dates` | D |
| `exercises.json`, template `finger_aerobic_endurance` | campo e esclusione | B |
| frontend `week-alerts.ts`, `types.ts` (badge low opzionale in `session-card.tsx`) | titoli dei quattro codici; fino ad allora fallback «Recovery alert» + messaggio del backend | E |
| `composer_guard`, `finger_key_guard`, `retest_policy`, `phase_anchor`, `complementary_v1`, `closed_loop_v1`, `adhoc_builder`, `body_part_picker` | **invariati**: leggono il booleano o il finger-hard, che restano | — |
| docs | `ENGINE_ARCHITECTURE.md:214`, `:241`, `:272`, `:291`, `:300`, `:306`, `:406`, `:426`, `:1145`; `vocabulary_v1.md` (enum + codici); `API_ENDPOINTS.md` (codici guardia); `user_guide_v1.md:797` + alert nuovi; `.claude/commands/custom-session.md:36`. `athlete_plan.md` §5 è già allineato nel worktree (modifica D288 non ancora committata) | tutti |

### 3.2 Golden

- **`a300_identity_digests.json` (180).** Atteso **0 cambi** a ogni passo, verificato sull'output attuale della matrice:
  - nessuna settimana supera 3 giorni dita-hard (distribuzione 0/1/2/3 → 57/49/52/22) né 2 max-hang;
  - nessuna ha falesia;
  - nessun PASS 2 piazza dita;
  - l'unica sessione low (`finger_aerobic_base`, caso `split|1|base|lead|2026-10-15`, domenica mattina, due giorni dopo `finger_maintenance_home`) resta dov'è con la regola delle 6 h.

  Un digest che cambia va spiegato caso per caso, come fece A305.
- **`c272_resolver_golden.json`, `b413_lunch_ladder_golden.json`, `a290_untested_golden.json`, `b364_untested_golden.json`.** Sono golden del **resolver**: il codice R1/R2 non li tocca. Il passo B aggiunge un campo che il resolver non copia nelle istanze (`resolve_session.py:1535-1575`); il pool del composer è hashato sugli id. L'esclusione di `intermittent_dead_hangs` sposterebbe solo le 6 chiavi `finger_aerobic_base` di c272 / b413, e oggi scelgono `bar_dead_hang` → 0 attese (da confermare in Fase 2).

### 3.3 Test

**Da aggiornare (attesi):**
- `test_b395_stale_custom_tags.py`: `finger_load` in `_DERIVED_TAG_KEYS`.
- `test_a293_athlete_context_script.py:159`: se `--simulate` stampa anche il livello.
- `test_a245_catalog_meta_consistency.py`: pin finger ⇔ finger_load.
- `test_b414_session_tags_pe.py`: pin dei livelli accanto a quello del booleano.

**Da rileggere in Fase 2** (scenari solo high o con una sola falesia: atteso verde):
- guardie: `test_a301_guards_are_alerts.py` (liste esatte a `:100-184`; `TestPlannerStillRespectsGuards:364-388`), `test_b372_outdoor_fatigue_alerts.py` (liste esatte a `:220-334`, mai due falesie consecutive);
- planner: `test_b382_slot_empty_crag_hard.py`, `test_b390_midweek_past_hard.py`, `test_b414_user_session_anchors.py`, `test_b415_planner_sees_customs.py`, `test_a282_quality_floors.py`, `test_planner_v2.py`, `test_a305_key_stimulus_pass.py`, `test_a300_complementary_slots.py`;
- retest: `test_a289_retest_policy.py`, `test_a319_retest_rules.py`, `test_b400_retest_merge_view.py` (PASS 3a con il tetto);
- athlete context: `test_d287_athlete_context_alerts.py` e `test_a293_athlete_context.py` (usano `finger_maintenance_gym`, che resta high), `test_a297_coach_athlete_context.py` (`exclude_ids` invariati: gli avvisi nuovi non escludono), `test_b385_athlete_context_render.py`;
- tag e stimoli: `test_b392_warmup_finger_tag.py`, `test_b405_coach_inbox.py`, `test_a288_stimulus.py`;
- replanner: `test_replanning_v1.py`, `test_quick_add.py`.

**Nuovi:**
- livelli esercizi e catalogo;
- `derive_finger_load`;
- `finger_load_of` (precedenze, tag vecchi = high);
- `is_finger_hard_session` sulle custom miste;
- planner: PASS 2 con gap; low a pranzo + high la sera; low–low ≤ 2;
- tetti (solo engine; l'utente conta e non si sposta; sostituzione neutra);
- R2 (falesia sab + dom → lunedì riposo, martedì niente hard, dita-high dal mercoledì sera);
- fallback di `crag_hard_dates`;
- i quattro codici;
- avvisi `athlete_context` che non toccano `finger_max_ok`.

**Invariante da estendere:** `TestPlannerStillRespectsGuards` («il planner da solo non produce alert») con falesie e cap 5 alla Daniele.

## 4. Effetto sulle settimane reali di Daniele (mirror del 13/11, in memoria)

Conteggio con la lettura di §2: giorni dita-hard, falesia dura B372 compresa. Cap hard di Daniele: 4 fino al 05/10, poi 5. Il tetto dita è un vincolo separato.

| Settimana | Fase | Giorni dita-hard | Tot. | Max-hang | Esito R1 / R2 |
|---|---|---|---|---|---|
| 21/09 | SP | test 24/09, falesia 26 e 27/09 | 3 | 1 | R2: lunedì 28/09 `technique_focus_gym` (engine) → alert `crag_block`. L'ancora non sarebbe scattata: settimana generata il 05/09 |
| 05/10 | SP | custom max hang 05/10, custom limit 08/10, falesia 10 e 11/10 | **4** | 1 | `finger_hard_cap` = **alert** (custom + falesia sono azioni sue). R2 rispettato: 12/10 riposo, 13/10 non hard, 14/10 sera ≥ 72 h |
| 12/10 | SP | power_contact 14, strength_long 15 (spostato da lui), falesia 17 | 3 | 1 | — (il `finger_gap` 14→15 esiste già: è uno spostamento suo) |
| **19/10** | PE | custom limit 24/10 | **1** | 0 | — |
| **26/10** | PE | custom gara 26/10 (tag stantio finger False, ma esercizi finger-hard), custom gara 28/10. Vercors 31/10–1/11 facile dal log | **2** | 0 | — (niente run R2: falesia non dura) |
| **02/11** | PE | custom max hang 02/11, power_contact 05/11, custom gara 07/11 | **3** | 1 | — |
| **09/11** | Perf | custom limit 09/11, `limit_boulder_gym` 13/11 (spostato da lui), `route_projecting_gym` 14/11 | **3** | 0 | al tetto: avviso per domenica 15/11 (il `finger_gap` 13→14 resta, è uno spostamento suo) |
| 16/11, 23/11 | Perf | limit mercoledì + progetto sabato | 2 | 0 | — |

**Il tetto di 3 non avrebbe cambiato nulla dal 19/10 al 09/11:** 1, 2, 3, 3; max-hang al massimo 1 a settimana; nessun blocco R2 (il Vercors è facile dal log). Nel periodo solo il 05/10 supera il tetto, e lì sarebbe un alert, non una modifica.

**Cosa libera il livello low: per lui, nulla.**
- Le 10 custom dita da settembre a novembre contengono tutte almeno un esercizio high: `limit_bouldering` ×4, `three_attempt_comp` ×3, `max_hang_7s` ×2, `horst_7_53` ×1. I ramp-up sono sempre accompagnati.
- `finger_aerobic_base` si fa solo a casa e lui la sera si allena in palestra: l'engine non la piazza mai.
- Da domani una custom fatta solo di ramp-up o di sospensioni aerobiche non mette più «NO dita max» né `finger_gap` sui giorni vicini.
- Una custom «ramp-up + trazioni zavorrate» smette di bloccare il test di 72 h.
- Nel catalogo, il guadagno va a chi si allena a casa in base (la coppia di PASS 2 di §1.3-1) e al blocco low-load che C-CATALOG-METHODOLOGY (c) deve ancora aggiungere.

**L'engine con i suoi input** (6 sere, pranzi complementari, cap 5, settimane del 16 e del 23/11):
- **Settimane pulite:** SP 3 giorni dita-hard (1 max-hang), PE 2, Performance 2, Base 1 → il tetto non scatta mai.
- **Schema «falesia sab + dom ogni weekend»:**
  - SP: oggi lunedì technique, martedì `limit_boulder_gym`, giovedì `power_contact_gym` + 2 falesia = **4**; R2 segnala il lunedì (non riposo) e il martedì (hard e dita < 72 h).
  - Con R1 + R2: lunedì riposo, martedì non hard, **un solo** dita-high (mercoledì o giovedì). In SP resta una sola delle due key a priorità 1 (domanda 1).
  - PE: il martedì perde `power_endurance_gym`.
  - Performance: il lunedì technique diventa riposo.
- **Contesto, non R1/R2:** `low_rest_days` scatta già ogni settimana dal 19/10 al 23/11 (6 sere + pranzi; una custom «Work —» a pranzo non è complementare per la definizione di oggi).

## 5. Rischi e primo passo minimo sicuro

**Rischi:**
1. **Undici siti di piazzamento in `planner_v2`.** Mancarne uno riapre il buco (è già successo con il pre-trip, A281). Mitigazione: un solo gate, più l'invariante «il planner da solo non produce alert» estesa a falesie e cap 5.
2. **Gli alert vengono prima del planner** (passo A prima del D). In SP con weekend di falesia, la settimana dell'engine mostrerà `finger_hard_cap` / `crag_block` sulle proprie sessioni finché D non è in produzione. Per Daniele la finestra è sicura: oggi è in Performance, poi deload fino al 06/12, poi base. In Performance l'alert R2 sul lunedì dopo due giorni duri è corretto.
3. **Accoppiamento PASS 2.7 / A294.** Gli alert nuovi cambiano cosa piazzano PASS 2.7 e le proposte. È voluto (engine), ma è un cambio di comportamento del planner senza toccarne il codice: per questo il passo A resta sotto STOP.
4. **R2 nel planner ha portata limitata** finché la falesia non marca stale le settimane (§1.3-5) → domanda 3.
5. **Due letture della falesia.** L'input `crag_hard_dates` le unifica; senza input si torna alla lettura dichiarata (conservativa).
6. **Custom salvate.** Le custom future portano `finger_load`; quelle vecchie valgono high. Un riallineamento B395 serve solo per custom ancora da fare e solo-low: oggi Daniele non ne ha (l'unica pianificata, 19/11 «Work — gambe», non ha dita).
7. **Composer.** Un avviso nuovo in `finger_codes` diventerebbe un rifiuto: va testato che `exclude_ids` non cambi.

**Primo passo minimo sicuro → passo A, solo alert.** Tetto di 3 giorni dita-hard (falesia dentro), tetto di 2 max-hang e R2 in `guards_v1` e `athlete_context`:
- usa solo predicati che esistono già (`is_finger_hard_session`, famiglia finger_max, `outdoor_fatigue_days`);
- nessuna riga di `planner_v2`, nessun campo nuovo, nessuna migrazione;
- golden attesi invariati; Daniele vede subito tetto e blocco falesia.

Poi i livelli (B dati, C codice). Le regole nel planner (D) vengono per ultime, quando gli alert hanno girato almeno una settimana.

## 6. Effort e ordine

| # | Passo | Tipo | Contenuto | Effort | STOP |
|---|---|---|---|---|---|
| A | Tetti + R2 come alert | A | 4 codici in `guards_v1` (3 senza livelli, `finger_low_gap` arriva con C); avvisi `athlete_context` fuori da `finger_max_ok`; docs | S (~1 g) | sì, per l'accoppiamento PASS 2.7 / A294 |
| B | Livelli negli esercizi | C | `finger_load` su 55 esercizi + test di regola; `finger_aerobic_base` onesto; `vocabulary_v1` | S (~0,5 g) | no |
| C | Livelli e spacing | A | `finger_load_of`; `_SESSION_META`; `derive_finger_load` + salvataggio; `is_finger_hard_session`; `finger_gap` / `finger_low_gap`; gate nel planner per lo spacing + **fix di PASS 2**; `athlete_context`, `key_sessions`, `suggest_sessions` | M (~2 g) | sì |
| D | Planner: tetti + ancora R2 | A | tetto e max-hang solo sull'engine (sostituzione neutra, scelta per key); ancora R2; input `crag_hard_dates` da `week.py` | M (~1,5-2 g) | sì |
| E | Frontend | UI | titoli dei 4 codici (+ badge «dita leggero» opzionale) | XS (~0,5 g) | branch + preview + OK |

Totale ≈ 5-6 giorni. Ordine: A → B → C → D → E, ogni passo mergiato prima del successivo. Ogni brief chiude con `sync_status`, roadmap (`A-FINGER-LOAD-TIERS` diviso nei passi, C-CATALOG-METHODOLOGY (c) collegato) e guida utente per gli alert nuovi.

## 7. Domande aperte (solo quelle che servono a Daniele)

1. **SP con due giorni duri in falesia nella stessa settimana:** il tetto lascia all'engine un solo dita-hard. Max hang (finger_max) o limit? *Proposta: max hang, perché la falesia dà già lo stimolo da limit.* Oggi, per ordine del pool, vincerebbe il limit.
2. **Ripetute e IntHangs al 60-80 %:** «high» solo per lo spacing di 48 h, oppure anche dentro il tetto di 3? *Proposta: solo spacing; il tetto conta le esposizioni dita-hard della definizione A288.*
3. **Dopo un weekend di falesia (≥ 2 giorni duri) la settimana seguente è già generata:** va rigenerata, così l'engine sposta le **proprie** sessioni (le tue restano intatte), oppure basta l'alert? *Proposta: solo alert (A301); l'ancora R2 agisce quando la settimana viene generata dopo.*
4. **Tentativi da rotpunkt indoor su corda dentro una custom** (`route_redpoint_attempt`, per esempio D-Summit del 25/10): sono dita-high come un giorno duro in falesia? `route_projecting_gym` di catalogo lo è già. *Proposta: sì.* Il 25/10 conterebbe e la settimana del 19/10 passerebbe da 1 a 2.

---

**Verifiche eseguite** (script nello scratchpad della sessione, non nel repo; tutto in memoria, mirror in sola lettura, nessun pytest):
- `sim_r1_r2.py`: conteggi per settimana, run R2, alert attuali;
- `customs_tiers.py`: livello delle custom di Daniele;
- `sim_engine_weeks.py` / `sim_crag_weeks.py`: l'engine con i suoi input, settimane pulite e con falesia;
- `sim_pass2_gap.py` / `sim_broad.py`: 120 + 640 settimane sintetiche;
- `sim_a300_matrix.py` / `sim_a300_low.py` / `sim_a300_fab.py`: la matrice dei 180 casi a300.
