# D254 — Full repo review (frontend + backend)

> **Provenance:** external review of 2026-07-20, originally an untracked `REVIEW.md` at repo root; filed here by the hygiene pass of the same day so its findings are tracked (CLAUDE.md: audit findings ARE roadmap items).
> **Status:** 81 findings (F1-F62 frontend, B1-B19 backend).
> - **Closed:** B1, B2, B11, B13 by [[B285]] · B3, B6, B7, B9, B18 by [[B287]].
> - **Scheduled:** 63 findings in **A245 — REVIEW-REMEDIATION-V1** (phases A-G), plus F28 → Phase C and F13/F14/F15/F27 → Phase F added at triage.
> - **Deferred:** F55-F58 (component-decomposition refactor batch) — out of scope for A245 v1, see roadmap.
> **File:line references were accurate on 2026-07-20 and drift with every commit — always re-verify before editing.**

---

# REVIEW — climb-agent

**Data:** 2026-07-20 · **Scope:** review completa del repo, approfondimento frontend Next.js/PWA, passata di severità su backend FastAPI / engine / security.
**Metodo:** audit parallelo su 9 aree, build Next.js reale (40 route: 33 statiche, 7 dinamiche), verifica manuale riga-per-riga di tutti i finding Critici/Alti. Solo lettura: nessuna riga di codice modificata.

**Criteri severità** — **Critico**: rompe funzionalità core o rischio sicurezza/dati · **Alto**: degrada l'esperienza reale in palestra/falesia · **Medio**: qualità/manutenzione · **Basso**: miglioramento.

**Contesto di pesatura:** utenti in palestra/falesia, spesso offline o 3G, PWA installata su iPhone, uso con mani sudate/magnesio.

---

## Frontend (approfondita)

### Critico

**F1 — A freddo e offline la PWA non si apre: spinner infinito o schermata bianca**
`frontend/public/sw.template.js:7` · `frontend/src/app/page.tsx:13-44` · `frontend/src/lib/query-client.ts:17-28`
Tre strati concorrono: (1) il precache contiene solo `/` e `/manifest.json`; (2) la root `/` è un client component che attende Clerk e chiama `getState()` verso Railway — irraggiungibile offline — e al fallimento fa `router.replace("/onboarding/welcome")` (navigazione che offline fallisce a sua volta, vedi F2) per poi renderizzare `null`; (3) TanStack Query è solo in-memory (nessun persister, `gcTime` 5 min) e il SW scarta tutte le richieste `/api` (`sw.template.js:44`) — quando iOS uccide la PWA, piano/settimana/sessioni sono persi.
**Impatto:** lo scenario d'uso primario — "apro la PWA in falesia senza campo" — non funziona. Non è possibile nemmeno *vedere* l'allenamento del giorno.
**Fix:** precache dell'app shell reale (`/today`, `/week`) o fallback di navigazione a pagina offline; la root non deve dipendere dalla rete per decidere dove andare (persistere l'ultima destinazione nota in localStorage); persistere le query chiave (`state`, `week/0`) con `@tanstack/query-persist-client` su localStorage/IndexedDB.

**F2 — Le navigazioni client-side offline falliscono in silenzio; l'unico flusso offline-ready (guided) non è avviabile offline**
`frontend/public/sw.template.js:71` · `frontend/src/components/training/session-card.tsx:369`
Le navigazioni App Router sono fetch RSC, non document navigation: il SW le cacha solo se `request.mode === "navigate"`, quindi non entrano mai in cache. Offline la fetch RSC fallisce e Next gestisce il rejection tornando allo stato corrente *senza alcun feedback*. Le route dinamiche (`/session/[id]`, `/guided/...`, `/outdoor/[date]`) sono raggiunte solo via `router.push`, mai prefetchate: irraggiungibili offline. `handleStartGuided` scrive correttamente lo stato in localStorage prima di navigare, ma il `router.push` fallisce muto.
**Impatto:** in palestra senza campo l'utente tocca la bottom nav o "Start session" e non succede nulla, senza messaggio. Il meccanismo di coda feedback costruito per l'offline resta inutilizzato proprio quando servirebbe.
**Fix:** cachare anche le risposte RSC (network-first con fallback per URL) o intercettare il fallimento con UI "sei offline"; per il guided flow, se `navigator.onLine === false` forzare `location.href = url` (document load servibile dalla cache) o al minimo un toast esplicito.

**F3 — Falesia: cancellazione di una via a un tap, target ~22px, senza conferma**
`frontend/src/components/outdoor/live-route-logger.tsx:399-401` · `live-route-logger.tsx:214-218`
I bottoni riga `+✓` / `+✗` / `✕` sono `px-2 py-0.5 text-xs` (~22px) con `gap-1.5` (6px). `✕` chiama `remove()`, che elimina la via **con tutti i tentativi loggati, senza conferma né undo** — ed è immediatamente a destra di `+✗`, il bottone premuto più spesso. Anche i toggle OS/FL sono ~20px (`:387-396`).
**Impatto:** con mani magnesiate, un mis-tap di 6px cancella irreversibilmente una via e i suoi try — dati che alimentano il closed-loop. È il flusso usato in falesia, spesso al sole.
**Fix:** delete separato dagli action button con conferma o undo toast; `+✓`/`+✗`/OS/FL a `py-2.5` minimo (≥44px di hit-area).

### Alto

**F4 — Il feedback post-sessione (carburante del closed-loop) è perso silenziosamente su rete scarsa**
`frontend/src/app/(main)/today/page.tsx:923-924` · `frontend/src/app/(main)/week/page.tsx:489-490`
`handleFeedbackSubmit` ingoia qualsiasi errore con `catch { /* Non-critical */ }`. La guided session ha invece la coda localStorage con retry (`(guided)/guided/[date]/[sessionId]/page.tsx:460-464` + retry al mount di `/today`, `today/page.tsx:244-298`) — la stessa protezione non esiste per il FeedbackDialog.
**Impatto:** l'utente compila il feedback in palestra, questo sparisce, e la progressione resta disallineata senza alcun segnale.
**Fix:** estendere il pattern `feedback_pending` (già collaudato) al FeedbackDialog; al minimo, errore visibile con retry.

