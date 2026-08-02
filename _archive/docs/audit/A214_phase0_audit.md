# A214 — Phase 0 Audit Report

**Date:** 2026-04-24
**Scope:** Read-only audit of the frontend design layer before A214 Phase 1 implementation.
**Author:** Claude Code (Opus 4.7)
**Status:** **STOP GATE** — awaiting Daniele's explicit "OK, procedi con Phase 1".

---

## Executive summary

Il brief è scritto per **Tailwind v3 + `tailwind.config.ts`**, ma il frontend usa **Tailwind v4** con configurazione CSS-first (`@theme` directive in `globals.css`). Nessun `tailwind.config.ts` esiste nel repo. Questo è il delta più grande: §4.2 del brief va **riscritto** in sintassi v4 (tutto dentro `globals.css`).

Buone notizie:
- **Zero `light:` variants** nel codebase → §4.3 è quasi no-op.
- **Nessun `next-themes` / toggle UI** → non c'è niente da rimuovere, solo `:root` light + `.dark` da collassare in un unico `:root` dark.
- **Solo 2 hex hardcoded** fuori da `globals.css` e dalla `/demo` page (entrambi trascurabili).
- shadcn aliases already in place → remap trasparente funziona come da brief §4.2.

Rischio principale: il colore base attuale è **#1a1a2e ≈ HSL(240 28% 14%)**, mentre il brief propone **`220 30% 7%` ≈ #0c1019** (notevolmente più scuro e più blu-verdastro). Serve conferma visual direction prima di spingere.

---

## §3.1 Tailwind config audit

**Result: nessun `tailwind.config.ts/js` presente.**

```bash
$ ls frontend/tailwind.config.*
no matches found
```

**Tailwind v4 setup confermato:**

| Fonte | Valore |
|-------|--------|
| `frontend/package.json` | `"tailwindcss": "^4"`, `"@tailwindcss/postcss": "^4"` |
| `frontend/postcss.config.mjs` | presente (configurazione PostCSS standard v4) |
| `frontend/src/app/globals.css` | `@import "tailwindcss"`, `@theme inline { … }` |
| `frontend/components.json` | `"tailwind.config": ""` (intenzionalmente vuoto — coerente con v4) |

**Tutta la "config" (theme extension) vive in `@theme inline { … }` dentro `globals.css` (righe 7-58).**

Entrate attualmente definite nel blocco `@theme`:

| Categoria | Token definiti |
|-----------|----------------|
| Colors (shadcn aliases) | `background`, `foreground`, `card`, `card-foreground`, `popover`, `popover-foreground`, `primary`, `primary-foreground`, `secondary`, `secondary-foreground`, `muted`, `muted-foreground`, `accent`, `accent-foreground`, `destructive`, `border`, `input`, `ring` |
| Colors (chart) | `chart-1..5` |
| Colors (sidebar) | `sidebar`, `sidebar-foreground`, `sidebar-primary`, `sidebar-primary-foreground`, `sidebar-accent`, `sidebar-accent-foreground`, `sidebar-border`, `sidebar-ring` |
| Colors (climbing) | `hold-red #e94560`, `hold-green #10b981`, `hold-orange #f59e0b`, `hold-blue #3b82f6`, `wall-dark #1a1a2e`, `wall-card #0f3460`, `rock-light #faf5f0`, `chalk #f5f0eb` |
| Fonts | `sans: var(--font-geist-sans)`, `mono: var(--font-geist-mono)` (solo `Inter` caricato via `next/font/google` in `layout.tsx`) |
| Radius | `sm`, `md`, `lg`, `xl`, `2xl`, `3xl`, `4xl` — tutti derivati da `var(--radius)` = `0.625rem` |
| Screens / breakpoints | default v4 (mobile-first, standard sm/md/lg/xl/2xl) — nessuna override |

**Hook `hsl(var(--xxx) / <alpha-value>)`:** **non usato**. I token shadcn sono definiti come valori diretti (hex, `oklch()`, `rgba()`) — non come channel-only. Questo è uno shift stilistico rispetto alla proposta del brief (§4.1 richiede channel-only HSL per supportare `bg-surface-raised/80`).

**Custom variant:** `@custom-variant dark (&:is(.dark *));` (riga 5) — pattern Tailwind v4 per far rispettare `.dark` sul root.

---

