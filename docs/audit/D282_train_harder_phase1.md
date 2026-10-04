# D282 — Programma «train harder»: sintesi della Fase 1 e decisioni vincolanti

> **Data:** 2026-10-04 · **Tipo:** D (documentazione, sola lettura) · committato con [[A288]]
> **Fonte:** sette analisi di Fase 1 (B364, R2, R3, R4, R5, R6, R7), la verifica incrociata e le decisioni di Daniele del 04/10.
> **Stato:** programma approvato («parti con 1, 2 e 3 in ordine, poi fai anche gli altri»). Questo file è il riferimento per tutti i brief del programma. **Dove un'analisi di Fase 1 e le decisioni (§6) non sono d'accordo, vincono le decisioni.**

## 1. Perché il programma

Daniele ha chiesto che l'app lo faccia allenare più duro, senza perdere la prudenza:
- intensità più alte sugli esercizi ancorati a un test (max hang, trazioni zavorrate);
- massimale ufficiale separato dal carico di lavoro;
- una policy di retest che non dipenda dalle etichette;
- sessioni chiave ben visibili nella settimana;
- feedback misurato;
- un limit che ricordi davvero il suo livello;
- sessioni custom (Claude Code e composer in-app) che sappiano dove si trova nel macrociclo.

Le sette analisi di Fase 1 erano corrette prese una per una. Insieme, però, **reimplementavano in modo diverso sei concetti**. Implementarle in ordine avrebbe prodotto numeri diversi a seconda della schermata (piano, composer, custom, coach). I sei concetti:
1. la rampa di rientro;
2. il registro delle esposizioni;
3. il massimale ufficiale con la sua confidenza;
4. la posizione nel macrociclo;
5. le sessioni chiave;
6. la funzione del carico.

## 2. I conflitti e come li ha risolti la verifica incrociata

| Concetto | Definizioni trovate | Decisione | Proprietario |
|---|---|---|---|
| Rampa di rientro | 4 incompatibili: stacco 14 o 21 gg, il test conta o no, variante «neurale» | una sola `reentry_step(state, family, as_of)`: stacco ≥ 14 gg, il test conta, niente variante neurale, fattore sul tetto 0,90 / 0,95 / 1,0 | **A288** |
| Registro esposizioni | 5 implementazioni, famiglie diverse | una sola tabella delle famiglie in `stimulus.py` e viste in lettura sopra week_plans, archivio, free session e outdoor; persistito **una volta** in `progression_counters.stimulus_exposures` | A288 (viste), B364 (persistenza) |
| Massimale e confidenza | 4 letture: baselines dopo `estimate_missing_baselines` (bug di R3), solo `tests.*`, test della stessa durata vecchio di 6 mesi, confidenza salvata che non misura nulla | `official_max(state, protocol, as_of)`: il test più fresco, con il 5" convertito dal 7"; `test_confidence` **calcolata** con le settimane archiviate | **A288** |
| Posizione nel macrociclo | 3 helper uguali (R2, R3, R7) | resta solo `macro_position.py`, a cui `deps` delega, con test di parità sulla pausa A223 | **A288** |
| Sessioni chiave | 4 definizioni (B364, R5, R6c, R7) | proprietario R5 (→ A294); ricavate in lettura, mai salvate | A294 |
| Funzione del carico | B364 e R3 sono lo stesso brief | una sola `anchored_load`, tabella di B364; R3 confluisce in B364 | B364 |
| Progressione dal feedback | 3 regole | rivista da Daniele il 04/10: le etichette **alzano** il carico di lavoro, sempre dentro il tetto del massimale ufficiale (§6) | B364 / A295 |
| Retest anticipato | 2 contatori e 2 soglie | un solo `progression_counters.retest_signals`, nella forma di R4; solo la retest policy programma test | B364 / A289 |
| Blocco prima del retest | 3 risposte diverse per il 24/10 | una sola definizione di «giornata bloccante» e una costante `RETEST_BLOCK_H` | **A288** (definizione), A289 (uso) |
| Soglia outdoor | 3 criteri (RP−2, RP−1, load_score ≥ 25) | una sola regola: tentativo ≥ RP − 2 gradini | **A288** |

