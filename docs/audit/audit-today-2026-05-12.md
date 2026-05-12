# Audit visuale `/today` — 2026-05-12

> **Status:** Backlog informale (non-brief)
> **Tool:** skill `example-skills:frontend-design` (validata utile per identità visuale, marginale per a11y standard)
> **Target review:** post-launch + 30 giorni → convertire in brief A-design quando avremo dati reali su retention iniziale
> **Files audited:** `frontend/src/app/(main)/today/page.tsx` (1310 righe), `frontend/src/components/training/today-hero-cta.tsx` (253 righe)
> **Fix immediato applicato:** P1 #5 (touch target dismiss `×` da 24px → 44px) — committed insieme a questo file

---

## 🔴 P0 — Issue critiche

### 1. Banner stacking incontrollato

**Where:** `page.tsx:939-1083`

Fino a **5 banner consecutivi** nei primi 200px (checkout success, new-macrocycle CTA, resume-session, boulder-phase-tip, feedback-edu), tutti con varianti visuali simili: `rounded-lg border xxx/30 bg xxx/5 p-3`. Nessuna gerarchia: "urgente" (resume session in progress) e "informativo" (boulder phase tip) sembrano identici. L'utente arriva su /today e vede una parete di rettangoli colorati prima del contenuto vero.

**Fix proposta:**
- Mutua esclusione: `resume-session` (azione critica in corso) annulla tutti gli altri
- Sposta `boulderPhaseTip` (L1046) e `feedbackEduDismissed` (L1066) **dopo** `DayCard` (L1086) — sono "educational", non "actionable"
- Cap a 1 banner attivo sopra il fold

### 2. Hero atmosferica relegata a fondo pagina

**Where:** `page.tsx:1159-1188`

L'immagine + quote (unico elemento con identità climbing reale) è renderizzata DOPO tutto il funzionale, con `aspect-[4/5]` (verticale). Su offday/empty_week l'utente non scrolla mai fin lì → la componente più emotiva è invisibile per la maggior parte dei giorni.

**Fix proposta:**
- Porta hero+quote in cima (sotto TopBar) con `aspect-[3/2]` invece di `4/5` per non rubare il fold
- Diventa "atmosphere setter" giornaliero, non outro nascosto

---

## 🟡 P1 — Coerenza shadcn & accessibilità

### 3. Bottoni inline ad-hoc invece di `<Button>` shadcn

**Where:** `page.tsx:955-963, 977-994, 1009-1014, 1026-1031`

5 varianti di bottone scritte a mano: `rounded-md bg-X px-3 py-1.5 text-xs` vs `px-4 py-2 text-sm` vs `text-sm underline`. shadcn/ui esporta `<Button variant size>` già; non è usato qui.

**Fix proposta:** refactor a `<Button variant="default|outline|ghost|link" size="sm|default">`. Audit di tutte le occorrenze button-like in `app/` e `components/`.

### 4. Pattern Banner non astratto

**Where:** `page.tsx:949, 969, 1047, 1067`

4 banner identici per struttura. shadcn ha `<Alert>` con `variant` + `<AlertTitle>` + `<AlertDescription>`.

**Fix proposta:** estrai `<DismissibleAlert variant="info|warning|promo">` o usa `Alert` shadcn — elimina ~80 righe di duplicazione.

### 5. ~~Touch target dismiss `×` sotto soglia~~ ✅ FIXED 2026-05-12

**Where:** `page.tsx:1054-1061, 1074-1081`

`h-6 w-6` = 24×24px. Apple HIG min 44pt, WCAG 2.5.5 AAA 44×44px.

**Fix applicato:** `h-11 w-11` (44px), riposizionato `right-1 top-1`, banner `pr-10` → `pr-12` per accomodare. Mantiene `aria-label="Dismiss"`.

**Rationale immediato:** climber in palestra con dita sporche di magnesite/sudore deve poter chiudere i banner al primo touch — frustration immediata altrimenti.

### 6. Typography senza scala