## §3.2 globals.css variables audit

Posizione: `frontend/src/app/globals.css` (140 righe totali).

### Struttura

| Blocco | Righe | Contenuto |
|--------|-------|-----------|
| `@import` | 1-3 | `tailwindcss`, `tw-animate-css`, `shadcn/tailwind.css` |
| `@custom-variant dark` | 5 | Dark scope tramite `.dark` class ancestor |
| `@theme inline` | 7-58 | Mapping Tailwind v4: `--color-*` ridireziona a `var(--*)` shadcn + 8 token climbing hardcoded |
| `:root` | 60-93 | **Palette LIGHT** (cream/red) |
| `.dark` | 95-127 | **Palette DARK** (navy/magenta) |
| `@layer base` | 129-139 | `* { border-border outline-ring/50 }`, `body { bg-background text-foreground }`, antialiasing |

### `:root` (light — attivo solo se `.dark` non è applicato a `<html>`)

```css
--radius: 0.625rem;
--background: #faf5f0;      /* cream */
--foreground: oklch(0.145 0 0);
--card: #ffffff;
--primary: #e94560;          /* magenta */
--secondary: oklch(0.97 0 0);
--muted: oklch(0.97 0 0);
--accent: oklch(0.97 0 0);
--destructive: oklch(0.577 0.245 27.325);
--border: oklch(0.922 0 0);
--input: oklch(0.922 0 0);
--ring: #e94560;
--chart-1..5: #e94560 / #10b981 / #f59e0b / #3b82f6 / #8b5cf6
--sidebar: oklch(0.985 0 0) (+ altri 7 token sidebar)
```

### `.dark` (dark — **sempre attiva in produzione**)

```css
--background: #1a1a2e;        /* wall-dark */
--foreground: #f5f0eb;         /* chalk */
--card: #0f3460;               /* wall-card */
--popover: #0f3460;
--primary: #e94560;            /* magenta */
--secondary: #16213e;
--muted: #16213e;
--muted-foreground: #a0a0b8;
--accent: #16213e;
--destructive: oklch(0.704 0.191 22.216);
--border: rgba(255, 255, 255, 0.1);
--input: rgba(255, 255, 255, 0.15);
--ring: #e94560;
--chart-1..5 (stessi valori di :root)
--sidebar-* (sidebar: #0f3460, primary: #e94560, etc.)
```

### Pattern shadcn/ui in uso

Sì — **shadcn "New York" style, `baseColor: "neutral"`, `cssVariables: true`** (da `components.json`). I token chiave (`--background`, `--foreground`, `--primary`, `--muted`, `--border`, `--ring`, `--card`, `--popover`, `--destructive`) sono tutti definiti. Il remap che §4.2 del brief propone (alias di `--background` → `var(--surface-base)`) è compatibile e minimamente invasivo.

### `@layer` customizations

Solo una: `@layer base` con selector globale `* { @apply border-border outline-ring/50 }` + override `body`. Nessun altro custom layer.

### Formato valori

Mix attuale: **hex** (`#e94560`, `#1a1a2e`, `#f5f0eb`) + **`oklch()`** (11 occorrenze) + **`rgba()`** (2 occorrenze: border/input su dark). Il brief richiede HSL channel-only. Decisione format da prendere in Phase 1 (vedi §6).

---

## §3.3 Color usage grep

### Top-30 utility color classes (mobile frontend/src, solo `bg-*`, `text-*`, `border-*`, `ring-*`, `shadow-*`, `from-*`, `to-*`, `via-*`)

| Rank | Class | Count |
|------|-------|-------|
| 1 | `text-muted-foreground` | 443 |
| 2 | `text-sm` (size, non-color — filtrato fuori) | 346 |
| 3 | `text-xs` (size) | 342 |
| 4 | `text-center` (layout) | 102 |
| 5 | `text-foreground` | 79 |
| 6 | `text-primary` | 56 |
| 7 | `text-white` | 30 |
| 8 | `text-destructive` | 30 |
| 9 | `bg-card` | 26 |
| 10 | `text-red-400` | 25 (raw palette) |
| 11 | `bg-red-500` | 25 (raw palette) |
| 12 | `bg-green-500` | 23 (raw palette) |
| 13 | `text-amber-400` | 20 (raw palette) |
| 14 | `border-primary` | 20 |
| 15 | `bg-background` | 20 |
| 16 | `border-border` | 19 |
| 17 | `bg-primary` | 19 |
| 18 | `bg-muted` | 17 |
| 19 | `bg-orange-500` | 17 (raw palette) |
| 20 | `bg-green-600` | 17 (raw palette) |
| 21 | `border-primary/30` | 16 |
| 22 | `text-green-400` | 15 |
| 23 | `text-orange-400` | 14 |
| 24 | `text-green-500` | 14 |
| 25 | `bg-primary/5` | 14 |
| 26 | `bg-destructive/10` | 13 |
| 27 | `text-primary-foreground` | 12 |
| 28 | `text-red-500` | 12 |
| 29 | `bg-yellow-500` | 12 |
| 30 | `bg-amber-500` | 12 |

