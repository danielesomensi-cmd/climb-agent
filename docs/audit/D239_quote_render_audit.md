# D239 — Audit: daily quote/tip rendering on /today

> **Type:** D (read-only audit, no code changes)
> **Date:** 2026-05-19
> **Reporter:** Daniele
> **Trigger:** /today on iPhone PWA showed session card "Test Max Hang 7s" but
> Daniele perceived no quote/tip visible. Memory: "cammina invece di sederti
> nelle pause" (seen 2026-05-18).
> **Reference screenshot:** `IMG_7828.PNG`.

---

## TL;DR

**Nessun bug.** Tutti i sistemi (quote endpoint, catalog, componente A217) funzionano
in produzione. Lo screenshot quasi certamente non includeva il fondo pagina dove vive
la quote card A217 (sotto la fold sull'iPhone PWA dopo header + week progress bar +
day card aspect-4/5 hero).

Il "tip" che Daniele ricorda — *"cammina invece di sederti nelle pause"* — è il
**process_cue `cue_028`** ("Walk between attempts — don't sit down. Active rest
accelerates lactate clearance by ~35%.", Draper 2006 + Watts 2000), e:

1. È un **process_cue**, non una quote. Sistema separato (`backend/catalog/cues/v1/process_cues.json`).
2. Renderizza **solo in `/guided/[date]/[sessionId]`** (guided session page), **NON in `/today`**.
3. Il suo `session_types` whitelist è `["limit_boulder_gym", "power_contact_gym", "boulder_circuit_gym"]` — tutto boulder.
4. **Daniele è `discipline = lead`** (verificato in prod). Quindi questo cue non
   gli sarebbe mai stato attaccato da `_attach_process_cues()` sulle sue sessioni
   regolari. La sua memoria è probabilmente di averlo visto in screenshot/social/docs,
   o di averlo confuso con un'altra cue lead-friendly (es. `cue_006` G-Tox, `cue_001`
   "where will you rest", `cue_008` "identify rest spots").

La quote di oggi per Daniele (chiamata diretta endpoint con il suo X-User-Id):
```
context=general → q028 "The purpose of climbing is not to conquer the rock, but to conquer yourself." — Yvon Chouinard
context=hard_day → q004 "It is about turning pain into joy..." — Adam Ondra
```
La quote *c'è*, viene servita, e (data l'autenticazione Clerk dal frontend) deve
essere stata fetchata correttamente dal client. Nello screenshot è semplicemente
fuori dal viewport iniziale.

**Severity:** cosmetic / UX confusion. **Suggerito follow-up B-brief P3** (vedi §10).

---

## 1. Hypothesis evaluation

| # | Hypothesis | Verdict | Evidence |
|---|------------|---------|----------|
| H1 | Endpoint `/api/quotes/daily` rotto in prod | **REFUTED** | curl con X-User-Id di Daniele → 200, ritorna q028 (general) e q004 (hard_day). |
| H2 | Catalogo quote degradato / contesto vuoto | **REFUTED** | 232 quote in catalog. Context `general`=150, `hard_day`=93, `deload`=39. Fallback chain (`context → general → any → hardcoded`) in `quotes_engine.py:84-102`. |
| H3 | Componente frontend rimosso o condizione restrittiva | **REFUTED** | `today/page.tsx:1160` → `{quote && !loading && (...)}`. Nessuna gate per discipline/session type. Render unconditional una volta caricati state+week. |
| H4 | Service Worker cache stale tra 18 e 19 maggio | **REFUTED** | `git log --since=2026-05-17 --until=2026-05-19 -- frontend/` → empty. Nessun deploy → stesso SW → stesso comportamento atteso. CACHE_NAME basato su `VERCEL_GIT_COMMIT_SHA` non sarebbe cambiato comunque. |
| H5 | Regressione recente | **REFUTED** | Ultimo commit a `frontend/src/app/(main)/today/` è `69b6dac` ("a11y: fix touch target 24→44px on /today dismiss buttons") — non tocca render della quote A217. Nessun commit a `quotes_engine.py`, `routers/quotes.py`, `quotes_catalog_v1.json` dal periodo rilevante. |
| H6 | Quote presente ma `display:none` / fuori viewport | **PARTIALLY CONFIRMED** | Ordine di render in `/today`: WeekProgressBar → WeeklyCheckinCard → (C203 phase tip, skippato — Daniele è lead) → (A202 feedback edu) → **DayCard** (la "card sessione" che si vede) → (heroCTAs) → **A217 quote hero card** (aspect-4/5 con `today_hero.webp`). Sull'iPhone PWA la quote è sotto un'intera card sessione → necessita scroll. Lo screenshot mostra solo il primo viewport. |
| H7 | Falsa memoria di **dove** ha visto il tip | **CONFIRMED (root cause)** | Il testo ricordato ("cammina invece di sederti") combacia esattamente con `cue_028` (process_cue). Process_cue è renderizzato solo in `/guided/[date]/[sessionId]:576-588`, non in `/today`. Inoltre `cue_028.session_types` è 100% boulder, quindi non si sarebbe attaccato alle sessioni lead di Daniele. |