Mix incoerente: `text-xs`, `text-sm`, `text-base`, `text-lg` con `font-medium` sparsi senza ramp tipografica. Font stack: default shadcn (Inter / system) — citato dalla skill `frontend-design` come "generic AI aesthetic".

**Fix proposta:**
- Definisci type scale in `tailwind.config` con nomi semantici (`text-display`, `text-h1`, `text-body`, `text-caption`)
- Considera font display distintivo per heading (es. una grotesque tipo Söhne, ABC Diatype, GT Walsheim — non Space Grotesk che è anch'esso "AI slop")
- Separa identità climb-agent dal generic shadcn look

### 7. Hero image overlay → contrast risk

**Where:** `page.tsx:1170-1177`

Gradient hardcoded `transparent 40% → hsl(surface-base) 100%` con `text-fg` italic sopra. Su iPhone OLED in modalità chiara o con immagini chiare la quote può scendere sotto WCAG AA 4.5:1.

**Fix proposta:**
- Forza dark overlay esplicito (`bg-black/60` sotto il testo)
- Test contrasto con lighthouse / axe

---

## 🟢 P2 — Refinement

### 8. Loading state spinner generico

**Where:** `page.tsx:999-1003`

Full-page spinner senza skeleton. shadcn ha `<Skeleton>` già pronto.

**Fix proposta:** skeleton del DayCard + WeekProgressBar invece dello spinner.

### 9. Empty state "Welcome" anonimo

**Where:** `page.tsx:1020-1033`

Border-dashed grigio + due righe testo + CTA. Primo touch con l'app, momento più importante della retention iniziale, ed è la cosa più anonima della pagina.

**Fix proposta:** usa hero image qui in modo enfatico + welcome message tipografico personalizzato. È l'unico screen che vedrà un nuovo utente per ~3 secondi prima di decidere se completare l'onboarding.

### 10. Z-index magic number

**Where:** `page.tsx:939`

`<main className="relative z-10">` senza motivo documentato. Manca stack z-index (TopBar sticky? bottom-nav? hero overlay?).

**Fix proposta:** definisci 4-5 layer in `globals.css`:
```css
--z-base: 1;
--z-sticky: 10;
--z-overlay: 40;
--z-modal: 50;
```
e usali invece di numeri magici.

### 11. Safe-area su iOS

**Where:** `page.tsx:939`

`p-4` senza `pb-safe` per home-indicator iPhone. Se c'è bottom-nav fissa il contenuto può finire sotto.

**Fix proposta:** `pb-[calc(env(safe-area-inset-bottom)+5rem)]` o utility custom `pb-safe`.

---

## Note metodologiche

### Verdetto skill `frontend-design`

**Valore aggiunto:**
- ✅ Lente "anti-AI-slop" su typography (Inter generico → font display distintivo)
- ✅ Insight su gerarchia atmosferica (hero a fondo pagina = sprecata)
- ✅ Focus su "intentionality" — banner stacking smaschera lack of design intent

**Non aggiunto** (sarebbe emerso comunque da un audit normale):
- Touch target a11y (regola WCAG nota)
- Refactor a Button shadcn (compliance pattern)
- Skeleton vs spinner (best practice generale)

**Decisione:** la skill ha valore SE inizi a investire su identità visuale (font, atmosphere, tone-of-voice). Se /today resta funzionale-shadcn-default, la skill è marginale. **Non aggiunta a CLAUDE.md.** Riportala dentro quando affronti un brief A-design tipo "ridisegna /today con identità climb-agent" o "rebranding visual".

### Trigger di review

- **Quando:** Stripe LIVE + 30 giorni → ~2026-05-16
- **Perché:** entro quella data avremo dati su retention iniziale, conversione trial→paid, friction nel primo touch. L'audit va validato/declassato con dati reali, non con ipotesi.
- **Come:** convertire questo file in brief A-design strutturato (con ID via `next_brief.py`), prioritizzare le issue P0/P1 in base a quale punto di frizione i dati confermano.
