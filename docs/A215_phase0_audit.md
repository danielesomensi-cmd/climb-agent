# A215 — Phase 0 Audit Report

**Date:** 2026-04-24
**Scope:** Read-only audit before paywall redesign (Phase 1).
**Author:** Claude Code (Opus 4.7)
**Status:** **STOP GATE** — awaiting Daniele's explicit "OK, procedi con Phase 1" + 7 decisions at §3.7.

---

## Executive summary

L'attuale paywall vive in `frontend/src/app/(main)/subscribe/page.tsx` (162 righe, client component). È reachable da **6 entry point**: Settings, Today (3×), Onboarding `start-week`, Session Builder play, Guided session, Trial Banner (2×). L'API Stripe e la logica di guard sono solide e **non devono essere toccate** — la parte presentation è tutto quello che cambiamo.

**3 scoperte operative pre-implementazione:**

1. 🔴 **DarkModeToggle miss in A214** — esiste un componente funzionale `DarkModeToggle` in TopBar, che A214 Phase 0 non ha rilevato (grep cercava `ThemeToggle`, non `DarkModeToggle`). È presente su TUTTE le main screens (today, week, plan, settings, /subscribe). Post-A214 è **parzialmente rotto**: cliccarlo rimuove `.dark` da `<html>` fermando `dark:` variants shadcn ma lasciando il background scuro via `:root`. Va sistemato (raccomando hot-fix B225 prima di A215).

2. 🟡 **Niente Accordion shadcn installato** — brief §4.5 richiede `shadcn Accordion` per la FAQ. Servirà `npx shadcn@latest add accordion` in Phase 1 (aggiunge 1 file + 1 peer dep `@radix-ui/react-accordion`).

3. 🟡 **Niente endpoint backend per "spots remaining" / "beta count"** — per Founding Climber "Only N of 20 spots left" e social proof "Trusted by N climbers" servirebbero due endpoint (non esistono). Alternativa: hardcoded constants aggiornati a mano. Decisione da prendere.

**Stripe flow:** il CTA chiama `POST /api/subscription/checkout` via `createCheckoutSession(email, priceId)` in `frontend/src/lib/api.ts:486`. Redirigeil browser a `session.url`. Short-circuit B212 per utenti già attivi → redirect a `/today`. Tutto ciò è **hands-off**.

**BYPASS_USER_IDS** (Daniele): la pagina `/subscribe` si renderizza comunque; il CTA ritorna `already_active` → redirect a `/today`. **Per preview testing basta visitare la pagina** — il CTA è innocuo.

---

## §3.1 Existing paywall inventory

### Route

- **URL:** `/subscribe`
- **File:** `frontend/src/app/(main)/subscribe/page.tsx` (162 righe, `"use client"`)
- **Layout wrap:** `frontend/src/app/(main)/layout.tsx` aggiunge:
  - `<TrialBanner />` (sticky top — trial countdown / expired CTA)
  - `<BottomNav />` (sticky bottom — Today/Week/Plan/Free/More)
- **Header interno:** `<TopBar title="Subscribe" />` — contiene `<DarkModeToggle />` (vedi Risk flag 1).

### Entry points (6)

| File | Line | Trigger |
|------|------|---------|
| `components/layout/trial-banner.tsx` | 39 | Tap su "Subscribe" in trial countdown |
| `components/layout/trial-banner.tsx` | 55 | Tap su "Subscribe" post-expiry |
| `app/(main)/settings/page.tsx` | 774 | Tap su bottone Subscribe in Settings |
| `app/(main)/today/page.tsx` | 407 | Gate on `!canInteract` — guided start |
| `app/(main)/today/page.tsx` | 436 | Gate on `!canInteract` — mark done |
| `app/(main)/today/page.tsx` | 1084 | Gate on `!canInteract` — quick-add |
| `app/onboarding/start-week/page.tsx` | 58 | Post-onboarding redirect se non bypass |
| `app/(guided)/session-builder/[id]/play/page.tsx` | 81 | Gate guided session play |
| `app/(guided)/guided/[date]/[sessionId]/page.tsx` | 72 | Gate guided session detail |