**F5 — Nessuna coda per le mutation offline: free session, outdoor e custom feedback persi**
`frontend/src/components/free-session/climb-logger.tsx:242-246` · `frontend/src/app/(main)/outdoor/[date]/page.tsx:218-238` · `frontend/src/app/(guided)/session-builder/[id]/play/page.tsx:357-375` · `frontend/src/lib/query-client.ts:19-26`
Il SW scarta le non-GET (`sw.template.js:44`), non esiste outbox né Background Sync, e le mutation RQ hanno retry 0 di default. `logFreeClimb` fallito → solo `console.error`, la climb non entra in UI né in draft. Outdoor: in falesia offline la giornata non si può né iniziare né chiudere.
**Impatto:** arrampicate loggate offline spariscono senza che l'utente lo sappia; la feature outdoor è inutilizzabile esattamente nel suo contesto d'uso.
**Fix:** generalizzare il pattern `feedback_pending` in un outbox unico (localStorage/IndexedDB) con retry al mount di `/today`; `mutations: { retry: 1 }` come minimo.

**F6 — Race condition lost-update su Done/Skip: due tap rapidi perdono un mark-done**
`frontend/src/components/training/session-card.tsx:1161-1188` · `frontend/src/app/(main)/today/page.tsx:453-500` · `backend/api/routers/replanner.py:87`
I bottoni Done/Skip non hanno guard `disabled`/isPending; gli handler leggono `weekPlan` dalla closure e inviano l'intero piano al backend, che lo persiste con sovrascrittura totale. Due tap rapidi su due sessioni dello stesso giorno partono dallo stesso snapshot: il secondo POST sovrascrive il primo e il mark-done va perso (l'UI mostra done fino al refetch).
**Impatto:** in palestra l'utente segna due sessioni e ne ritrova una non segnata; lo storico si disallinea.
**Fix:** disabilitare i bottoni durante la mutation e serializzare le mutation sulla stessa settimana (o passare agli hook `useReplannerEvents` esistenti).

**F7 — Nessun timeout né AbortSignal su nessuna fetch: spinner infinito su connessione stallata**
`frontend/src/lib/api.ts:44-54`
`request()` non imposta timeout né propaga un `AbortSignal`; le queryFn non consumano il `signal` di React Query. Su rete scarsa una connessione TCP stallata resta appesa per minuti: il `retry: 1` globale non scatta mai e l'unica via d'uscita è ricaricare la PWA.
**Impatto:** la percezione è "app impallata" proprio nel contesto d'uso primario; l'utente chiude e riapre, peggiorando tutto.
**Fix:** `AbortSignal.timeout(15_000)` in `request()` con errore "rete lenta" + retry manuale.

**F8 — `useSubscription` tratta "rete giù" come "non abbonato": redirect a /subscribe in palestra**
`frontend/src/lib/hooks/use-subscription.ts:57-65,69` · `frontend/src/app/(main)/today/page.tsx:454,1177` · `frontend/src/app/(guided)/guided/[date]/[sessionId]/page.tsx:70-74`
Qualsiasi errore di fetch (incluso semplice offline) produce `setResult(_DENY)` → `canInteract: false`, e il poll ogni 5 min può ribaltare lo stato in qualsiasi momento. `today` redirige a `/subscribe` su mark-done/quick-add; la guided page redirige a metà sessione se la rete flappa (offline puro il redirect fallisce per F2, quindi lì la sessione sopravvive *per incidente*).
**Impatto:** un utente pagante senza campo viene rimbalzato alla pagina di abbonamento quando prova a segnare una sessione fatta — il peggior messaggio possibile nel posto peggiore.
**Fix:** su errore di rete mantenere l'ultimo stato noto (fail-closed solo al primo load o su 402/403 autenticato); esentare `/guided/*` dal gate una volta iniziata la sessione.

**F9 — Auth fallita in silenzio → `GET /api/state` risponde 200 con stato vuoto: "Welcome!" a utenti esistenti**
`frontend/src/lib/api.ts:33-42` · `backend/api/deps.py:165-170` · `frontend/src/app/(main)/today/page.tsx:1047-1059`
`_getAuthHeaders` swalla qualsiasi errore di Clerk e invia la richiesta senza `Authorization`; il backend con `user_id=None` serve l'`EMPTY_TEMPLATE` con HTTP 200. Il client non distingue "utente nuovo" da "auth fallita": token Clerk scaduto + rete assente → l'utente esistente vede "Welcome to climb-agent! Complete your onboarding", e ogni mutation esplode con 500 generico.
**Impatto:** lo scalatore offline vede la schermata da nuovo utente invece dei propri dati; panico e supporto.
**Fix:** client: se `getToken()` fallisce, sollevare un errore auth distinto (non inviare la richiesta); backend: in produzione gli endpoint autenticati devono rispondere 401 senza credenziali, non il template.

**F10 — Nessun error boundary in tutta l'app**
`frontend/src/app/` (0 file `error.tsx`/`global-error.tsx`; 0 `ErrorBoundary` in `src/`)
Un TypeError di render su payload inatteso butta giù l'intera app con la schermata generica di Next.js, irrecuperabile senza reload — e su PWA offline il reload stesso può fallire (F1).
**Impatto:** un solo campo inatteso dal backend trasforma l'app in una schermata morta in palestra.
**Fix:** `global-error.tsx` nella root + `error.tsx` almeno in `(main)` e `(guided)` con bottone retry.