**Key insight:** ~2/3 delle classi più usate sono **già token-based** (via shadcn aliases: `*-foreground`, `*-primary`, `*-card`, `*-muted`, `*-destructive`, `*-border`, `*-background`). Il remap proposto nel brief §4.2 le assorbe trasparentemente — zero component changes richieste per A214.

### Raw Tailwind palette usage (da migrare in A215+, NON in A214)

| Pattern | Count |
|---------|-------|
| `bg-<color>-<n>` | **163 occorrenze** (top: red-500 25, green-500 23, orange-500 17, green-600 17, yellow-500 12, amber-500 12, green-700 8, emerald-500 8) |
| `text-<color>-<n>` | **194 occorrenze** (top: red-400 25, amber-400 20, green-400 15, orange-400 14, green-500 14, red-500 12, yellow-400 11, emerald-400 11) |
| **Totale palette raw** | **357** |

Questi sopravvivono ad A214 (§4.6: no component changes). Verranno migrati a `bg-success`, `bg-warning`, `bg-danger`, `bg-info` nei brief A215/A216/A217 durante il redesign per-screen.

### Hardcoded hex colors

**Total: 59 righe con `#RRGGBB` / `#RGB` in `frontend/src/**/*.{tsx,ts,css}`.**

Breakdown per file:

| File | Count | Note |
|------|-------|------|
| `src/app/globals.css` | 49 | **Attesi** — definizioni dei token (hold-*, wall-*, rock-light, chalk, background, primary, etc.) |
| `src/app/demo/page.tsx` | 5 | **Intenzionali** — `/demo` Editorial Dark standalone (B-DEMO-05) |
| `src/app/demo/layout.tsx` | 2 | **Intenzionali** — demo layout |
| `src/components/guided/exercise-timer.tsx` | 1 | Da migrare in A217 — vale la pena auditare in Phase 1 |
| `src/app/layout.tsx` | 1 | `viewport.themeColor: "#1a1a2e"` — va aggiornato al nuovo `--surface-base` in Phase 1 (deriva dal token) |

**Hex count reale fuori demo + globals = 2.** Trascurabile.

### Top-5 shadcn/ui components (by import count)

| Component | Imports |
|-----------|---------|
| `button` | 60 |
| `card` | 30 |
| `label` | 23 |
| `input` | 18 |
| `badge` | 18 |

Segue: `dialog` (12), `select` (9), `drawer` (9), `switch` (7), `slider` (4).

**17 componenti shadcn installati** in `frontend/src/components/ui/`. Nessuno di loro richiede modifiche in A214 — leggono da shadcn aliases che il brief ridireziona trasparentemente.

---

## §3.4 Dark/light mode usage

### Toggle logic

| Check | Result |
|-------|--------|
| `next-themes` in `package.json` | **Non presente** |
| `useTheme` grep in `src/` | **0 match** |
| `ThemeProvider` grep | **0 match** |
| `prefers-color-scheme` grep | **0 match** |
| `setTheme` grep | **0 match** |
| `theme-toggle` / `ThemeToggle` | **0 match** |
| Sun/Moon icon come toggle UI | **0** (tutte le occorrenze `Sun/Moon` sono etichette "Sunday" o `board_moonboard` icon) |

**Conclusione: non esiste toggle UI né state management per il tema.** Dark è forzata hardcoded via `<html lang="en" className="dark">` in `src/app/layout.tsx:58`. Il blocco `:root` (light) nel CSS è **codice morto a runtime**.

### Light/dark Tailwind variants