(Totale 9 chiamate da 6 file/flow logici.)

### Component tree attuale

```
/subscribe/page.tsx
├── <TopBar title="Subscribe" />                ← components/layout/top-bar.tsx
│   └── <DarkModeToggle />                      ← 🚨 broken post-A214 (Risk flag 1)
├── <Card> Founding Climber                     ← shadcn Card (inline, no component)
│   ├── badge "Limited"
│   ├── $4.99/month
│   ├── 3 bullets (Locked/20 spots/15-day trial)
│   └── <Button>Start Free Trial</Button>       ← onClick → handleSubscribe(FOUNDER, "founding")
├── <Card> Standard                             ← shadcn Card (inline, no component)
│   ├── $9.99/month
│   ├── 1 paragraph description
│   └── <Button variant="outline">              ← onClick → handleSubscribe(STANDARD, "standard")
├── Feature list (hardcoded 5-item array)
├── Stripe disclaimer text
└── {error && <p className="text-destructive" />}
```

### Analytics already wired

- `captureUtmOnMount()` on mount (persists UTM from URL to localStorage, 30-day expiry)
- `trackEvent("subscribe_viewed")` on mount
- `trackEvent("checkout_clicked", { plan })` on CTA click

### A/B variants / experiments

**Nessuno.** Un solo rendering, gated solo dal loading state + `already_active` short-circuit.

---

## §3.2 Stripe integration boundaries

### Backend

- **File:** `backend/api/routers/subscription.py`
- **Endpoint CTA:** `POST /api/subscription/checkout`
- **Payload:** `{ email: string | null, price_id: string | null }`
- **Response (happy path):** `{ checkout_url: string }` (Stripe hosted URL)
- **Response (B212 short-circuit):** `{ already_active: true, status: "trialing"|"active", redirect_url: "/today" }`

**Key logic (lines 82-157):**
1. Validate `user_id` exists (401 if not)
2. Validate `STRIPE_PRICE_ID_STANDARD` configured (503 if not)
3. Whitelist `price_id` against `_ALLOWED_PRICE_IDS = {STANDARD, FOUNDER}` — fallback a standard se ignoto (+ warning log)
4. Check `get_subscription_row(user_id)`:
   - Se `status in {"trialing", "active"}` → **B212 short-circuit** con `already_active: true`
   - Altrimenti, riusa `stripe_customer_id` se esiste
5. Crea Stripe Checkout Session con:
   - `mode: "subscription"`
   - `trial_period_days: 15`
   - `subscription_data.metadata: {user_id}` (survives race conditions)
   - `client_reference_id: user_id`
   - `metadata: {user_id}`
   - `payment_method_types: ["card"]`
   - `allow_promotion_codes: true`
   - `success_url: {FRONTEND_BASE}/today?checkout=success`
   - `cancel_url: {FRONTEND_BASE}/today?checkout=canceled`
6. Fallback: se `No such customer` → clear `stripe_customer_id` + retry con `customer_email`
7. Mark subscription `pending_checkout` in DB (line 155)
8. Return checkout URL

### Frontend glue

- **File:** `frontend/src/lib/api.ts:486-490`
- **Function:** `createCheckoutSession(email?, priceId?)` → POST con body `{email, price_id}`
- **File:** `frontend/src/app/(main)/subscribe/page.tsx:25-48` (`handleSubscribe`)
  - Track event
  - Set loading
  - Call API with `email = user.primaryEmailAddress?.emailAddress` + priceId
  - If `already_active: true` → `window.location.href = res.redirect_url ?? "/today"`
  - Else if `checkout_url` → `window.location.href = res.checkout_url`
  - On throw → show error