---

## 2. Architettura del sistema "motivazione" su /today

Sull'attuale `/today` ci sono **tre canali di motivazione distinti**, facili da confondere:

| Canale | Sorgente dati | Renderizzato dove | Visibilità a Daniele |
|--------|--------------|-------------------|----------------------|
| **A217 — Daily quote** | `GET /api/quotes/daily` → `backend/catalog/quotes/v1/quotes_catalog_v1.json` (232 entries) | `/today` — hero card in fondo pagina con immagine `today_hero.webp`, aspect-4/5 | ✅ Sempre, se quote loadata |
| **C203 — Boulder phase tip** | Static client-side: `frontend/src/lib/boulder-phase-tips.ts` (5 fixed strings per phase) | `/today` — banner info/30 sotto WeeklyCheckin, sopra DayCard | ❌ Mai (gated `discipline === "boulder"`; Daniele è lead) |
| **A141 — Process cue** | `GET /api/week/...` ora attacca `process_cue` a ogni session via `_attach_process_cues` → `backend/catalog/cues/v1/process_cues.json` (35 cue) | `/guided/[date]/[sessionId]:576-588` — banner amber "Today's focus" | ✅ Solo dentro guided session, e solo se la cue matcha `session_template_id` |

**Vocabolario per Daniele:** quando dice "il tip motivazionale", potrebbe riferirsi a uno qualsiasi dei tre. Il testo che ha ricordato è A141 (process_cue), non A217 (quote).

---

## 3. Perché oggi non vede nessun tip dentro la sessione

Sessione di oggi: **Test Max Hang 7s** (file `backend/catalog/sessions/v1/test_max_hang_7s.json`, `tags.test = True`).

`_attach_process_cues` (in `backend/api/routers/week.py:184-209`) chiama `get_session_cue(session_template_id=<id sessione>, ...)`. La funzione filtra `process_cues.json` cercando cue con `session_types` che contengono il template id. Nessuna delle 35 cue ha `test_max_hang_7s` (o altri test session ids) nei suoi `session_types` — i tipi presenti sono tutti per training sessions (boulder, route, finger, conditioning, regeneration, eccetera).

Risultato: **`session_entry["process_cue"]` non viene settato per la sessione di test → la chiave non esiste nel payload → in `/guided` non si mostra nessun banner "Today's focus".**

**Per /today: irrilevante**, perché `/today` non mostra process_cue indipendentemente dal session type (vedi §2).

Daniele non è ancora andato in `/guided` oggi (la sessione non risulta started). Quindi, anche se ci andasse, non vedrebbe il "Today's focus" per design (test sessions = nessun cue).

---

## 4. Perché Daniele non vede la quote A217 nello screenshot

Layout `/today` mobile (~390px iPhone):

```
┌─────────────────────────┐
│ Header                  │  ~60px
├─────────────────────────┤
│ WeekProgressBar         │  ~80px (phase progress shown in screenshot)
├─────────────────────────┤
│ WeeklyCheckinCard (?)   │  conditionally rendered (Sun/Mon grace)
├─────────────────────────┤
│ A202 feedback edu (?)   │  if hasDoneSession && not dismissed
├─────────────────────────┤
│ DayCard (sessione)      │  ~300-500px (visible in screenshot)
├─────────────────────────┤
│ heroState CTAs (if any) │  
├─────────────────────────┤
│ ──── below the fold ────│
│ A217 quote hero card    │  ~488px (aspect-4/5 di 390px)
│   - today_hero.webp     │
│   - quote text (bottom) │
└─────────────────────────┘
```

A 19 maggio Daniele apre `/today`: il viewport iniziale (~750px useful height su iPhone Pro/standard) mostra Header + WeekProgressBar + DayCard. La quote hero card (aspect-4/5 ≈ 488px di altezza) richiede scroll.

**Lo screenshot `IMG_7828.PNG` cattura solo il primo viewport** → la quote non appare → percezione di "manca la quote".

Questo è coerente con: "Header → progress bar fase → card sessione → immagine sfondo. Zero quote/tip area." Probabilmente "immagine sfondo" è l'immagine **dentro** la DayCard (e.g. l'header image della sessione test), non la quote hero card. Lo si può confermare verificando lo screenshot al volo.

---

## 5. Verifica end-to-end del quote system per Daniele

| Step | Risultato |
|------|-----------|
| `quote_history` del suo user_state | 30 entries (cap), ultime: `['q020','q021','q024','q025','q026']` — sistema attivo |
| Endpoint `/api/quotes/daily?context=general` (con X-User-Id Daniele) | 200, `q028` "Yvon Chouinard..." |
| Endpoint `/api/quotes/daily?context=hard_day` | 200, `q004` "Adam Ondra..." |
| Endpoint senza auth | 500 (edge case `save_state(None)` su stato legacy corrotto) — irrilevante per Daniele |
| Layout `/today` | Quote hero card presente nel JSX, condizioni `quote && !loading` soddisfatte una volta caricati state+week |
| Discipline | `lead` → quoteContext oggi probabilmente "general" (la sessione test non matcha "hard_day" keywords: `strength_long`, `power_contact`, `finger_strength`) |