| Pattern | Count | Note |
|---------|-------|------|
| `light:*` | **0** | Zero variants da rimuovere |
| `dark:*` | **20** | Residuali — non dannose (dark sempre attiva), ma candidati a cleanup cosmetico |

**Estimate removal effort:** **< 30 min**. Merge `.dark` dentro `:root`, eliminare blocco `:root` light, eliminare `@custom-variant dark`, pulire le 20 `dark:` (cambio cosmetico: `bg-black dark:bg-white` → `bg-white`).

Il brief §4.3 parla di "Remove any theme-toggle UI component (the sun/moon icon in the top right of screens — see Today, Plan, Week screens)". **Questo componente non esiste nel codice attuale** — l'istruzione è un no-op. Da confermare che non è un'istruzione out-of-date (es. riferita a uno screenshot vecchio).

---

## §3.5 Risk flags & proposed delta

### 🚨 Risk flag 1 — Tailwind v4, non v3

**Impatto:** §4.2 del brief (`frontend/tailwind.config.ts` extension) **non è applicabile come scritto**.

**Proposta:** Riscrivere §4.2 come estensione del blocco `@theme inline` in `globals.css`:

```css
@theme inline {
  /* existing shadcn aliases rimangono … */

  /* NEW — Surface scale */
  --color-surface-base: hsl(var(--surface-base));
  --color-surface-raised: hsl(var(--surface-raised));
  --color-surface-elevated: hsl(var(--surface-elevated));
  --color-surface-inset: hsl(var(--surface-inset));

  /* NEW — Foreground scale */
  --color-fg: hsl(var(--fg-primary));
  --color-fg-secondary: hsl(var(--fg-secondary));
  --color-fg-muted: hsl(var(--fg-muted));
  --color-fg-disabled: hsl(var(--fg-disabled));

  /* NEW — Accents, functional, axis, etc … */

  /* NEW — Radius overrides */
  --radius-sm: var(--radius-sm);
  --radius-md: var(--radius-md);
  --radius-lg: var(--radius-lg);
  --radius-xl: var(--radius-xl);
  --radius-pill: var(--radius-pill);

  /* NEW — Shadows */
  --shadow-glow-primary: var(--shadow-glow-primary);
  --shadow-glow-secondary: var(--shadow-glow-secondary);
}
```

**Attenzione:** in Tailwind v4, l'alpha-modifier (es. `bg-surface-raised/80`) funziona su qualsiasi color definito in `@theme` tramite `--color-*`, purché il valore sia in un formato con alpha-channel supportato (RGB/HSL/OKLCH senza wrapper custom). Usando `hsl(var(--surface-base))` con `--surface-base` in formato channel-only (`220 30% 7%`), Tailwind v4 estrae automaticamente H/S/L e applica alpha. Questo preserva l'intento del brief senza la sintassi v3 `hsl(var(--x) / <alpha-value>)`.

Conflitto esistente con i radius — `@theme inline` già definisce `--radius-sm = calc(var(--radius) - 4px)` (righe 41-47). Da **sostituire** con i nuovi valori espliciti del brief:
- `--radius-sm: 6px` (vs attuale `calc(0.625rem - 4px) = 6px` — coincide ✅)
- `--radius-md: 10px` (vs attuale `calc(0.625rem - 2px) = 8px` — **cambia**)
- `--radius-lg: 16px` (vs attuale `0.625rem = 10px` — **cambia**)
- `--radius-xl: 24px` (vs attuale `calc(0.625rem + 4px) = 14px` — **cambia**)

**Da decidere:** adottare i nuovi radius più generosi (16/24px per lg/xl) — visually more premium, ma cambia il look di tutti i card+dialog in modo visibile anche senza ridisegnare. Alternativa: mantenere i radius correnti in A214 e riallineare per-screen in A215+.

### 🚨 Risk flag 2 — Surface palette shift visibile

- **Current `--background` (dark):** `#1a1a2e` ≈ `HSL(240 28% 14%)` (navy con forte componente blu-rosso)
- **Proposed `--surface-base`:** `HSL(220 30% 7%)` ≈ `#0c1019` (quasi nero, molto più cool)

Differenza percepita: brief propone superficie **~2× più scura** e shift hue 240°→220° (meno rosso, più ciano). Anche senza ridisegnare screen, tutto apparirà **più buio e "pro"**. Gli utenti beta (Christie, Cesar, Paolo, Agustin) noteranno.