### 🔒 Hands-off list (DO NOT MODIFY in A215)

| File / Function | Reason |
|-----------------|--------|
| `backend/api/routers/subscription.py` | Entire file — B212 guard, Stripe session creation, price whitelist |
| `backend/engine/subscription_guard.py` | check_subscription, BYPASS_USER_IDS, upsert logic |
| `frontend/src/lib/api.ts:486-495` | `createCheckoutSession` + `createBillingPortal` signatures |
| `frontend/src/lib/hooks/use-subscription.ts` | `useSubscription` hook — drives every access gate + TrialBanner |
| `handleSubscribe` orchestration logic (subscribe/page.tsx:25-48) | Can be refactored into helper but MUST preserve: track event → loading → call → already_active branch → checkout_url branch → error |
| `trackEvent("subscribe_viewed")` + `trackEvent("checkout_clicked", {plan})` | Existing funnel events — preserve |
| `captureUtmOnMount()` call | UTM first-touch attribution |

**Safe to modify:**
- Layout structure, copy, components, styling
- Add new analytics events ON TOP of existing
- Add/replace TopBar (purely presentational)
- Split page into sub-components (functional equivalence required)

---

## §3.3 Subscription tier data source

### Pricing + copy (tutto hardcoded in frontend)

| Field | Source | Value |
|-------|--------|-------|
| Founding price | `subscribe/page.tsx:74` | `$4.99/month` (string literal) |
| Standard price | `subscribe/page.tsx:113` | `$9.99/month` (string literal) |
| Founding bullets | `subscribe/page.tsx:79-90` | "Locked at $4.99/mo forever" / "Only 20 spots available" / "15-day free trial" |
| Standard description | `subscribe/page.tsx:117-119` | "Full access to AI-powered training plans. 15-day free trial." |
| Shared features | `subscribe/page.tsx:50-56` | 5-item array (Personalised plans / Guided sessions / Adapts / Indoor+outdoor / Hörst) |
| "Limited" badge | `subscribe/page.tsx:68` | Static string |
| "20 spots" claim | `subscribe/page.tsx:86` | **Static** — no backend data |

### Stripe price IDs (frontend env)

- `NEXT_PUBLIC_STRIPE_PRICE_ID_FOUNDER` — letto da `process.env` (line 11)
- `NEXT_PUBLIC_STRIPE_PRICE_ID_STANDARD` — letto da `process.env` (line 12)
- Presente sia su Railway (backend — `STRIPE_PRICE_ID_FOUNDER` / `STRIPE_PRICE_ID_STANDARD`) sia su Vercel (frontend — `NEXT_PUBLIC_*`). Due copie in sync manualmente.

### Trial duration

- **Backend:** hardcoded `trial_period_days: 15` in `subscription.py:112`
- **Frontend:** appare 4 volte come stringa "15-day free trial" / "15-day trial". **No constant esportato.**

### Spots remaining — NON ESPOSTO

**Nessun endpoint public restituisce quanti Founding slot sono occupati.** Il backend ha accesso via `SELECT COUNT(*) FROM subscriptions WHERE stripe_price_id = '{FOUNDER_ID}' AND status IN ('trialing', 'active')` ma non è esposto.

Per "Only N of 20 spots left" dinamico servirebbe un nuovo endpoint `GET /api/subscription/founding-spots` pubblico (no auth richiesta). Vedi Risk flag 3 + §3.7 Decisione 3.

### Beta tester count — NON ESPOSTO PUBLICAMENTE

Solo `GET /api/admin/users` esiste (admin-only via `X-Admin-Key`). Nessun endpoint pubblico con count degli utenti.

### BYPASS_USER_IDS logic