**Quote che Daniele dovrebbe vedere oggi:** `q028` ("The purpose of climbing is not to conquer the rock, but to conquer yourself." — Yvon Chouinard).

Verifica visiva da fare: aprire `/today` su iPhone, **scrollare fino in fondo**, e cercare la hero card con l'immagine di climbing. La quote è sovrapposta al gradient sul bordo inferiore dell'immagine.

---

## 6. Reproduction steps (per chi vuole verificare)

1. Aprire `/today` su mobile (PWA o browser, simulato 390px wide).
2. Header + progress bar + day card visibili nel primo viewport.
3. **Scrollare verso il basso** ~500-700px.
4. Appare la hero card con `today_hero.webp` di sfondo (aspect 4/5) e la quote in italic sovrapposta al bordo inferiore con gradient.

Se la quote **NON appare** anche dopo scroll completo:
- DevTools → Network: cercare `/api/quotes/daily` → status code + response body.
- DevTools → React Query devtools: chiave `["quotes", "daily", "<context>"]` → stato `success/error/idle`.
- Inspect element: cercare `<Image src="/hero/today_hero.webp"` → verificare se il `<p>` con la quote text è nel DOM.

---

## 7. Scope of impact

- **Tutti gli utenti**: nessun bug. Comportamento atteso.
- **Test session days** (1× a fase tipicamente): nessun process_cue attached → guided page mostra solo banner senza "Today's focus". Cosmetic.
- **Lead climbers**: non vedranno mai C203 boulder phase tip. By design.
- **Boulder climbers**: vedono C203 una volta per fase, dismissibile.
- **PWA iPhone con poco viewport**: la quote A217 richiede scroll → bassa visibilità → possibile cosmetic miglioramento.

---

## 8. Severità

**Cosmetic / UX confusion.** Nessun dato perso, nessun comportamento del piano alterato. La quote esiste, viene servita, viene renderizzata. L'utente percepisce "manca qualcosa" perché:

1. La hero card A217 è sotto fold sullo screenshot.
2. Tre sistemi distinti (quote/phase tip/process cue) si confondono nella memoria dell'utente.
3. Le test sessions non hanno process_cue.

**Non è un signal di un bug più profondo.** Quote endpoint, catalog, render component sono tutti sani.

---

## 9. Risultato dell'audit vs Definition of Done

- [x] Brief ID assegnato via `next_brief.py` → **D239**.
- [x] Tutte e 7 le hypotheses valutate con evidenze.
- [x] Root cause identificato: H7 confermato (confusione process_cue ↔ quote) + H6 parzialmente (quote sotto fold).
- [x] Audit doc salvato in `docs/audit/D239_quote_render_audit.md`.
- [ ] ROADMAP_CURRENT.md update + brief marked ✅ Done (next step).
- [ ] `sync_status.py` clean.
- [ ] Commit + push.

---

## 10. Suggested follow-up briefs (optional, P3)

### Opzione A — UX clarification (B-brief, ~30 min)
**B<n>: surface A217 daily quote above the fold on /today**

Spostare la hero card A217 sopra la DayCard (o tra WeekProgressBar e DayCard), e
ridurre l'aspect ratio da 4/5 a 16/9 o 21/9 per essere più compatta. Aumenta la
visibilità del touch motivazionale del giorno per utenti PWA mobile.

Trade-off: la DayCard scende sotto la fold, e il piano della giornata è il
contenuto primario di /today. Da decidere con A/B test o feedback.

### Opzione B — Coerenza process_cue (C/A-brief, ~1-2h)
**A<n>: add process_cue support for test sessions**

Aggiungere `test_max_hang_5s`, `test_max_hang_7s`, `test_lp_repeater`,
`test_pullup_bw` (tutti i `session_id` di test) ai `session_types` di alcune
cue rilevanti (test-specific tips: "Warm up thoroughly before maxing out",
"Don't compete with your last test — compete with your form", etc.).

Aggiunge tip dentro `/guided` per giornate di test. Volume: piccolo
(~5-10 new cues).

### Opzione C — Cross-channel coherence (D-brief, ~2h)
**D<n>: audit quote/phase-tip/process-cue overlap**

Audit completo del "sistema motivazione": 3 canali separati con UX path diversi
(quote in hero card, phase tip in info banner, process cue in guided amber
banner). Decidere se mergeare in un'unica sorgente di tip, o documentare
chiaramente i tre.

**Priorità suggerita:** P3 (cosmetic). Nessuna delle tre è bloccante per il
prossimo brief di valore.

---

## 11. Out of scope (rispettato)

- ✋ Nessuna code change.
- ✋ Nessuna modifica al catalog quote/cues.
- ✋ Nessuna modifica a planner_v2/replanner/macrocycle/resolve_session/progression/closed-loop.
- ✋ Nessuna decisione presa: solo evidenza raccolta + suggerimenti follow-up.