**Proposta:** approvare palette così com'è, oppure regolare: se vogliamo preservare la sensazione "navy classic" attuale, alternativa `HSL(230 25% 9%)` ≈ `#111624`.

### 🚨 Risk flag 3 — Climbing tokens legacy (`--color-hold-*`, `--color-wall-*`, `--color-chalk`, `--color-rock-light`)

**Status:** 8 token definiti in `@theme`, **ZERO reference in `frontend/src` outside globals.css**. Sono codice morto.

**Proposta:** in Phase 1, **rimuoverli dal `@theme inline`** (pulizia). Se serve retro-compatibilità, aggiungere aliases:
- `--color-hold-red` → `var(--color-accent)` (magenta)
- `--color-wall-dark` → `var(--color-surface-base)`
- etc.

Decisione Daniele.

### 🚨 Risk flag 4 — Raw Tailwind palette (357 occorrenze)

`bg-red-500`, `text-green-400`, `bg-amber-500`, etc. Sopravvivono ad A214 (default Tailwind palette) ma **non si agganciano al nuovo sistema functional** (`bg-success`, `bg-warning`, `bg-danger`, `bg-info`).

**Proposta:** rispettare §4.6 (no component changes). Migrazione funzionale in A215 (Paywall)/A216 (Onboarding)/A217 (Today). Documentare nella `design_system_v1.md` la mapping atteso:
- `bg-green-5xx/6xx` + `text-green-4xx/5xx` → `bg-success` / `text-success`
- `bg-red-5xx` + `text-red-4xx/5xx` → `bg-danger` / `text-danger`
- `bg-amber-5xx` + `bg-yellow-5xx` + `text-amber-4xx` + `text-yellow-4xx` → `bg-warning` / `text-warning`
- `bg-orange-5xx` + `text-orange-4xx` → `bg-warning` (o asse power-endurance se contestuale)
- `bg-blue-5xx` + `text-blue-4xx` → `bg-info`

### 🚨 Risk flag 5 — Training-axis colors: 6 vs 5 assi

Il brief §4.1 definisce **6 axis color** (finger, pulling, power-endurance, endurance, technique, recovery). Ma l'assessment engine (`assessment_v1.py`) ha **5 assi**: `finger_strength`, `pulling_strength`, `power_endurance`, `technique`, `endurance` (vedi CLAUDE.md riga 111).

**`recovery` non è un asse assessment** — è un fase/stato di deload. Va bene averlo come color, ma va classificato separatamente (es. "phase color" invece di "axis color") per evitare drift quando A215+ farà il radar.

**Proposta:** in `design_system_v1.md`, distinguere:
- **Axis colors** (5): `finger`, `pulling`, `power-endurance`, `endurance`, `technique` → usati per radar, progress bars per-axis.
- **Phase/state colors** (1 per ora): `recovery` → usato per deload week badge, rest day card.

Aggiungere eventualmente `performance`, `base`, `strength`, `pe`, `deload` come fase-color nel sistema se serve (ma fuori scope A214 — solo quando un brief di UI specifica li richiederà).

### 🚨 Risk flag 6 — `viewport.themeColor` hardcoded in layout.tsx

`src/app/layout.tsx:44`: `themeColor: "#1a1a2e"` — hardcoded. Dopo lo shift a `--surface-base = 220 30% 7%`, questo valore **non combacia più** con la chrome del PWA (status bar color su iOS).

**Proposta:** in Phase 1, aggiornare a `#0c1019` (o al valore deciso per `--surface-base`). Piccolo ma importante per coerenza visual PWA. Non duplicabile automaticamente (Next metadata non legge CSS variables).

### 🚨 Risk flag 7 — `/dev/tokens` route gating

Il brief §4.4 richiede `process.env.NODE_ENV !== "production"` → 404 in prod. In Next.js 16 App Router questo pattern si implementa con `notFound()` da `next/navigation` nel page component. È **funzionante** ma sconsigliato: espone la pagina a potenziali leak in development builds pubblicati (es. preview Vercel).

**Alternativa più robusta:** gate tramite variabile d'ambiente esplicita `NEXT_PUBLIC_SHOW_DEV_ROUTES=1` (settabile su preview, non su prod). Oppure, gate via auth Clerk (solo l'owner dell'app). Decisione cosmetica — default del brief va bene per ora.

