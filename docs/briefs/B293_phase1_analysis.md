# B293 — Phase 1 Analysis: Onboarding Funnel (entry points + regressioni)

**Data:** 2026-07-21 · **Tipo:** B (multi-issue) con fase D obbligatoria · **Stato:** ✅ Chiuso — Phase 2 (2A–2E) mergiata in `main` (e07e4a9) e verificata in prod da Daniele il 2026-07-21

Contesto: walkthrough manuale UX del 2026-07-21 su iPhone (Safari incognito + account loggato). Sei failure collegati. Questo documento è read-only: nessuna modifica al codice è stata fatta.

---

## 1A — Entry points: inventario e verdetto

### Route pubbliche vs auth-gated

Il "middleware" Clerk vive in `frontend/src/proxy.ts` (Next 16 ha rinominato middleware→proxy, D209):

```ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { PUBLIC_ROUTES } from "@/lib/public-routes";

const isPublicRoute = createRouteMatcher(PUBLIC_ROUTES);

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
};
```

`PUBLIC_ROUTES` (`frontend/src/lib/public-routes.ts`):
`/`, `/sign-in(.*)`, `/sign-up(.*)`, `/legal`, `/demo(.*)`, `/onboarding/welcome`, `/offline`, `/manifest.json` (ultimi due aggiunti da B292).

Tutto il resto — inclusi TUTTI gli altri step `/onboarding/*` — è auth-gated a livello middleware. Corretto by design: solo `welcome` deve essere leggibile da anonimi.

### Dove finisce un visitatore logged-out

- `/` (`app/page.tsx`) → client-side: `!isSignedIn` → `router.replace("/sign-in")`. La root NON è una landing.
- `/onboarding/welcome` (`app/onboarding/welcome/page.tsx`) → server component: `auth()` senza userId → **rende `<WelcomeContent />`** (hero + pitch + CTA `SignUpButton` con `forceRedirectUrl="/onboarding/profile"` + link recover). Con userId → fetch `/api/state` (timeout 5s) → `/today` se ha macrocycle, altrimenti `/onboarding/profile`.
- `/demo` → pubblica (A182), demo session con CTA. Distinta dal wizard, tuttora funzionante come landing secondaria.

### Perché il visitatore anonimo viene comunque sbattuto sul sign-in (la regressione)

La pagina welcome è corretta. Il problema è il **layout** che la avvolge:

1. `app/onboarding/layout.tsx` monta `OnboardingProvider` su TUTTI gli step, welcome inclusa.
2. `OnboardingProvider` (`components/onboarding/onboarding-context.tsx:149-233`), al mount, se non trova un draft in localStorage chiama **`getState()`** — anche per un visitatore anonimo.
3. `_getAuthHeaders()` (`lib/api.ts:53-67`): nessuna Clerk session → richiesta inviata **senza** Authorization header (scelta deliberata A245 C-2: "il backend risponde 401 autoritativamente").
4. Backend: da **B285** (2026-07-20, `_auth_enforced()` in `backend/api/deps.py:101`) una richiesta anonima in produzione riceve **401** (prima: 200 con EMPTY_TEMPLATE).
5. Client (`lib/api.ts:153-173`): 401 → retry B155 dopo 500ms → ancora 401 → online → **`window.location.href = "/sign-in"`** (percorso F51, A245 C-3).

Risultato: la welcome rende per un istante, poi il visitatore viene deportato su `/sign-in`. Esattamente il sintomo osservato.

### Timeline git (verdetto sulla storia)