- **Env var:** `BYPASS_USER_IDS` (comma-separated UUIDs) in Railway backend
- **Load:** `_load_bypass_user_ids()` in `subscription_guard.py:21` — set read at module import
- **Effect:** `check_subscription(user_id)` ritorna `_ALLOW_ALL.copy()` immediatamente se `user_id in _BYPASS_USER_IDS` (line 158-159)
- **Frontend visibility:** response shape `{status: "active", is_active: true, trial_days_remaining: null, can_interact: true}` — **IDENTICO** alla response di un real active subscriber. Il frontend non può distinguere bypass vs real active.

#### Implicazioni per Daniele preview

Daniele (user_id bypass) visita `/subscribe`:
1. `useSubscription()` ritorna `isActive: true, isTrialing: false` → `TrialBanner` non mostra nulla (ok)
2. `SubscribePage` component renderizza integralmente (no conditional gate) → **paywall visibile** (ok per preview)
3. Tap CTA → `createCheckoutSession` → backend:
   - `user_id in _BYPASS_USER_IDS` NON influisce su `/checkout` endpoint — il bypass è solo nel guard
   - **Tuttavia** `get_subscription_row` per Daniele potrebbe esistere con `status: "active"` OR `status: None` a seconda se ha mai fatto un checkout
   - Se status active → B212 short-circuit → redirect `/today`
   - Se status not-active → endpoint crea veramente una Stripe Checkout Session con la sua email!

**Questo è un edge case.** Se Daniele non ha mai completato checkout (o ha row with non-active status), cliccando CTA **avvia** Stripe Checkout reale. Per preview safe, raccomando:

**Proposta §4.7 preview affordance:**
- Aggiungere check `?preview=1` nella page
- Se param presente: disabilita il CTA (mostra toast "Preview mode — CTA skipped") oppure renderizza CTA come `<div>` non cliccabile con label "Preview — tap disabled"
- Alternativa zero-code: Daniele confida che il suo subscription row esista già con status attivo (e quindi B212 scatta) → preview con CTA cliccabile → redirect innocuo. Richiede setup manuale una volta.

---

## §3.4 Trial countdown banner

### File + behavior

- **File:** `frontend/src/components/layout/trial-banner.tsx` (62 righe)
- **Hook:** `useSubscription()` from `@/lib/hooks/use-subscription`
- **Mounted in:** `frontend/src/app/(main)/layout.tsx` — sopra ogni main screen, incluso `/subscribe`
- **CTA routing:** 2× `router.push("/subscribe")` (line 39 + 55)

### States

| Subscription state | Banner render |
|-------------------|---------------|
| `loading === true` | `null` (niente) |
| `isActive && !isTrialing` (paid) | `null` |
| `status === "pending_checkout"` | `null` |
| `isTrialing`, `days > 3` | `bg-primary/5` + text muted; "N days left in your free trial · Subscribe" |
| `isTrialing`, `days ≤ 3` | `bg-amber-500/10` text-amber-400 (urgent); "N days left / 1 day / Trial ends today" |
| `past_due` / `canceled` / `expired` | `bg-destructive/10` text-destructive; "Your trial has ended. Subscribe…" |

### A214 interaction

Il banner usa **raw Tailwind palette** (`bg-amber-500/10`, `bg-destructive/10`, `bg-primary/5`, `text-amber-400`). Queste classi **funzionano** ancora (palette di default Tailwind presente). Ma non sono A214 tokens (dovrebbero essere `bg-warning/10 text-warning`, `bg-danger/10 text-danger`, `bg-brand/5`).

**Brief §4.7:** "Trial countdown banner behavior unchanged." → non tocco.

**Cosmetic drift:** post-A215 il banner sarà visibilmente "fuori palette" sulla pagina paywall (amber/destructive raw vs warm warning/danger tokens). Lo segnalo come non-blocker; opportunistic migration in A215 stesso (1-liner change di 3 classi) oppure parkeggio ad A217.

### KEEP / INTEGRATE

- **KEEP** il componente `TrialBanner` as-is (ok per brief §4.7)
- **NON integrare** nella nuova paywall — resta sopra la page come oggi