### Proposed delta summary

| Brief §  | Status | Delta |
|---------|--------|-------|
| §3 Phase 0 audit | ✅ This doc | — |
| §4.1 CSS vars | 🟡 Adjust | Formato channel-only HSL OK, ma richiede decisione su palette shift (Flag 2), radius shift (Flag 1) |
| §4.2 Tailwind config | 🔴 **Rewrite** | Tailwind v4 → spostare in `@theme inline` di `globals.css` (Flag 1) |
| §4.2 shadcn aliases | 🟢 OK | Remap diretto, compatibile con v4 |
| §4.3 Dark/light removal | 🟢 Mostly no-op | Zero `light:`, zero `next-themes`, zero toggle UI. Solo merge `.dark` → `:root` + cleanup 20 `dark:` residuali. Rimuovere anche `:root` light blocco (dead code) + `@custom-variant dark` |
| §4.4 /dev/tokens | 🟢 OK | Gate con `notFound()` in page component, aggiungere sezione "Phase colors" se utile |
| §4.5 design_system_v1.md | 🟢 OK | Aggiungere mapping raw-palette→functional e note su axis vs phase colors (Flag 5) |
| §4.6 No component changes | 🟢 OK | Confermato fattibile; 357 raw-palette classes restano come sono |

---

## §3.6 Commit strategy adjustment

Il brief propone 6 commit (§6). Suggerisco:

1. `chore(A214): Phase 0 audit report` (questo doc)
2. `feat(A214): add design tokens in @theme (surface, fg, accent, functional, axis, glow, radius, shadow)`
3. `refactor(A214): remap shadcn aliases to new tokens, drop dead :root light block`
4. `chore(A214): enforce dark-only (remove @custom-variant dark, cleanup 20 dark: variants)`
5. `feat(A214): /dev/tokens showcase page`
6. `docs(A214): design_system_v1.md + raw-palette migration guide`

Note:
- Commit 3 collassa `.dark` in `:root` come unica palette.
- Commit 4 gestisce i 20 `dark:` residuali (cambio cosmetico).
- Commit 5-6 indipendenti, possono essere mergeati separatamente.

**Branch name:** `brief/A214-visual-tokens-foundation`.

**Preview Vercel:** obbligatoria (CLAUDE.md branch workflow, touched `frontend/`). Preview URL va testato su iPhone PWA installata prima del merge.

---

## §3.7 Decisioni richieste prima di Phase 1

1. **Palette shift (Risk flag 2):** adottare `HSL(220 30% 7%)` del brief (più scuro/cool), oppure regolare verso `HSL(230 25% 9%)` per preservare l'attuale feeling navy?
2. **Radius shift (Risk flag 1):** adottare `md=10 / lg=16 / xl=24` del brief (più premium) oppure mantenere i valori attuali (`md=8 / lg=10 / xl=14`) in A214 e riallineare per-screen in A215+?
3. **Climbing tokens legacy (Risk flag 3):** eliminare `hold-*`, `wall-*`, `chalk`, `rock-light` in Phase 1, oppure mantenere come aliases per 1 brief prima di dismetterli?
4. **Axis vs phase colors (Risk flag 5):** separare `recovery` come "phase color" in `design_system_v1.md` (raccomandato), oppure lasciarlo nella sezione axis come fa il brief?
5. **Training-axis color count:** il brief elenca 6 axis colors ma l'engine ne ha 5. Confermo riduzione a 5 assi?
6. **`/dev/tokens` gate (Risk flag 7):** `NODE_ENV !== "production"` via `notFound()` OK, o vuoi un gate più stringente (env var dedicata / Clerk owner)?
7. **`viewport.themeColor` (Risk flag 6):** aggiornare in questo brief (Phase 1), oppure lasciarlo ad A217 quando tocchiamo `layout.tsx`?
8. **Commit granularity:** OK 6 commit proposti, o preferisci raggruppare?

---

## STOP GATE

**Non procedo con Phase 1 finché non ricevo "OK, procedi con Phase 1" esplicito da Daniele + risposta (anche sintetica) alle 8 decisioni sopra.**

Una volta approvato, Phase 1 stimata ~1 giornata (8h wall-clock) con test manuale su preview Vercel + iPhone PWA prima del merge.