| Data | Commit | Evento |
|---|---|---|
| 2026-05-07 | `f7acf65` B-SHOP-FLYER-01 | Welcome resa pubblica (middleware + page). Funzionava: getState anonimo rispondeva 200/EMPTY_TEMPLATE |
| 2026-07-20 | `c3eeb2c` B285 | Backend fail-closed: anonimo → 401 (fix sicurezza corretto e da NON toccare) |
| 2026-07-20 | `c63bc56` A245 C-3 (F51) | Redirect su 401 reso "soft" ma sempre presente per il caso online |
| 2026-07-20 | `a60d3bd` B292 | `/offline` + `/manifest.json` pubbliche (non c'entra con la regressione) |

**Verdetto:** il change di maggio NON è stato revertito né perso in un merge — è stato **rotto il 2026-07-20 da B285** (interazione backend-401 × getState incondizionato del provider × redirect F51). Regressione vecchia di un giorno al momento del test.

**URL pubblico corretto per QR / Reddit: `https://climb-agent.vercel.app/onboarding/welcome`** (la root `/` non va usata: logged-out → sign-in).

**Fix shape (2A):** l'`OnboardingProvider` non deve chiamare `getState()` quando non esiste una Clerk session (skip → defaults, `loaded=true`). Nessuna modifica a B285 né al percorso F51.

---

## 1B — Invalidazione sessione Clerk mid-wizard + dove vive lo stato

### Cosa ha buttato fuori l'utente

Gli step del wizard sono quasi tutti client-only. Le uniche chiamate API mid-wizard sono:
- `OnboardingProvider` al mount (getState, una volta);
- step **locations** e **start-week** (uniche pagine step che importano da `@/lib/api`);
- submit finale nella review.

Il blocco è avvenuto "~dopo lead-grades": il percorso grades → goals → weaknesses → tests → limitations → **locations** è coerente con un 401 sulla chiamata API dello step locations → retry B155 → 401 → `window.location.href = "/sign-in"` (F51). Il "logout forzato" è quindi il **nostro** redirect su un 401, non un logout Clerk esplicito.

### Perché il token era invalido: Clerk Development mode (valutazione esplicita)

Clerk è ancora su **istanza Development in produzione** (issue nota, brief separato). È la causa più probabile dell'invalidazione:
- le istanze dev usano il dominio `*.accounts.dev` con handoff cookie/URL pensato per sviluppo locale; su Safari iOS (ITP, terze parti bloccate, PWA) il refresh del session token (TTL ~60s) fallisce con facilità quando il tab viene sospeso/ripreso — tipico durante un wizard con app-switch;
- un refresh fallito → `session.getToken()` produce un token scaduto/nullo → il backend risponde 401 → F51.

In produzione (istanza Production, dominio proprio, cookie first-party) questa classe di failure sparisce quasi del tutto. Confermo quindi: **Dev-mode è la causa probabile del blocco**; la migrazione resta fuori scope (brief separato), ma il wizard deve sopravvivere comunque a una re-auth (2B).

### Dove vive lo stato onboarding oggi

- **Client-only**: draft in `localStorage`, chiave `climb_onboarding_draft_<clerkUserId | "anon">`, TTL 30 giorni, envelope `{data, deepestStep, savedAt}` (A245 F16). Nessuna persistenza server per-step: il backend vede i dati solo al submit atomico `/api/onboarding/complete`.
- Salvataggio a ogni `update()` (keystroke) sotto la chiave calcolata **al momento della scrittura**.

### Il meccanismo di perdita dati (bug indipendente dal Dev-mode)

`draftKey()` legge `window.Clerk?.user?.id` — ma clerk-js si carica **async**, e l'effect di mount del provider parte quasi sempre prima:

1. Durante il wizard (Clerk carico) i salvataggi vanno sotto `_user_XXX`.
2. Al reload post re-login, l'effect legge `draftKey()` → Clerk non ancora inizializzato → chiave **`_anon`** → draft non trovato.
3. Fallback `getState()` (che nel frattempo, grazie al retry B155, parte autenticato): per un utente che non ha mai completato l'onboarding lo state è quasi vuoto → `d` resta ai DEFAULT (profile name "", weight 0, height 0).
4. Riga 229: `saveDraft(d, ...)` — a quel punto Clerk È carico → scrive i default **sopra il draft buono `_user_XXX`**. Il draft reale è distrutto.

Questo spiega il pattern osservato: profilo/esperienza persi (0y, 0kg, 0cm), mentre grades/goal/availability "sopravvissuti" perché **re-inseriti dall'utente dopo il re-login** (era fermo allo step grades). Non c'è stato un salvataggio parziale: è andato perso tutto il pre-blocco.

**Fix shape (2B):** persistenza per-step server-side keyed sul Clerk user (+ resume al primo step incompleto), e comunque mai calcolare la draft key prima che Clerk sia `loaded` (usare `useUser()` invece di `window.Clerk` letto in un effect). Cleanup: draft/step-state cancellati al completamento onboarding.

---

## 1C — Gap di validazione profilo

### Dove la validazione esiste e dove manca

- **Step profile** (`app/onboarding/profile/page.tsx:26-30`): Next disabilitato se `name` vuoto o `age/weight/height ≤ 0`. ✅ Corretta — ma protegge solo il passaggio DA quello step.
- **Review/summary** (`app/onboarding/review/page.tsx:204`): mostra `"{name}, {age}y, {weight}kg, {height}cm"` senza alcuna validazione; il submit non è bloccato. Con il draft clobberato (1B) l'utente arriva in review senza mai ripassare dal profile step → "0y, 0kg, 0cm" visualizzato e inviato.
- **Backend** `/api/onboarding/complete` (`backend/api/routers/onboarding.py`): valida SOLO le equipment keys (`_validate_equipment_keys`, 422). `profile.get("weight_kg")` etc. scritti as-is in `body` e `bodyweight_kg`. Nessun bound check.

### Consumer downstream di weight/height che si corrompono con 0

| Consumer | Comportamento con weight 0 |
|---|---|
| `backend/engine/assessment_v1.py:168,196` | `bw = body.get("weight_kg") or 70.0` → fallback silenzioso a 70: assi calcolati su un corpo inventato |
| `backend/engine/progression_v1.py:246,598-633` | `_get_bodyweight` → 0.0; `suggested_external = target_total - 0` → carichi esterni suggeriti gonfiati dell'intero bodyweight |
| `backend/engine/resolve_session.py:148-198` | `bw=0` passa il check `is None` (riga 149) → `added = target_total - 0` → prescrizione "aggiungi N kg" pari al totale |
| Test Max Hang UI (`components/guided/guided-exercise-step.tsx:745-752`) | "Total load: 35.0 kg (your weight 0 kg + 35 kg added)" — esattamente il sintomo #4; il baseline salvato come `total=35` invece di ~bw+35 corrompe tutte le prescrizioni future (in difetto), mentre bw=0 le corrompe in eccesso |
| `app/onboarding/tests/page.tsx` | i test "total = body + added" ereditano il peso 0 nel calcolo |

**Fix shape (2C):** blocco client su review/summary + guard server-side su `/complete` con bounds (weight 30–150, height 120–220, name non vuoto; reject 422, nessun clamp silenzioso).

---

## 1D — Timing del resolver (read-only; nessuna proposta dentro `resolve_session`)

### Quando gira la risoluzione

**Sincrona, dentro la stessa request.** `GET /api/week/{n}` (`backend/api/routers/week.py:255-501`): carica/genera il piano, lo salva, poi chiama `_auto_resolve()` (riga 501) che risolve ogni sessione inline prima di rispondere. Anche gli endpoint replanner (`/override`, `/events`, `/quick-add`) fanno `_auto_resolve` prima del return. **Non esiste un percorso legittimo che ritorni al client un piano non risolto.**

Dettaglio chiave: il piano è salvato in `state.week_plans` PRIMA della risoluzione (riga 495-498); i dati `resolved` delle sessioni non completate **non vengono persistiti** (solo done/skipped via `_cache_completed_resolved`, B120). Quindi ogni GET ri-risolve da zero → un fallimento transitorio si auto-ripara al refetch successivo. Combacia con "gli esercizi sono apparsi dopo senza azione".

### Perché la card era "No exercises resolved" ma completabile

`_auto_resolve` (`week.py:120-132`): se `resolve_session()` solleva, setta `resolved=None` + **`resolve_error=True`** (A245 E-3/B17, esplicitamente introdotto "so a transient error can be surfaced (and retried)"). Ma:

- **Il client non legge `resolve_error` da nessuna parte** (`grep resolve_error frontend/src` → zero hit). La metà client di B17 non è mai stata implementata.
- `session-card.tsx:997-1003`: `instances.length===0 && blocks.length===0` → rende il placeholder "No exercises resolved"…
- …e i bottoni Done/Skip (righe 1090-1125) sono gated solo su `marking`, mai sullo stato di risoluzione → card vuota ma completabile. Sintomo #5 riprodotto alla lettera.

### Cosa è cambiato tra il primo sguardo e il secondo

`useWeekPlan` ha `staleTime: 60s` → il refetch (focus/navigazione) ha rieseguito `GET /api/week` → `_auto_resolve` ritentata → risoluzione riuscita → esercizi appaiono. L'equipment non c'entrava (coerente con l'osservazione).

Causa del fallimento transitorio della PRIMA risoluzione: non determinabile con certezza senza i log Railway (`logger.error "_auto_resolve: session resolution failed"` con traceback — da controllare in verification). Candidati: eccezione da stato appena scritto dal submit onboarding letto in una race, o hiccup infra. Nota: essendo l'engine deterministico, un fallimento *persistente* avrebbe altre cause (es. bw=0 → 1C); qui il retry è riuscito, quindi transitorio.

**Fix shape (2D — solo UI/orchestrazione):** la card deve distinguere tre stati: (a) `resolve_error=true` → banner errore + retry (refetch); (b) risolto ma 0 esercizi → empty-state esplicativo; (c) in ogni caso Done/Skip disabilitati finché non c'è una risoluzione valida. Zero modifiche a `resolve_session`/`_auto_resolve`.

---

## 1E — Interruzioni al primo load di /today

Inventario completo di ciò che può sparare al primo mount (tutti indipendenti, nessuna coda):

| # | Interruzione | Componente | Trigger |
|---|---|---|---|
| 1 | **Phase-change modal** ("Power Endurance complete!") | `training/phase-celebration.tsx` (A235), montato a `today/page.tsx:1346` | Al mount se fase corrente index>0 con celebration key non vista. Fresh user finito mid-cycle via `/api/onboarding/start-week` (shift indietro) → celebra fasi mai allenate |
| 2 | **Achievement toast** ("Send Season") | `training/milestone-toast.tsx` (A239), `today/page.tsx:1350` | Al mount, prima eval lazy dei milestones: i grade inseriti in onboarding sbloccano retroattivamente → toast immediato (>2 unseen collassano in un summary — ma 1-2 sparano singoli) |
| 3 | **Retest prompt** ("Time to retest") | `training/test-reminder-card.tsx`, `today/page.tsx:1150` | `test_reminder` nella risposta GET /week (`should_show_test_reminder`); con `tests_source=estimated` + start shiftato scatta subito. È una card inline, non un modal — la meno invasiva delle quattro |
| 4 | **Popup geolocalizzazione iOS** | `training/weather-card.tsx:70-100` (A238) | `navigator.geolocation.getCurrentPosition` **al mount** del today, senza gesto utente, se la sessionStorage cache è vuota. Permission popup di sistema sopra tutto il resto |

Altri utilizzi di geolocation (coach `page.tsx:226`, outdoor `[date]/page.tsx:116`) sono già legati a contesti di feature — il problema del "popup al primo login" è solo la weather card del today.

**Fix shape (2E):** coordinatore con una interruzione alla volta, priorità: phase modal > retest > milestone toast; geolocation spostata dietro un gesto (es. tap su un placeholder "Show conditions") o comunque differita alla prima feature meteo/outdoor.

---

## Riepilogo verdetti

1. **Entry point pubblico:** `https://climb-agent.vercel.app/onboarding/welcome`. La welcome pubblica di maggio è stata rotta il 2026-07-20 da B285 (backend 401 anonimo) via getState incondizionato dell'OnboardingProvider + redirect F51. Fix client-side, B285 intoccato.
2. **Blocco Clerk mid-wizard:** probabile fallimento refresh token da istanza Development su Safari iOS; il "logout" è il nostro redirect F51 su 401 (step locations). Migrazione Clerk fuori scope; il wizard deve diventare resiliente.
3. **Perdita profilo:** race sulla draft key (`window.Clerk` non pronto al mount) → miss del draft utente → fallback getState scrive i DEFAULT sopra il draft. Persi TUTTI i dati pre-blocco; i "sopravvissuti" erano re-inseriti.
4. **Peso 0 nei test:** validazione esistente solo sullo step profile; review e backend non validano; 5 consumer downstream documentati.
5. **"No exercises resolved" completabile:** risoluzione sincrona server-side con retry naturale a ogni GET; `resolve_error` (B17) mai consumato dal client; Done/Skip mai gated sulla risoluzione.
6. **Stacking interruzioni:** 4 trigger indipendenti al primo mount, nessuna coda; geolocation senza gesto utente.

## Scope Phase 2 proposto (conferma richiesta)

- **2A** `OnboardingProvider`: skip `getState()` senza sessione Clerk (welcome pubblica di nuovo funzionante).
- **2B** Persistenza per-step server-side + resume; draft key mai calcolata con Clerk non-loaded.
- **2C** Validazione review (client) + bounds su `/api/onboarding/complete` (server): weight 30–150, height 120–220, name non vuoto, age 13–99 (proposta — da confermare), 422 senza clamp.
- **2D** Session card: gestione `resolve_error` + empty-state + Done/Skip disabilitati se non risolta. Nessun tocco a `resolve_session`.
- **2E** Coda interruzioni (phase modal > retest > milestone toast) + geolocation dietro gesto/feature.

Fuori scope confermato: `resolve_session`/engine, migrazione Clerk Dev→Prod, weather card redesign, nuova landing.
