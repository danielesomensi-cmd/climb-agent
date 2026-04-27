# A216 — Phase 0 Audit Deliverable

**Date**: 2026-04-27
**Status**: Phase 0 complete, awaiting Daniele's row-by-row review of §7 + answers to §10 before Phase 1.
**Scope**: Onboarding flow visual + copy redesign (presentation only, zero structural changes).

---

## §1 — File map

```
frontend/src/app/onboarding/
├── layout.tsx                  19 LoC  ── OnboardingProvider + StepIndicator wrapper
├── page.tsx                     5 LoC  ── redirect → /welcome
├── welcome/page.tsx            63 LoC  ── step 1 (Welcome) ★ HERO TARGET
├── install/page.tsx           178 LoC  ── step 2 (Install PWA, iOS/Android tabs)
├── profile/page.tsx           123 LoC  ── step 3 (name, age, weight, height)
├── experience/page.tsx         86 LoC  ── step 4 (climbing years, structured years)
├── discipline/page.tsx         98 LoC  ── step 5 (lead/boulder/both)
├── grades/page.tsx            280 LoC  ── step 6 (RP/OS lead+boulder, font/V toggle)
├── goals/page.tsx             322 LoC  ── step 7 (target grade, total_weeks slider)
├── weaknesses/page.tsx        223 LoC  ── step 8 (primary+secondary weakness)
├── tests/page.tsx             396 LoC  ── step 9 (hangboard/loading-pin tests, optional)
├── limitations/page.tsx       263 LoC  ── step 10 (injuries: area/side/severity)
├── locations/page.tsx         376 LoC  ── step 11 (home + gyms + outdoor spots)
├── availability/page.tsx      360 LoC  ── step 12 (weekday×slot grid + planning prefs)
├── trips/page.tsx             239 LoC  ── step 13 (outdoor trips, optional)
├── review/page.tsx            385 LoC  ── step 14 (summary + completeOnboarding)
├── start-week/page.tsx        131 LoC  ── post-completion (skip to phase, separate route)
└── recover/page.tsx            12 LoC  ── stub: redirect → /sign-in (Clerk-era leftover)

frontend/src/components/onboarding/
├── onboarding-context.tsx     150 LoC  ── React Context + sessionStorage draft
├── step-indicator.tsx          37 LoC  ── progress bar + dots
└── radar-chart.tsx            176 LoC  ── (NOT used in onboarding flow — only in /plan; out of scope)
```

**In scope per A216**: tutti i `page.tsx` degli step + `welcome/page.tsx` (hero) + `step-indicator.tsx` + `onboarding-context` (solo per inspection, NESSUNA modifica).

**Out of scope**: `layout.tsx` (già minimal e token-clean), `radar-chart.tsx` (usato solo in `/plan`), `recover/page.tsx` (stub redirect, niente UI).

**Step count reality check**: CLAUDE.md dichiara "16 onboarding steps". Reale: **14 step lineari** nel wizard (welcome → review) + 1 post-completion (start-week, route separata) + 1 stub redirect (recover). StepIndicator conta correttamente 14.

---

## §2 — Step inventory (CRITICAL)