---

## §3.5 Analytics hooks

### Existing events (all via `@vercel/analytics` + custom `trackEvent` in `lib/analytics.ts`)

| Event | Fire location | Props |
|-------|---------------|-------|
| `subscribe_viewed` | subscribe/page.tsx:22 (on mount) | (none; UTM auto-attached) |
| `checkout_clicked` | subscribe/page.tsx:26 (on CTA click) | `{plan: "founding" \| "standard"}` |
| `demo_viewed` | demo/page.tsx | `{variant: "editorial_dark"}` |
| `demo_engaged` | demo/page.tsx | `{variant}` |
| `demo_scrolled_to_end` | demo/page.tsx (IntersectionObserver) | `{variant}` |
| `demo_cta_clicked` | demo/page.tsx | `{location: "inline"\|"sticky", variant}` |

### Nuovi eventi A215 (stubs only per §7 "analytics integration beyond stubs out of scope")

Aggiungo 2-3 eventi per tracciare funnel granulare:
- `paywall_scrolled_to_tiers` — IntersectionObserver sul primo TierCard (o scroll >70% viewport)
- `faq_expanded` — su accordion item open, `{question_id: "cancel" | "after_trial" | "why_founding" | "refund"}`
- (opzionale) `tier_compared` — se l'utente apre entrambi i tier (scroll past Standard)

Preservo esistenti: `subscribe_viewed` + `checkout_clicked` + UTM capture.

---

## §3.6 Additional risk flags (beyond the exec summary)

### 🚨 Risk flag 1 — DarkModeToggle is live + broken post-A214

Il componente `frontend/src/components/layout/dark-mode-toggle.tsx` esiste ed è usato in `top-bar.tsx:28` su ogni main screen (via `<TopBar>`). Contiene logica functional:
- Legge `localStorage.theme` (default `dark`)
- Chiama `document.documentElement.classList.toggle("dark", next)` su click

**Post-A214:** cliccare toggle rimuove `.dark` dall'`<html>`, il che:
- **Non** cambia il background (A214 ha merged `.dark` into `:root`, quindi le tokens vivono in `:root` e applicano sempre)
- **Sì** cambia i 20 residual `dark:` variants (shadcn button outline, input etc.) — quei pattern smettono di matchare e fanno fallback alle base classes, producendo rendering inconsistente

