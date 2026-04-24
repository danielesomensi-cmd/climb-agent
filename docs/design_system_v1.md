# climb-agent design system — v1 (Dark Performance)

> **Status:** A214 Phase 1 (foundation only — no screen redesigns).
> **Source of truth:** `frontend/src/app/globals.css`.
> **Live preview:** run `cd frontend && npm run dev`, then visit `http://localhost:3000/dev/tokens` (local-only, 404 on prod + Vercel preview).
> **Philosophy:** "Dark Performance" — athletic, premium, engineered. The default surface is a deep cool-navy (`hsl(222 28% 8%)` ≈ `#0f121a`), magenta magnifies action (CTAs, highlights), cyan supports it. Colors are saved for meaning — surfaces and text carry hierarchy, accents carry attention.

---

## 1. How to use tokens

All tokens are exposed as two layers:

1. **CSS variables** on `:root` (HSL channel-only for alpha-modifier support): `--surface-base`, `--accent-primary`, `--axis-finger`, etc.
2. **Tailwind utilities** via `@theme inline` in `globals.css`: `bg-surface-base`, `bg-brand`, `bg-axis-finger`, etc.

**Always prefer Tailwind utilities.** Reach for the CSS variable directly only when the utility system can't express what you need (e.g., `box-shadow: 0 0 20px hsl(var(--accent-primary) / 0.2)` in a one-off style tag).

