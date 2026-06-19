# climb-agent — Active Roadmap

> Last updated: 2026-06-08 (A221 — lazy-archive past week_plans nel cold store `week_archive`: hot state Daniele −77%, flag lazy attivo in prod, beta auto-archiviati. B256 scorporato come item separato. + B257/D241/D242/B255.)
> Archived history: `docs/ROADMAP_v2.md`
> Project status: `PROJECT_BRIEF.md`

---

## Open

**A-COACH-KB-V1 (in progress, Phase B, Session 7a of 7b complete)**
- Phase A audit: `docs/research_kb/coach_kb_v1_audit.md` (commit `75bd4f5`)
- Phase B output: `backend/coach/knowledge/` (Session 1: commit `1971da1`; Session 2: commit `1415b2f`; Session 3: commit `7a98d05`; Session 4: commit `e682efb`; Session 5: commit `f87cdd0`; Session 6: commit `bc3db55`; Session 7a: TBD)
- Steps 1-4 ✅ (scaffold 24 file, L0 11 safety rules, L1 voice, L2 35 decision index)
- Step 5 ✅: Batch A ✅ (files 01-05), Batch B ✅ (files 06-09), Batch C ✅ (files 10-12), Batch D ✅ (files 13-15: tapering/redpoint, female/age/youth, goal-setting/motivation), **Batch E ✅** (files 16-20: assessment interpretation, readiness/overtraining, equipment fallback, lifestyle integration, return-to-training)
- **Step 6 ✅** — `docs/coach/design.md` (2865 word ≈ 3725 tok, target 3000-4000): 9 sezioni (scope, architettura multi-layer, layer spec + catalogo 20 file L3, loading strategy, firewall 14 D-ID engine-internal, citation policy + gap markers, fase A→B→next, governance, open items v1.1). Sostituisce la dangling reference a `_archive/docs/coach_knowledge_base_spec.md` (ghost file confermato D-COACH-AUDIT).
- **Step 8 ✅** — `backend/coach/routing.py` (BM25-style keyword router su `_index.md`, max 3 file, fallback `01_periodization`+`15_goal_setting_motivation`, co-load rule `10_injuries_fingers`→`02_finger_strength` se keyword finger-strength). Tests: `backend/tests/test_coach_routing.py`, 39 test passing (20 per UC + 19 ranking/fallback/cap/co-load/robustness).
- Step 9 ⏳ (28-question regression scoring con Daniele), Step 10 ⏳ (final v1.0 lock + roadmap entry)
- Est. remaining: ~2.5h in Session 7b con Daniele (Steps 9 + 10)
- Step 7 (L4 schema + coach_rationale catalog edits) **DEFERRED to v1.1** per brief scope-change
- Risk register: see brief; key items = books not yet acquired (MacLeod/Ilgner/Mobråten/Christophersen Part 1+2/Bechtel pp.31-90/Lattice 2019 taper newsletter/Hörst redpoint chapter/Bechtel Integrated Strength/Lattice MXEdge protocol/Mujika & Padilla 2000a/b detraining primaries) → L3 files 06, 07, 10, 11, 13, 15, 16, 18, 19, 20 ship v1.0 with explicit `**v1.0 coverage gap**` markers for v1.1 refresh
- **Engine-internal D-ID firewall (D03, D04, D05, D06, D08, D13, D23, D32, D42, D61, D62, D63, D88, D90) honored across all 20 L3 files.** File 16 (assessment interpretation) explicitly firewalls D88/D90 in its v1.0-gap block: the brief mentioned them but they govern engine scheduling/protocol-selection internals, not user-facing knowledge. Verified via `grep -nE "\bD(03|04|05|06|08|13|23|32|42|61|62|63|88|90)\b"` — only hit across Batch E is the firewall block itself in file 16.
- Known token undershoot/overshoot vs §4.6 audit targets: Batch A files ~40-60% of upper-band; Batch B files 06+07 ~25%/13% under, files 08+09 spot-on; Batch C files 10+11+12 ~13%/5%/7% under; Batch D file 13 +12% over, file 14 +2% (spot-on), file 15 +25% over; **Batch E file 16 +10% over (4419 tok vs 4000 target), file 17 -4% (4334 vs 4500 target, spot-on), file 18 +23% over (4310 vs 3500 target — substitution matrix density), file 19 +19% over (4176 vs 3500 — concurrent-training pairings + central fatigue + cut-order detail), file 20 +17% over (4666 vs 4000 — three-band decision tree + D71 reset math + injury-driven differential)**. Content complete and source-anchored; deviation is content-driven, not padding. Documented for v1.1 refresh decision.

**B256 — Rimuovere `current_week_plan` (dedup hot state)** 🔴 high-risk, **scorporato da A221**. Ora che l'hot è `{N-1, N, future}` (post-A221), `current_week_plan` (~234 KB, byte-identico a `week_plans[this_monday()]`) è peso morto duplicato. Reindirizzare i ~10 reader backend a un helper unico `week_plans[this_monday()]` + sistemare lo stash `_prev_week_plan` (alimentato da `week_plans[N]`) + strip su prossima write. Riduzione attesa: hot Daniele 448→~250 KB. **Tocca multi-modulo** (`week.py`, `feedback.py`, `free_session.py`, `deps.py`, …) → richiede Fase 1 di analisi (mappa completa reader) + STOP prima dell'implementazione, branch + test invariante. Reader map di partenza: vedi D242 §2 + nota B256 nell'audit `docs/audit/D242_archive_weekplans.md`.