**Severità:** LOW (bypass/beta likely non l'ha mai cliccato) ma è dead/broken UI visibile su `/subscribe`.

**Miss di A214:** il grep del Phase 0 cercava `ThemeToggle|setTheme|theme.toggle|theme-switch` ma NON `DarkMode`/`DarkModeToggle`. Il componente è stato missed. **Proposta:** aprire **B225** come hot-fix separato (3-file change: rimuovere import in TopBar, rimuovere tag `<DarkModeToggle />`, cancellare file component). OR foldarlo in A215 come parte del "TopBar replacement" (vedi Risk flag 5).

### 🚨 Risk flag 2 — Paywall non-bypass edge case

Bypass user Daniele cliccando CTA **potrebbe** avviare Stripe Checkout reale se la sua subscription row non è `active`. Verifica state row prima di preview, o gate tramite `?preview=1`. Vedi §3.7 Decisione 2.

### 🚨 Risk flag 3 — Spots remaining + beta count data gap

Brief §4.4 pitcha "Only N of 20 spots left" (Founding badge) + "Trusted by N climbers in active beta" (social proof). Nessuno dei due è disponibile dal backend oggi.

**Opzioni:**

| Opt | Approccio | Effort | Pro | Con |
|-----|-----------|--------|-----|-----|
| A | Aggiungere 2 endpoint public no-auth (`/founding-spots`, `/beta-count`) | ~1h backend | Dynamic; preserva scarcity signal verosimile | Nuova public surface; caching considerations |
| B | Hardcoded constants in `lib/paywall-constants.ts` (`SPOTS_REMAINING`, `BETA_COUNT`) | ~5 min | Ship veloce; Daniele update manuale | Stale dopo primo subscriber; "fake" se copy dice "Only 17 left" quando sono 18 |
| C | Omit spots count (usa badge statico "Limited · 20 spots"); omit social proof | 0 min | Onesto; zero manutenzione | Meno urgency signal |

Raccomandazione: **Opt B** per launch. Migrazione a Opt A post-launch se i metrici mostrano che Founding tier è il top converter (giustifica effort).

### 🚨 Risk flag 4 — Shadcn Accordion da installare

Non presente in `components/ui/`. In Phase 1 aggiungo via `npx shadcn@latest add accordion`. Aggiunge:
- `frontend/src/components/ui/accordion.tsx` (1 file, ~60 righe)
- Peer dep: `@radix-ui/react-accordion` (aggiungi a `package.json` auto)
- Commit dedicato.

### 🚨 Risk flag 5 — TopBar vs full-bleed hero

TopBar (con DarkModeToggle rotto) è in cima a `/subscribe`. Options:

| Opt | Approccio | Pro | Con |
|-----|-----------|-----|-----|
| A | **Keep TopBar** — solo sostituiamo card layout | Conservative; match other pages | DarkModeToggle rimane (bug) finché B225 non scatta |
| B | **Replace TopBar** con minimal back-chevron overlay sopra hero | Full-bleed hero immersive; sidestep DarkModeToggle bug; mobile SaaS modern UX | `/subscribe` diventa "diversa" dalle altre pages (inconsistenza UI) |
| C | **Keep TopBar + hot-fix DarkModeToggle in B225** | Best of both | Richiede B225 prima di A215 merge |

Raccomandazione: **Opt C** (B225 hot-fix first, poi A215 con TopBar standard — title "Subscribe" rimane). Tenere consistenza con resto app.

### 🚨 Risk flag 6 — Copy lock freeze

Brief §8 + §4.4 danno copy dettagliato ma marca "may want to rewrite" e "Confirm copy in Phase 0 review." **Decisione 5 in §3.7.**

### 🚨 Risk flag 7 — Hero asset timing + path

Brief §9: Daniele genera hero via ChatGPT usando `A215_master_prompt_paywall.md` (file non ancora nel repo). Phase 1 parte con `HERO_PLACEHOLDER` gray box. Conferma:
- Path target: `frontend/public/hero/paywall_hero.webp`
- Fallback: `.jpg`
- Alt text suggerito: "Climber on overhanging wall at dusk" (verificare quando arriva l'immagine)

### 🚨 Risk flag 8 — TrialBanner visual mismatch post-A215

Banner usa `bg-amber-500/10` (off-palette) + `bg-destructive/10` (palette). Sulla nuova paywall design, il banner sarà visibilmente "diverso". Opzioni:
- A214-ish migration: `bg-amber-500/10` → `bg-warning/10`, `text-amber-400` → `text-warning`, `bg-primary/5` → `bg-brand/5` (1-liner, 3 classi). Preserva behavior, allinea palette.
- Skip: brief §4.7 esplicito "behavior unchanged" (leave as-is).

Raccomandazione: **Skip in A215** (per brief). Annotare in `ROADMAP_CURRENT` come micro-task A217 o P3 "TrialBanner palette migration". 1-liner, 5 min.

### 🚨 Risk flag 9 — `TopBar` does NOT visually integrate with hero

TopBar è `sticky top-0 bg-background/95 backdrop-blur`. Sopra un hero image full-width, crea una barra opaca che "taglia" l'immagine in alto. Options:
- A: lascia come oggi (hero starts sotto TopBar — no full-bleed ma pulito)
- B: rendere TopBar transparent over hero (usage-only su /subscribe)
- C: replace con back-chevron overlay (vedi Risk flag 5 Opt B)

Se scegliamo Opt C (Risk flag 5), risolve anche questo. Altrimenti A.

### 🚨 Risk flag 10 — TierCard `border-brand` utility

Verifico: Tailwind v4 genera `border-*` utilities da ogni `--color-*` entry. A214 definisce `--color-brand: hsl(var(--accent-primary))` → `border-brand` utility **esiste già** ✓ (confermato dal showcase `/dev/tokens` rendering successo).

Ok, nessun token extra da aggiungere.

### 🚨 Risk flag 11 — Bottom nav visibility

Brief §4.7: "Bottom nav visible (user must be able to navigate away without paying)." Attualmente `(main)/layout.tsx` rende `<BottomNav />` su TUTTE le main routes incluso `/subscribe`. ✓ No change needed — just confirm we don't accidentally hide it.

### 🚨 Risk flag 12 — Lighthouse Performance ≥90

Acceptance §5: "Lighthouse score on paywall route ≥ 90 on Performance and Accessibility."

**Performance** dipende da:
- Hero image: brief §4.3 impone <200KB at 2x (ok)
- Next/Image con `priority` (ok)
- No heavy client JS oltre hook useSubscription + analytics (ok)
- LCP candidate = hero image → optimization critical

**Accessibility** dipende da:
- Proper heading order (`<h1>` for hero headline; `<h2>` per section)
- Alt text su hero image
- CTA come `<button>` (non `<div>`)
- Color contrast WCAG AA sull'overlay gradient (test dopo hero arrival)

Entrambi raggiungibili; eseguo Lighthouse come acceptance check post-implementation.

---

## §3.7 Decisioni richieste prima di Phase 1

| # | Decisione | Raccomandazione |
|---|-----------|-----------------|
| 1 | **DarkModeToggle fix timing** — B225 hot-fix prima di A215, oppure foldato nel TopBar di A215, oppure dopo A215? | **B225 prima** (pulisci debt A214 su branch separato, poi A215 parte da state pulito) |
| 2 | **Preview affordance** — `?preview=1` con CTA disabled, oppure Daniele pre-imposta sua subscription row active e si fida di B212 redirect? | `?preview=1` con CTA → toast "Preview mode" (safest) |
| 3 | **Spots remaining + beta count** — endpoint backend (Opt A), hardcoded constants (Opt B), o omit (Opt C)? | **Opt B hardcoded** con constants in `lib/paywall-constants.ts`, Daniele aggiorna manualmente. Migrazione a Opt A post-launch se ROI giustifica. |
| 4 | **TopBar vs back-chevron overlay** — keep standard TopBar (Opt A), o replace con minimal overlay (Opt B)? | **Opt A keep TopBar** (consistenza app) + B225 fix dark-mode-toggle first |
| 5 | **Copy §4.4 lock** — OK così o riscrivi prima di implementare? | Chiedo conferma. I testi del brief sono già forti ("Train like the top 5%", "Built on Hörst, Lattice, López") — suggerisco ship as-is e iterare da dati. |
| 6 | **Hero filename/path** — `frontend/public/hero/paywall_hero.webp` ok? | Conferma. Alternative: `frontend/public/images/paywall-hero.webp` (più explicit namespace). |
| 7 | **TrialBanner palette migration** — skip (per brief §4.7) o opportunistic 1-liner migration? | **Skip in A215** — aperto micro-task P3 "TrialBanner functional-token migration" per A217 |

### Bonus (non pesante, procedo con best judgment se non dici altro)

- **Shadcn Accordion install:** userò `npx shadcn@latest add accordion` all'inizio di Phase 1 (commit dedicato).
- **Analytics events da aggiungere:** `paywall_scrolled_to_tiers`, `faq_expanded` (con `question_id`), opzionale `tier_compared`. Tutti via `trackEvent()` esistente.
- **HERO_PLACEHOLDER:** scenario gray box 1200×800 con label "HERO_PLACEHOLDER" centrato, `bg-surface-inset` border dashed. Swap asset quando arriva.
- **Branch name:** `brief/A215-paywall-redesign`.
- **Model:** suggerisco `/model sonnet` quando apri Phase 1 (brief lo consiglia esplicitamente, non siamo in high-risk modules).

---

## §3.8 Proposed delta vs brief

| Brief § | Status | Delta |
|---------|--------|-------|
| §3 Phase 0 audit | ✅ This doc | — |
| §4.1 Layout structure | 🟢 OK | TopBar presunta keep (Decisione 4) — non full-bleed |
| §4.2 Components (5 new) | 🟢 OK | PaywallHero + ValueBullets + TierCard + SocialProof + PaywallFAQ |
| §4.3 Hero image | 🟡 Pending asset | HERO_PLACEHOLDER durante implementation; Daniele sostituisce |
| §4.4 Copy | 🟡 Pending freeze | Decisione 5 |
| §4.5 Behavior/interaction | 🟢 OK | Accordion install needed (Risk flag 4); "Only N spots" diventa hardcoded via constants (Decisione 3 Opt B) |
| §4.6 Accessibility | 🟢 OK | Pass standard + Lighthouse check |
| §4.7 Keep working | 🟡 Conflict minor | TrialBanner resta con palette raw (Decisione 7 skip); `?preview=1` affordance aggiunta (Decisione 2) |
| §5 Acceptance | 🟢 OK | Lighthouse ≥90 on /subscribe — fattibile, solo hero size è fattore critico |
| §6 Commits | 🟢 OK | 7 commit come proposto + 1 `chore(A215): install shadcn accordion` pre-PaywallFAQ |
| §7 Out of scope | 🟢 OK | Rispettato |

---

## §3.9 Estimated delivery (Phase 1)

| Task | Effort | Note |
|------|--------|------|
| Branch + install accordion | 15 min | `npx shadcn@latest add accordion` + commit |
| `PaywallHero` component + HERO_PLACEHOLDER | 45 min | `next/image`, overlay gradient, headline/subheadline |
| `ValueBullets` component | 20 min | 3-row icon+text (lucide icons) |
| `TierCard` component + variants | 1h | Variants founding / standard, CTA integration, badge conditional |
| Wire new layout in `subscribe/page.tsx` | 1h | Orchestrator, preserve handleSubscribe/analytics/state |
| `SocialProof` (optional, hidden if no data) | 15 min | Usa `BETA_COUNT` constant; hide if 0 |
| `PaywallFAQ` | 30 min | 4 Q&A, shadcn Accordion |
| `?preview=1` affordance | 20 min | Query param read + CTA disable + preview strip |
| Copy refinements + a11y pass | 30 min | Heading order, alt text, contrast test |
| Lighthouse + manual smoke | 30 min | mobile 375×812 + preview URL |
| Roadmap update | 10 min | Mark A215 Done |

**Total effort Phase 1:** ~5h wall-clock (più veloce di 1d stimato nel brief perché molta foundation è già fatta da A214).

**Phase 0 effort this report:** ~1h (vs 2h stimato).

---

## STOP GATE

**Non procedo con Phase 1 finché non ricevo "OK, procedi con Phase 1" esplicito da Daniele + risposta (anche sintetica) alle 7 decisioni sopra.**

Raccomando in particolare di pronunciarsi su:
- **Decisione 1** (DarkModeToggle): se scegli "B225 prima", apro piccolo brief separato ~10 min che taglia quella coda di A214 prima che A215 inizi.
- **Decisione 3** (spots/beta): importante per copy del Founding card — se Opt B, dimmi valori iniziali (tipo `SPOTS_REMAINING = 17`, `BETA_COUNT = 4`).
- **Decisione 5** (copy): se vuoi riscrivere parte del §4.4, passamelo ora.