**F11 — Touch target sotto i 44px nei controlli usati sotto sforzo**
Verificati (tutti in flussi usati con mani sudate/magnesio):
- Chip feedback "How did it feel?" ~24px — `frontend/src/components/guided/guided-exercise-step.tsx:880` (duplicato a `:585`); stesso pattern in `frontend/src/components/training/day-card.tsx:251-264,310-324`
- Done/Skip del flusso guidato `size="sm"` = 32px — `guided-exercise-step.tsx:1032-1048`
- Chiusura di tutti i Dialog = icona 16px senza padding — `frontend/src/components/ui/dialog.tsx:71-77`
- Pallini navigazione esercizi = 12px — `frontend/src/components/guided/guided-progress-bar.tsx:26`
- Radio difficoltà del feedback post-sessione = 16px con label `text-[10px]` — `frontend/src/components/ui/radio-group.tsx:30`, `frontend/src/components/training/feedback-dialog.tsx:109-119`

**Impatto:** dopo una serie di hangboard, colpire il chip giusto su 24px è difficile; feedback errato degrada direttamente la progressione.
**Fix:** `py-2.5`/`min-h-[44px]` sui chip; `size="default"`+ su Done; hit-area `p-2.5 -m-2.5` su pallini e close; radio `size-5/6`.