| # | Step | File | Purpose | Title | Subtitle/body | CTA | Helper/error |
|---|------|------|---------|-------|---------------|-----|--------------|
| 1 | welcome | `welcome/page.tsx` | Splash + recover link | "Welcome to Climb Agent" | "Intelligent training, built for serious climbers" + "Climb Agent uses **AI-driven periodization** to build a training plan tailored to your strengths, weaknesses, and schedule. The more complete your initial assessment, the better. Your plan also adapts from session feedback over time." + 3 bullets (axes / periodized macrocycle / weekly adapt) | "Let's start" | "Already have an account? Recover access" |
| 2 | install | `install/page.tsx` | PWA install instructions | "Add to Home Screen" | "For the best experience, add Climb Agent to your home screen — it works just like a native app." | "Next" / "Back" | "Already installed? Just tap Next." |
| 3 | profile | `profile/page.tsx` | name, age, weight, height | "Your profile" | "Weight is used to calculate relative loads (e.g. weight-to-finger-strength ratio)" | "Next" / "Back" | required asterisks |
| 4 | experience | `experience/page.tsx` | years climbing + structured | "Your experience" | (none) | "Next" / "Back" | "If you've never followed a training plan, enter 0" |
| 5 | discipline | `discipline/page.tsx` | lead/boulder/both | "What do you want to improve?" | "This sets your main training focus. You'll still improve across all areas." | "Next" / "Back" | per-card desc: "Lead — I want to send harder routes" / "Boulder — I want to send harder problems" / "Both — I want to improve at everything" |
| 6 | grades | `grades/page.tsx` | RP+OS lead/boulder + font/V toggle | "Lead grades" / "Boulder grades" | "The gap between redpoint and onsight tells us about your power endurance and technique" | "Next" / "Back" | "Your highest grade after working the route" / "The grade you can climb on sight" / "Your maximum boulder grade" / "Your boulder onsight or flash grade" |
| 7 | goals | `goals/page.tsx` | target grade + plan duration | "Your goal" | (none on header) — body: "Redpoint = your max grade after working the route. Onsight = climbing it clean on the first try. This changes how we prioritize your weaknesses." | "Next" / "Back" | "Plan duration (weeks) *", "8 wk / 12 wk recommended / 24 wk", "Your plan ends: <date>", "A well-structured periodization cycle needs at least 12 weeks to go through all training phases (base, strength, power endurance, peak, recovery). Shorter plans compress phases and reduce effectiveness."; warnings: "Short plan — some training phases will be compressed", "Ambitious goal! The plan will be aggressive", "The target is equal to or lower than your current level" |
| 8 | weaknesses | `weaknesses/page.tsx` | primary + secondary weakness | "What is your main weakness?" / "And your second weakness?" | (none) — 12 cards (5 universal + 3 lead + 4 boulder) ognuno con title + descr | "Next" / "Back" | (none) |
| 9 | tests | `tests/page.tsx` | hangboard/loading-pin device + 6 test fields | "Finger training device" / "Do you have test data? (optional but recommended)" | "Which device do you primarily use for finger strength training?" / "If you've done these tests, enter the results. They will significantly improve the accuracy of your profile." | "Next" / "Skip" / "Back" | banner info: "Accurate test data helps climb-agent build a plan tailored to your specific strengths and weaknesses. After onboarding, we'll offer a dedicated test week to establish or refresh baselines." + per-test descr (Max Hang, Pull-up, Repeater, Duration, L-sit, Hip Flex) |
| 10 | limitations | `limitations/page.tsx` | injuries area/side/severity | "Do you have current injuries or limitations?" | "The plan will avoid exercises that aggravate your limitations and prioritize targeted prehab work to support your recovery." | "Next" / "Skip" / "Back" | "Yes, I have something" + severity descr: monitor "Mild discomfort — keep training but stay aware" / active "Noticeable pain — reduce stress on this area" / severe "Significant injury — avoid all exercises that stress this area" |
| 11 | locations | `locations/page.tsx` | home equipment + gyms + outdoor spots | "Where do you train?" / "Gyms" / "Outdoor Spots" | (none) | "Next" / "Back" | "I train at home", warning "A hangboard is essential for finger training", "At least one climbing area is required for climbing sessions", "Optional — you can add these later in Settings", error "All gyms must have a name", presets "Quick-fill: Boulder/Lead/Fitness/All" |
| 12 | availability | `availability/page.tsx` | weekday×slot grid + planning prefs | "When do you train?" / "Training preferences" | "Outdoor days can be added later in your weekly plan based on weather and season." / "Hard sessions include max hang, limit bouldering, power training" | "Next" / "Back" | banner amber: "Want to train at a gym? Go back to the Locations step and add at least one gym. Even a generic gym with all equipment selected will work — you can refine it later." + banner blue: "Set your typical training week. The planner will build sessions around your schedule, matching each slot to the right location and equipment. You can adjust this anytime — and each weekend you'll review and confirm next week's plan." + per-cell labels (Home/Gym/Other) + "Other — other activities... block this slot from climbing training and help calculate your total weekly training load" + "Reduce next day — enable if this activity is physically demanding..." + "No rest days — not recommended" |
| 13 | trips | `trips/page.tsx` | outdoor trips, optional | "Do you have outdoor trips planned?" | "If you have a crag trip planned, the plan will automatically deload the days before" | "Next" / "Skip — no trips planned" / "Back" | "No trips? No problem — you can add them anytime from Settings.", error "End date must be after start date", placeholder "E.g.: Arco, Kalymnos..." |
| 14 | review | `review/page.tsx` | summary + completeOnboarding submit | "Summary" / "Plan generated!" | (rows con label+value+Edit per ogni step) | "Start training now" / "Do a test week first" / "Back" | warnings: "Your grades suggest significant climbing experience..." / "None of your gyms have climbing walls..." + tip: "A test week helps calibrate your plan with precise data. You can always start training immediately." |
| post | start-week | `start-week/page.tsx` | skip to phase N | "Where do you want to start?" | "If you've already been following a structured training plan, you can skip ahead and start from a later phase." | "Continue" / "Skip" | radio labels: "Start fresh — Week 1 (Base)" / "Skip to Strength — Week 5" |