**Never hardcode hex.** The only exception is `viewport.themeColor` in `src/app/layout.tsx`, which requires a static string (Next.js metadata doesn't read CSS vars).

---

## 2. Token reference

### 2.1 Surfaces

Page background → card → popover → recessed input.

| Token | CSS var | Utility | Use |
|-------|---------|---------|-----|
| `surface-base` | `--surface-base` = `222 28% 8%` | `bg-surface-base` | Page background (`<body>`) — bridged to `--background` → `bg-background` |
| `surface-raised` | `--surface-raised` = `222 25% 12%` | `bg-surface-raised` | Card surface — bridged to `--card` → `bg-card` |
| `surface-elevated` | `--surface-elevated` = `222 22% 16%` | `bg-surface-elevated` | Popover, modal, selected state — bridged to `--popover`, `--muted`, `--accent`, `--secondary` |
| `surface-inset` | `--surface-inset` = `222 30% 6%` | `bg-surface-inset` | Input recessed background, footer trays |

### 2.2 Foregrounds

| Token | CSS var | Utility | Use |
|-------|---------|---------|-----|
| `fg` | `--fg-primary` = `210 20% 98%` | `text-fg` | Headings, primary body text — bridged to `--foreground` → `text-foreground` |
| `fg-secondary` | `--fg-secondary` = `215 15% 75%` | `text-fg-secondary` | Supporting paragraph text |
| `fg-muted` | `--fg-muted` = `215 12% 55%` | `text-fg-muted` | Labels, captions, meta — bridged to `--muted-foreground` → `text-muted-foreground` |
| `fg-disabled` | `--fg-disabled` = `215 10% 35%` | `text-fg-disabled` | Disabled inputs, placeholder-style dims |

### 2.3 Borders

| Token | CSS var | Utility | Use |
|-------|---------|---------|-----|
| `border-subtle` | `--border-subtle` = `222 20% 18%` | `border-border-subtle` | Dividers, low-contrast separations |
| `border-default` | `--border-default` = `222 18% 25%` | `border-border-default` | Standard card + input borders — bridged to `--border` → `border-border` |
| `border-strong` | `--border-strong` = `222 15% 40%` | `border-border-strong` | Focused/selected borders |

### 2.4 Brand (primary accent — magenta)

**Renamed from brief's `accent` namespace** to avoid collision with shadcn's `bg-accent` used in ghost-button hover (`button.tsx`, `badge.tsx`, `toggle.tsx`).

| Token | CSS var | Utility | Use |
|-------|---------|---------|-----|
| `brand` | `--accent-primary` = `340 85% 58%` | `bg-brand`, `text-brand` | Scoped brand fills (badges, highlighted cards). **For CTAs, prefer `bg-primary` (shadcn alias).** |
| `brand-hover` | `--accent-primary-hover` = `340 85% 52%` | `bg-brand-hover` | Hover/pressed state for `bg-brand` |
| `brand-muted` | `--accent-primary-muted` = `340 60% 20%` | `bg-brand-muted` | Subtle brand tint (callout bg) |
| `brand-fg` | `--accent-primary-fg` = `0 0% 100%` | `text-brand-fg` | Text on `bg-brand` (white) |

### 2.5 Brand secondary (cyan)

| Token | CSS var | Utility | Use |
|-------|---------|---------|-----|
| `brand-secondary` | `--accent-secondary` = `190 90% 55%` | `bg-brand-secondary`, `text-brand-secondary` | Highlighted stats, graph accents, secondary brand moments |
| `brand-secondary-muted` | `--accent-secondary-muted` = `190 60% 18%` | `bg-brand-secondary-muted` | Subtle cyan tint |
| `brand-secondary-fg` | `--accent-secondary-fg` = `222 28% 8%` | `text-brand-secondary-fg` | Text on `bg-brand-secondary` (dark for readability on cyan) |

### 2.6 Functional colors

Each has a solid + muted pair. Use solid for high-emphasis signals (badges, dots); use muted for backgrounds with matching solid text.

| Token | Solid (HSL) | Utility | Use |
|-------|-------------|---------|-----|
| `success` | `145 65% 48%` | `bg-success` / `text-success` | Completed session, OK feedback |
| `success-muted` | `145 40% 15%` | `bg-success-muted` | Success banner background |
| `warning` | `40 90% 55%` | `bg-warning` / `text-warning` | Caveat, soft negative |
| `warning-muted` | `40 50% 15%` | `bg-warning-muted` | Warning banner background |
| `danger` | `0 75% 58%` | `bg-danger` / `text-danger` | Missed session, errors — bridged to `--destructive` |
| `danger-muted` | `0 45% 15%` | `bg-danger-muted` | Danger banner background |
| `info` | `210 85% 60%` | `bg-info` / `text-info` | Neutral info, tips |
| `info-muted` | `210 50% 15%` | `bg-info-muted` | Info banner background |

### 2.7 Training-axis colors (5)

Assessment radar, per-axis progress bars, axis legends.

| Axis | CSS var | Utility | Note |
|------|---------|---------|------|
| finger | `--axis-finger` = `285 75% 60%` | `bg-axis-finger`, `text-axis-finger` | Violet |
| pulling | `--axis-pulling` = `220 80% 62%` | `bg-axis-pulling` | Blue |
| power-endurance | `--axis-power-endurance` = `25 90% 58%` | `bg-axis-power-endurance` | Orange |
| endurance | `--axis-endurance` = `160 70% 50%` | `bg-axis-endurance` | Teal |
| technique | `--axis-technique` = `190 85% 55%` | `bg-axis-technique` | Cyan — aligns with brand-secondary |

**Only 5 axes.** The assessment engine has 5 axes (`finger_strength`, `pulling_strength`, `power_endurance`, `endurance`, `technique`). Recovery is not an axis — see §2.8 phase colors.

### 2.8 Phase colors (5)

Macrocycle timeline, phase badges, training-phase cues.

| Phase | CSS var | Utility |
|-------|---------|---------|
| aerobic | `--phase-aerobic` = `195 70% 55%` | `bg-phase-aerobic` |
| anaerobic-alactic | `--phase-anaerobic-alactic` = `340 80% 60%` | `bg-phase-anaerobic-alactic` |
| anaerobic-lactic | `--phase-anaerobic-lactic` = `25 90% 58%` | `bg-phase-anaerobic-lactic` |
| specific | `--phase-specific` = `285 75% 60%` | `bg-phase-specific` |
| recovery | `--phase-recovery` = `145 55% 55%` | `bg-phase-recovery` |

### 2.9 Glow

Used **sparingly** — only on primary CTAs, key cards, or selection states.

| Token | Utility | Value |
|-------|---------|-------|
| `shadow-glow-primary` | `shadow-glow-primary` | `0 0 24px -4px hsl(340 85% 58% / 0.35)` (magenta halo) |
| `shadow-glow-secondary` | `shadow-glow-secondary` | `0 0 24px -4px hsl(190 90% 55% / 0.35)` (cyan halo) |

**Do not use glow on body text, paragraph blocks, or non-interactive chrome.** It loses meaning if applied everywhere.

### 2.10 Shadow scale

| Token | Utility | Use |
|-------|---------|-----|
| `shadow-sm` | `shadow-sm` | Hairline lift for buttons, chips |
| `shadow-md` | `shadow-md` | Card elevation (default for `Card` components) |
| `shadow-lg` | `shadow-lg` | Dialog, drawer, modal elevations |

### 2.11 Radius scale

Flat values (no `calc()` cascade).

| Token | Value | Utility |
|-------|-------|---------|
| `sm` | `6px` | `rounded-sm` — chips, small pills |
| `md` | `10px` | `rounded-md` — default buttons, inputs (shadcn `--radius` aliases here) |
| `lg` | `16px` | `rounded-lg` — cards, sheets |
| `xl` | `24px` | `rounded-xl` — large prominent cards, hero sections |
| `pill` | `999px` | `rounded-pill` — capsules, status pills |

---

## 3. Usage rules

1. **CTAs use `bg-primary`** (shadcn alias → magenta). Never use `bg-brand` on a primary button — it renders the same color but routes via a different semantic channel. Reserved for `bg-brand` for badges, highlighted chips, or icon bubbles.
2. **`bg-accent` belongs to shadcn** (ghost-button hover, outline-button hover). **Do not override.** If you need a magenta hover, use `hover:bg-brand-hover` or `hover:bg-primary/90`.
3. **Axis colors only on assessment / progress UI.** Don't use `bg-axis-finger` as a generic violet — it's meaningful.
4. **Phase colors only on macrocycle / training-phase UI.** Same reasoning.
5. **Glow is sparing.** Every glow dilutes the next. Keep it to ~2 elements per viewport.
6. **No hardcoded hex.** If you catch yourself writing `#1a2e44`, stop and pick a token (or propose a new one).
7. **`dark:` variants are OK for now** if they already exist. Don't add new `dark:` in new code — always-dark means the base class suffices.

---

## 4. Migration guide — raw Tailwind palette → functional tokens

A214 deliberately does **not** migrate existing screens. ~357 raw-palette classes (`bg-red-500`, `text-green-400`, etc.) survive this brief and will be migrated per-screen in **A215 (Paywall)**, **A216 (Onboarding)**, **A217 (Today)**.

When migrating, use this mapping table:

| Old raw class | New token class | Notes |
|---------------|-----------------|-------|
| `bg-green-500` / `bg-green-600` / `bg-emerald-500/600` | `bg-success` | Completed, OK state |
| `text-green-400` / `text-green-500` / `text-emerald-400` | `text-success` | OK feedback |
| `bg-green-50` / `bg-green-950` | `bg-success-muted` | Success banners |
| `bg-amber-500` / `bg-yellow-500` | `bg-warning` | Warning state |
| `text-amber-400` / `text-yellow-400` / `text-yellow-200` | `text-warning` | Warning text |
| `bg-yellow-50` / `bg-yellow-950` / `bg-amber-50` / `bg-amber-950` | `bg-warning-muted` | Warning banners |
| `bg-red-500` / `bg-red-600` | `bg-danger` (or `bg-destructive` via shadcn) | Danger/error state |
| `text-red-400` / `text-red-500` / `text-red-800` / `text-red-200` | `text-danger` | Error text |
| `bg-red-50` / `bg-red-950` | `bg-danger-muted` | Error banners |
| `bg-blue-500` / `bg-sky-500` | `bg-info` | Informational state |
| `text-blue-400` / `text-blue-800` / `text-blue-200` | `text-info` | Informational text |
| `bg-blue-50` / `bg-blue-950` | `bg-info-muted` | Info banners |
| `bg-orange-500` / `text-orange-400` | `bg-axis-power-endurance` (**if contextual to PE axis**) OR `bg-warning` | Check context |
| `bg-purple-500` / `text-violet-400` | `bg-axis-finger` (**if contextual to finger axis**) OR keep raw until a real token exists | |
| `text-teal-400` | `bg-axis-endurance` OR `bg-brand-secondary` | Check context |
| `text-white` | `text-fg` or `text-foreground` | Semantic text-on-dark |
| `text-black` | `text-surface-base` or `text-background` | Rare in always-dark |
| `bg-black/20`, `bg-black/50` | `bg-surface-inset/20` or specific overlay token | Avoid raw `bg-black` |

**During per-screen migration:**
1. Grep the screen for all `bg-<color>-<n>` / `text-<color>-<n>` classes.
2. Replace with functional tokens per the table above (check context — orange may be warning OR PE axis).
3. Verify visual parity in dev before committing.

---

## 5. Removed / deprecated tokens

These **no longer exist** in the codebase (A214 removed them, confirmed 0 references):

- `--color-hold-red`, `--color-hold-green`, `--color-hold-orange`, `--color-hold-blue`
- `--color-wall-dark`, `--color-wall-card`
- `--color-rock-light`, `--color-chalk`

If you encounter legacy code referencing these (e.g., from a stale branch), replace with the closest A214 token:

| Legacy | Replacement |
|--------|-------------|
| `bg-hold-red` | `bg-brand` or `bg-danger` (context-dependent) |
| `bg-wall-dark` | `bg-surface-base` |
| `bg-wall-card` | `bg-surface-raised` |
| `text-chalk`, `text-rock-light` | `text-fg` |

---

## 6. Caveats & gotchas

### Namespace collision: `brand` vs `accent`

The original brief named the primary accent namespace `accent`, but shadcn already uses `bg-accent` / `text-accent-foreground` in ghost-button hover states (`button.tsx`, `badge.tsx`, `toggle.tsx`). Overriding `bg-accent` to magenta would change every ghost hover in the app — a silent component regression violating §4.6 of the brief.

**Resolution:** the Tailwind namespace is `brand`. CSS variable names stay as `--accent-primary-*` (matching brief terminology). Shadcn `bg-accent` remains gray (`hsl(var(--surface-elevated))`), unchanged.

### `dark:` variants remain in 20 locations

All currently **active** (e.g., onboarding warning banners with `bg-yellow-50 dark:bg-yellow-950` — the light half is dead code since `<html class="dark">` is hardcoded, but the dark half is live). Scheduled for cleanup in A215+ when screens migrate to functional tokens (the `bg-yellow-950` becomes `bg-warning-muted`, dropping the `dark:` prefix entirely).

### Radius shift from previous system

Current app used `--radius: 0.625rem` → shadcn derived `rounded-md = 8px`, `rounded-lg = 10px`, `rounded-xl = 14px`. A214 flattened to `md=10, lg=16, xl=24`. **Visible consequence:** cards, sheets, and dialogs have slightly more generous rounding. `rounded-sm` (6px) stays identical.

### Tailwind v4 (no `tailwind.config.ts`)

All theme extension lives in `@theme inline { … }` inside `globals.css`. If you add a new token, add both:
1. The raw value in `:root` (HSL channel-only).
2. The utility bridge in `@theme inline` (`--color-<name>: hsl(var(--<name>));`).

### The `@custom-variant dark` directive

Preserved intentionally in `globals.css` even though the app is always dark. Shadcn UI components (e.g., `button.tsx` line 16) ship `dark:` classes internally. Removing the custom-variant would orphan those rules. Always-dark + variant-present is the safe configuration.

### Adding new tokens

Checklist:
1. Add raw HSL channel value to `:root`.
2. Add `--color-<name>: hsl(var(--<name>));` to `@theme inline` (or `--shadow-<name>`, `--radius-<name>`).
3. Update `/dev/tokens/page.tsx` to include a swatch (so the preview stays complete).
4. Update this doc (§2 token reference).
5. Add usage rule in §3 if the new token needs scope enforcement.

---

## 7. References

- **Brief:** A214 in `docs/ROADMAP_CURRENT.md` (Phase 1.75 Phase 1 section)
- **Phase 0 audit:** `docs/A214_phase0_audit.md`
- **Live showcase:** `/dev/tokens` (local dev only)
- **Source:** `frontend/src/app/globals.css`
- **Downstream briefs (planned):** A215 Paywall redesign, A216 Onboarding redesign, A217 Today redesign