La verifica incrociata completa (conflitti di file, dipendenze d'ordine, rischi da revisore) è stata la base di questo documento. Le sue conclusioni sono riportate qui; le analisi originali restano nello scratchpad della sessione.

## 3. Ordine dei brief

Serializzati: ognuno si mergia prima che parta il successivo.

| # | Brief | Contenuto |
|---|---|---|
| 1 | **B365** ✅ | hotfix limit (R6.0): memoria per famiglia e superficie a 180 gg, rientro −½ grado per 2 sedute, fix di `target_grade_low` |
| 2 | **A288** ✅ | fondamenta F0, nessun cambio di comportamento (§4) + questo documento |
| 3 | B364 | massimale ufficiale ≠ carico di lavoro, assorbe R3: `anchored_load`, fix B156, registro, `retest_signals`, `load_mode` custom, migrazione |
| 4 | A289 | retest policy in PASS 3 + `retest_status` per la UI |
| 5 | B366 | ripple: mai riscrivere custom/forced, dopo il reconcile, riportato in `adjustments` |
| 6 | A290 | rotazione delle ancore di fase nel resolver (R2) |
| 7 | A291 | scala gradi con «+», mezzi gradi (R6a) |
| 8 | A292 | evidenza onsight + offset PE (R6b/R6-PE), entro il 19/10 |
| 9 | A293 | contesto atleta per Claude Code (R7a) |
| 10 | A294 | sessioni chiave (R5), backend + frontend |
| 11 | A295 | feedback misurato (R4), backend + frontend |
| 12 | A296 | `limit_log` + logger dei problemi (R6c) |
| 13 | A297 | contesto nel composer e nel coach, dietro `COACH_ATHLETE_CONTEXT` (R7b) |

R6d (sessioni di progetto) è rimandato: servono la via di progetto di Daniele e le sue sezioni.

## 4. Cosa contiene A288 (F0)

Tre moduli puri e deterministici, in sola lettura. Nessuno di loro chiama `date.today()` o scrive lo stato. Nessun modulo di produzione li usa ancora, tranne la delega di `deps`.

- **`backend/engine/macro_position.py`**: `effective_anchor`, `phase_and_week_on`, `position_on`. `deps._effective_anchor` e `deps.current_phase_and_week` delegano qui con `today` opzionale. La parità giorno per giorno con l'implementazione precedente è testata con sei configurazioni di pausa.
- **`backend/engine/stimulus.py`**:
  - tabella delle famiglie `finger_max` / `pulling_max` / `limit_power` / `power_endurance`, derivata dal catalogo e pinnata da un test che ricostruisce la regola;
  - `stimulus_of` e `session_stimuli`, con **una sola regola** sulla lista esercizi: actual, altrimenti planned, mai l'unione; per le sessioni del player servono `completed_sets ≥ 1`;
  - vista `exposures` sopra week_plans done, `week_archive`, free session e registro;
  - regola OUTDOOR-HARD;
  - `finger_hard_days`, che rende visibili anche le custom;
  - `is_pulling_hard_session`.
- **`backend/engine/retest_policy.py`**:
  - `official_max` e `is_tested`;
  - `test_confidence(…, archived_weeks)`;
  - `reentry_step`;
  - `is_heavy_pulling_session`;
  - costanti condivise: `FINGER_GAP_H` 48, `RETEST_BLOCK_H` 72, `PULL_TEST_BLOCK_H` 48, `LOW_CONF_*`, `TEST_FRESH_DAYS` 90, `HANG_PCT_PER_S` 0,015. Le costanti senza fonte pubblicata sono marcate **ENGINEERING CONSTANT** nel codice.

### Scelte di A288 da conoscere

- **Famiglia `finger_max`:** è la regola del catalogo «domain `finger_max_strength` su un bordo definito». Restano fuori min_edge_hang (a corpo libero, nessun bordo confrontabile) e anche **max_hang_10s / lp_max_lift_10s**, che R3 includeva: il catalogo li classifica solo `finger_strength`.
- **Esposizioni contate in giorni distinti.** Due esercizi della stessa famiglia nella stessa giornata valgono una esposizione.
- **Una sessione done senza log** conta con i suoi esercizi pianificati (`evidence: planned`). Una entry loggata vale `evidence: measured`. Le viste espongono il campo, così chi consuma può scegliere quale evidenza accettare.
- **Outdoor:** è solo una giornata dita dura, mai un'esposizione di famiglia (decisione R7). Free session boulder: diventa esposizione `limit_power` con ≥ 2 problemi ≥ soglia. Free session lead: non classificata, perché i suoi gradi sono validati sulla scala Font.
- **Trazione pesante senza carico leggibile**, o senza un massimale con cui confrontarla, conta come pesante. È la scelta prudente: può solo ritardare un test.

## 5. Cosa A288 ha verificato sui dati di Daniele (snapshot del 04/10 + archivio a 8 settimane)

- **Massimali ufficiali al 13/10:**
  - hang 7" 116 kg (24/09, testato, 19 gg);
  - hang 5" **119,5** (convertito dal 7"; il 5" da 120 kg del 17/03 è ignorato);
  - trazione 2RM 123 (1RM 128,9).
- **Confidenza:** **entrambi i test del 24/09 sono a bassa confidenza.** Nei 21 giorni prima non ci sono esposizioni né dita né di trazione; le settimane 07 e 14/09 sono state lette da `week_archive`. È chiuso il dubbio di cross-check §6.2: l'affermazione di B364 sulla trazione «low» ora è dimostrata.
- **Rampa:**
  - hang del 13/10 → n = 1, ×0,90 (stacco di 19 gg dal test);
  - trazione del 09/10 → n = 3, ×1,0 (24/09 e 04/10).
- **Soglia outdoor-hard:** 7c+ lead e 7B boulder. Giornate dure da agosto: 02/08, 05/08, 26/08, 29/08, 30/08, 03/09, 26/09, 27/09, 03/10.
- **Aperto per A289:** con la regola letterale «sessione taggata pulling + hard», `power_endurance_gym` del 22/10 conta come trazione pesante. Il test di trazione accoppiato del 24/10 cade a 48 h, cioè proprio sulla soglia `PULL_TEST_BLOCK_H`. A289 deve decidere il caso al confine e riportare l'esito (decisione: «tieni il 24/10 se la regola unificata lo consente, altrimenti il primo giorno ammesso, 25/10»).

## 6. Decisioni vincolanti (copia integrale di `DECISIONS.md`, 2026-10-04)

### Train-harder programme — decisions (2026-10-04)

Daniele approved the programme ("parti con 1, 2 e 3 in ordine, poi fai anche gli altri", "anche frontend senza preview", "vai, non fermarti").
These decisions close the open questions of the Phase 1 analyses (phase1/*.json) and the conflicts of phase1/cross_check.md.
Where a Phase 1 analysis and this file disagree, THIS FILE WINS. Where the cross-check assigns ownership of a concept to one brief, follow it.

#### Global
- Frontend changes go to main WITHOUT Vercel preview (explicit exception granted by Daniele for this programme). They still must pass `npm run build`, eslint on touched files and vitest.
- Every engine constant without a published source is declared as an ENGINEERING CONSTANT in a comment (0.015 per second, PRILEPIN_CAP bands, ramp 0.90/0.95, BW thresholds, outdoor thresholds).
- Higher intensities / anchor rules apply ONLY to users with a tested baseline (official_max with source test/test_session and <90 days). Untested users: behaviour bit-for-bit unchanged (regression test required).
- Past/completed sessions immutable. Deterministic. No regeneration of cached week plans; prod data changes only through migration scripts with --dry-run (never run by implementers — Claude main loop runs them after deploy).
- Official max = tests/baselines, written ONLY by test logs. Feedback writes only working loads.

#### Brief IDs and order (serialized; each merged before the next starts)
1. B365 — limit hotfix (R6.0): limit memory per family+surface, 180 d, re-entry −1 half grade for 2 sessions, target_grade_low fix.
2. A288 — F0 foundations, NO behaviour change: macro_position.py (+deps delegation, parity test incl. A223 pause), stimulus.py (single family table, stimulus_of, session_stimuli, exposure views over week_plans done + custom actual + outdoor + free), retest_policy.py read-only primitives (official_max, test_confidence with archived_weeks from week_archive, reentry_step), shared constants (FINGER_GAP_H=48, RETEST_BLOCK_H=72, OUTDOOR_HARD rule). Also commit docs/audit/D282_train_harder_phase1.md summarising the programme + this decisions file.
3. B364 — official max vs working load, absorbs R3 (intensities) and the already-done body-part-picker frontend in worktree ../climb-agent-b364. Single `anchored_load`. Remove e2rm + legacy branch + label-based retest enqueue. B156 fix (test_* in session must not let a training max_hang_7s write the official max). Exposure registry persisted ONCE in progression_counters.stimulus_exposures. retest_signals counter (R4 form). Custom sessions: load_mode 'anchored' default for anchored exercises (computed at read with ?date=), 'fixed' only if user chooses. Migration script scripts/migrate_b364.py (--dry-run default): pop e2rm_total_kg, seed registry (reads week_archive), confidence on 24/09 tests, load_mode on existing customs, rewrite the false "~65%" note on cs_743c5d6d.
4. A289 — retest policy in planner PASS 3 + retest_status payload for UI (±5% stable, next test date + reason).
5. B366 — ripple fix (B-RIPPLE): ripple never rewrites custom/forced, runs after reconcile, reported in adjustments.
6. A290 — R2 phase-anchor rotation in resolve_session (uses F0 views).
7. A291 — R6a grade ladder with + grades, half-grade steps, closed_loop categories from catalog, vocabulary update.
8. A292 — R6b onsight evidence + confirm endpoint, and R6-PE offsets (PE/threshold anchored to max(OS, RP−3 half grades)). Must be live before 2026-10-19.
9. A293 — R7a Claude Code context: backend/engine/athlete_context.py, scripts/athlete_context.py (live Supabase read), .claude/commands/custom-session.md (project slash command / skill), CLAUDE.md section.
10. A294 — R5 key sessions backend + frontend (owns key-session definition, derived not persisted, debt card, badges in /week and /today, re-schedule proposal, custom collision warning, coach/composer exposure). Absorbs "A288 key sessions" of B364 and R6c key_stimulus_status.
11. A295 — R4 measured feedback backend + frontend (absorbs B365-fe of B364).
12. A296 — R6c limit_log + problem logger (source of limit_power exposure for A294).
13. A297 — R7b in-app composer/coach context: single prompt integration point for B364/R4/R5/R6c data, behind flag COACH_ATHLETE_CONTEXT (default on), coach regression documented.
(R6d project sessions deferred: needs Daniele's project route + sections.)

#### Decisions on open questions
Re-entry ramp: gap ≥14 days; the test counts as an exposure; no "neural" variant. factor on cap: n=1 0.90, n=2 0.95, n≥3 1.0; floor_eff = min(floor, cap_eff).
Cap table: B364's (Prilepin bands + (r+2)RM for pulling; hang cap = 3 s of reserve, phase caps SP/perf 0.95, PE 0.90, base 0.85, deload 0.70). To train at 90% the scheme changes (3-4x2), the cap of 4x3 does not rise.
Rep factor: NON-rounded _rep_factor (estimate_1rm_from_reps rounds to 0.1 — do not reuse it for conversion).
5 s hang official max: converted from the freshest 7 s test (never the >90-day 5 s test).
Labels (REVISED by Daniele 2026-10-04: "se dice 3 ripetizioni io ne faccio 3 anche se easy" — he does exactly the prescribed reps, so an easy label IS the signal): labels RAISE the working load for anchored exercises too, always inside the cap from the official max and the escalation limits. Anchored steps: weighted_pullup/chinup easy +2.5 kg, very_easy +5 kg, ok hold, hard −2.5%, very_hard −7.5%; max hangs easy +2 kg, very_easy +4 kg, ok hold, hard −2 kg, very_hard −4 kg. Escalation limits: pulling ≤ +5 kg per session; fingers ≤ +5% of official max per 7 days. Measured last-set reps / hang margin (when given) take precedence and may justify the same or a bigger step within the cap. Accessories without measure: easy +5%, very_easy +10%. Measured success → double progression (+1 rep, then load). Labels NEVER touch the official max and never trigger a retest by themselves. When the cap binds and the label is easy/very_easy, surface "you are at the ceiling of your tested max — the next scheduled retest will raise it" (and count it as a retest_signal only if a measured performance is present).
Early retest: ONLY upward, measured, twice: pull-up last set (AMRAP stop 1 before failure) e1RM > official 1RM; hang held > target+5 s (timed overhold, opt-in, cap target+6 s) at ≥0.90. Single counter progression_counters.retest_signals. Only retest_policy schedules tests.
Retest blockers: hang test blocked <72 h after a finger-hard session (max hang family, limit, outdoor-hard); pull-up test blocked <48 h after a heavy pulling session (weighted pull ≥85% or session tagged pulling hard); very_hard in last 3 days; performance/deload phase; ≤10 days before a trip. Low-confidence test (<2 exposures in the 21 days before, computed with archived weeks) → retest allowed after 28 days. Paired test day: hang first, then pull-up. Daniele 24/10: keep if the unified rule allows it, else next allowed day (25/10); report the outcome.
Outdoor-hard rule (single constant): lead attempt ≥ RP − 2 grades (Daniele: ≥7c+) or boulder ≥ (boulder RP − 2 grades) → finger-hard day.
Key sessions: derived at read (not persisted). SP: finger_max 1 (finger_strength_home OR strength_long — alternatives), limit_power 1, pulling_max 1. PE: intervals/PE 1 + finger maintenance 1 + limit max gap 12 days. Performance: project 1. Base/deload: none. Custom that removes a key → warning with confirm + replace_key when same stimulus. Card after skip (no blocking confirm). Composer filter near finger keys / 72 h pre-test (A259 extension approved). Proposals with side effects are shown declaring them.
Heavy pulling: max 2 heavy (≥85%) pulling sessions per 7 days (chin-up included); no ≥85% pull or front lever within 24 h before limit/strength_long. SP heavy slot: weighted_pullup in up to 2 sessions/week.
Level thresholds for anchors: fingers 1.35×BW total (20 mm 7 s), pulling 1.45×BW total (2RM). min_edge_hang excluded from SP main for weighted-tested users (density variant in PE only).
PE finger session: max_hang_7s maintenance, max 3 sets at 85-90%. PE blocks fixed per phase. Limit: limit_boulder on wall + power_contact on board, fixed per phase; SP campus: campus_max_ladders. Core: intensity floor for advanced users (no plank/dead_bug/plank_shoulder_tap in engine blocks when alternatives exist). Grip: half crimp 20 mm for the phase.
Pain: per session with zone, 0-3. 2 → −10% and hang ≤85% for 7 days; 3 → 14 days, cap 0.80, suggest a limitation. Pain applies BEFORE the floor (floor_eff = min(floor, cap after pain)). Not an RPE field.
Legacy "ok" without contract = not rated. Max-hang label streaks deleted together with label enqueue.
Fatigue: 3 hard in 14 days → floor + warning.
Chin-up: CHINUP_TO_PULLUP_RATIO = 1.0.
Very_hard after plan generated: flag on the test card (no auto-shift).
set_availability losing tests/snapshot: separate B, not in this programme (add to roadmap).
6-week test reminder: derived from retest policy.
Grades: '+' allowed in targets (lead and boulder), half-grade steps, close B-LEAD-HALF-GRADE-ROUNDING. Off-plan sessions stay out of the closed loop (A240/A213) but count for "key session done". Free boulder counts as limit if ≥2 problems ≥ target. _user_edited future sessions keep their exercises; only targets refresh.
R7: script reads live Supabase each run. Claude always shows a preview and waits for OK before writing to prod. Missing stimulus default: inside an existing session. Outdoor near RP counts as finger-hard day only. Composer drops lines violating guards (listed in dropped with reason). Flag "Work" recurrences at each phase change.
Separate Bs to add to roadmap (not implemented now): adaptive_replan insert_recovery deletes customs; skip undo restores regeneration_easy; hard cap ignores done sessions; set_availability loses tests/snapshot.

#### Facts confirmed by Daniele (2026-10-04)
- Kalymnos 25-27/08: Blue Moon 7b, Ataraxia 7b, Meraki 7b were ONSIGHT → real lead onsight is 7b (declared 7a+). Nishiki Alien 7b+ was worked (redpoint).
- Project route: Cima Nikita 8a (Berdorf). Lead RP max 8a+ confirmed. Goal stays 8b RP by 2026-12-06 (engine only displays it).
- Berdorf sandstone: climb only ≥24 h after rain (engine constant for the conditions gate / R6d).

#### Facts asked to Daniele (non-blocking; use logged data meanwhile)
- 24/09 bodyweight: logged 76 kg for the hang test, 78 for pull-up → use the logged values.
- 04/10 pull-up: logged prescribed reps 3 at +30 "ok" → use 4x3.
- Onsight evidence (Kalymnos routes) and project route: handled by A292 confirm flow / deferred R6d.