---

## §3 — State management

- **Storage**: React Context `OnboardingProvider` (`onboarding-context.tsx`).
- **Persistence**: `sessionStorage` chiave `climb_onboarding_draft` (sopravvive ai refresh dentro la stessa sessione, sparisce con tab close).
- **Pre-load**: al mount, `getState()` carica eventuali dati precedenti dal backend (utente che riprende l'onboarding via Clerk).
- **Per-step submit**: ❌ **nessuno**. Niente endpoint chiamato a ogni step. Tutti i dati restano client-side fino al review.
- **Submit finale**: solo `completeOnboarding(data)` in review (POST `/api/onboarding/complete`, atomico) → ridireziona a `/onboarding/start-week`.
- **Validation**: per-step locale (variabile `isValid` calcolata dai field, gate sul Next button). **Nessun schema/zod**. Logica inline.
- **Navigation**: imperative `router.push()` su ogni Back/Next button. Niente state machine, niente conditional skip basato su risposte (eccetto goal type derived da discipline e weaknesses filtered by discipline).

→ **Documentazione, non proposte di cambio.** State logic resta intatto.

---

## §4 — Hardcoded color inventory + token mapping

11 occorrenze totali in 6 file. **Zero hex/rgb literali**. Tutti banner/error text con coppia light+dark `dark:` (light half è dead code per `<html class="dark">` hardcoded — A214 cleanup atteso).

| File | Linea | Classe | Mapping A214 |
|------|------|--------|--------------|
| `goals/page.tsx` | 286, 294 | `border-yellow-300 bg-yellow-50 text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200` | `border-warning/30 bg-warning/10 text-warning` |
| `goals/page.tsx` | 299 | `border-red-300 bg-red-50 text-red-800 dark:border-red-600 dark:bg-red-950 dark:text-red-200` | `border-danger/30 bg-danger/10 text-danger` |
| `tests/page.tsx` | 274 | `border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-600 dark:bg-blue-950 dark:text-blue-200` | `border-info/30 bg-info/10 text-info` |
| `locations/page.tsx` | 171 | `border-yellow-300 bg-yellow-50 text-yellow-800 dark:...` | `border-warning/30 bg-warning/10 text-warning` |
| `locations/page.tsx` | 277 | `text-red-500` | `text-danger` |
| `review/page.tsx` | 335, 341 | `border-yellow-300 bg-yellow-50 text-yellow-800 dark:...` | `border-warning/30 bg-warning/10 text-warning` |
| `review/page.tsx` | 347 | `border-red-300 bg-red-50 text-red-800 dark:...` | `border-danger/30 bg-danger/10 text-danger` |
| `availability/page.tsx` | 134 | `border-amber-300 bg-amber-50 text-amber-800 dark:...` | `border-warning/30 bg-warning/10 text-warning` |
| `availability/page.tsx` | 138 | `border-blue-300 bg-blue-50 text-blue-800 dark:...` | `border-info/30 bg-info/10 text-info` |
| `availability/page.tsx` | 213 | `border-amber-500 bg-amber-500/10 text-amber-500` | `border-warning bg-warning/10 text-warning` |
| `availability/page.tsx` | 316 | `text-yellow-600 dark:text-yellow-400` | `text-warning` |
| `trips/page.tsx` | 160 | `text-red-500` | `text-danger` |

Tutti i mapping seguono `docs/design_system_v1.md` §Migration map. Coerente con A215/A217.

---

## §5 — Visual debt inventory

Beyond colors:

- **Spacing**: pattern coerente `mx-auto max-w-lg space-y-6 pt-8` su tutti gli step (✅ no fix necessario)
- **Buttons**: tutti `<Button>` shadcn (variant: default/outline/ghost). `disabled` correttamente usato. **No hex / no custom button styles**. ✅
- **Typography**: tutti `<CardTitle>` shadcn (default text-2xl/text-xl/text-lg coerente). `<Label>` + `<CardDescription>` shadcn. `text-sm`/`text-xs` per body. ✅
- **Radius**: solo Tailwind defaults (`rounded-md`, `rounded-lg`, `rounded-full`) — già mappati ai token A214 via `--radius-*`. ✅
- **Shadows**: nessuno custom (gli step usano shadcn `Card` di default che è già A214-compliant). ✅
- **StepIndicator**: usa `Progress` component shadcn + `bg-primary`/`bg-muted` token-based. Header `text-muted-foreground`. **Nessun fix necessario**. ✅
- **Card click states** (welcome bullets, discipline cards, weakness cards, install platform tabs): usano `border-primary ring-2 ring-primary/30` — già token-based ma uso di `ring-primary/30` un po' aggressivo per cards selezionabili. Lascerei invariato salvo Daniele preferisca downgrade.
- **Spinner colors** (locations L132, L233): `border-primary border-t-transparent` ✅
- **Slider markers** (goals L276): `font-medium text-primary` per "12 wk recommended" ✅
- **Pill buttons** (locations L216): `border ... hover:bg-accent` shadcn ✅

→ **Nessun debito visivo significativo oltre ai colori di §4**. Onboarding è uniformemente shadcn-based, pre-A214 ma già abbastanza neutro. Rischio basso.

---

## §6 — Hero placement decision

**Default raccomandato (welcome/page.tsx)**:

- Hero full-bleed prima del contenuto: `<section className="relative h-[55vh] w-full overflow-hidden">` con `<Image fill priority object-cover>`.
- Bottom-up gradient overlay `linear-gradient(to bottom, transparent 35%, hsl(var(--surface-base) / 0.95) 100%)`.
- Headline DENTRO l'hero, bottom-aligned (stesso pattern di paywall A215): `<h1 className="text-3xl font-semibold leading-tight tracking-tight text-fg md:text-4xl">` + tagline.
- La `Card` corrente (con bullets) resta SOTTO l'hero, gestisce gli stessi 3 punti (axes / periodized / weekly adapt) ma con typography ridotta.
- CTA "Let's start" + recover link sotto la card, INVARIATI strutturalmente.

**Counter-considerazioni**:
- L'hero su welcome è **contestuale, non promozionale** — niente glow, niente border-brand (già coerente con feedback B244).
- Header h1 nell'hero diventa l'h1 della pagina; CardTitle attuale `<CardTitle className="text-2xl">Welcome to Climb Agent</CardTitle>` va DEMOTO a h2/h3 o rimosso (è ridondante con l'hero headline).
- Niente hero in altri step (sarebbe distrazione visiva mentre l'utente compila form).

→ Conferma o controproposta?

---

## §7 — Copy review proposals (CRITICAL — review row by row)

Priorità: ★ critico (bug/inconsistency) · ◐ raccomandato · ▪ opzionale stilistico · = keep as-is.

### Step 1 — welcome (★ ha un bug di brand)

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ★ | Title | "Welcome to Climb Agent" | "Welcome." (se hero ha headline propria) **OPPURE** "Welcome to climb-agent" (lowercase, brand consistente) | Brand è "climb-agent" lowercase in CLAUDE.md, README, package.json. "Climb Agent" capitalizzato è incoerente. |
| ★ | Tagline | "Intelligent training, built for serious climbers" | "Periodized training. Built for the top 5%." | Match A215 paywall tone ("Train like the top 5%"). "Intelligent" vague, "serious" generico. |
| ★ | Body L1 | "Climb Agent uses **AI-driven periodization** to build a training plan tailored to your strengths, weaknesses, and schedule. The more complete your initial assessment, the better. Your plan also adapts from session feedback over time." | "climb-agent uses **deterministic periodization** based on Hörst 4-3-2-1 to build a plan from your assessment, weaknesses, and schedule. Every session you log adapts the next." | **CRITICAL BUG**: copy attuale dice "AI-driven periodization" ma CLAUDE.md non-negotiable principle è "No LLM is used at runtime — all logic is rule-based and testable". Falsa promessa che contraddice l'architettura. "Hörst 4-3-2-1" cita la metodologia reale (in CLAUDE.md). |
| ◐ | Bullet 1 | "Maps your strengths and weaknesses across 5 performance axes" | "5-axis assessment: finger strength, pulling, power-endurance, technique, endurance" | Più specifico, nomina gli assi (sono nel codice). |
| ◐ | Bullet 2 | "Builds a periodized macrocycle matched to your goal and timeline" | "10–13 week macrocycle: base → strength → power-endurance → performance → deload" | Nomina le fasi (sono in CLAUDE.md macrocycle_v1). |
| ◐ | Bullet 3 | "Adapts every week based on your session feedback" | "Closed-loop adaptation: every session feedback adjusts the next week" | "Closed-loop" è il termine tecnico in CLAUDE.md (closed_loop_v1.py). |
| = | CTA | "Let's start" | keep | OK |
| = | Recover | "Already have an account? Recover access" | keep | OK |

### Step 2 — install

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Title | "Add to Home Screen" | keep | Functional, OK |
| = | Subtitle | "For the best experience, add Climb Agent to your home screen — it works just like a native app." | "For the best experience, add climb-agent to your home screen — it works just like a native app." | Solo brand lowercase. |
| = | iOS step 1-3 | (vedi §2) | keep | Tecnicamente corrette. |
| = | Hint | "Already installed? Just tap Next." | keep | OK |

### Step 3 — profile

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Title | "Your profile" | keep | OK |
| ◐ | Subtitle | "Weight is used to calculate relative loads (e.g. weight-to-finger-strength ratio)" | "Weight calibrates relative loads (e.g. body-weight + added load on hangboard)" | Più diretto e accurato — "weight-to-finger-strength ratio" non è un termine standard, ma "added load on hangboard" è cosa l'utente fa davvero. |
| = | Field labels | "Name *", "Preferred name", "Age *", "Weight (kg) *", "Height (cm) *" | keep | OK |
| = | Placeholder "preferred_name" | "Nickname (optional)" | keep | OK |

### Step 4 — experience

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Title | "Your experience" | keep | OK |
| ▪ | Q1 label | "How many years have you been climbing?" | "Years climbing" | Più conciso, slider self-explanatory. |
| ▪ | Q2 label | "How many years of structured training?" | "Years of structured training" | idem |
| = | Helper | "If you've never followed a training plan, enter 0" | keep | Utile. |

### Step 5 — discipline

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "What do you want to improve?" | "Your focus" | Più diretto, meno lifestyle-blog. |
| ◐ | Subtitle | "This sets your main training focus. You'll still improve across all areas." | "We'll bias the macrocycle toward this discipline. Other areas still improve." | Meno generico, "macrocycle" è il termine tecnico. |
| ◐ | Lead descr | "Lead — I want to send harder routes" | "Sending harder routes" | "I want to" generico, ridondante. |
| ◐ | Boulder descr | "Boulder — I want to send harder problems" | "Sending harder boulders" | idem |
| ◐ | Both descr | "Both — I want to improve at everything" | "Both, balanced focus" | "improve at everything" è imprecisa. |

### Step 6 — grades

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Lead title | "Lead grades" | keep | OK |
| = | Lead descr | "The gap between redpoint and onsight tells us about your power endurance and technique" | keep | Specifico e utile. ✅ |
| = | RP helper | "Your highest grade after working the route" | keep | OK |
| = | OS helper | "The grade you can climb on sight" | keep | OK |
| = | Boulder title | "Boulder grades" | keep | OK |
| = | Boulder RP helper | "Your maximum boulder grade" | keep | OK |
| = | Boulder OS helper | "Your boulder onsight or flash grade" | keep | OK |

### Step 7 — goals

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Title | "Your goal" | keep | OK |
| ◐ | Style helper | "Redpoint = your max grade after working the route. Onsight = climbing it clean on the first try. This changes how we prioritize your weaknesses." | "Redpoint = max grade after working a route. Onsight = first-try clean. We bias your weakness priority by style: redpoint loads finger/power, onsight loads route-reading and endurance." | Spiega l'effetto concreto sulla pianificazione. |
| = | "12 wk recommended" | keep | keep | Già specifico. |
| ◐ | Phase helper | "A well-structured periodization cycle needs at least 12 weeks to go through all training phases (base, strength, power endurance, peak, recovery). Shorter plans compress phases and reduce effectiveness." | "A full periodization cycle is 12+ weeks: base → strength-power → power-endurance → performance → deload. Shorter plans compress phases." | Più conciso, fasi accurate (matchano `macrocycle_v1`). |
| = | Short plan warning | "Short plan — some training phases will be compressed" | keep | OK |
| ◐ | Ambitious warning | "Ambitious goal! The plan will be aggressive" | "Ambitious goal — load increases will be aggressive" | Niente exclamation, più tecnico. |
| ◐ | Too low error | "The target is equal to or lower than your current level" | "Target must be above your current grade" | Imperative, più chiara. |

### Step 8 — weaknesses

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Primary title | "What is your main weakness?" | "Primary weakness" | Più conciso. |
| ◐ | Secondary title | "And your second weakness?" | "Secondary weakness" | idem |
| = | 12 weakness cards | (titles + desc) | keep all | Già specifiche e ben fatte. |

### Step 9 — tests

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Device title | "Finger training device" | keep | OK |
| = | Device subtitle | "Which device do you primarily use for finger strength training?" | keep | OK |
| = | LP note | "The loading pin isolates finger strength without shoulder stress. All finger exercises will use your selected device. You can change this later in Settings." | keep | Specifica e utile. ✅ |
| ◐ | Tests title | "Do you have test data? (optional but recommended)" | "Test data (optional)" | Più conciso. |
| ◐ | Tests subtitle | "If you've done these tests, enter the results. They will significantly improve the accuracy of your profile." | "If you've measured these benchmarks, enter results. We use them to calibrate prescriptions in week 1." | Specifica COSA succede (week 1 calibration). |
| ◐ | Info banner | "Accurate test data helps climb-agent build a plan tailored to your specific strengths and weaknesses. After onboarding, we'll offer a dedicated test week to establish or refresh baselines." | "Accurate baselines tighten week-1 prescriptions. If you skip, we'll offer a dedicated test week to establish them." | Più diretto. |
| = | Per-test desc | (max hang, pull-up, repeater, duration, L-sit, hip flex) | keep all | Tecnicamente accurate e dettagliate. ✅ |
| = | Hangboard example | "E.g.: weigh 77kg + 48kg added = 125kg total" | keep | Esempio chiaro. |

### Step 10 — limitations

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "Do you have current injuries or limitations?" | "Injuries or limitations" | Conciso, statement non question. |
| = | Subtitle | "The plan will avoid exercises that aggravate your limitations and prioritize targeted prehab work to support your recovery." | keep | Specifica e accurata. ✅ |
| = | Severity descs | (monitor / active / severe) | keep all | Già ottime. ✅ |
| ◐ | Toggle label | "Yes, I have something" | "Yes — I have something to flag" | Meno casual. |

### Step 11 — locations

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "Where do you train?" | "Where you train" | Statement coerente con altri step. |
| = | Hangboard banner | "A hangboard is essential for finger training" | keep | Vero. ✅ |
| = | Gyms title | "Gyms" | keep | OK |
| = | Gym section helper | "At least one climbing area is required for climbing sessions" | keep | OK |
| = | Outdoor Spots title | "Outdoor Spots" | keep | OK |
| = | Outdoor Spots subtitle | "Optional — you can add these later in Settings" | keep | OK |
| = | Quick-fill labels | "Boulder / Lead / Fitness / All" | keep | OK |
| = | Error | "All gyms must have a name" | keep | OK |

### Step 12 — availability

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "When do you train?" | "When you train" | Statement |
| = | Subtitle | "Outdoor days can be added later in your weekly plan based on weather and season." | keep | OK |
| ◐ | Banner blue | "Set your typical training week. The planner will build sessions around your schedule, matching each slot to the right location and equipment. You can adjust this anytime — and each weekend you'll review and confirm next week's plan." | "Set your typical training week. The planner builds sessions around your schedule and equipment. You'll confirm next week's plan every Sunday/Monday." | "Sunday/Monday" è preciso (matcha WeeklyCheckinCard logic). |
| = | Banner amber | "Want to train at a gym? Go back to the Locations step and add at least one gym..." | keep | OK |
| ◐ | Training prefs title | "Training preferences" | "Training volume" | Più specifico (la sezione regola days/week + hard days/week). |
| ◐ | Hard sessions descr | "Hard sessions include max hang, limit bouldering, power training" | "Hard sessions: max hang, limit bouldering, power training, projecting" | Aggiungo projecting (è in macrocycle). |
| = | Slider warning | "No rest days — not recommended" | keep | OK |
| = | "Other" descr | "Other — other activities (sports, circus, etc.) block this slot from climbing training and help calculate your total weekly training load." | keep | OK |
| = | "Reduce next day" descr | "Reduce next day — enable if this activity is physically demanding. We'll lower the intensity of your next climbing session." | keep | OK |

### Step 13 — trips

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "Do you have outdoor trips planned?" | "Outdoor trips" | Statement. |
| ◐ | Subtitle | "If you have a crag trip planned, the plan will automatically deload the days before" | "Trips trigger an automatic deload before departure so you arrive fresh." | Più diretto, "deload" è il termine tecnico (in macrocycle). |
| = | Empty state | "No trips? No problem — you can add them anytime from Settings." | keep | OK |
| = | Error | "End date must be after start date" | keep | OK |

### Step 14 — review

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| = | Title | "Summary" | keep | OK |
| = | Success state | "Plan generated!" / "Redirecting..." | keep | OK |
| = | All SummaryRow labels | (Profile, Experience, Grades, Goal, ...) | keep all | OK |
| ◐ | Grade-experience warning | "Your grades suggest significant climbing experience. Please review your experience inputs." | "Your grades suggest more climbing experience than you've reported. Double-check the experience step." | Più diretto, dice cosa fare. |
| ◐ | No-climbing-eq warning | "None of your gyms have climbing walls. Climbing-specific sessions will be limited. Consider adding a gym with bouldering or route areas." | "No gym has bouldering or route walls. Climbing-specific sessions will be skipped. Add a gym with these in the Locations step." | "skipped" più chiaro di "limited". |
| ◐ | Test week tip | "A test week helps calibrate your plan with precise data. You can always start training immediately." | "A test week calibrates your week-1 prescriptions with precise baselines. Or start immediately and self-report." | Più specifico (week-1 calibration). |
| = | "Start training now" | keep | keep | OK |
| ◐ | "Do a test week first" | keep | "Run a test week first" | "Do" → "Run" più tecnico. |

### Post — start-week

| Pri | Field | Current | Proposed | Rationale |
|-----|-------|---------|----------|-----------|
| ◐ | Title | "Where do you want to start?" | "Where to start" | Statement |
| = | Subtitle | "If you've already been following a structured training plan, you can skip ahead and start from a later phase." | keep | OK |
| = | Radio labels | "Start fresh — Week 1 (Base)" / "Skip to Strength — Week 5" | keep | OK |
| = | Buttons | "Skip" / "Continue" / "Applying..." | keep | OK |

---

**Summary count**: ★ critical: 4 (welcome bug + brand casing) · ◐ recommended: ~30 · ▪ optional stylistic: 2 · = keep as-is: ~50.

---

## §8 — Test surface

- **Frontend tests**: zero. `find frontend -name "*.test.*"` ritorna solo node_modules.
- **Backend tests che toccano onboarding**:
  - `test_cors.py`: GET `/api/onboarding/defaults` (header check, irrilevante per UI)
  - `test_admin.py`: assert su `onboarding_date` field (admin endpoint, non UI)
  - `test_a_activation_timing.py`: regression su start_date shift (engine, non UI)
- **Impatto A216**: zero. Backend pytest count invariato (1832 passing). Manual QA mandatory.

---

## §9 — Hero asset wiring confirmation

- `frontend/public/hero/` ✅ esiste, contiene `paywall_hero.{jpg,webp}` + `today_hero.{jpg,webp}`.
- Nessun `onboarding_hero.png` ancora caricato — Daniele deve uploadare prima di Phase 1.
- Pattern coerente confermato: A217 ha usato `next/image` con `fill priority sizes` → A216 farà uguale.
- Build script Pillow Phase 1.1.a: il glob `[f for f in glob.glob("frontend/public/hero/*.png") if "today_hero" not in f and "paywall_hero" not in f]` funzionerà per identificare la sorgente.

---

## §10 — Open questions for Daniele

**Q1 — Brand casing nel copy**: la app è `climb-agent` lowercase ovunque (CLAUDE.md, README, package.json). Onboarding dice "Climb Agent" capitalizzato in 4 punti (welcome title, welcome body, install subtitle, paywall TopBar copy). Confermo migrazione a "climb-agent" lowercase ovunque nel copy? È coerente con paywall A215 che dice "climb-agent Pro".

**Q2 — Welcome AI claim ★ CRITICAL**: la copy attuale "AI-driven periodization" contraddice il principio non-negoziabile in CLAUDE.md "No LLM is used at runtime — all logic is rule-based". Confermo modifica a "deterministic periodization based on Hörst 4-3-2-1"? Oppure preferisci una variante meno tecnica come "rule-based periodization" / "scientific periodization"?

**Q3 — Hero placement su welcome**: full-bleed top 55vh + headline-in-hero + Card sotto con bullets demoted (h3) + CTA fuori card? Oppure preferisci pattern paywall (hero su 70vh, copy minimo overlay, niente Card sotto)?

**Q4 — Tagline tone**: "Periodized training. Built for the top 5%." (matcha A215). Va bene riusare lo stesso messaging del paywall, o preferisci differenziare? Es. "Periodized training, scientific feedback." / "Hörst 4-3-2-1 for serious climbers." / altro?

**Q5 — Step indicator visual**: lo step-indicator attuale (progress bar + 14 dots) è già token-clean ma compete visivamente con l'hero (sticky in alto). Lo lascio com'è o nascondo step-indicator sulla welcome page (perché è step 1/14, dot di progresso minimo serve)?

**Q6 — Microcopy conciseness style**: nelle proposte ◐ ho convertito molte question→statement ("When do you train?" → "When you train"). È un pattern intenzionale (più direct, meno chatty) o preferisci mantenere lo stile question (più friendly per onboarding)?

**Q7 — Submit risk**: review/page.tsx ha 2 submit paths (`handleGenerate` "Start training now" / `handleTestWeek` "Run a test week first"). Niente cambia nella logica ma confermo che NON tocco `completeOnboarding` payload.

**Q8 — Discipline cards copy regression risk**: proposta di rimuovere "I want to" prefix ("I want to send harder routes" → "Sending harder routes"). Più tecnico ma meno self-identification. Meglio tenere la prima persona? È un trade-off voice/concision.

**Q9 — Card click states**: discipline + weaknesses cards usano `border-primary ring-2 ring-primary/30` che nel post-A214 magenta diventa molto saturo. Va bene downgrade a `border-brand bg-brand/5` (senza ring) per coerenza con WeeklyCheckinCard?

**Q10 — Recover stub**: `recover/page.tsx` (12 LoC) è un redirect a `/sign-in`. Il link nel welcome ("Already have an account? Recover access") va a `/onboarding/recover` → `/sign-in`. È una catena legacy. Tocco questo? (Default: no, fuori scope).

---

## 🛑 STOP GATE

Audit completo. Aspetto il review row-by-row di §7 (copy proposals) + risposte alle Q1–Q10 di §10. Phase 1 inizia solo dopo:

1. Tabella copy consolidata (approvazioni esplicite per le righe ◐ e ▪)
2. Conferma hero placement (Q3)
3. Conferma scope tokens (Q9 sui card click states)
4. Asset PNG caricato in `frontend/public/hero/`

Phase 1 stimata ~3-5h dopo lo STOP. Resta su Sonnet (low-medium risk, presentation+copy).