**B-SUB-TRIAL-RECONCILE — Riconciliazione subscription `trialing` scadute (proposto, da D243/B258)** 🟡 revenue-leak latente. `check_subscription` tratta `trialing` come attivo (`is_active = status in {trialing, active}`) **senza ricontrollare `trial_end`**: se un webhook Stripe (`customer.subscription.updated/deleted`) non arriva, una riga resta `trialing` a tempo indefinito → accesso gratuito permanente. Caso reale osservato: alias `daniele.somensi@ferrero.com` ancora `trialing` con `trial_end=2026-05-01` (scaduto >1 mese). Stripe è source-of-truth e i webhook B226 sono hardened (dedup + retry), quindi il rischio è basso ma non nullo. Opzioni: (a) guard difensivo `status==trialing && trial_end < now → deny` (fail-closed, ma rischia falsi-deny se l'orologio diverge dalla transizione Stripe); (b) job/endpoint di riconciliazione che ripaga lo stato da Stripe per le righe `trialing` scadute; (c) solo monitoraggio (admin dashboard flag "trialing scaduto"). **Da decidere con Daniele** — backend-only, tocca `subscription_guard.py` (sensibile, paywall). Non urgente.

_Nessun follow-up D238 aperto. Tutti i finding del report `docs/audit/D238_test_load_calculation.md` sono chiusi: B251 (Fix 1 catalog), B252 (Fix 3 protocol_version), B253 (Fix `tests_source` legacy backfill)._

_Nessun follow-up D239 aperto. Audit conferma "no bug" — 3 possibili miglioramenti cosmetici suggeriti (vedi §10 di `docs/audit/D239_quote_render_audit.md`) sono P3 e non bloccanti._

_D240 next step **chiuso da C239** (2026-05-26): le 25 proposte KB (cue_036→cue_060) sono state mergeate nel catalog._

---

## Recently closed (2026-06-19)

- **A224 — Weather Capability (Today widget + Outdoor infra)** ✅ (feature, LOW risk — no engine modules). **Goal A**: live weather card su `/today` (collassabile/progressive disclosure: header compatto temp+cielo+banda, tap per dettaglio umidità/rugiada/vento + frase contesto climbing), geolocation GPS con fallback pulito (denied/unavailable/503 → card nascosta). **Goal B (infra, NON wired)**: `GET /api/weather` supporta forecast-by-date + location arbitraria per auto-fill outdoor futuro. **Fase 1**: OpenWeatherMap free tier (commercial OK + attribuzione) — Open-Meteo respinto (free tier non-commercial). Dew point via Magnus-Tetens; proxy server-side; gating fail-closed; cache 15-min keyed `(lat,lon,date,bucket)`; `lang=it`; `wind_label` Beaufort-IT (assente→molto forte). `condition_band` deterministico weakest-link (dew+temp+precip+vento>40 cap). Test: `test_weather_v1.py`. Doc: `docs/A224_weather_integration.md`. `OPENWEATHER_API_KEY` su Railway (verificata live Torino/Berdorf). **GAP Goal B (D247)**: outdoor spots senza coordinate → wiring demandato al brief design outdoor. **Follow-up aperti**: (1) attribuzione OpenWeather visibile (licenza); (2) opzionale — wind-bonus che fa *salire la banda* in caldo-secco-ventilato (ora solo la frase lo comunica, banda invariata).

- **C241 — Outdoor Strategy & Nutrition catalogs (v1, lead)** ✅ (catalog/content, LOW risk — pure JSON + validation test, no engine/frontend). Da KB Topic 11. Due file in `backend/catalog/outdoor/v1/`: `strategy.json` + `nutrition.json`. **Modello lookup a layer**: `base[discipline][day_type]` = entry completa (i 4 lead day_type `project|onsight_flash|volume|scout_easy`, 8 campi ciascuno); `patches[discipline][dimension][value]` = override parziali su 6 dimensioni (`wall_angle`/`route_length`/`hold_style`/`target_grade_relative`/`macrocycle_phase`/`condition_band`). **Entrambi scoped per `discipline`** → aggiungere `boulder` in futuro è puramente additivo (zero schema change). **Contratto resolver documentato** nel test (resolver vero arriva nel brief successivo): base completa → layer dei patch per suffisso (`*_override` rimpiazza il campo base, `*_add`/`*_note`/`nudge`/`strategy_add` si stratificano; dimensioni mancanti = skip/graceful degradation). Safety copy ribadita (no full-crimp a freddo D72, no stretching statico avambracci pre-perf CUE-02, nutrition = fueling-only mai peso D64). Test `test_outdoor_catalog.py` (16 test): parse, 4 base lead complete/non-vuote, patch solo su valori-dimensione validi, framing fueling-only, struttura discipline-keyed. Suite verde. Backend/catalog-only → push diretto a main. **Sample resolved verificato** (`project+overhang+long_endurance+performance`): `rest_between_attempts_min` sovrascritto da long_endurance `~1:4 work:rest`, note overhang/length/phase stratificate. Next: brief resolver backend che consuma questi cataloghi.

## Recently closed (2026-06-17)

- **D246 — Plan Pause/Resume: read-only audit (pre A-PLAN-PAUSE)** ✅ (audit, read-only, ZERO code change) — Report `docs/audit_plan_pause.md`. Mappa esaustiva call-site/consumer di `start_date`/`end_date`/`duration_weeks`, scrittori `week_plans`, keying `week_archive` (A221, chiavi assolute → immutabili), consumer frontend. **Finding cardine:** due famiglie di consumer leggono l'anchor in modo opposto — forward (`current_phase_and_week`, `week_num_to_phase_context` in `deps.py`, gli **unici 2** forward) vs finestra completamento (`macrocycle_archive.py:50-138`, filtro `start<=date<=end`). **Option A (shift `start_date`) RESPINTA**: spostando l'anchor in avanti le settimane completate pre-pausa cadono **sotto** `start_date` → espulse dalla finestra → completion % corrotto (rettifica di un'analisi automatica che la dava "più pulita"). **Raccomandata Option B**: `start_date` immutabile, `pause_offset_days` cumulativo (sempre ×7, misurato lunedì-pausa→lunedì-resume → Monday-invariant auto-preservato), `end_date += N`, anchor effettivo = `start_date+offset` usato SOLO dai 2 forward, week future hot shiftate/invalidate, archivio mai toccato. Confermato: subscription/trial/free-session **indipendenti** dal piano. 12 test invariante + outline A-brief (HIGH risk, branch+preview). **STOP gate**: Daniele rivede prima di autorizzare A-PLAN-PAUSE.

- **B259 — Webhook Stripe→backend rotto (500 su ogni delivery)** ✅ **P0**, da D245. **Root cause:** `stripe.Webhook.construct_event()` ritorna uno `stripe.Event` (StripeObject) e in stripe-python ≥8 `StripeObject` **non ha `.get()`** → `event.get("id")` a `stripe_webhook.py:106` sollevava `AttributeError` **fuori dal try/except** → **500** su ogni delivery reale → Stripe ritenta poi rinuncia (`pending_webhooks=1`) → righe `subscriptions` mai sincronizzate. **Provato** via log Railway (500, traceback riga 106) + payload firmato col secret di Railway che **supera** la verifica firma (l'ipotesi iniziale del secret-mismatch era SBAGLIATA — il secret è corretto). I test B226 non l'hanno preso perché mockavano `event` come `dict`. Regressione da **bump silenzioso di `stripe`** (requirements unpinned). **Fix (commit `659c43a`):** (1) `event` convertito a dict una volta via `_stripe_to_dict`; (2) `stripe==15.0.0` pinnato; (3) `test_b259_webhook_stripeobject.py` (8 test, StripeObject reale su tutti i rami di dispatch). **Deploy verificato in prod**: evento firmato → **200** (era 500). **Riconciliazione drift:** Arnaud già `active` in D245 (NON ri-inviato di proposito — `_handle_checkout_completed` forza `status=trialing` e lo declasserebbe); `98f77487-…` riportato a `canceled` via Supabase (mirror del handler, Stripe è source-of-truth). **Immutabilità sessioni Arnaud verificata** (0 sessioni, riga subscription invariata). _Nota: resend di un webhook non genera mai addebiti né tocca il coupon — è solo replay di notifica; l'unico rischio era il downgrade via checkout.session.completed, evitato non ri-inviando._ Mitiga parzialmente **B-SUB-TRIAL-RECONCILE** (con webhook funzionante le righe `trialing` scadute si sincronizzano da sole).

## Recently closed (2026-06-14)

- **D245 — Arnaud unexpected payment: investigation + refund remediation** ✅ (audit read-only + ops gated) — Report `docs/audits/D245_arnaud_findings.md`. **Cosa è successo:** Arnaud (`52681ef7-…`, `cus_Ubz0qNFUk7Wxx0`) aveva il **trial standard di 15 giorni** (30 mag→14 giu); oggi il trial è scaduto, la sub si è rinnovata e Stripe lo ha addebitato **$4.99**. `BYPASS_USER_IDS` apre solo il guard di accesso (B202) — **non blocca il billing Stripe**, quindi l'addebito è avvenuto comunque. **Scoperta sistemica → B259:** webhook Stripe→backend rotto (tutti gli eventi `pending_webhooks=1`), per questo la riga DB era ferma a `pending_checkout` nonostante la sub fosse `active`+pagata. **Remediation eseguita** (decisioni Daniele: refund SÌ, opzione A coupon): refund `re_3TiDA4Dyam3CcHNQ0HsD67I6` ($4.99); coupon 100%-off forever `bPfe4kTR` applicato a `sub_1Tcl3P` (prossima fattura $0); riga `subscriptions` sincronizzata a mano → `active`+linked. **Residuo:** rimozione da `BYPASS_USER_IDS` (richiede Railway CLI auth) — non più necessaria funzionalmente (riga reale `active`), copertura ridondante finché rimossa. Invariante past-sessions immutability: intatta (0 sessioni). **Lesson:** `BYPASS_USER_IDS` ≠ esenzione pagamento — friends&family vanno gestiti con coupon al checkout, non solo bypass.

- **D244 — Design audit: Partner Mode + Surface Preference + extensible Modifier architecture** ✅ (design, read-only) — Spec consolidata in `docs/design/D244-PARTNER-MODE_audit.md`. **Findings chiave che ribaltano le premesse del brief**: (F1) la surface preference **esiste già** via A210 ("Boulder only": `equipment_override` nel resolver + banner/badge/undo in `session-card.tsx` + `boulder_fallback` su 12 sessioni) → il modifier surface è generalizzazione di A210, non greenfield; (F2) gli esercizi non hanno campo `surfaces` (è `equipment_required`/`required_equipment` con `gym_routes`/`gym_boulder`) → catalog enrichment non necessario; (F3) nessun `user_state.schema.json` → `session.modifiers: []` senza migration; (F4) niente menu 3-dot, le azioni vivono nell'edit Drawer dove A210 è già; (F5) A210 applica senza preview (apply+undo); (F6) `injured` futuro overlappa col sistema `limitations` esistente; (F7) 225 esercizi (non 218). **Decisione cardine confermata**: modifier ortogonali agli intent (`session.modifiers: []`, intent=cosa/modifier=come). **Decisioni Daniele 2026-06-14**: surface pref EFFIMERO come A210 (D-PARTNER-05), preview SOLO per partner mode (D-PARTNER-11). **Piano implementativo ridotto da 7 a 5 brief** (A-MODIFIER-CORE, A-SURFACE-PREF, A-PARTNER-MODE, B-MODIFIER-SCHEMA, C-PARTNER-CATALOG — questi ultimi due opzionali). A219 superseded → puntatore. Docs-only → push diretto main.

---

## Recently closed (2026-06-10)

- **B258 — Sblocco UX utenti `pending_checkout` + messaggio paywall corretto** ✅ — Origina dalla diagnosi **D243** (beta Arnaud "non riesce ad avviare il training"). Root cause: l'utente che avvia il checkout ma non lo completa resta in `pending_checkout` → fail-closed guard (B202) blocca ogni azione con **402**, ma (a) il messaggio era hardcoded "Your trial has ended" anche per chi un trial non l'ha **mai** iniziato, e (b) la `TrialBanner` **sopprimeva** il banner proprio per `pending_checkout` → vicolo cieco senza CTA. **Fix backend** (`deps.py`): messaggio 402 status-aware — `_subscription_required_message()`, `none`/`pending_checkout` → "Subscribe to start training.", `past_due`/`canceled`/`expired` → "Your trial has ended…"; docstring di `require_active_subscription` corretto (era stale: diceva "no row → no-op", il codice fa fail-closed/deny). **Fix frontend** (`trial-banner.tsx`): banner CTA "Complete your subscription to start training." + bottone Subscribe → `/subscribe`, visibile app-wide (layout `(main)`). Coperti **entrambi** gli stati never-started — `pending_checkout` **e `none`** (riga subscription assente): prima `none` cadeva nel ramo "Your trial has ended", stessa classe di bug. Allineato a `_NEVER_STARTED_STATUSES` backend. **Scope deliberato**: NESSUN redirect globale su 402 in `api.ts` (regredirebbe il dialog macrocycle che usa `classifyApiError` + test dedicato). +5 test (`test_a159_subscription.py::TestSubscriptionRequiredMessage`). Mitigazione immediata per Arnaud: UUID aggiunto a `BYPASS_USER_IDS` (verificato 402→200). **Mergiato diretto su main** (decisione di Daniele: test da prod invece che da preview); branch eliminato post-merge.

- **D243 — Diagnosi "Arnaud non avvia il training"** ✅ (audit, read-only) — Identificato Arnaud (`52681ef7…`, onboarding completo, macrocycle 16w valido, **stato integro**, 0 sessioni). Errore riprodotto in live: endpoint gated → **402** `subscription_required` perché subscription ferma a `pending_checkout` (checkout creato 2026-05-30, mai completato, no `stripe_customer_id`/trial). Non è un crash/500: è il fail-closed paywall + 3 difetti UX (messaggio fuorviante, banner soppresso, gestione 402 incoerente nel frontend). Log Railway non pullati (CLI scaduta). Chiuso da **B258**.

---

## Recently closed (2026-06-08)

- **A221 / A-ARCHIVE-WEEKPLANS** ✅ — **Lazy-archive past `week_plans` (cold store).** Implementa il design D242 (Opzione A + confine hot C1 `{N-1, N, future}`). **Fatto:** tabella `week_archive` (Supabase JSONB + file backend, read-after-write verify); `deps.hot_floor()` / `archive_past_weeks()` (move puro, **write-verify-before-prune**, idempotente); read-path su 4 consumer — guard B257 esteso (hot→archivio→fail-closed) + flag `served_from_archive` (mai re-save nell'hot), recency `load_recent_exercise_ids` hot∪archivio (determinismo byte-identico, archivio consultato solo se hot<3 settimane), `report_engine._find_week_plan`, `macrocycle_archive._planned_session_count`; trigger lazy in `load_state` gated da env `WEEKPLAN_ARCHIVE_LAZY` (default OFF). Script `scripts/migrate_archive_weekplans.py` (backup-first, dry-run, `--rollback`, guard `--expect-name`/`--expect-uid`). +24 test (`test_a221_archive_weekplans.py`). **Migrazione prod di Daniele eseguita e verificata sul live**: 17 settimane → archivio byte-identiche, stato 1918→448 KB (**−77%**), recency invariata, `/api/week` + report leggono dall'archivio, settimana corrente intatta; rollback provato byte-identico. Sequenza appresa: deploy codice → canary di verifica → migrazione (vedi lessons 2026-06-08). DDL: `docs/migrations/week_archive_table.sql`. Flag `WEEKPLAN_ARCHIVE_LAZY=true` **attivo in prod** (verificato: beta Christie auto-archiviata 7/7 al `load_state`, dati integri) → beta + nuovi utenti si archiviano automaticamente, nessuna migrazione manuale. **B256 scorporato** come item separato (vedi sotto). Origina da D242.

## Recently closed (2026-06-04)

- **B257** ✅ — **Never regenerate a past week (fail-closed guard).** Chiude la violazione latente d'invariante trovata da D242: `GET /api/week/{past}` su cache-miss rigenerava la settimana passata (`today_str=None` → regen completa, preserve non scattano perché `old_plan=None`) → sessioni completate + feedback persi. Fix: `deps.is_past_week(monday)` (check canonico `monday < this_monday()`, riusa `this_monday()`); `week.py` serve le settimane passate **read-only** dalla cache (force ignorato), altrimenti **fail-closed** `{week_plan: null, past_week_unavailable: true}` — mai `generate_phase_week`; `replanner /override` → **422** su qualsiasi target passato (copre regen di `set_availability` + modifiche). **Cambiamento user-facing approvato**: macrociclo scaduto (week 0 clampa a Monday passato) e navigazione a settimane passate non in cache ora mostrano l'empty-state esplicito invece di un piano fabbricato. Frontend: `/week` "This week is in the past", `/today` "training plan has ended" (+ gate onboarding-welcome su `!hasMacrocycle` per non mostrare onboarding a utente con ciclo scaduto). Test: `test_b257_guard_pastweek.py` (12) + 2 test stale aggiornati (codificavano il vecchio fabricate-the-past). Verifica end-to-end locale (backend contract 3 scenari + render Playwright dei 2 messaggi). Deploy: backend-first su main (Railway) → frontend su main dopo verifica. Origina da D242.
- **D242 / D-ARCHIVE-WEEKPLANS** ✅ (audit, read-only) — Design + invariant proof per lazy-archive delle `week_plans` passate (radice del lag azioni: 86% dello state / 1.7MB). Confermato D241 sul live (week_plans 86%, `current_week_plan` 234KB byte-identico). Ipotesi N-2 **refutata** (`load_recent_exercise_ids` legge 3 settimane). Crux: nessun guard impediva la rigenerazione di settimane passate → estratto come **B257** (prerequisito di sicurezza). Opzione A (JSONB archive cold) consigliata + prova invariante + risk list + outline STOP-gated. **Assorbe B256** (rimozione `current_week_plan`, ID bruciato). Report: `docs/audit/D242_archive_weekplans.md`. A-brief stimato M-L, high-risk. *(Implementato come **A221** — vedi sopra.)*
- **B255** ✅ — Compressione gzip risposte (`GZipMiddleware`, `minimum_size=1000`). `/api/state` 1.89MB → 217KB (8.7×). Nessun endpoint streaming/SSE → safe. Test `test_gzip.py`. Backend-only, push diretto. Riduce solo il transfer (non il TTFB di `load_state` — quello è il lavoro sulla dimensione state, D242). Origina da D241.
- **D241 / D-STARTUP-LAG** ✅ (audit, read-only) — Diagnosi lag 2-3s su apertura/azioni. **Non è cold start** (Railway non dorme). Radice: `user_state` ~2MB → ogni `load_state()` paga ~1.7s di fetch+deserialize Supabase (prova: `/api/state/status` 29B → TTFB 2.29s). 86% = `week_plans` (19 settimane). Quick win gzip (→ B255); fix radice = ridurre dimensione state (→ D242). Report: `docs/audit/D241_startup_lag.md`.

## Recently closed (2026-05-26)

- **A220** ✅ — Process cue ora visibile su `/today`, non più solo in `/guided` (chiude il display gap dell'audit D239). Nuova sezione standalone **"Focus di oggi"** (componente `frontend/src/components/training/daily-cue-banner.tsx`) renderizzata sopra la `DayCard` in `today/page.tsx`, stile card amber coerente col banner `/guided` (icona lampadina, label, testo). **Decisione di design con Daniele**: invece di un banner per-card, una sola sezione a livello giorno; le cue sono per-sessione quindi con più sessioni se ne pesca **una** in modo deterministico (hash sulla data → stabile nel render, varia giorno-per-giorno). Mostrata solo da sessioni **non** finalizzate (briefing pre-sessione → sparisce a giornata conclusa); nascosta se nessuna sessione ha cue. Banner `/guided` invariato; daily quote A217 invariata in fondo. Frontend-only, branch `brief/A220-cue-today` → preview Vercel → merge su main (Daniele verifica in prod). `tsc`/lint puliti sui file nuovi, `next build` verde. Componenti 76→77. User guide aggiornata (§3).
- **C240** ✅ — Pilot batch Bechtel positioning drills. **7 drill mergeati** (di 8 proposti dal KB), **1 escluso per dedup** (`matched_breathing` → già coperto da `breathing_awareness` esistente, technique_relaxation, pari qualità). Drill aggiunti: `tech_applied_strength`, `tech_banded_climber`, `tech_diagonal_drill`, `tech_five_step`, `tech_matchy_matchy`, `tech_surface_of_the_shoe`, `tech_talon_feet`. **Deviazione strutturale dal brief**: il brief assumeva "un file `.json` per drill" ma il catalog reale è un singolo `backend/catalog/exercises/v1/exercises.json` (lista `exercises`, letta da loader+test) → entry appese in-place (218→225). **Mappatura schema v1 reale** (≠ YAML del KB): `fatigue_cost` intero, `stress_tags` dict fingers/elbow/cns/skin con valore `medium` (non "moderate"), `recency_group` con suffisso `_drills`, durata via `time_min`+`prescription_defaults`, **nessun field `source`** → attribuzione Bechtel in coda alla `description` tra parentesi (convenzione catalog). **Zero field tabù** (scartati i 5 opzionali KB: `visual_priority`/`visual_description`/`image_generation_brief`/`partner_required`/`bechtel_progression_ladder` + `technique_subtype`/`drill_format`) e **zero nuove D-decision** (rifiutate D92/D93/D94 proposte dal KB). Vocabulary v1 invariato (domain/pattern/role/recency/contraindications tutti già canonici). **Smoke test `technique_focus_gym` (lead intermediate, gym_boulder+gym_routes)**: 6/7 eleggibili (banded correttamente escluso, serve `resistance_band`); con pressione di recency il resolver seleziona effettivamente `tech_applied_strength`+`tech_diagonal_drill` → pickup reale confermato. **Fix D133**: `tech_diagonal_drill` (reps=2, work_seconds=9) richiedeva `rest_between_reps_seconds` → impostato a 15s (reset tra i due lati). Count test 218→225 aggiornato in `test_exercises_v2.py`. Suite verde. Predecessore: discussione claude.ai 2026-05-26 (scope semplificato — pilot di 8 entries senza debito di schema). Backend/catalog-only → push diretto a main. Next batch KB: Movement Drills (pp.51-69, ~8 drill).
- **C239** ✅ — Merge delle 25 nuove process_cue proposte dal KB (cue_036→cue_060), follow-up del next-step D240. **Session_id audit: 0 mismatch** — tutti i 32 session_id citati dal KB esistono nel catalog (`backend/catalog/sessions/v1`), quindi nessuna mappatura né drop: tutte le 25 cue inserite as-is. Catalog `backend/catalog/cues/v1/process_cues.json` 35→60 cue. **Coverage 24/35 → 35/35 session template** (28/28 non-test + 7/7 test — le test session prima erano completamente scoperte). Schema minimal preservato (`id`/`text`/`session_types`/`source` opzionale). **Formatter fedeltà byte-for-byte verificata** prima dell'append: la convenzione del file escapa i codepoint > U+00FF (em-dash `—`, en-dash `–`, ≥ `≥`, ₂ `₂`) ma tiene Latin-1 letterale (`Hörst`). 2 nuovi test in `test_process_cues.py` (`test_session_types_reference_real_sessions` + `test_text_length_sanity`, 20<len<400) a guardia di drift futuri. Suite 2051→2053. Backend/catalog-only → push diretto a main.

## Recently closed (2026-05-20)

- **B254** ✅ — Manual phase override sul macrociclo personale di Daniele (lead 8a+, start_date 2026-05-18, total_weeks 12): Endurance Base ridotta da 4 a 2 settimane perché tornato fresco da un macrociclo precedente, non vuole 4w di solo aerobico. Surplus +2 redistribuito: strength_power 3→4 (al cap 4), power_endurance 2→3 (al cap 3); performance/deload invariati. `total_weeks=12` e `end_date=2026-08-09` preservati. Patch applicata via `scripts/manual_phase_override_daniele.py` (one-shot, backup pre-write in `_archive/data_backups/`). **Past sessions immutable rispettato:** `week_plans[2026-05-18]` (week 1 corrente con 3 sessioni status='done': lun boulder_circuit + mar heavy_conditioning + mar test_max_hang_7s) e `week_plans[2026-05-25]` (week 2 futura, base in entrambi i piani) preservati intatti. 0 entries da invalidare in pratica perché week 3+ non ancora pre-generate. Verifica end-to-end: `/api/state` ritorna nuove phases, `/api/week/3?force=true` ora ritorna `phase_id=strength_power` (era `base` nel piano vecchio), `/api/week/1` mostra le 3 done preservate. **Nota engine:** base=2 viola `_PHASE_FLOORS_LEAD['base']=4`. Override manuale esplicito bypassa `_compute_phase_durations()` — `week_num_to_phase_context()` legge `phases[].duration_weeks` senza ri-validare, `is_macrocycle_stale()` confronta solo `assessment.profile` quindi nessun flag dirty. La feature proper A-PHASE-EDIT (P3) prevede policy "soft warning, no hard block" come default. Roadmap entry A-PHASE-EDIT aggiunto in P3 — UI polish. Backend/data patch → push diretto main.

## Recently closed (2026-05-19)

- **D240** ✅ — Process cue pattern snapshot per claude.ai KB project. Estratte le 35 cue esistenti di `backend/catalog/cues/v1/process_cues.json` in formato pattern self-contained (schema autoritativo, tone & style guide quantitativo, coverage map, source citation rules, gap analysis con target counts, output format strict). **Schema verificato**: 4 campi mandatory (`id`/`text`/`session_types`/`source` — 35/35 coverage). NO `phases`/`weight`/`tags`/`discipline` come suggerito erroneamente nel brief originale (chiarito al KB di NON proporli — verrebbero rifiutati). **Stats**: 79-163 chars (avg 116/median 113), 13-28 words (avg/median 19), 29/35 1-2 sentences, 33/35 imperative second-person voice. **Coverage gap riconfermato**: 11 session_types con zero cue (7 test sessions + `yoga_recovery`, `flexibility_full`, `handstand_practice`, `prehab_maintenance`). **Gap analysis ask al KB**: 7+ test cues (1 per test) con tono "no PR-chasing/honest measurement", 4+ ancillary cues con tono mind-body, ~8-12 cross-cutting underrepresented (lead-specific: fear management, clip strategy, breath cadence, antagonist activation, hydration/skin, mental refresh). **Decisione Daniele 2026-05-19**: `source` field opzionale per il nuovo batch (omittere se no studio specifico, mai inventare citazioni). Next step manuale: copia doc in KB project + apri C-brief per merge proposte. Output: `docs/audit/D240_cue_pattern_snapshot.md`. Read-only audit, no code change.
- **D239** ✅ — Audit read-only "daily quote/tip non visibile su /today" (iPhone PWA, 2026-05-19, sessione "Test Max Hang 7s"). **Verdetto: no bug.** 7 hypotheses (endpoint rotto, catalog degradato, componente rimosso, SW cache stale, regressione recente, fuori viewport, falsa memoria di dove l'ha visto) valutate. **Root cause confermato**: confusione tra 3 canali di motivazione separati (A217 quote in hero card a fondo `/today`, C203 boulder phase tip — gated boulder solo, Daniele è lead → skipped, A141 process_cue renderizzato solo in `/guided/[date]/[sessionId]:576-588`). Il "tip" ricordato — *"cammina invece di sederti nelle pause"* — combacia 1:1 con `cue_028` (process_cues.json, Draper 2006 + Watts 2000), il cui `session_types` whitelist è `[limit_boulder_gym, power_contact_gym, boulder_circuit_gym]` — tutto boulder, mai esposto a lead climbers via `_attach_process_cues()`. Verificato endpoint `/api/quotes/daily` 200 con X-User-Id di Daniele (q028 general, q004 hard_day); `quote_history` a 30 entries cap, sistema attivo. La hero card A217 (aspect-4/5 `today_hero.webp`) è sotto WeekProgressBar + DayCard sull'iPhone PWA → richiede scroll, non catturata nel viewport iniziale dello screenshot `IMG_7828.PNG`. Possibili follow-up P3 cosmetici (vedi §10 audit doc): (A) spostare A217 sopra fold, (B) aggiungere process_cue per test sessions, (C) audit cross-channel coherence dei 3 sistemi tip. Report: `docs/audit/D239_quote_render_audit.md`. Read-only, no code change.

## Recently closed (2026-05-18)

- **B253** ✅ — Lazy on-read migration per chiudere il finding §5.5/3 di D238: utenti onboarded **prima del 2026-04-20** (commit D214) avevano `assessment.tests_source` mancante anche dopo aver completato test in-app, perché D214 non implementò backfill ("legacy state remains valid with no migration" dal commit message). Per Daniele: `tests.max_strength[0]` con `exercise_id=max_hang_5s, total=120, date=2026-03-17` esistente ma sidecar vuoto → `week.py:345-356` freshness gate D214/F3 non scattava → planner schedulava sempre test al rinnovo macrocycle. **Phase 1 audit**: identificati 4 consumer (`week.py`, `_estimate_hangboard_baseline`, `_estimate_pulling_baseline`, frontend NON consuma) e 2 producer (onboarding, closed-loop). **Phase 2 fix**: nuovo modulo `backend/engine/migrations/__init__.py` + `m001_backfill_tests_source.py` con `migrate(state) -> bool` puro (idempotente, no side-effect su no-op). Hook in `backend/api/deps.py:load_state` accanto a `_migrate_gym_ids` (pattern già esistente, `dirty` aggregato e save una volta sola). Inference rules: presenza `tests.max_strength` con exercise_id ∈ {max_hang_5s, max_hang_7s} → marca entrambe le chiavi 5s/7s; presenza `tests.repeater_strength_endurance` → marca repeater_7_3_max_sets_20mm; presenza `tests.pulling_strength` → marca weighted_pullup_2rm_total_kg. **Dry-run su stato reale Daniele**: migration ritorna `True` e popola correttamente 3 chiavi (max_hang_7s+5s+repeater); pulling NON marcato perché `baselines.pulling.source=assessment` non `test` (correct: nessun test in-app). **12 regression test** in `test_b253_tests_source_backfill.py`: backfill max_hang/repeater/pullup, idempotenza, skip-existing, pre-D214 estimated stays estimated, no-op safety per stati malformati. Suite 2000→2012. STOP gate engine-change rispettato (`progression_v1.py`/`deps.py` sono moduli sensibili). Mai più follow-up D238 aperti.
- **B252** ✅ — D238 §5.5 finding 1 chiuso. `suggest_max_hang_load` in `resolve_session.py:169,182` aveva hardcoded `"max_hang_7s.v1"` (fallback assessment) e `"max_hang_5s.v1"` (default output) → quest'ultimo emesso erroneamente anche per baselines a 7s (il baseline scritto da `progression_v1.py:1205-1216` non include `protocol_version`, quindi il `b.get(..., default)` faceva sempre fallback al wrong default). **Fix**: derivare il default da `hang_seconds` già in scope (line 161): `f"max_hang_{hang_seconds}s.v1"` in entrambi i siti. Phase 1 audit: zero consumer in codice (frontend `api.ts` non legge il campo, nessun test asseriva su esso, mai persistito in feedback_log/tests history) → campo puramente cosmetico per audit/snapshot. **Regression tests** (4 nuovi in `TestB252_ProtocolVersionDerivation`): baseline 7s→v1, baseline 5s→v1, fallback assessment 7s→v1, explicit baseline preserved. Suite 1996→2000. STOP gate engine-change rispettato (Phase 1 analysis + OK before Phase 2).
- **B251** ✅ — D238 §6 Opzione A implementata catalog-only. **Fix 1**: aggiunto `intensity_pct_of_total_load: 1.0` nel block `main` di `finger_max_strength_test.json:38` → test sessions (`test_max_hang_7s` e alias `test_max_hang_5s`) ora suggeriscono **120 kg total / +43 kg added** (=MVC reale) invece di 108/+31. **Fix 2 skipped**: `test_max_hang_5s` è alias deprecato (catalog notes line 8 dichiarano backward-compat planner_v2; `test_planner_v2.py:517-910` ha ~7 `assertNotIn` che lo escludono dalle schedulazioni); modificarlo romperebbe la legacy feedback log parser. Già coperto dal Fix 1 perché monta lo stesso template. **Fix 3 deferred a B252**: contraddizione brief vs vincolo "no engine changes" — `protocol_version` vive solo in `resolve_session.py:182`, non nel catalog. **Regression tests** (3 nuovi in `test_session_1b.py::TestB251_TestSessionLoadCalibration`): template carries override, test session computes 100%, training session still computes 90%. Test count 1993→1996. Verifica locale con stato reale di Daniele (BW=77, MVC=120) confermata: `suggested.target_total_load_kg=120.0, added_weight_kg=43.0, intensity_pct=1.0`. Backend/catalog-only → push diretto a main.
- **D238** ✅ — Audit read-only del bug "test_max_hang_7s suggerisce 108 kg invece di 120 kg" (90 % vs 100 % MVC). Tracciato origine in `resolve_session.py:140-199` (`suggest_max_hang_load`): `intensity = exercises[max_hang_7s].attributes.intensity_pct = 0.9`, applicato incondizionatamente perché `finger_max_strength_test.json` non override `intensity_pct_of_total_load` nella prescription del block main. Nessun branch test-aware nel resolver (a differenza del planner che ha tag `session.tags.test=true` e bypass intensity cap in pass3). **Blast radius**: 2 test session catalog (`test_max_hang_7s`, `test_max_hang_5s` — entrambi montano `finger_max_strength_test` che embed `max_hang_7s`). Bug terziari: `test_max_hang_5s` punta a un template che usa `max_hang_7s` (catalog inconsistency); `protocol_version` default `"max_hang_5s.v1"` anche per max_hang_7s; `assessment.tests_source = {}` malgrado test reale del 2026-03-17 in `tests.max_strength`. **Raccomandazione fix**: opzione A (catalog-only) — aggiungere `intensity_pct_of_total_load: 1.0` nel block main di `finger_max_strength_test.json` (e variante LP). XS, low risk, motore intatto. Implementazione su B-brief separato dopo OK Daniele. Report: `docs/audit/D238_test_load_calculation.md`.

## Recently closed (2026-05-12)

- **D229** ✅ — Doc drift alignment, 5 finding chiusi in single commit. **F2**: `CLAUDE.md:144` "13 indoor + 3 outdoor intents" → "15 + 4" (ground truth dal codice: `INTENT_TO_SESSION` 15 keys, `OUTDOOR_INTENT_TO_DISCIPLINE` 4 keys). **F3**: 3 occorrenze Stripe stale lifted to canonical "Stripe LIVE since 2026-04-16, sk_live keys on Railway + Vercel" — `PROJECT_BRIEF.md:76` (Payments row), `ROADMAP_CURRENT.md:117` (GTM callout), `ROADMAP_CURRENT.md:121` (Week 0 timeline → marked archived ~2026-04-01). **F4**: `ROADMAP:130` GTM-02b — beta tester names "Christie, Vato, Alexis" → "Christie, Cesar, Paolo, Agustin" (allineato a PROJECT_BRIEF). **F5**: pricing decision row `ROADMAP:420` "EUR 14.99/month, 14-day trial, Founding Climber EUR 9.99 lifetime for first 50 users" → "USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Net/exclusive (VAT added on top at future Stripe Tax activation, decision locked 2026-04-28). Live since 2026-04-16." + GTM-02b question rewrite. **F7**: `DESIGN_GOAL_MACROCICLO_v1.1.md:4` header "Versione: 1.2 (file: v1.1) — febbraio 2026" → "Versione: 1.1 — febbraio 2026", `Ultimo audit` bumped to 2026-05-08, no file rename. F1 (endpoint count/table) + F1-sub (routers/ narrative include body_part_picker) già chiusi da B250 (2026-05-11). F6 (beta tester count) era già coerente — no fix needed. Backend/docs-only, push diretto a main.

## Recently closed (2026-05-11)

- **B250** ✅ — D236 Group 3 closed (post-D237 pre-push warnings). **F-09**: tabella endpoint `CLAUDE.md` riconciliata 64→68 righe — aggiunti 4 endpoint `body_part_picker` (A213, mai inseriti in tabella): `GET /options`, `POST /preview`, `POST /start`, `GET /estimate`. Header (68) e tabella ora allineati. **F-13**: 8 orphan vocab templates rimossi da `docs/vocabulary_v1.md` §3 canonical list — tutti archiviati da B186 (`320f80e`) ma mai rimossi dal vocab (`general_strength_accessories`, `gym_aerobic_endurance`, `gym_power_bouldering`, `gym_power_endurance`, `gym_technique_boulder`, `pulling_endurance`, `pulling_strength`, `warmup_recovery`). Scope strict: solo `CLAUDE.md` + `docs/vocabulary_v1.md`, zero touch engine/test. Full suite green 1993/1993 (invariato). `sync_status.py` ora emette zero warnings.
- **B249** ✅ — Fixed 3 failing tests in `test_undo_session_B192.py` (T2/T3/T4). Root cause: fixture date drift — `backend/tests/fixtures/test_user_state.json` ha `macrocycle.start_date=2026-02-16` e `end_date=2026-05-10` frozen, oggi (2026-05-11) è 1 giorno dopo `end_date` → `current_phase_and_week()` cade in branch "past end" → `/api/week/0` genera piano vuoto. Fix: helper `_rebase_macrocycle_to_today()` nell'autouse `isolate_state` fixture (module-scoped, non impatta gli altri 18 test file che condividono la fixture). Rebase in-memory only — fixture su disco intatta. Scope strict: `backend/tests/test_undo_session_B192.py` solo, zero touch engine/API/data. Full suite green: 1993 passing (invariato).
- **D237 / D-REPO-HYGIENE** ✅ — Repo hygiene + memory consistency check, post D156 (~149 briefs ago, **definitely overdue** per warning di `repo_hygiene.py`). Phase 0: archiviati 10 brief docs da `docs/briefs/` → `_archive/docs/briefs/` (A-ACTIVATION ×4, B208/B214-15/B216/B217 ×4, D214 ×2); ricollocati 4 audit deliverable da top-level `docs/` → `docs/audit/` (A214/A215/A216_phase0_audit + B183_duration_review). `B202/B203/B204_proposal.md` lasciati in `docs/briefs/` (già scope D236 G1 F-29 per delete). `AUTH_AUDIT.md` root e `docs/audits/` dir merge **non duplicati** (D236 G4/G5 li copre). Phase 1 memoria claude.ai project triangolata: **M1** Body Part Picker → suggested_*_load_kg ✅ done, description copy ❌ missing ma cosmetic only (nessun consumer frontend); **M2** B212 ✅ done (`848eacd`), B213 → **ghost** (zero hit git/roadmap, probabilmente assorbito da B227); **M3** core circuit → A203+C205 ✅ merged, 4/8 confirmed additions in catalog (4 mancanti: dragon_flag/star_side_plank/straddle_l_sit/arch_body_hold). Phase 2 contatori: tutti match con PROJECT_BRIEF (1993/68/218/35/19), ma **scoperti 3 test failure** in `test_undo_session_B192.py` (fixture date drift, week_plans vuoto) → suggerito B-brief separato per fix. Report: `docs/audit/D237_repo_hygiene_2026-05-11.md`. Memo claude.ai per Daniele incluso nel report (§Phase 3 - Memo).

## Recently closed (2026-05-10)

- **B-SYNC-FIX / D236 Group 0** ✅ — Riparato regex rotto in `scripts/sync_status.py:200-202` (F-01: header endpoint matchava "1 app-level health check" mentre CLAUDE.md è "2 app-level: health check + stripe webhook" da quando A159 ha aggiunto Stripe webhook → no-op silenzioso, CLAUDE.md fermo a 64 vs codice 68). Aggiunti 2 check a `validate()`: reverse vocab→disk (F-37, emette 8 orphan template warnings = ground truth di F-13) e pre/post-update endpoint drift detection (F-38, guardrail per RC-1 future). F-39 (auto-update tabella endpoint) e F-40 (status callouts non auto-syncabili) documentati come limiti. Sentinel test pytest con 9 casi su snapshot fixtures (`backend/tests/test_sync_status_sentinel.py` + `backend/tests/fixtures/sync_snapshots/`). Test count: 1984 → 1993 (+9 sentinel). Branch: pushato direttamente a main (backend-only). Predecessor: D236 (47 findings deduplicati su 78 raw da 4 subagents).
- **D236 / D-DOCS-CLEANUP** ✅ — Read-only audit of every doc/script artifact in the repo (90 live `*.md`, 6 archived, 11 scripts). 4 parallel Sonnet subagents (consistency, obsolescence, archive refs, status drift) → Opus synthesis. 78 raw findings deduplicated to 47 unique. Surfaced 8 root causes including: `sync_status.py` regex broken since Stripe-webhook addition (silent counter sync no-op); commit `00cdc33` mislabeled deletion as archive (4 dangling ROADMAP citations to `_archive/docs/horst_integration_audit.md` — recoverable from git `70dadfa`); Stripe go-live (2026-04-16) not retro-swept (3 P0 lies in PROJECT_BRIEF + ROADMAP); A218 cap rewrite not retro-swept ("10-13 weeks" residue). Remediation plan in 7 groups: **Group 0 = B-SYNC-FIX** (prerequisite to Group 3 counter fixes), Group 1 = Stripe/pricing P0 (suggested-text included), Group 2 = other status drift, Group 3 = counter reconciliation, Group 4 = bulk archive (~30 files) + `docs/audits/` plural→singular merge, Group 5 = misplaced renames + 4 escalations, Group 6 = broken-citation fixes incl. horst restore. Execution deferred to follow-up briefs. Output: `docs/audit/D236/` (7 files, 124 KB).

## Recently closed (2026-05-07)

- **A218 / A-MACRO-CAPS** ✅ — Macrocycle phase duration caps (total ≤ 16 weeks, base ≤ 4, perf floor 3 for total ≥ 13). Consolidated `_compute_phase_durations` + `_compute_remaining_durations` into a single function with a `phases=` scope parameter. Side findings folded in: F1 (off-by-one 9w lead → ValueError), F4 (boulder weakness self-cancel), F6/F7 (drift between full and incremental regen paths), F9 (slider min mismatch). F2 dead functions removed (`should_extend_phase`, `should_trigger_adaptive_deload`). Frontend: slider capped at [11–16] lead / [8–16] boulder; goal-editor date picker replaced by slider. Test count: 1948 → 1984 (+36 new caps tests). Design: `docs/audit/A-MACRO-CAPS_design.md`. Predecessors: `D233_macro_durations_report.md`, `D234_macro_deadline_findings.md`.
- **D234 / D-MACRO-DEADLINE** ✅ — Read-only audit confirming `total_weeks` and `goal.deadline` are independent inputs (Conclusion A). No deadline → total_weeks coupling exists; capping `total_weeks` is sufficient.
- **D233 / D-MACRO-DURATIONS** ✅ — Read-only audit mapping the duration formula. Surfaced 10 findings (F1–F10); A218 closed F1, F2, F4, F6, F7, F9, F10. Remaining (F3 floor-blocked weakness, F5 all_round alias, F8 default-12 cosmetic) accepted as-is per Phase 1 sign-off.

---

## Priority 1.25 — Audit Remediation (D163 + D164)

> Full reports: `docs/audit/D164/` (138 findings) and `docs/audit/D163_frontend_audit.md` (67 findings)
> Date: 2026-03-28
> Combined: 205 findings (20 P1, 71 P2, 102 P3, 12 P4)

### P2 highlights (not individually tracked — see full reports)

**Engine (D164 Agents 3-5):** Phase duration sum mismatch for 9-11 week macrocycles (P2), deload weights sum 0.40 not 1.0 (P2), `move_session` doesn't validate spacing (P2), `_reconcile()` enforces finger but not hard-day spacing (P2), streak field saved but unused in multiplier (P2).

**Frontend (D164 Agent 1 + D163):** PHASE_LABELS duplicated 4 files, `window.location.href` instead of router.push, console.warn/error in prod, eslint-disable on hooks deps, hardcoded email, session-card 1081 lines, tap targets <44px (6 instances), missing aria-labels (5 instances) → partially covered by B165c, rest deferred to R141/R144/R145.

**Catalog (D164 Agents 7-8):** 10 campus exercises use non-canonical `age_under_16` contraindication, `easy_climbing_deload` legacy schema, `deload_recovery` missing fields, 8 orphan templates, 11 generic placeholder video URLs → covered by B165e.

**Docs (D164 Agent 6):** Intent counts wrong in CLAUDE.md (13+3 vs actual 15+4), `closed_loop_v1.py` filename stale, session "active" label mismatch in sync_status.py, `grip_transition` missing from vocabulary → vocabulary fix in B165a, rest are P2 doc fixes (standalone).

**API contract (D164 Agent 9):** `POST /api/outdoor/convert-slot` response shape mismatch.

**Test coverage (D164 Agent 10):** 9 API endpoints lack integration tests, no full-pipeline E2E test (R150), `cluster_utils` 5/6 functions untested, test fixtures duplicated inline.

### P3 items (102 total) — see full reports, not individually tracked in roadmap

---

## Priority 1.26 — Audit Remediation (D170 + D172)

> Tracking docs: `docs/audit/D172_findings_tracker.md` (full 25-finding breakdown with status per item)
> Audits: D170 (gym_id propagation, 24 findings, 2026-03-31), D172 (all other fields: session_id / template_id / equipment / slot / phase / API validation, 25 findings, 2026-03-31)
> Combined: 49 findings — 13 fixed in B173, 2 P1 hotfixes pending (B174/B175), 21 deferred to B176

### Post-launch (P2)

| ID | Title | Type | Effort | Notes |
|----|-------|------|--------|-------|
| **B176** | D172 consolidated remediation — 21 remaining findings (P2+P3) | B | L | 5 groups: type safety (D172-05,11,12), equipment validation (D172-07,08,22), event/input validation (D172-09,13,14,25), logging (D172-10,15,17-20,23,24), structural/deferred (D172-16,21). Supabase migration already complete — no longer a prerequisite. |

### Deferred from B173 (need API refactoring)

| Title | Priority | Effort | Notes |
|-------|----------|--------|-------|
| `apply_day_add` doesn't receive `gyms` parameter (D170 P1-04) | P3 | M | Needs signature refactoring. Frontend fix in B173 covers the main user-facing path. |

---

## Priority 1.27 — Audit Remediation (D211 / D-TESTUSER-VERIFY residuals)

> Origin: `docs/audit/D-TESTUSER-VERIFY_report.md` §5 (2026-04-19)
> F1 (HIGH) + F3 (HIGH) closed by D214 (`assessment.tests_source` sidecar). Residuals below parked post-launch.

### Post-launch (P2/P3)

| ID | Title | Severity | Priority | Type | Effort | Notes |
|----|-------|----------|----------|------|--------|-------|
| F2 | **Onboarding input validation** — no bounds on BW/height/age/test inputs (BW=33 kg, height=33 cm, age=3, max_hang=3.5× BW accepted silently; radar saturates to 100). | MEDIUM | P2 | B | S | Add range checks at onboarding: BW 35–150 kg, height 120–220 cm, age 10–80, max_hang ≤ 3× BW (soft-warn). |
| F4 | **Stale cached week plan across deploys** — no regeneration trigger on deploy; users onboarded within ~5 min of a push keep pre-push output. | LOW | P3 | B | XS | Accept (deploy-window artifact). Users can force-regenerate via Settings. Document in user guide. |
| F5 | **`goal.primary_weakness`/`secondary_weakness` are absent** — actual storage at `assessment.self_eval.*`. Consumers reading `goal.*` see `None`. | LOW | P3 | D+B | XS | Grep consumers; if any read `goal.*` for weaknesses, fix read site (not write). Spec-drift only. |
| F6 | **`macrocycle.phases[].weeks` is `null`** — consumers iterating `phases[].weeks` see `null`; sum via `start_week` deltas works. | LOW | P3 | D+B | XS | Audit consumers; drop the field from schema if all compute from `start_week` deltas, else populate at generation. |
| F7 | **`goal.deadline` empty while `total_weeks=12`** — onboarding writes `deadline=""` when deadline is derived from `total_weeks`. | LOW | P3 | B | XS | Cosmetic. Compute ISO date from `total_weeks + start_date`, or drop the field. |
| F8 | **`assessment.tests.last_test_date = 2026-04-16`** (3 days before macrocycle start) — writer not traced in D211. | COSMETIC | P3 | D | XS | Grep writer site; likely legacy path in `progression_v1.py`. |
| F9 | **Pass 3 test placement requires non-empty day** (`planner_v2.py:1360`: `if not day_sessions[offset]: continue`). Tests can only replace existing sessions — users with few available days silently lose tests. | MEDIUM | P2 | B | S | Loosen empty-day rule for test sessions, or order `required=True` first across axes. |

---

## Priority 1.28 — Audit Remediation (D236)

> Tracking docs: `docs/audit/D236/00_remediation_plan.md` (piano completo, 6 Group), `docs/audit/D236/00_findings.md` (47 finding deduplicati su 78 raw).
> Audit: D236 read-only cleanup, completato 2026-05-09 (47 findings: 6 P0, 22 P1, 13 P2, 6 P3).
> Group 0 chiuso da B-SYNC-FIX (2026-05-10). Group 1-6 aperti come C-brief indipendenti.
>
> **Ordine raccomandato**: Group 3 → Group 1 → Group 6 → Group 4 → Group 2 → Group 5.
> Razionale: Group 3 fixa code-ref errati in CLAUDE.md (F-15 closed_loop path, F-16 planner_v1→v2) — file letto da ogni istanza Claude Code, alta probabilità di morsicare in brief macrocycle/engine. Group 1 chiude P0 Stripe/pricing lies in PROJECT_BRIEF e ROADMAP. Group 6 sblocca KB anchors per D33/CUE-02. Resto è cleanup.

| Group | Title | Type | Effort | Status | Notes |
|---|---|---|---|---|---|
| 0 | Fix `sync_status.py` regex + validate() | B | S | ✅ Done 2026-05-10 (B-SYNC-FIX) | Closed F-01, F-37, F-38; F-39, F-40 documentati come limiti |
| 3 | Counter fixes (CLAUDE.md, PROJECT_BRIEF, README, vocabulary, ENGINE_ARCHITECTURE) | C | S | **Open — next recommend** | F-09 (endpoint count 64→68), F-10/F-11 (intent count 13+3 → 15+4), F-12 (macrocycle weeks 10-13 → lead 11-16/boulder 8-16), F-13 (8 vocab orphan templates), F-14 (`_SESSION_META` 34→31), F-15 (`closed_loop_v1.py` path → `backend/engine/adaptation/closed_loop.py`), F-16 (`planner_v1` → `planner_v2` import example), F-36, F-46, F-47. **Closes D229 implicitly.** |
| 1 | P0 Stripe/Pricing drift + redundant cleanup | C | XS | Open | F-02 (PROJECT_BRIEF Stripe "TEST MODE"), F-03 (ROADMAP Stripe "Not live"), F-04 (pricing row "EUR 14.99" wrong on currency/amount/trial/cap), F-29 (delete 3 stub `B202/B203/B204_proposal.md`), F-30 (delete 3 abandoned `users_report_*.md`) |
| 6 | Broken citations + horst restore | C | S | Open | F-05 (D163 path), F-06 (D172 tracker never created), F-07 (horst ghost file — `git show 70dadfa:docs/horst_integration_audit.md > _archive/docs/horst_integration_audit.md`) |
| 4 | Bulk archive obsolete docs + merge `docs/audits/` → `docs/audit/` | C | M | Open | F-08 (dir merge), F-18 through F-28 (24 closed-brief deliverables), F-31, F-32, F-33 |
| 2 | Status-marker drift | C | S | Open | F-17 (`design_system_v1.md` A215/A216/A217 "planned" → ✅ Done), F-35 (DESIGN doc Guided Session "spec futura" → implemented) |
| 5 | Misplaced renames + escalations | C | XS | Open | F-34 (outdoor_audit_D170 → docs/audit/), F-41 (AUTH_AUDIT.md → docs/audit/); F-42-45 sono escalations a Daniele (4 decisioni nel piano §Group 5) |

---

## Priority 1.75 — Go-to-Market Sprint

> Origin: Strategic Advisory Council (2× runs, 5 advisors each, 2026-04-01)
> Key insight: distribution + onboarding friction are the real blockers, not features.
> Constraint: solo founder, zero marketing budget, feature freeze for 30 days.
> Stripe status: LIVE since 2026-04-16, sk_live keys on Railway + Vercel.

### Timeline

- **Week 0 (archived, ~2026-04-01):** Beta testers using the app (4-5 users). Founder dry-run. Stripe LIVE since 2026-04-16, sk_live keys on Railway + Vercel.
- **Week 1-2:** Collect beta feedback + fix onboarding blockers from dry-run.
- **Week 2-3:** Pricing decision → activate Stripe live → soft launch on r/climbharder.
- **Week 3-6:** Feature freeze. Only fix bugs from paying/trialing users. Measure.

### Phase 0 — Onboarding dry-run + beta feedback (week 0-2)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-02b | **Beta tester feedback collection** — structured check-in with Christie, Cesar, Paolo, Agustin on their experience | — | XS | Open | Ask: what confused you? what's missing? would you pay? Key signal: would they pay $9.99/mo Standard (or $4.99/mo as a Founding Climber). |

### Phase 1 — Pricing + Stripe go-live (week 2-3)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| B207 | **Harden `warmup_climbing` template — fallback for no-wall home** | B | S | Open **P2** | Residual from D210. `warmup_easy_boulders` referenced by explicit `exercise_id`, bypasses P0 equipment gate. Options: (a) filter-based selection with equipment gate, or (b) add `warmup_general_mobility` fallback. |
| B205 | **Verify cancel_at_period_end grace period** | B | XS-S | 🔁 Rolled into B226 | Targeted test added inside B226 (`stripe_webhook.py` is opened once for fail-loud + customer.deleted + cancel_at_period_end). Marginal cost. |
| GTM-STRIPE-TAX | **Stripe Tax registration** | Config | S | 🟡 Deferred | Reactivate when **either** condition met: (a) 10+ paying EU customers, OR (b) €5k cumulative EU revenue, OR (c) approaching €10k OSS threshold. Below these, IT domestic VAT rules apply (regime forfettario or ordinario per Daniele's setup), Stripe Tax is scope creep. When reactivating: 4 dashboard steps + 4-line code change in `subscription.py:108-124` (`automatic_tax: {enabled: true}` + `tax_id_collection` + `billing_address_collection: 'required'`). Decide now: prices $9.99/$4.99 are **net** (exclusive — VAT added on top at activation) — document this so future activation is consistent. |
| GTM-05 | **r/climbharder soft launch** — post asking for 5 beta testers, zero pitch | — | XS | Open | Not a code task. After B204 + B203. |
| B228 | **Frontend 402 global handler in `api.ts`** | B | S | Open P2 | Audit F4. Centralize 402 → router.push('/subscribe') + sonner toast. Frontend branch + Vercel preview. After both P1. |
| D229 | **Doc drift alignment — CLAUDE.md endpoints + intents + Stripe text** | D | XS | ✅ Done 2026-05-12 | Closed by D229 EXTENDED (this commit): 7 findings resolved. F1 (endpoint count/table) + F1-sub (routers/ narrative) already chiusi da B250. F6 (beta tester count) was a non-issue (already coherent). F2 (intent count 13+3→15+4), F3 (3 Stripe stale strings → canonical "LIVE since 2026-04-16"), F4 (Vato/Alexis → Christie/Cesar/Paolo/Agustin), F5 (pricing EUR 14.99/14-day/first 50 → USD $9.99/$4.99/15-day/first 20, GTM-02b question updated), F7 (DESIGN header v1.2→v1.1, audit date 2026-03-28→2026-05-08) fixed in this commit. |
| C231 | **Catalog `intensity_level` enum normalization — drift singletons** | C | XS | Open P3 | B227 P0.2 discovery: catalog uses 7-value enum (very_low, low, moderate, medium, high, very_high, max). Two drift singletons absorb cleanly via ordinal mapping (`reverse_lunge`=moderate→medium, `thirty_thirty_intervals`=very_high→high), but worth normalizing to a clean 5-value canonical set `{very_low, low, medium, high, max}`. 2 catalog edits + test_exercises_v2.py enum check. Zero engine impact. |

### Phase 2 — Measure + iterate (week 3-6)

| ID | Title | Type | Effort | Status | Notes |
|----|-------|------|--------|--------|-------|
| GTM-06 | **Feature freeze** — zero new features for 30 days, only fix bugs reported by paying/trialing users | — | — | Open | Starts when first non-beta user signs up. |
| GTM-07 | **Success metric** — 3-5 paying users by end of April 2026 | — | — | Open | 0 paying after 30 days → reassess PMF. 3+ paying → validate and continue. |
| D230 | **Frontend lint hygiene — 30 errors / 38 warnings** | D | M | Open P3 | Audit F5. Mostly `react-hooks/set-state-in-effect` from React Compiler in Next 16. CI does not enforce, but debt accumulating. One afternoon, branch + preview. After GTM stability window. |

### Council recommendations (reference)

**Convergence across both runs (high confidence):**
- Launch NOW — Supabase migration is not a blocker (JSONB handles ~260KB/year/user)
- r/climbharder is the #1 acquisition channel
- Zero new features for 30 days post-launch
- Onboarding is the critical blind spot — no advisor caught it initially, both chairmen flagged it
- Don't build Kilter/Capacitor/LLM Coach before validating willingness to pay

**Divergence (Daniele decides after beta feedback):**
- Price: €14.99/mo (Run 1) vs €9.99/mo Founding Climber lock-in (Run 2)
- Synthesis: €14.99 standard + €9.99 Founding Climber for first 20-30 users

---

## Priority 2 — Auth + Payments + DB (go-to-market blockers)

Clerk auth ✅, Supabase JSONB ✅, and Stripe ✅ are complete. Stripe LIVE since 2026-04-16.

- **Supabase migration** ✅ — JSONB live in production (6 tables: users, session_logs, outdoor_logs, event_logs, recovery_codes, subscriptions)
- **A159 — Stripe subscriptions** ✅ — **LIVE** (sk_live keys on Railway + Vercel). Two-tier pricing ($9.99 Standard + $4.99 Founding Climber). B202 fail-closed guard active. B226 hardening done: fail-loud (500 → Stripe retries), LRU event dedup, customer.deleted handled. No known gaps.
  - Backend: `subscription_guard.py`, 4 endpoints (status/checkout/portal/webhook), guards on 10 POST endpoints
  - Frontend: `useSubscription()` hook, `TrialBanner`, `/subscribe` page, settings portal link, guided session gate
  - Phase 3: `onboarding/start-week` → redirect to `/subscribe` (both Continue and Skip)
  - SQL migration: `docs/migrations/subscriptions_table.sql` — ✅ run in Supabase (confirmed 2026-03-31)

### A-B6 — Session pool boulder audit & completion

**Priority:** P2 | **Status:** Open | **Type:** D + A (audit + feature) | **Effort:** M

Audit `_SESSION_POOL_BOULDER`: verify ≥3 primary sessions per phase, limit_boulder exists, board session templates exist (board_limit, board_volume), PE sessions adapted (boulder_circuit, linked_boulders), climbing_routes excluded from boulder pool, technique sessions adapted, all_round pool = union of lead + boulder.

### A-B8 — Board session templates (guided)

**Priority:** P2 | **Status:** Open | **Type:** A (catalog + template) | **Effort:** M

Three new session definitions: `board_limit_session` (6-10 problems at max, 3-5 min rest), `board_volume_session` (15-20 problems 2-3 below max, 1-2 min rest), `board_pe_session` (4x4 format, 3-4 below max). Equipment: board_kilter/board_moonboard/board_other. No board API integration.

## Priority 2.25 — Code Quality & Hardening

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R142 — Magic Numbers Extraction

**Priority:** P2.25 | **Status:** Open | **Type:** R (refactor)

- Estrarre magic numbers da `progression_v1.py` in named constants
- Spostare tabelle grade-to-score e axis weights da `assessment_v1.py` in JSON catalog

**Rischio:** BASSO — estrazione costanti

## Priority 2.5 — Session Quality (post-launch)

### Flex/rest auto-fill (Pass 3)

**Status:** Open | **Effort:** S

After Pass 1 (primary) and Pass 2 (complementary), add a Pass 3 that fills remaining empty days with flex/rest/mobility sessions. Currently empty days stay empty. Especially needed in deload phase (3 sessions on 7 days). Depends on: nothing.

## Priority 2.5b — Catalog & Polish

### C130 — Audit sistematico domain/intensity/pattern

**Priority:** P2.5 | **Status:** Partially closed (2026-03-22)

**Completato:** Audit 178 esercizi, 5 intensity mismatch corretti, 4 session filter corretti, 9 sessioni orfane triagate.

**Ancora aperto:** ~33 pattern/domain borderline cases (multi-domain exercises, vocabulary gaps) — richiedono decisione design.

### A-B10 — Board benchmark tracking

**Priority:** P2.5 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Track max grade + angle per board type in free session logs. Dashboard trend widget. Optional benchmark problems (user marks 2-3 reference problems).

### A-B11 — Movement drills for boulder in exercise catalog

**Priority:** P2.5 | **Status:** Open | **Type:** C (catalog) | **Effort:** S

Add exercises: flagging practice, heel/toe hook drills, volume traversing, coordination drills, drop knee practice, body tension drill, smearing practice. Tag with technique_drill pattern.

### A-B12 — Discipline-aware PE routing

**Priority:** P2.5 | **Status:** Open | **Type:** A (planner) | **Effort:** S

Expand gym-aware PE routing: boulder discipline → prefer gyms with gym_boulder, lead → prefer gym_routes, all_round → no preference.

### A-B13 — Conditioning weights audit per discipline

**Priority:** P2.5 | **Status:** Open | **Type:** A (engine) | **Effort:** S

Audit `_BASE_DOMAIN_WEIGHTS` for boulder: more power pulling, core, antagonist push; less ARC, forearm endurance.

### A-B14 — Free session UX for boulder

**Priority:** P2.5 | **Status:** Open | **Type:** A (frontend) | **Effort:** S

Phase-aware suggestion card when logging free session on gym_boulder. Grade range suggestions based on user max + phase.

### A-B15 — Spray wall as guided session surface

**Priority:** P2.5 | **Status:** Open | **Type:** A (catalog) | **Effort:** S

Add spraywall to location_any for relevant session templates: limit bouldering, technique drills, work capacity circuits.

### Exercise images for complex exercises

**Priority:** P2.5 | **Status:** Open — TBD post-launch | **Type:** A + C (schema + content)

- Add `image_url` or `images[]` field to exercise catalog schema (currently no image support — only `video_url` exists)
- Generate instructional images (Gemini AI) for exercises that assume prior knowledge and are hard to understand from text alone
- Priority targets: hangboard grip exercises (grip_transitions, overcoming_isometric_pull), campus board exercises, technique drills
- Style: clean side-view instructional photos, consistent framing, suitable for in-app display on exercise detail cards
- Frontend: display image(s) on `exercise-detail-sheet.tsx`, above or below the description
- Discovered during B157 audit: `grip_transitions_half_to_open` was the only hangboard exercise with a one-line description and no visual reference

---

## Priority 2.9 — Retention & Discovery (post-launch)

> Origin: discussione 2026-05-08 (gamification + daily tips).
> Filosofia guida: "Train better, not more" (D79). Nessun elemento premia giorni consecutivi, volume cumulativo, o RPE alto. Si premia qualità, completamento di fase, e rispetto del recupero.
> Tutte le entries sono post-launch. Non toccano moduli high-risk (planner_v2, replanner_v1, macrocycle_v1, resolve_session, progression_v1, closed_loop_v1).
> Da rivisitare quando: 3+ paying users attivi da 30 giorni + feature freeze conclusa.

### A-GAMIFY-00 — Design audit: gamification senza spingere all'overtraining

**Priority:** P3 | **Status:** Open | **Type:** D (design audit) | **Effort:** S
**Pre-requisito di tutti gli A-GAMIFY-*.**

Documento di design (`docs/design_gamification.md`) che fissa:
- Quali metriche premiamo (qualità, completamento fase, milestone una tantum)
- Quali metriche NON premiamo mai (giorni consecutivi, volume cumulativo, RPE alto, "fai una sessione ogni giorno")
- Vincolo hard: nessun elemento di gamification può indurre senso di colpa per un giorno saltato o un rest day
- Linee guida copy per badge/notifiche (allineate a D77/D79: SDT principles + "train better, not more")

Da approvare prima di qualunque A-GAMIFY-* di implementazione.

### A-DAILYTIP — Daily tips card on Today page

**Priority:** P3 | **Status:** Open | **Type:** A (catalog + backend + frontend) | **Effort:** M

Card discreta su `/today`, posizionata **sotto la daily quote**, che mostra ogni giorno un tip diverso. Risolve il problema concreto: i beta tester non scoprono metà delle feature.

**Catalog:** nuovo `backend/catalog/daily_tips/v1/feature_discovery.json` con ~20 tip iniziali che coprono le feature meno scoperte (recovery code, weekly override, free session, custom session builder, equipment toggle, settings → regenerate, export/import, convert outdoor slot, ecc.).

**Schema tip:**
```json
{
  "id": "tip_outdoor_convert",
  "category": "feature_discovery",
  "text": "Sapevi che puoi convertire un giorno indoor in outdoor con un tap dalla week view?",
  "cta_label": "Provala",
  "cta_url": "/week",
  "tags": ["outdoor", "week_view"]
}
```

**Backend:**
- `get_daily_tip(user_id, date)` — selezione deterministica via hash `user_id + date`
- Rotazione 30 giorni (stesso tip non riappare per 30gg allo stesso utente)
- `GET /api/tips/daily` → `{tip, dismissed_today: bool}`
- `POST /api/tips/{id}/dismiss` → append in `user_state.tips_seen[]` con timestamp
- Pattern parallelo all'esistente `/api/quotes/daily`

**Frontend:**
- Componente `DailyTipCard` su `/today` sotto `DailyQuoteCard`
- Stile discreto: icona lampadina, dismiss button (X), CTA opzionale
- Persistenza dismissal nella stessa giornata

**Espansione futura:** categorie `training_science` (Hörst/Lattice tip tecnici) e `personalized` (basato su user_state, es. "Test repeater programmato la prossima settimana — riposa bene il giorno prima").

### A-GAMIFY-01 — Macrocycle progress + phase completion badges

**Priority:** P3 | **Status:** Open | **Type:** A (frontend + light backend) | **Effort:** M
**Depends on:** A-GAMIFY-00

Visualizzazione del progresso nel macrociclo come elemento centrale di gratificazione. Niente streak.

**Frontend:**
- `MacrocycleProgressBar` su `/plan`: barra orizzontale con i 5 phase, % completata per fase, marker week corrente
- Modal/toast di celebrazione quando si entra in una nuova fase ("Strength & Power completata 💪")
- Sezione "Macrocycles completed" con storico (nome, durata, goal raggiunto/mancato)

**Backend:**
- Lettura da `user_state.macrocycle.phases[]` (già presente)
- Flag `phase_completion_seen[]` in user_state per non rifare la celebrazione
- Su `start-new-cycle`, snapshot in `user_state.completed_macrocycles[]`

### A-GAMIFY-02 — Milestone system

**Priority:** P3 | **Status:** Open | **Type:** A + C (catalog + feature) | **Effort:** M
**Depends on:** A-GAMIFY-00

Eventi una tantum sbloccabili. Niente ricorrenza — solo "first time" celebrations.

**Catalog:** `backend/catalog/milestones/v1/milestones.json` (~15-20 milestone iniziali):
- Climbing grades: primo 7a/7b/7c/8a redpoint, primo onsight di grado
- Sessions: prima sessione outdoor, prima sessione guidata, prima sessione free, prima custom session
- Macrocycle: primo test completato di ogni tipo, prima fase performance, primo macrociclo completato
- Consistency: primo trip programmato, primo recovery code generato

**Schema:**
```json
{
  "id": "first_7a_redpoint",
  "name": "First 7a Redpoint",
  "description": "Hai chiuso la tua prima via 7a in redpoint",
  "category": "climbing_grade | session | macrocycle | consistency",
  "condition": "<expression on user_state>",
  "icon": "trophy"
}
```

**Backend:**
- Hook su feedback log + outdoor log + macrocycle transitions → check unlock
- `user_state.milestones_unlocked[]` (append-only, idempotente — una milestone non si "ri-blocca" se l'utente cancella un climb)
- `GET /api/milestones` (lista + stato locked/unlocked)
- `POST /api/milestones/{id}/seen`

**Frontend:**
- Pagina `/milestones` (galleria locked/unlocked)
- Toast celebrativo al unlock
- Widget "ultimi milestone" su `/plan`

### A-GAMIFY-03 — Monthly activity heatmap

**Priority:** P3 | **Status:** Open | **Type:** A (frontend) | **Effort:** S
**Depends on:** A-GAMIFY-00

Calendario mensile stile GitHub contributions per le sessioni di climbing.

**Frontend:**
- Componente `MonthlyHeatmap` su `/reports/weekly` (in fondo) o nuova pagina `/history`
- Cella per giorno colorata in base a:
  - Grigio: nessuna sessione programmata
  - **Verde tenue: rest day rispettato** (premiamo il riposo!)
  - Verde chiaro/medio/scuro: sessione completata (intensità via load score)
  - Neutro: sessione skipped (NO color shame)
- Tap sulla cella → apre la day view di quel giorno

**Backend:** nessuna nuova logica (derivato da feedback log + outdoor log + plan).

**Punto chiave filosofico:** i rest day rispettati hanno colore positivo distinto. È la differenza con altre app: premia il rest, non solo il lavoro.

### A-GAMIFY-04 — Weekly adherence "perfect week" badge (opzionale)

**Priority:** P4 | **Status:** Open — opzionale | **Type:** A | **Effort:** M
**Depends on:** A-GAMIFY-00, A-GAMIFY-01

Riconoscimento per chi ha completato fedelmente la settimana programmata, **incluso il rispetto dei rest day**.

**Engine:** `compute_week_adherence(week_plan, logs)` → `{score: 0-100, perfect: bool}`. "Perfect" = sessioni hard fatte nei giorni programmati + nessuna sessione extra non programmata (anti-overtraining).

**Rischio:** tocca la semantica del piano, può essere percepito come pressione. **Da fare per ultimo**, dopo aver visto la reazione utenti ai 3 elementi precedenti. Se feedback negativo → si scarta.

### Sequenza implementazione consigliata

1. **A-GAMIFY-00** (S) — design audit, fissa filosofia, evita drift
2. **A-DAILYTIP** (M) — alto valore, basso rischio, risolve problema reale di discovery
3. **A-GAMIFY-01** (M) — macrocycle progress + phase badges
4. **A-GAMIFY-03** (S) — heatmap mensile
5. **A-GAMIFY-02** (M) — milestone system
6. **A-GAMIFY-04** (M, opzionale) — perfect week, solo se feedback positivo sui 3 precedenti

**Effort totale:** ~5-7 giorni di lavoro post-launch.

### C-FEEDBACK-LOOP — Feedback-loop email automation

**Priority:** P2.9 (post-launch, alongside C-RETENTION-ROADMAP) | **Status:** Open — design only, no implementation | **Type:** A (automation) | **Effort:** M+
**Depends on:** LLM coach layer (Phase 3.5) + knowledge-base RAG (solo per Track B)

> **⚠️ Timing — NON ora.** Da affrontare **solo quando ci saranno tanti utenti**: finché il volume di supporto è gestibile a mano, il valore non giustifica il lavoro. Inbox di gestione: **daniele.somensi@gmail.com**. Origin: Daniele (2026-05-31).

Automatizzare il loop di feedback/supporto clienti oggi gestito manualmente (welcome email a mano, risposte via Claude).

**Due track disaccoppiati — ship indipendenti:**

- **Track A — Outbound (basso rischio, può partire per primo):** trigger Stripe webhook `customer.subscription.created` → invia welcome/feedback email templata (deterministica, no LLM). Idempotenza: dedupe su subscription id; mai re-inviare su plan change o device switch. Nessuna dipendenza da Phase 3.5 — standalone.
- **Track B — Inbound (gated su Phase 3.5):** cron (Claude Code su Mac) polla l'inbox supporto, classifica ogni reply (feedback / training question / feature request / bug). Training questions → LLM coach risponde via KB RAG (stesso layer di Phase 3.5, NON costruire un secondo RAG). Feature requests/bug → auto-file come roadmap candidate.

**Non-negoziabili Track B:**
- **Human-in-the-loop finché piccolo.** Il cron CLASSIFICA + DRAFTA solo. Daniele approva prima dell'invio. Nessuna risposta LLM non supervisionata a clienti paganti (rischio allucinazione/reputazione su consigli di training).
- **Accesso inbox separato da claude.ai.** Il connettore Gmail nella chat claude.ai NON dà a Claude Code su Mac accesso all'inbox. Il cron serve credenziali proprie (Gmail API / IMAP) sul Mac.
- **La KB è prerequisito, non side-project.** Risposte "tailored" hanno senso solo quando il coach legge la KB letteratura. Allineato a Phase 3.5 RAG.

**Open decisions prima di qualsiasi brief:**
1. Indirizzo inbox supporto + routing delle reply → **daniele.somensi@gmail.com** (deciso).
2. Metodo di accesso inbox Mac-side per il cron.
3. Soglia auto-send (se mai) — definire l'exit criteria dell'human-in-the-loop.

---

## Priority 2.75 — KB Research Integration

> **Companion project:** The KB research lives in a **separate claude.ai project** called **"climb-agent knowledge base"**.
> All research files, Hörst syntheses, topic files, and decision consolidations live in that project's knowledge.
>
> **⚠️ RULE: Before implementing any deferred decision from the backlog below, open the KB project and check
> `_archive/docs/horst_integration_audit.md` for enrichment material. Many deferred decisions have ready-to-use content.**

### Open KB Research Items

| Item | Status | Where |
|------|--------|-------|
| Session 2 patch (4 corrections: D11, D12, D39, D72) | ⏸️ Prepared | KB project memory (not yet a file) |
| D84 pulling strength test (max load review) | ⏸️ Under review | KB project |
| Finger strength test architecture (5s→7s Lattice) | ⏸️ Under review | KB project |
| CUE-02 formalize (forearm stretch → D33 amendment) | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §6 |
| Coach KB spec: add 8 Hörst coaching cues | 📋 Proposed | `_archive/docs/horst_integration_audit.md` §5 |
| Decision consolidation: append D84-D91 | 📋 Proposed | `kb_gaps_analysis.md` |
| Topics 05-10 Steps 4-5 (decision specs) | ⏳ Not started | KB project |

### Remaining Books

| Book | Status | Needed for |
|------|--------|-----------|
| Bechtel — Climb Strong: Drills Manual (pp. 31-90) | 📷 Photograph physical copy | Topic 08 drills |
| MacLeod — 9 Out of 10 Climbers | 🛒 Buy (DRM-free PDF or photos) | Topics 04, 05, 07, 08 |
| Ilgner — The Rock Warrior's Way | 🛒 Buy | Topics 05, 09 |
| Mobråten — The Climbing Bible | 🛒 Buy | Topics 01, 02, 04, 07, 08 |
| Christophersen — Climbing Bible: Injuries | 🛒 Buy | Topic 07 |

---

## Priority 2b — Test results → full exercise calibration

Every test result we collect MUST influence exercise prescription.

| Test result | Current use | New use | Impact |
|-------------|------------|---------|--------|
| L-sit hold (sec) | radar only | Core progression tier (3 tiers) | Exercise selection + prescription |
| Hip flexibility (cm) | radar only | Mobility tier (skip acquired stretches) | Exercise selection |
| Repeater 7/3 max sets | radar only | Finger endurance volume calibration | Prescription (sets/volume) |
| Max hang duration (sec) | radar only | Endurance hang calibration | Prescription (time) |

Depends on: B122 pattern. Supabase migration ✅ complete.

---

## Priority 2.8 — Refactoring

> Origin: Full codebase audit con Agent Teams (2026-03-21)

### R143 — Refactor replanner_v1.py

**Status:** Open | Spezzare in package `replanner/` + estrarre `_SESSION_META` in modulo condiviso.
**Rischio:** ALTO — mandatory analysis phase

### R145 — Spezzare pagine componente grandi

**Status:** Open | `today/` (971), `week/` (889), `settings/` (1018), `guided/` (600+) → hook + sotto-componenti.
**Rischio:** MEDIO

### R146 — Estrarre logica duplicata

**Status:** Open | Backend: load score utility. Frontend: `useSessionHandlers` hook, shared states.
**Rischio:** MEDIO

### R147 — Resolve Session Refactor

**Status:** Open | Spezzare `resolve_session()` + pipeline pattern per filtri P0.
**Rischio:** ALTO — mandatory analysis phase

---

## Priority 2.75 — Architecture

### D168 — Outdoor / Week Plan Unification Audit

**Priority:** P2 | **Status:** Audit done (D170) — implementation open | **Type:** D (architecture audit) | **Effort:** L

Outdoor sessions and week plan are two separate systems that don't communicate:
- Outdoor: JSONL storage, `/api/outdoor/*` endpoints, `OutdoorLogForm` component
- Week plan: `user_state.week_plans`, `/api/week/*` endpoints, week/today views

Problems caused by this split:
- Today/Week views don't show outdoor sessions logged via /outdoor
- Multiple entry points create sessions in different backends
- Delete mechanisms are inconsistent (week plan removal vs JSONL deletion)
- Same-day conflict checks need to be duplicated everywhere

Audit should:
1. Map all data flows and entry points
2. Propose single source of truth for daily sessions
3. Design unified view: Today/Week shows ALL sessions (planned + outdoor + free)
4. Migration path from current split to unified model

Depends on: B186 (immediate fixes). Must be done before further outdoor features.

Audit deliverable: `docs/outdoor_audit_D170.md` (2026-04-04) — 13 findings (2 P1, 5 P2, 6 P3), 5 redesign recommendations. Root cause of outdoor+indoor coexistence bug identified (F1: `add_outdoor` doesn't clear sessions).

---

## Priority 3 — UI polish

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| B40 | Branch develop/main workflow | S | Staging/production branches |
| R148 | Centralize weakness→axis mapping | S | Single dict in assessment_v1.py instead of scattered if-strings. Prerequisite for R149 and LLM Coach. LOW risk. |

### Stretching Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture as Core Circuit for post-session static stretching (30-60s holds).

### Warmup Circuit add-on

**Status:** Open — design pending | **Effort:** M
Same architecture for pre-session dynamic warmup (30s work / 10s transition).

### A-PHASE-EDIT — Phase Duration Editor in /plan

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

UI in `/plan` (controllo accanto al nome di ogni fase del macrociclo: +/- buttons o slider) che permette all'utente di aumentare o ridurre la durata di una fase. Le settimane recuperate o necessarie vengono redistribuite automaticamente alle altre fasi rispettando le caps A218 (con surplus distribution B). Il `total_weeks` resta invariato (la deadline non si sposta).

**Policy decisa (Daniele 2026-05-20):**
- **NO hard block, solo soft warning.** L'utente è libero di portare qualsiasi fase a 0 settimane.
- Warning sotto floor: *"Riducendo Base sotto 3 settimane potresti compromettere la capacità aerobica di base. Per atleti advanced (8a+ lead, 7C boulder) con macrocicli completati nei 6 mesi precedenti, una base abbreviata è accettabile. Continuare?"*
- Caps A218 diventano **soft default** (valori proposti dall'algoritmo), non hard cap.
- L'override manuale è persistito in `macrocycle.phases[].manual_override=true` e sopravvive a rigenerazioni del macrociclo finché l'utente non cambia `goal.target_grade` o `goal.deadline`.

**Decisioni di UX ancora aperte** (da chiudere nel brief A-type proper):
1. Controllo: pulsanti +/- accanto al nome fase, slider per fase, o modal editor full-screen?
2. Visualizzazione del ricalcolo: preview live mentre l'utente modifica, o conferma esplicita?
3. Cosa succede se l'utente porta una fase a 0? Cancella la fase dal macrociclo o la tiene a 0w (skip)?
4. Reset to default: pulsante "ripristina suggerito A218" per ogni fase?

**Risk:** HIGH — tocca `macrocycle_v1.py`. Brief A-type proper richiede mandatory analysis phase + STOP gate (regola CLAUDE.md non-negoziabile). Suggerire `/model opus` per Phase 1 analysis.

**Predecessore:** A218 (A-MACRO-CAPS), B254 (one-shot manual override per Daniele).

**Origin:** Daniele richiesta diretta 2026-05-20 — caso d'uso: advanced climber che vuole base abbreviata dopo cicli completi precedenti, evitando detraining gap.

### End-of-cycle reminder UX

**Priority:** P3 (post-launch) | **Status:** Open | **Type:** A (frontend) | **Effort:** S
**Origin:** A218 / KB Q4-d red flag — without a reminder, advanced users who lose 2-3 weeks between cycles begin detraining (Hörst, Lattice).

When a macrocycle reaches its final deload week (or its `end_date` is within the next 7 days), surface a reminder card on `/today` and `/plan`: *"Your training cycle is ending. Want to start a new one?"* Links to the existing `start-new-macrocycle-dialog` flow (D-NEW-MACRO).

The user does the manual re-trigger (block-stacking is intentionally not automatic in v1, per A218 design doc). The reminder bridges the gap between automatic prompt and inactive cycle.

**Implementation hints:**
- Use `current_phase_and_week()` to detect "deload phase, last week".
- Or compare `macrocycle.end_date - today < 7d`.
- Dismissable; remember dismissal in `state.preferences.dismissed_reminders` keyed on `macrocycle.start_date` so it doesn't re-show after the user opts out.

### Smart planner availability suggestions

**Priority:** P3 (post-launch) | **Status:** Open | **Type:** A (engine + frontend) | **Effort:** M

When the planner struggles to fit sessions into the user's availability (e.g., too many skips, spacing violations, key sessions dropped), surface proactive suggestions:
- "Your plan needs 2 hard climbing sessions per week, but you only have 1 gym slot. Consider adding a gym day on Wednesday."
- "Finger training on Monday and Wednesday violates the 48h spacing rule. Try moving Wednesday's session to Thursday."

**Implementation:** After `planner_v2` generates a week, run a diagnostic pass checking: sessions dropped vs requested, spacing violations resolved by skipping, equipment mismatches forcing substitutions. If diagnostic score is below threshold → generate suggestion(s) as structured data. Frontend: suggestion card on Week view ("Optimize your schedule" expandable). User can accept → triggers availability update + replan.

**Depends on:** Nothing (standalone diagnostic layer on top of existing planner).
**Origin:** GTM-01 dry-run insight (2026-04-01) — if the plan looks weak because of bad availability input, the user blames the app, not their schedule.

---

## Priority 4 — Go-to-market

- Landing page / marketing site
- ~~Pricing model definition~~ ✅ Decided (final): USD $9.99/month Standard (15-day trial) + USD $4.99/month Founding Climber (first 20 users). Net/exclusive (VAT added on top at future Stripe Tax activation, decision locked 2026-04-28). Live since 2026-04-16.

### Capacitor Native Wrap

**Status:** Open | **Effort:** S (base wrap) / M (with native plugins)
**Recommended timing:** 2-4 weeks post soft-launch, after stabilization.

Base wrap (1-2 days): wrap the Next.js PWA in Capacitor for App Store + Google Play. Identical UX to PWA but gains: native push notifications, no localStorage loss on iOS Safari, App Store credibility. Free to test on own devices (Xcode + free Apple ID); Apple Developer Program (99€/yr) only needed for App Store publication. Google Play: 25$ one-time.

Native plugins (incremental): BLE (Kilter Board), haptics, background timers. Each plugin added as needed.

**Dependency sequence:** PWA soft-launch → bug stabilization → Capacitor base wrap → native plugins (BLE for Kilter, etc.)

### Board-specific features (Kilter first)

**Status:** Open | **Effort:** L (basic) / XL (games)

**Dependency sequence:** PWA launch → stabilization → Capacitor base wrap → Level 1 → Level 2.

**Level 1 — Data integration (L):**
API integration for Kilter Board problem lookup, difficulty grades, and ascent logging. Use [BoardLib](https://github.com/lemeryfertitta/BoardLib) (Python) for Aurora API access — downloads the SQLite DB with holes, LEDs, placements, and climbs. Covers all Aurora boards (Kilter, Tension, Grasshopper, Decoy). Other boards (MoonBoard) follow same pattern. Can start before Capacitor (data layer is web-only).

**Level 2 — LED control + games (XL, exploratory):**
Interactive games via BLE LED control: tic tac toe on the wall, incremental hold lighting (add one hold each round), circuit creation. **Requires Capacitor BLE plugin for iOS support** (Web Bluetooth API works on Chrome/Edge but NOT Safari/iOS). This is the main reason to do Capacitor wrap before Kilter Level 2.

**Open-source references:**
- [BoardLib](https://github.com/lemeryfertitta/BoardLib) — Python, Aurora board API utilities, SQLite DB sync
- [Boardsesh](https://github.com/marcodejongh/boardsesh) — Apache license, unified multi-board app with queue management and Party Mode
- [kilterboard.app](https://tim.wants.coffee/posts/kilterboard-app/) — Web Bluetooth reverse engineering blog post
- [fake_kilter_board](https://github.com/1-max-1/fake_kilter_board) — BLE protocol documentation
- [Grip Connect](https://stevie-ray.github.io/hangtime-grip-connect/devices/kilterboard) — DB schema and placement format docs

**Risk:** Kilter launched a new standalone app (kilterboard.io) separate from the old Aurora app — API stability uncertain.

---

## Future — Phase 3.5: LLM Coach

Claude Sonnet as conversational layer over the deterministic engine.
Design spec: `docs/coach/design.md`

- Dynamic system prompt injecting user_state + current plan + recent logs
- POST /chat endpoint
- Use cases: conversational onboarding, pre-session coaching, post-session analysis
- The LLM suggests and converses — it does NOT modify the plan directly

**Dependent items:** B89 (weekly report narrative), B11 (configurable test protocols), B29a (dedicated test exercises), science explainers, nutrition hints.

### R149 — Weakness→resolver hints

**Priority:** P3.5 | **Status:** Open | **Type:** A (feature) | **Effort:** S

Pass user weaknesses as soft preferences to `score_exercise()` in the resolver. Example: `weak_on_slopers` → boost exercises with `grip: open_hand`. Depends on R148 (centralized weakness mapping).

---

## Future — Load calculation v2

> Origin: D151 load coherence audit (2026-03-23)

| # | Area | Detail |
|---|------|--------|
| 1 | Outdoor user-relative scaling | Use `grade / user_max` instead of absolute French grades |
| 2 | Other activities load map | `activity_load_map` with fixed AU values per type |
| 3 | Engine load normalization | Replace ×1.5 magic number with proper formula |
| 4 | Free session non-linear scaling | Exponential curve above 90% of max |
| 5 | Unified AU scale validation | Validate with beta tester data |

Depends on: D69 (ACWR) design, beta tester data.

---

## Future — Engine improvements

| ID | Title | Notes |
|----|-------|-------|
| P3 | Data-driven phase→axis mapping | Replace hardcoded `_PHASE_TEST_MAP` with `stimulated_axes` metadata on phase definitions in `macrocycle_v1.py` (KB Decision D92) |
| ARCH-3 | Generic timer from prescription | Frontend timer derives behavior from `work_seconds` + `reps` + `rest_*` fields |
| — | Override intensity cap warning | Warn when user overrides above phase intensity cap |
| — | P1 ranking in resolver | Recency, intensity, fatigue-based exercise prioritization |
| — | Advanced adaptivity | Readiness score, overreach detection, plateau detection |
| — | Test results → exercise calibration | Use ALL test results to calibrate difficulty and prescription |
| B127 | Pre-test adjacency rule | Planner excludes finger work day before finger test sessions |
| B133c | Multiple other_sport same day | `other_activities: []` array instead of boolean |
| R148 | Performance: JSON catalog caching | `@lru_cache` on `json_loader.py`, optimize `pick_best_exercise_p0()` |
| R149 | Frontend performance | Code splitting, `React.memo` on hot-path components |

---

## Future — Content & UX

### Educational content (methodology explanations)

Two-layer system: reference doc (`docs/training_methodology_explained.md`) + condensed UI cards in Plan page.
Content: 5 phases, DUP vs linear, feedback loop, deload science, exercise ordering.

### Outdoor redesign

Guided outdoor session mode, load calculation, ripple effect, done tracking, history/stats UI, spots in onboarding.
Consolidates: B68, B69, B70, B72, B73.

### Trip Management (post-onboarding CRUD)

**Status:** Open | **Effort:** M | **Priority:** P3

Full trip lifecycle outside onboarding: add, edit, delete planned trips from Settings.
When a trip is added/modified:
- Trip days auto-marked as outdoor in affected week plans
- Pre-trip deload (3-5 days before, no hard/max sessions) via existing `compute_pretrip_dates()`
- Recovery day after return
- Affected week plans auto-regenerated

Backend: CRUD endpoints for `user_state.trips` + trigger plan regeneration on change.
Frontend: Settings → "Planned Trips" section (list + add/edit/delete). Week view shows trip days with visual badge (read-only).
Workaround until implemented: use weekly overrides to manually mark days as outdoor/rest.

Related: Outdoor redesign (B68-B73), `compute_pretrip_dates()` in planner_v2.

### Social Session (fun bouldering with friends)

**Status:** Open | **Effort:** M
Recreational session: game catalog, purpose selector, timer, social_modifier=0.5 load. Available as a free session mode. Origin: real session 2026-03-14.

### Technique Drills in Free Session

**Status:** Open | **Effort:** S-M
Add technique drill selection as a free session activity type. User picks from the drill catalog (D76) and runs drills as a standalone free session or add-on. Depends on D76 (drill catalog population) being complete.
Related: D73 (technique drill % allocation), D76 (drill catalog).

### A-B20 — Video/GIF reference for movement patterns

**Priority:** P3 | **Status:** Open | **Type:** C (content) | **Effort:** L

Short clips for technique drills and complex exercises. Priority: flagging, heel hooks, drop knees, dynos. Boulder is more visual than lead — video reference is a differentiator.

### Injury-Specific Rehab/Prehab

Rehab exercise catalog + injury→exercise mapping. Medical disclaimer required. Best candidate for LLM Coach layer (Phase 3.5). Origin: Christie feedback 2026-03-21.

---

## Future — Evolution (Phase 4+)

### A-B16 — Board workout generator

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

Structured board workout mode: input board type + angle + goal → output grade range, problem count, rest times, timer, RPE per problem.

### A-B17 — Pyramid/circuit builder for board

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Pre-built formats: grade pyramid, 4x4, density sets. User can save custom circuits.

### A-B18 — Competition prep mode

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** L

Flash/onsight training, time pressure, style variety, comp-specific periodization.

### A-B19 — Indoor grade calibration

**Priority:** P3 | **Status:** Open | **Type:** A (feature) | **Effort:** M

Self-report gym grading (soft/accurate/hard) or anchor to board grades. Multiplier on grade-based calculations.

- UI-25 — Test Maxes & Loads panel (Plan tab)
- Multi-goal support (boulder, all-round, outdoor_season)
- Annual report
- Multi-macrocycle periodization
- Notifications/reminders
- Gym preferences per day
- Crowdsourced gym DB

### A-B21 — Board API integration (v2+)

When Kilter/Tension/Moon open public APIs: sync sends, problem recommendation, auto-log. Future/v2+.

### A-B22 — Style finder — strength profile analysis (v2+)

Analyze boulder style preferences (crimpy, dynamic, slopey). Best candidate for LLM Coach layer. Future/v2+.

### A-B23 — Advanced finger strength periodization (v2+)

Lattice-style stimulus cycling: max hang → repeaters → contact strength → board. Refined DUP. Future/v2+.

### A-B24 — Boulder-specific injury prevention (v2+)

Higher pulley injury rate, shoulder impingement from steep terrain, fall injuries. Adapted prehab emphasis. Combine with injury tracking (Phase 3.5/4). Future/v2+.

---

## Backlog / exploration

### Mega Brief v1 — Deferred Decisions (v2+)

> Full specifications in `docs/claude_code_mega_brief_v1.md`. Grouped by theme.

**Effort Level / Intensity System (mega brief Session 5)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D34 | EL (Effort Level) as primary intensity metric | L | New field on every prescription, resolver + feedback changes. Current very_easy→very_hard feedback sufficient for launch. |
| D52 | EL prescription table by experience level | M | Depends on D34. Intensity ranges per beginner/intermediate/advanced. |
| D14 | López load monitoring (EL trend tracking) | M | Depends on D34. Autoregulation: reported_el vs target_el trend → load adjustment. |

**Periodization & Load Management (mega brief Session 9)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D19 | Simplified linear periodization for beginners | M | Longer base, no MaxHangs, more technique. Also subsumes D44 (ARC ≥6wk for beginners). |
| D20 | Overreach + taper before Performance phase | M | +10-15% volume overreach → 40-60% taper. Advanced periodization. |
| D44 | ARC ≥6 weeks in Base phase | S | Currently base=4wk/floor=2wk. Best handled via D19 (beginner path gets ≥6wk base). |
| D45 | ARC <25% MVC formal enforcement | S | Currently via process cues only. Formal resolver load cap. |
| D69 | ACWR-based load monitoring | L | Needs 4+ weeks accumulated data. Overlaps Load Model v2 section. |
| D70 | Overtraining detection heuristics | M | 5-flag system. **⚠️ KB: Ch. 12 adds central fatigue timeline — nerve cell 7× slower recovery than muscle (Bompa 1983). If "off" after several rest days → 2-10 more days needed.** |
| D71 | <10% weekly volume increase cap | S | Guard on planner output. Needs historical volume baseline. |
| D15 | Progressive ARC duration | XS | Confirmed by D44 + D45. ARC duration increases progressively within Base phase. Covered by current implementation (4wk base with floor=2wk). |

**Warm-Up & Recovery (mega brief Sessions 4, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D33 | Dedicated `generate_warmup()` function | M | 5-phase protocol generator. **⚠️ KB: Ch. 6 has warm-up exercises + CUE-02 (no forearm flexor stretch pre-performance). See `_archive/docs/horst_integration_audit.md` §5-§6.** |
| D36 | PAP (Post-Activation Potentiation) | S | Advanced users only (3+ years, pulling ≥60). Niche. |
| D74 | `silent_feet` auto-inject in warmup template | XS | Drill exists, not auto-injected in warmup. |
| D53 | Active recovery progression (3-step) | S | References EL system (D34). **KB: Ch. 12 confirms active rest +35% lactate clearance (Watts 2000).** |

**Session Balance & Ratios (mega brief Session 8)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D51 | Climbing vs conditioning ratio by level | M | 70/30 → 60/40 → 50/50. Currently approximated by template weights. Formal enforcement = resolver change. |
| D59 | Hypertonic/inhibited muscle reference table | S | Internal resolver pairing logic. Exercises already exist. |
| D73 | Technique drill % allocation by level | M | Beginners ≥30% drill time. Resolver change. |

**Endurance & Hangboard (mega brief Sessions 6, 7)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D47 | Varied-intensity intervals (replace 4×4) | M | Consuegra Ch.8. Add as option first, 4×4 is industry standard. |
| D49 | Don't combine MaxHangs + IntHangs in same mesocycle | M | López-Rivera 2018. Planner change (high-risk). Current system tends to pick one naturally. |

**Coaching & UX (mega brief Session 10)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D29 | Post-climb mental reflection questions | S | 5 rotating questions, free text, optional. Good UX differentiator. |
| D41 | Campus board auto-stop rules | S | RPE check after campus sets → stop + substitute. Safety layer on top of B159a. |
| D77 | SDT principles in all copy | S | Audit + rewrite all user-facing strings. Partially followed already. |
| D79 | "Train better, not more" personality | S | Messaging guidelines. Already embodied in current copy. |
| D65 | Sleep education tips | S | **KB: Ch. 12 §5.5 (6-7h min, 8-10h after hard training) + Ch. 11 hydration data.** |
| D66 | Nutrition messaging at phase transitions | S | **KB: Ch. 11 has macro ratios by climbing style (65:15:20 vs 55:15:30), GI tables, 3-step refueling protocol.** |
| D67 | Collagen + vitamin C educational mention | XS | **KB: Ch. 11 also covers creatine (2-5g OK, loading counterproductive) + caffeine periodization.** |

**Exercise Catalog (mega brief Sessions 2, 3)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D10 | Overcoming isometric pull exercise | S | Requires pin/strap equipment not in vocabulary. Tyler Nelson protocol. |
| D37 | Core activation drills from Matros (8 exercises) | M | Tic tac toe, diagonal, freeze wall, etc. Catalog enrichment. |
| D50 | Three named repeater protocols (López/Anderson/Hörst) | M | Level-based selection logic in resolver. |
| D55 | Exercise safety blacklist formal guard | S | Validate no blacklisted exercises in catalog (CI test or resolver check). De facto safe today. |
| D58 | YTW raises exercise (missing from postural set) | XS | 4/5 done, only YTW missing. **⚠️ KB: Ch. 6 has T exercise (EX-SCAP-01) and Y exercise (EX-SCAP-02) with full protocols + 38 total exercises. See `horst_ch6_mobility_synthesis.md` §8.** |
| D72 | `grip_type` field on hangboard exercises | M | Structural schema change + full_crimp validation block. |

**Test Protocols v2 (mega brief Session 1b deferred)**

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D87b | PE diagnostic test (repeaters 60% to failure) | M | New test protocol for power endurance baseline. |
| D89 | Critical Force test (simplified, 2-point) | M | `critical_force_test` orphan exists in catalog. |
| D91 | `test_pe_repeaters_60` + `baselines.power_endurance` | S | Depends on D87b. |

### Other backlog items

| Theme | Detail | Origin |
|-------|--------|--------|
| R150 | Integration test full-pipeline (assessment → closed-loop) | audit 2026-03-21, confirmed by D164 Agent 10 |
| R151 | Type hints (`TypedDict`/`dataclass`), eliminate `any`, date utils | audit 2026-03-21 |
| R152 | Periodic full codebase audit con Agent Teams | audit 2026-03-21 |
| R160 | Audio util dedup: beep/countdownTick/transitionBeep duplicated in CircuitTimer and Tabata — extract to single shared module in lib/ | B160 audit 2026-03-26 |
| — | Dynamic background imagery (Midjourney, phase-aware) | roadmap discussion |
| — | Technique drills from book (scan + catalog) | roadmap discussion |

### Bodyweight exercises — load and band progression (v2+)

Exercises like dip, push-up, pull-up currently use `load_model: bodyweight_only`.
When feedback is "too easy", the engine should suggest adding external load (weight belt + disc).
When feedback is "hard" or "failed", it should suggest resistance band assistance.

Implementation approach:
- Add two optional boolean flags to the exercise catalog schema: `supports_load_progression` and `supports_band_assistance`
- Extend `closed_loop_v1.py` / `progression_v1.py` to read these flags and adjust suggestions accordingly
- Same pattern as existing external_load progression — no new concepts

**Scope:** catalog schema change + closed-loop extension. Generic solution (not dip-specific).
**Depends on:** nothing. Natural fit alongside LLM Coach closed-loop work (Phase 3.5).
**Origin:** beta feedback (Daniele, 2026-03-31)

### Superseded Decisions

| ID | Superseded by | Reason |
|----|---------------|--------|
| D16 | → D47 | Replace 4×4 entirely, not tweak |
| D18 | → D33 | Absorbed into full warm-up protocol |
| D28 | → D75 | Upgraded to structured route preview |

---

## v2+ Deferred Decisions (Decision Consolidation)

> Origin: Decision consolidation cross-check (D-ROADMAP-XCHECK, 2026-04-05)
> Source docs: `decision_consolidation_D01_D83.md` + `claude_code_mega_brief_v1.md`
> Intentionally excluded: D25 (microcycle types), D27 (reverse periodization), D40 (VBT), D46 (BFR) — too niche for target audience.

### Assessment Expansion

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D03/R-01 | Flexibility axis (6th assessment dimension) | L | Requires radar UI redesign, domain weight rebalancing. Real gap for many climbers. |
| D08/R-02 | Test bank concept (optional tests beyond defaults) | M | Natural extension of current test framework. Low priority. |
| D13 | Open hand grip strength test | S | Tyler Nelson protocol. Depends on D72 (grip_type field). |
| R-03 | Technique assessment improvement | M | Current technique axis is weakest (onsight/redpoint gap + self-eval only). May need LLM Coach for video analysis → could slip to v3. |

### Periodization

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D22 | Competition taper protocol | S | Deload variant with competition-specific timing. Niche but differentiating for competitive climbers. |
| D23 | Seasonal multi-macrocycle planning | L | Already listed in "Future" section as "Multi-macrocycle periodization" — this is the formal decision ID. |
| D24 | ATR as alternative macrocycle model | L | Accumulation-Transmutation-Realization. Practically a second engine. **Recommend v3.** |

### Female-Specific

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D82 | Menstrual cycle tracking with light algorithm | M | **Upgraded from original "no algorithmic rules" scope.** v2 scope: optional cycle input (last period date + avg duration), light algorithmic adjustment on planner (follicular → favor intensity, luteal → favor volume/recovery), educational tips per phase. LLM Coach layer: expert mode for personalized cycle-aware coaching. Opt-in, privacy-first. Positive beta feedback received. Differentiates from all climbing training competitors. |

### Conditioning & Mobility

| ID | Title | Effort | Notes |
|----|-------|--------|-------|
| D61 | VO2 max benchmark + optional HIIT sessions | S | Useful for endurance/multipitch focus. Supplementary session, not core. Low priority. |
| D62 | Separate mobility into ROM vs postural categories | S | Catalog refinement. Improves prescription accuracy. Not user-visible. |
| D63 | PNF stretching protocols | S | Linked to D62. Add PNF as method once ROM/postural distinction exists. Can be bundled with D62. |

---

## v3 — LLM Coach & Advanced Assessment

> These decisions require the LLM Coach layer (Phase 3.5) or specialized hardware.

| ID | Title | Category | Effort | Notes |
|----|-------|----------|--------|-------|
| D04/R-04 | Mental/tactical assessment via AI conversation | Assessment | L | Perfect LLM Coach use case. Qualitative assessment through dialogue. |
| D05/R-05 | Contact strength / RFD axis | Assessment | L | Requires force plate or similar hardware. Linked to D42. |
| D06/R-06 | Critical Force test (full protocol) | Assessment | M | D89 (v2) is the simplified 2-point version. D06 is the complete protocol. |
| D31 | Route preview coaching | Coaching | M | AI-guided route reading. Potential photo input. High differentiation. |
| D32 | Fear assessment protocol | Coaching | M | Sensitive topic, needs LLM Coach for nuance. Very differentiating if done well. |
| D42 | Levernier & Laffaye one-arm hang for RFD | Exercise DB | S | Depends on D05 (RFD axis). Specific test protocol. |

---

## Post-launch — Christie feedback (2026-03-28)

| ID | Title | Priority | Type | Effort | Status | Notes |
|----|-------|----------|------|--------|--------|-------|
| — | **Free session expansion** — standalone non-structured activities | P3.5 | A | M | Open | Standalone hangboard cycle, mobility routine, core circuit. "Tap and go" — no resolver, no structured prescription. Complements Session Builder. Core/mobility partially exist in free session surfaces. |
| — | **Quick-add equipment guard**: `suggest_sessions` and `apply_day_add` don't validate `required_equipment` — user can quick-add `limit_boulder_gym` without gym_boulder | P3 | B | S | Open | Touches replanner_v1.py — needs analysis brief (STOP gate). Origin: B185 verification. |
| — | **Warmup/cooldown P0 rotation**: convert hardcoded warmup/cooldown blocks to P0 selection for exercise variety | P3 | A | M | Open | Low priority — warmup sequences are standard. 11 hardcoded warmup blocks (warmup_climbing ×4, warmup_strength ×3, general_warmup ×2, cooldown_stretch ×2). Origin: B185 catalog audit. |
| — | **Quick-add filter/search** — session list discoverability | P4 | A | S | Open | Search/filter by goal or body part in quick-add list. Data available via `intent.primary_goal`. Low priority — Session Builder likely subsumes most of this. |
| — | **Session phase coloring** — warmup/cooldown dimmed | P4 | A (frontend) | XS | Parked | Dim warmup/cooldown, vivid main work. Data from `module_role` + `exercise_ordering.py`. Pure CSS, zero backend. |
| — | **Exercise request mailto banner** — "Missing an exercise? Email us" | P4 | A (frontend) | XS | Open | Simple mailto link/banner in Free Session page and exercise-related UI. Encourages users to request new exercises. No backend needed. Origin: Christie idea (2026-04-08). |
| A-FREE-01 | **Free Tier Logging** — logging as free tier, training plan as paid upsell | P3 | A | L | Open | All logging (outdoor, hangboard, campus, any activity) is free. Paywall on: training plan, guided sessions, resolver, progression, radar assessment, closed-loop adaptation. Requires: decouple logging from plan, define paywall boundary in frontend + API, extend outdoor session framework for generic activity types. Connects to D168 (outdoor/week plan unification). Design brief (D-type) needed first. |
| A-FREE-02 | **Flexible Activity Logger** — log any climbing/training activity without going through the weekly plan | P3 | A | M | Open | Intuitive UX to log what you actually did: open app → tap "Log activity" → pick type (hangboard, boulder session, campus, stretching, weights, outdoor, etc.) → enter details → done. No plan dependency. Solves Christie's pain point (can't easily log non-plan activities). Connects to Session Builder (custom sessions) and Free Session Expansion. Design brief (D-type) needed first. |
| A219 | **Partner Training Mode** — ⤳ **superseded da D244**. Lo spec è ora `docs/design/D244-PARTNER-MODE_audit.md` (modifier system estendibile). Implementazione scorporata nei 5 brief sotto. | P3 | A | M | Superseded | Vedi D244 §6. Origin: Daniele (2026-05-07/21). Marketing angle: differenziatore vs competitor solo-focused. |
| A-MODIFIER-CORE | **Modifier system core** — astrazione `session.modifiers: []` + reversibilità snapshot; estende il replanner per applicare/rimuovere modifier. Riusa `equipment_override` (A210) e `boulder_fallback`. | P3 | A | S-M | Open | **HIGH RISK** (`replanner_v1.py`) → mandatory analysis + STOP gate. NON tocca `resolve_session.py` per L1. Spec: D244 §3/§6. |
| A-SURFACE-PREF | **Surface preference modifier** — generalizza A210 ("Boulder only") aggiungendo `prefer_routes` + toggle bi-direzionale. EFFIMERO (no persistenza). | P3 | A | XS-S | Open | Quasi indipendente (riusa A210). Frontend → branch + Vercel preview. Spec: D244 §3.3/§5. |
| A-PARTNER-MODE | **Partner mode L1** — swap sessione partner-friendly per fase (`boulder_fallback`/helper-text), preview modal, banner/badge/undo, persistenza + immutabilità. | P3 | A | M | Open | Dipende da A-MODIFIER-CORE. Frontend → branch + preview. Spec: D244 §3.2/§5. |
| B-MODIFIER-SCHEMA | **`session.modifiers: []` convenzione** — campo additivo, **nessuna migration** (user_state schemaless). | P3 | B | XS | Open | Quasi no-op; assorbibile in A-MODIFIER-CORE. Spec: D244 F3/§6. |
| C-PARTNER-CATALOG | **`partner_compatibility` su 225 esercizi** (parallel/rotation/solo_only). | P3 | C | S | Open | **OPZIONALE/post-MVP** — non serve per L1 (serve solo per L2/badge). Spec: D244 §4.1. |
| — | **Audit visuale `/today`** — 11 issue identificate (2 P0 + 5 P1 + 4 P2). Backlog informale, non-brief. | P3 | A (design) | — | Parked | File: `docs/audit/audit-today-2026-05-12.md`. Solo P1 #5 (touch target dismiss × da 24→44px) fixato immediatamente. Review post-launch + 30gg (~2026-05-16) → convertire in brief A-design con dati reali su retention. Origin: skill `example-skills:frontend-design` validation (2026-05-12). |

---

## Completed phases (reference only)

Full details in `docs/ROADMAP_v2.md`.

| Phase | Completed | Highlights |
|-------|-----------|------------|
| 0: Catalog | 2026-02 | 102 exercises, 29 sessions, vocabulary |
| 1: Macrocycle engine | 2026-02 | assessment_v1, macrocycle_v1, planner_v2 |
| 1.5: Post-E2E fixes | 2026-02 | 14 findings resolved |
| 1.75: Session enrichment | 2026-02 | Load scores, test scheduling, ripple fix |
| 2: Tracking + outdoor | 2026-03 | Outdoor logging, reports, quotes |
| 2.5: Catalog audit | 2026-02 | 10 enrichment patches, grade_ref, working loads |
| 3: UI (Next.js PWA) | 2026-02 | 14 routers, mobile-first dark PWA |
| 3.1-3.2: Bug fixes + polish | 2026-02 | 22+ bugs, adaptive replanning, quick-add |
| 4a: Multi-user + deploy | 2026-02 | UUID multi-user, Railway/Vercel |
| 4b: Guided session + beta | 2026-03 | Step-by-step timer, settings editors, dirty-state |