**F12 — `safe-area-inset-top` mai gestita: header sticky sotto la status bar iOS**
`frontend/src/app/layout.tsx:21-25,49` · `frontend/src/components/layout/top-bar.tsx:11`
`viewportFit: "cover"` + `statusBarStyle: "black-translucent"` + `display: standalone`, ma **zero** occorrenze di `env(safe-area-inset-top)` in tutto il frontend (solo bottom). Gli header `sticky top-0` (top-bar, guided page, play page) renderizzano il bottone Back sotto orologio/batteria.
**Impatto:** nella PWA installata (il caso d'uso dichiarato) il Back è parzialmente coperto su ogni schermata.
**Fix:** `pt-[env(safe-area-inset-top)]` sul contenitore root o sugli header sticky.

**F13 — Immagini esercizi da 1,7 MB servite via `<img>` nativo nel circuit timer**
`frontend/src/components/circuit/CircuitTimer.tsx:578-582,610-614` · `frontend/public/exercises/core/33_hanging_wipers.png` (1,78 MB), `32_front_lever_tuck.png` (1,69 MB)
`<img>` senza `next/image`: niente resize/compressione/lazy-load; asset in `public/` non content-hashed.
**Impatto:** in palestra con 3G una singola immagine richiede 10+ secondi e blocca la card esercizio a metà circuito.
**Fix:** ricomprimere i PNG (target <150 KB, webp) e usare `next/image` con `sizes`; valutare il preload dell'esercizio successivo durante il countdown.

**F14 — Today page: spinner → contenuto completo = CLS massiccio sulla route più usata**
`frontend/src/app/(main)/today/page.tsx:1026-1030`
Solo uno spinner centrato mentre caricano state+week; tutto il contenuto (resume banner, WeekProgressBar, WeatherCard, DayCard, hero quote `aspect-[4/5]`) appare in blocco unico dopo il fetch.
**Impatto:** con rete scarsa la pagina salta da vuota a piena altezza: CLS vicino al massimo possibile, proprio sulla schermata di apertura.
**Fix:** skeleton statico che riserva l'altezza delle sezioni principali (DayCard + progress bar).

**F15 — Fetch N+1 manuale fuori da React Query, riattivato da OGNI mutation**
`frontend/src/app/(main)/today/page.tsx:315-344,355-370` · `frontend/src/app/(main)/week/page.tsx:129-175`
Ogni cambio di `weekPlan` innesca 1 `getOutdoorSessions` + 7 `getFreeSessionHistory` (una per giorno) via `useEffect` con deps `[weekPlan]`. Con `structuralSharing: false`, ogni `setQueryData` produce una nuova reference → 8 richieste extra per ogni azione utente, senza dedup né cache. Gli hook RQ equivalenti esistono e non sono usati (`useFreeSessionHistory`: zero call site).
**Impatto:** traffico inutile su rete scarsa; navigando today→week→today si rifanno tutte.
**Fix:** usare gli hook RQ esistenti (cache + dedup) o un endpoint batch settimanale.

**F16 — Onboarding: chiudi il tab/app e perdi tutto il wizard (nessun resume cross-sessione)**
`frontend/src/components/onboarding/onboarding-context.tsx:23-38,59` · `frontend/src/app/onboarding/recover/page.tsx:8-10`
La bozza vive solo in `sessionStorage` (muore alla chiusura del tab — la norma su mobile); nulla è persistito server-side fino al submit; la pagina "recover" è solo un redirect a sign-in; il draft è caricato solo se `profile.name` è già valorizzato.
**Impatto:** chi molla a metà (step 8-10 di 14, ~10 min di input) ricomincia da zero — punto di abbandono ad altissima probabilità.
**Fix:** draft in `localStorage` + ripresa dallo step più profondo raggiunto (salvare lo step corrente), o bozze incrementali server-side.

**F17 — Submit onboarding: errori grezzi/JSON all'utente + timeout 15s contro cold start Railway**
`frontend/src/app/onboarding/review/page.tsx:134-135,150,353-356` · `frontend/src/lib/api.ts:82`
Al momento di massima intenzione ("Start training now") l'utente vede `API 422: {"detail":"Macrocycle generation failed: ..."}`, `API 429: ...`, o `TypeError: Load failed`. L'abort client a 15s può scattare mentre Railway è in cold start (e il server salva comunque); il retry brucia il rate limit da 3/min.
**Impatto:** il momento di conversione più importante mostra JSON grezzi o errori criptici; abbandono a un tap dal traguardo.
**Fix:** mappare gli errori a messaggi umani, distinguere offline via `navigator.onLine`, timeout adattivo, retry esplicito senza ricaricare.

**F18 — Onboarding: validazioni bloccanti senza spiegazione (bottone Next grigio e non si sa perché)**
`frontend/src/app/onboarding/weaknesses/page.tsx:160-161,186` · `frontend/src/app/onboarding/grades/page.tsx:110-112` · `frontend/src/app/onboarding/availability/page.tsx:348-355`
Weaknesses richiede **sia** primary **che** secondary (la card secondary appare solo dopo la primary); grades richiede redpoint **e** onsight per disciplina senza opzione "non lo so"; availability disabilita Next senza testo che lo spieghi.
**Impatto:** sono i classici punti in cui l'utente fissa un bottone grigio e abbandona.
**Fix:** non disabilitare — mostrare inline cosa manca al tap su Next; "non lo so / salta" su secondary weakness e gradi onsight.

**F19 — Duplicazione massiva today ↔ week: ~450 righe di handler copiati quasi verbatim**
`frontend/src/app/(main)/today/page.tsx` ↔ `frontend/src/app/(main)/week/page.tsx` — coppie verificate riga per riga: `handleReplanApply` (today:612-638 ↔ week:211-237), `handleQuickAddApply`, `handleQuickAddCustomApply`, `handleMoveApply`, i 4 handler other-activity, `handleMarkDone`/`handleMarkSkipped`/`handleUndo`/`handleRemoveSession`, `handleChangeGymApply`, gli 8 handler outdoor, `handleFeedbackSubmit`, la IIFE `feedbackExercises`, i due effect di fetch, `todayISO()`, e la composizione JSX dei 6 dialog.
**Impatto:** ogni fix va applicato due volte (la storia lo conferma: B186, D134, B276); divergenza silenziosa già presente (today:471 cerca in `dayPlan`, week:410-412 in `weekPlan.weeks?.[0]?.days` — stessa intenzione, implementazioni diverse).
**Fix:** estrarre `useWeekPlanMutations()` condiviso (o `lib/week-plan-actions.ts`) usato da entrambe le page. È il refactor a più alto valore del frontend.

**F20 — `SessionCard` monolite: 1388 righe con 6 responsabilità mescolate**
`frontend/src/components/training/session-card.tsx`
Factory dati guidati pura (101-311), orchestrazione avvio + scrittura localStorage (316-371), dialog "Add Exercise" completo con fetch catalogo (377-661), chiamate API nel componente di presentazione (725, 794, 801), UI card, menu/dialog (1219-1327). L'algoritmo di raggruppamento blocchi/esercizi esiste due volte nello stesso file (252-272 e 1047-1071).
**Impatto:** la logica che decide cosa l'utente si trova in palestra è sepolta in un file UI non testabile isolatamente, con doppione interno a rischio divergenza.
**Fix:** estrarre `lib/guided-state-builder.ts` (unit-testabile con vitest), `AddExerciseDialog` in file proprio, unificare il grouping in una funzione condivisa.

### Medio

**F21 — SW network-first senza timeout: su rete flappante (il caso tipico in falesia) ogni navigazione attende il timeout TCP**
`frontend/public/sw.template.js:68-78` — il `.catch` scatta solo a fetch fallita, dopo decine di secondi. **Fix:** network-first-with-timeout (`Promise.race` a 3-4s, poi cache) o stale-while-revalidate per le pagine visitate.

**F22 — `skipWaiting()` incondizionato: il banner "Aggiorna" è dead code e ogni deploy forza un reload automatico**
`frontend/public/sw.template.js:14` · `frontend/src/components/sw-update-banner.tsx:28,50,53-55`
Il nuovo SW non transita mai da `waiting` (il banner non può apparire); `clients.claim()` → `controllerchange` → reload incondizionato. Se scatta durante una sessione guidata, su iOS PWA la pagina si ricarica a metà allenamento (stato salvo in localStorage, timer/posizione resettati visivamente). L'obiettivo B196 è raggiunto, ma con effetti collaterali non intenzionali. **Fix:** rimuovere `skipWaiting()` dall'install e lasciare il flusso banner → `SKIP_WAITING` (già implementato), o sopprimere il reload quando una sessione è in corso.

**F23 — Il tipo `ResolvedSession` è completamente falso; l'unico consumer crasherebbe (dead route)**
`frontend/src/lib/types.ts:182-198` · `frontend/src/app/(main)/session/[id]/page.tsx:92` · shape reale in `backend/engine/resolve_session.py:1858-1880`
Il tipo dichiara `blocks: [{block_name, exercises}]`; il payload reale ha `resolved_session.modules/blocks/exercise_instances` con chiavi `block_uid/selected_exercises`. `resolved.blocks.map(...)` → TypeError garantito; non esplode solo perché nessun link punta a `/session/[id]`. **Fix:** riscrivere il tipo sulla shape reale (o eliminare tipo + dead page).

**F24 — La pipeline dati più critica (sessione risolta) gira su cast non verificati**
220 `as X` in 63 file, 13 `as unknown as`; picco: `session-card.tsx` 47 cast (`resolved` è `Record<string, unknown> | null` — `types.ts:97`). **Impatto:** un rename di campo backend compila verde e renderizza `undefined` silenziosi nella schermata di allenamento. **Fix:** tipare il payload resolved (una sola interfaccia condivisa con F23) e rimuovere i cast nel percorso guided/today.

**F25 — Zero code splitting manuale: i dialog pesanti finiscono nel first-load di /today**
0 occorrenze di `next/dynamic`/`lazy()` in `src/`. `today/page.tsx:19-30` importa staticamente QuickAddDialog (776 righe), OutdoorLogForm (383), weekly-checkin, replan/move/gym dialogs — tutti on-demand per definizione. **Fix:** `next/dynamic` per i dialog aperti da azione utente.

**F26 — Zero `React.memo` + timer che ri-renderizzano ~1000 righe a 1 Hz**
`frontend/src/components/guided/exercise-timer.tsx:219-317` (tick 200ms → re-render dell'intero subtree ogni secondo per tutta la sessione), `frontend/src/app/(main)/tabata/page.tsx:584`. **Impatto:** batteria e INP su telefoni di fascia bassa, per minuti interi. **Fix:** estrarre il display countdown in un componente piccolo memoizzato.

**F27 — Clerk nel root layout: ~227 KB di chunk auth su ogni route, incluse quelle pubbliche**
`frontend/src/app/layout.tsx:58` — chunk verificati in `.next/static/chunks/` (86+59+50+31 KB). **Fix:** `ClerkProvider` solo nel gruppo `(main)`/route protette.

**F28 — `start-week`: schermata bianca se `getState` fallisce (offline subito dopo il submit)**
`frontend/src/app/onboarding/start-week/page.tsx:64-73,90` — promise senza `.catch`; `ready` resta false → `return null`. **Fix:** catch con fallback all'opzione default o errore con retry.

**F29 — Locations: il copy dice "almeno un'area climbing richiesta", la validazione dice il contrario**
`frontend/src/app/onboarding/locations/page.tsx:282-284,368` · `frontend/src/app/onboarding/review/page.tsx:347` — con zero palestre si passa lo step e l'avviso in review non compare nemmeno. **Impatto:** piano generato senza sessioni di arrampicata, scoperto a posteriori. **Fix:** allineare validazione e copy.

**F30 — Availability: segnare solo slot "Other sport" sblocca Next con zero giorni di arrampicata**
`frontend/src/app/onboarding/availability/page.tsx:349-351` — il gate accetta `preferred_location === "other_sport"` mentre il contatore giorni lo esclude (`:99-104`); `target_training_days_per_week` resta al default 4. **Fix:** il gate deve richiedere almeno uno slot di arrampicata.

**F31 — CircuitTimer sotto la BottomNav: un tap perso abbandona il circuito**
`frontend/src/components/circuit/CircuitTimer.tsx:452` (`fixed inset-0 z-50`) vs `frontend/src/components/layout/bottom-nav.tsx:92` (stesso z-50, renderizzata dopo → vince lo stacking). `MobilityFlowTimer.tsx:418` fa già giusto con `z-[60]`. **Fix:** `z-[60]` sul CircuitTimer.

**F32 — Input kg/reps senza `inputMode` in tutti i flussi di logging**
40+ `type="number"` senza `inputMode` (`guided-exercise-step.tsx`, `feedback-dialog.tsx:131-140`, `OutdoorLogForm.tsx:244-250`, `session-card.tsx:601-640`, `day-card.tsx:269-276,328-336`); solo 3 punti lo usano. **Impatto:** iOS apre la tastiera piccola "numeri e punteggiatura" invece del tastierino grande. **Fix:** `inputMode="decimal"` (kg) / `inputMode="numeric"` (reps/durata).

**F33 — `maximumScale: 1` blocca il pinch-zoom**
`frontend/src/app/layout.tsx:48` — combinato con 151 occorrenze di `text-[10px]`/`text-[11px]` in 41 file, in falesia al sole l'utente non può ingrandire (WCAG 1.4.4). **Fix:** rimuovere `maximumScale` (o alzarlo); label critiche a ≥12px.

**F34 — Aliasing della cache key settimanale: `week(0)` e `week(N)` sono due entry divergenti**
`frontend/src/lib/hooks/queries/use-week-plan.ts:28` · `frontend/src/app/(main)/week/page.tsx:194-198` — `updateWeekCache` ne aggiorna solo una; viste divergenti fino a 60s. **Fix:** normalizzare la chiave sul `week_num` server o invalidare entrambe.

**F35 — Due sistemi di mutation paralleli e divergenti**
Gli hook centralizzati (`lib/hooks/mutations/*`) non sono usati da nessuna page (unico import: session-builder); today/week chiamano le funzioni raw e aggiornano la cache a mano. Divergenza concreta: `useReplannerEvents` invalida `week(n+1)`, i path diretti no. **Fix:** migrare le page agli hook esistenti.

**F36 — Cache `resolveSession` 5 min: carichi pre-progressione dopo il feedback**
`frontend/src/app/(main)/session/[id]/page.tsx:42-47` — il commento dice "deterministic per session_id" ma la risoluzione dipende dai working_loads aggiornati dalla progressione. **Fix:** invalidare `["session","resolve"]` nelle mutation di feedback.

**F37 — Errore di rete scambiato per "nessun log outdoor"**
`frontend/src/app/(main)/today/page.tsx:816-828` · `week/page.tsx:578-590` — qualsiasi errore di `getOutdoorLogByDate` apre il form di nuovo log anche se il log esiste; `getOutdoorSpots().catch(() => ({spots: []}))` ingoia gli errori. **Fix:** distinguere 404 da errori di rete.

**F38 — Friction strutturale onboarding: 14 step prima del primo piano, install PWA allo step 2**
`frontend/src/app/onboarding/install/page.tsx:108-177` — la richiesta di aggiunta alla home è la prima azione post-registrazione, prima di qualsiasi valore percepito; skip solo su 4 step. **Fix:** spostare l'install a fine flusso (dopo start-week o in /today); valutare fusione experience+discipline e weaknesses+goals.

**F39 — OutdoorLogForm: badge tentativi ~24px e il secondo tap su "Fell" cancella il dato**
`frontend/src/components/training/OutdoorLogForm.tsx:102-120,310-329` — `cycleAttempt` cicla Sent→Fell→rimozione: un doppio tap accidentale elimina il tentativo. **Fix:** `py-2`; separare la rimozione (✕ dedicato con conferma).

**F40 — Elementi interattivi `div onClick` senza semantica + bottoni icon-only senza nome accessibile**
`day-card.tsx:439-444`, `CircuitTimer.tsx:476-479,556-558`, `tabata/page.tsx:905-908,986-988` (no role/tabIndex/keyboard); `top-bar.tsx:15-19` (Back solo-SVG senza aria-label, e `<a href>` nativo → full reload), `session-card.tsx:674-679` (Trash2 28px senza aria-label), `tabata/page.tsx:951-966`. **Fix:** replicare il pattern corretto già usato in `exercise-timer.tsx:596-604`; aria-label ovunque.

**F41 — Slider: track 6px, thumb 16px**
`frontend/src/components/ui/slider.tsx:42,56` — usato in onboarding e settings. **Fix:** thumb `size-5/6` o padding verticale sul Root.

**F42 — `pb-20` insufficiente: contenuto sotto la BottomNav su iPhone con notch**
`frontend/src/app/(main)/layout.tsx:10` — riserva 80px; la nav è ~56px + `env(safe-area-inset-bottom)` ~34px ≈ 90px. **Fix:** `pb-[calc(3.5rem+env(safe-area-inset-bottom))]` o altezza nav via variabile CSS condivisa.

### Basso

**PWA / manifest**
- F43 — Nessuna icona `purpose: "maskable"` (icona Android ritagliata brutta) e `theme_color: "#e94560"` incoerente col viewport `#0f121a` — `frontend/public/manifest.json:8-20` vs `frontend/src/app/layout.tsx:45`.
- F44 — Polling subscription ogni 5 min spreca richieste destinate a fallire offline — `use-subscription.ts:69`.

**Onboarding**
- F45 — Step indicator: il primo step visibile mostra "2 / 14" (welcome nascosto ma contato) — `step-indicator.tsx:6-14`.
- F46 — Tests: "Skip" cancella silenziosamente i dati già inseriti (`update("tests", {})`) — `tests/page.tsx:379-387`.
- F47 — Edit dalla review: si ripercorre a catena tutto il wizard (fino a 10 tap di Next) — `review/page.tsx:66-72`.
- F48 — Welcome: fetch server-side senza timeout né `loading.tsx` — `welcome/page.tsx:17-24`.
- F49 — Context onboarding con `value` non memoizzato: ogni keystroke re-renderizza tutti i consumer — `onboarding-context.tsx:147`.

**Data / type / resilienza**
- F50 — Parsing date `YYYY-MM-DD` incoerente: alcuni punti lo trattano come UTC (data di inizio un giorno indietro per utenti a ovest di UTC) — `frontend/src/lib/phase-progress.ts:16,27-29`, `plan/page.tsx:192`, `phase-celebration.tsx:57`. **Fix:** un helper `parseISODateLocal()`.
- F51 — 401 → full redirect `window.location.href = "/sign-in"` (perde lo stato in memoria; offline la pagina sign-in non si carica) — `frontend/src/lib/api.ts:61-63`.
- F52 — `test_reminder` emesso dal backend (`backend/api/routers/week.py:510-518`) ma assente dal tipo TS e mai letto: payload morto o feature mancante.

**Architettura / duplicazioni**
- F53 — `beep()` con `createOscillator` copiata in 6 file (guided, circuit, mobility, session-play ×2, tabata) con volumi/durate divergenti; fix iOS del timer principale non propagati — es. `exercise-timer.tsx:47`, `CircuitTimer.tsx:53`. **Fix:** `lib/beep.ts` + hook `useWallClockCountdown`.
- F54 — Storage key della guided session ricostruita inline in 4 punti — `(guided)/guided/[date]/[sessionId]/page.tsx:22-28`, `guided-session-utils.ts:5-9`, `today/page.tsx:247`, `session-card.tsx:352`. Un disallineamento rompe silenziosamente resume e retry feedback offline.
- F55 — `QuickAddDialog` (776 righe): tre wizard in un dialog con 18 `useState` e tre IIFE di filtro equipment quasi identiche.
- F56 — Serializzazione del feedback (contratto col motore) inline nella guided page: ~140 righe di business logic in `handleSubmit` — `(guided)/guided/[date]/[sessionId]/page.tsx:311-472`. **Fix:** `buildFeedbackPayload()` in `lib/`, unit-testabile.
- F57 — Prop drilling a 3 livelli: page → DayCard (27 prop, 19 callback) → SessionCard → ExerciseCard; i wrapper closure ricreati a ogni render vanificano memoizzazioni — `day-card.tsx:20-61,606-635`.
- F58 — `GuidedExerciseStep` (1053 righe): 8 modalità input con flag mutuamente esclusivi per sottrazione (162-181) — aggiungere una modalità richiede di modificare tutte le altre; form R/L copiati 4 volte.
- F59 — Utility duplicate: `formatSessionName` in 8 punti, `formatDateShort` ≡ `formatDateLabel`, `FEEDBACK_OPTIONS` copiato verbatim, `exercisePrescriptionSummary` doppio. **Fix:** un `lib/format.ts`.
- F60 — Ring di selezione dei chip feedback mai generato da Tailwind (interpolazione dinamica `ring-${...}` senza safelist) — `guided-exercise-step.tsx:882`.
- F61 — Exit minuscolo (~16px, contrasto basso) nei timer full-screen — `CircuitTimer.tsx:461-470`, `MobilityFlowTimer.tsx:427-436`.
- F62 — Testo informativo 10px nei timer ("Tap when done") — `exercise-timer.tsx:832,842`.

### Punti di forza (frontend)

- **Il guided flow è progettato davvero offline-first**: stato persistito a ogni step, feedback accodato con retry al mount di `/today` e cleanup entry >24h, resume con banner, timer wall-clock con resync su `visibilitychange` (iOS background). È il pattern giusto — va solo generalizzato.
- **Cache invalidation del SW per build ben risolta**: template + build id iniettato con catena di fallback + purge in activate chiudono davvero il problema B196.
- **`providers.tsx` minimale e corretto**, defaults RQ sensati (`refetchOnWindowFocus: false`, catalog a `staleTime: Infinity`), `ApiError` tipizzato con gestione 402 dedicata, utility gradi con test di round-trip.
- **`exercise-timer.tsx` è il modello della casa per mobile UX**: frecce 48-56px, aria-label ovunque, `role="button"`+keyboard, enlarged mode full-screen.

---

## Full-stack (severità)

### Critico

**B1 — Fallback `X-User-ID` attivo in produzione: IDOR totale su tutti gli endpoint**
`backend/api/deps.py:109-117`
Il fallback `X-User-ID` (dichiarato "dev/test" nel commento) è accettato **senza alcun controllo che Clerk sia configurato né sull'ambiente**: basta omettere `Authorization` e inviare `X-User-ID: <uuid-v4>` per essere autenticati come quell'utente. Nessun middleware filtra l'header (verificato in `main.py`). Con l'UUID di una vittima: export completo dello stato (`user.py:93-103`), sovrascrittura totale via import/patch (`user.py:106-119`, `state.py:61`), cancellazione account (`state.py:153`). Gli UUID sono recuperabili dai log Railway (`auth.py:95` logga user_id+clerk_id alla creazione). Effetto collaterale: `GET /api/state` con UUID casuali **crea righe utente nuove nel DB** (bootstrap in `deps.py:165-169`) → DB-fill illimitato senza auth.
**Impatto:** takeover completo di qualunque account di cui si conosca l'UUID; perdita/cancellazione dati di utenti paganti. In produzione LIVE con Stripe attivo.
**Fix:** in `get_user_id`, se `is_clerk_configured()` (o `STORAGE_BACKEND=supabase`), rifiutare il fallback con 401; abilitarlo solo dietro flag esplicito (`ALLOW_LEGACY_HEADER=1`) per dev/test.

### Alto

**B2 — Subscription guard fail-open per richieste anonime: LLM a pagamento chiamato senza auth**
`backend/engine/subscription_guard.py:157-158` · `backend/api/routers/coach.py:40` · `backend/coach/service.py:137-139` · `backend/api/routers/weather.py:440-455`
`if not _stripe_enabled() or not _supabase_enabled() or not user_id: return _ALLOW_ALL` — in produzione (Stripe+Supabase attivi) una richiesta senza header supera `require_active_subscription`. Su `/api/coach/chat` la chiamata Anthropic avviene **prima** della persistenza, che poi fallisce con 500: fino a 30 chiamate LLM/giorno pagate dal founder per traffico anonimo (cap condiviso sul bucket `__legacy__`). `/api/weather` non prende nemmeno `user_id`.
**Impatto:** costi API ricorrenti da traffico anonimo; bypass del paywall sugli endpoint gated. In combinazione con B1, l'intera postura auth è di fatto aperta.
**Fix:** `user_id is None` → `_DENY_ALL` quando Stripe+Supabase sono attivi (o 401 nei gated endpoint).

**B3 — `set_availability` rigenera l'intera settimana cancellando le sessioni completate; `/events` senza guard anti-past-week; pool lead per utenti boulder**
`backend/engine/replanner_v1.py:1195-1209` · `backend/api/routers/replanner.py:322-361` (contrasto: `/override` ha il guard a `replanner.py:199`)
Il ramo `set_availability` chiama `generate_phase_week()` e sostituisce wholesale `updated["weeks"]` senza `regenerate_preserving_completed` né `preserve_before`: sessioni `done`/`skipped` perse — violazione diretta del pillar di immutabilità. Inoltre `_build_session_pool(phase_id)` non riceve `discipline` (default `"lead"`, `macrocycle_v1.py:463`): un utente boulder riceve il pool lead. Amplificatore: `/events` non ha il check `is_past_week` che `/override` ha. Il frontend non invia mai `set_availability` (latente), ma l'endpoint è pubblico e raggiungibile via API.
**Impatto:** perdita di storico allenamenti e piano riscritto con sessioni della disciplina sbagliata.
**Fix:** `regenerate_preserving_completed(old, regenerated, preserve_before=today)`; passare `discipline` al pool (aggiungerla allo snapshot); estendere il guard B257 a `/events` per gli event_type che rigenerano.

### Medio

**B4 — Rate limiting basato su `get_remote_address` rotto dietro il proxy Railway: limiti globali condivisi**
`backend/api/rate_limit.py:8-10` — legge il peer TCP (il load balancer), quindi `PUT /api/state` 30/min, `POST /api/feedback` 30/min e `/api/user/recover` 5/min sono limiti **globali**: utenti legittimi si prendono 429 generati dal traffico altrui, proprio negli orari di punta in palestra. **Fix:** chiave su `X-Forwarded-For` o, meglio, su `user_id` per gli endpoint autenticati.

**B5 — "Today" dipendente dalla timezone del server in tutti i path caldi**
`backend/api/routers/week.py:368`, `deps.py:68`, `plan.py:141,160`, `feedback.py:324`, `resolve_session.py:1920`, `progression_v1.py:772,835` — nessun punto dello user_state memorizza la timezone. Per un utente a ovest di UTC che si allena la sera, una rigenerazione tratta oggi come passato → nessuna sessione assegnata; date di feedback slittate. Il determinismo dichiarato è di fatto server-locale. **Fix:** `profile.timezone` + un unico helper "today utente" in `deps.py`.

**B6 — `persist_week_plan` e `_is_current_macrocycle_monday` ignorano il pause offset: `current_week_plan` mai sincronizzato dopo un resume**
`backend/api/routers/replanner.py:90-99` · `backend/api/routers/feedback.py:63-75` (l'anchor corretto pause-aware è in `deps.py:391-404`) — con `offset_days > 0` i reader che usano `current_week_plan` (feedback step 1, suggest-sessions, adaptive replan) lavorano su un piano stale fino al prossimo GET `/api/week/0`. **Fix:** riusare `week_num_to_phase_context(macrocycle, 0)["start_date"]`.

**B7 — Quick-add senza `_reconcile` e spacing cross-week cieco nel replanner**
`backend/engine/replanner_v1.py:361-480` (unico path di mutazione senza `_reconcile`: niente enforcement del gap 48h finger né hard-cap, solo warning) · `replanner_v1.py:758,778` (`_enforce_*` scansionano solo la settimana corrente: il boundary domenica→lunedì non è mai controllato nel replanner, a differenza del planner che seeda la settimana precedente). **Impatto:** l'utente può creare giorni finger consecutivi (<48h) — invariante a rilevanza infortuni — senza alcun segnale. **Fix:** `_reconcile` anche in `apply_day_add` + seed dei trailing day della settimana precedente.

**B8 — `adaptation/closed_loop.py` è dead code in produzione: il cooldown per-cluster non scatta mai**
Importato solo da `adaptation/__init__.py` e dai test; `cooldowns.per_cluster` è scritto solo lì (`closed_loop.py:113-120`), quindi il lettore `_cooldown_until_date` (`resolve_session.py:914-920`) trova sempre vuoto e i fallback `cluster_cooldown_fallback`/`downshift` non scattano mai. La doc lo descrive ancora come attivo. **Impatto:** una protezione da sovraccarico documentata e testata è di fatto mai eseguita. **Fix:** collegare `update_user_state_adjustments` nel feedback path, o rimuovere modulo + fallback e correggere la doc — decidere esplicitamente.

**B9 — `merge_prev_week_sessions`: il fallback per weekday ri-timbra sessioni completate su date di un'altra settimana**
`backend/engine/replanner_v1.py:573-588` — quando le date non si sovrappongono, il match per weekday riscrive `copied["date"]`: una sessione `done` del vecchio piano ricompare come completata sul lunedì della nuova settimana; `_attach_feedback` può agganciare feedback sbagliati via chiave (date, session_id). **Impatto:** storico allenamenti fabbricato su date mai allenate. **Fix:** nel fallback weekday, merge solo per giorni `>= preserve_before` e solo per sessioni preservabili; mai rewrite della data.

**B10 — `POST /api/macrocycle/generate` non è subscription-gated, a differenza di tutte le altre mutazioni**
`backend/api/routers/macrocycle.py:34-35` — un utente con trial scaduto può rigenerare il macrociclo pur essendo bloccato ovunque altro. **Fix:** aggiungere la dependency o documentare l'asimmetria.

**B11 — `X-Admin-Key` confrontato con `!=` (timing attack in linea di principio)**
`backend/api/routers/admin.py:23` — il fix costa una riga: `secrets.compare_digest(key or "", secret)`. (Positivo: segreto non configurato → 403, fail-closed.)

### Basso

- **B12 — CORS regex ammette preview Vercel di qualunque account** — `backend/api/main.py:103` (`climb-agent(-[a-z0-9-]+)?\.vercel\.app`). Auth Bearer → impatto diretto nullo, ma superficie trust più larga del necessario. **Fix:** vincolare al team slug reale.
- **B13 — Logging di identificatori utente a INFO** — `auth.py:95`, `stripe_webhook.py:190-193`, `subscription_guard.py:57-59`. In combinazione con B1 i log diventano il vettore per recuperare UUID. **Fix:** DEBUG + mascheramento.
- **B14 — Bucket `__legacy__` leggibile da richieste anonime** — `storage_supabase.py:52-54,77-83`. **Fix:** in produzione 401 sulle read con `user_id=None`.
- **B15 — 422 con internals esposti + `total_weeks` senza bounds** — `macrocycle.py:98-99,268-269` propaga il testo delle `ValueError` engine (strutture interne); `MacrocycleRequest.total_weeks` (`models.py:36`) senza `Field(ge=8, le=16)`.
- **B16 — `planner_v1.py` tenuto vivo solo dai test** — zero import in produzione; peso morto e drift documentale. **Fix:** `_archive/` o marcatura legacy esplicita.
- **B17 — `_auto_resolve` swalla tutto → `resolved=None` silenzioso** — `week.py:118-123`, `replanner.py:171-176`: l'utente riceve una session card senza esercizi indistinguibile da "nessun esercizio compatibile". **Fix:** marcare `resolve_error` per uno stato di errore esplicito con retry.
- **B18 — Fase derivata da `date.today()` quando `phase=None` nel resolver** — `resolve_session.py:1911-1934`; `replanner._auto_resolve` non passa mai `phase` (`replanner.py:154-164`): override/quick-add su settimane future in fase diversa ordinano gli esercizi con la fase di oggi.
- **B19 — Side-effect I/O all'import in `planner_v2`** — `_validate_session_meta_equipment()` (`planner_v2.py:110-133`) apre ~35 JSON a import-time con `except Exception: pass`. **Fix:** spostare in uno script/test di validazione catalogo.

### Punti di forza (backend)

- **Webhook Stripe hardened**: firma verificata su raw body, dedup LRU, eccezioni → 500 per retry, upsert idempotenti, skip fatture $0.
- **Boundary auth→storage pulita**: nessun `user_id` accettato da query/path/body in nessun router; filtro sempre server-side. La falla è il solo fallback header (B1), non il disegno.
- **Guard B257 fail-closed sulle settimane passate**, resubmit-safety del feedback (dedup + `max()` sulle duration), determinismo verificato (nessun `random` non seedato, tie-break md5, Monday invariant con triplo gate, `from_phase="current"` preservato).

---

## Quick wins

I 5 interventi frontend a massimo rapporto valore/sforzo, in ordine:

1. **Proteggi il delete in falesia** (F3): conferma/undo sul `✕` di `live-route-logger.tsx` + `py-2.5` sui bottoni riga. Poche righe: elimina l'unico gesto distruttivo a un tap dell'app.
2. **Touch target dei controlli closed-loop** (F11): `py-2.5` sui chip feedback, `size="default"` su Done/Skip guidati, hit-area su close dialog e pallini. Una passata CSS su 5 file: migliora il dato che alimenta tutta la progressione.
3. **Timeout fetch** (F7): `AbortSignal.timeout(15_000)` in `request()` + messaggio "rete lenta, riprova". ~5 righe in un solo file: fine dello spinner infinito su rete scarsa.
4. **Guard anti-doppio-tap sulle mutation** (F6): `disabled={isPending}` su Done/Skip/action button. ~10 righe: chiude il lost-update del mark-done.
5. **Safe-area top** (F12): `pt-[env(safe-area-inset-top)]` sul contenitore root in `layout.tsx`. Una riga CSS: il Back torna tappabile su ogni schermata della PWA installata.

Nota a margine: il singolo intervento a più alto valore assoluto è l'outbox offline generalizzato (F4+F5, riuso del pattern `feedback_pending` già esistente) — non è un "quick" win (~1-2 giorni), ma è il più vicino al cuore del prodotto. Subito dopo: F1/F2 (app shell offline), che è il vero gap rispetto alla promessa PWA.
