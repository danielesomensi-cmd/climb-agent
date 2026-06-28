# Handoff: climb-agent `/demo` redesign — Direction A (Editorial Dark)

## Overview

Redesign of the public `/demo` page at `climb-agent.vercel.app/demo` — the primary conversion surface for cold traffic arriving from flyer QR codes, r/climbharder, and direct links. The page shows a generic ~100-min gym session for an intermediate 6b–7a climber (warmup → finger strength → weighted pull-ups → limit bouldering → 4×4 → core → antagonist → cooldown → end-of-session) with `Show cues` expand and `Use timer` affordances on every exercise, and a sticky bottom CTA driving signup.

This redesign resolves the brand clash between the current pink/navy app and the cream/black/orange flyer identity. The target aesthetic is the phone mockup on page 3 of the A5 flyer (FIG. 02 — TODAY VIEW): black background, cream body, monospace metadata, condensed display headers, solid-orange full-width CTA.

Implement on branch `brief/A-DEMO-03-redesign` and ship a Vercel preview for validation before merge.

---

## About the Design Files

The files in `prototype/` (`index.html`, `demo.jsx`, `ios-frame.jsx`) are **design references created in HTML/React** — a prototype showing intended look and behavior, **not production code to copy directly**. `ios-frame.jsx` only exists to frame the mock as an iPhone for review; discard it for the real app.

Your task is to **recreate the design in the existing Next.js 16 + Tailwind + shadcn/ui codebase** using its established patterns — App Router routes, Tailwind classes, shadcn primitives where they fit. Lift exact token values (colors, type, spacing) from this README; adopt the structural ideas from the prototype; don't copy the inline-styled JSX verbatim.

---

## Fidelity

**High-fidelity.** Colors, typography, spacing, and interactions are final-intent. Recreate pixel-close using the codebase's existing libraries. The only negotiable elements are the exact copy in the spec card and closure (I've written candidate copy — swap with whatever the marketing voice prefers, as long as it matches the flyer's tone: "Periodized. Strength + skill.", "Session logs shape next week.", etc.).

---

## Design Tokens

Add these to `tailwind.config.ts` as named tokens. All names are canonical — use them across the codebase.

### Colors

```ts
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      ink: {
        DEFAULT: '#0A0A0A',        // page background (near-black, not pure black)
        card:    '#121211',        // exercise card fill
        rule:    'rgba(245,241,234,0.14)',
        ruleStrong: 'rgba(245,241,234,0.28)',
      },
      cream: {
        DEFAULT: '#F5F1EA',        // body text, primary foreground
        dim:     'rgba(245,241,234,0.55)', // metadata, secondary text
        faint:   'rgba(245,241,234,0.32)', // section sub-metadata
      },
      brand: {
        orange:    '#FF4A1C',      // accent, CTA, main-work emphasis
        orangeDim: 'rgba(255,74,28,0.15)',
      },
    },
  },
}
```

**No pink. No rose. No corporate blue. No gradients.** Orange is the only accent; it is sparing — used for main-work sections, the sticky CTA, the FIG. 02 aside, and cue-list index numbers.

### Typography

Add to `app/layout.tsx` via `next/font/google`:

```ts
import { Archivo_Narrow, JetBrains_Mono, Inter } from 'next/font/google';

const archivo = Archivo_Narrow({
  subsets: ['latin'],
  weight: ['400','500','600','700'],
  variable: '--font-display',
});
const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400','500','600','700'],
  variable: '--font-mono',
});
const inter = Inter({
  subsets: ['latin'],
  weight: ['400','500','600','700'],
  variable: '--font-body',
});
```

Tailwind config:

```ts
fontFamily: {
  display: ['var(--font-display)', 'Impact', 'sans-serif'],
  mono:    ['var(--font-mono)', 'ui-monospace', 'Menlo', 'monospace'],
  body:    ['var(--font-body)', 'system-ui', 'sans-serif'],
}
```

**Note on Archivo Narrow:** the prototype uses `Archivo Narrow` because it's the closest Google-font match to the flyer's condensed bold display. If the brand team has a licensed font (NB Architekt, Neue Haas Grotesk Display Condensed), substitute it here — otherwise Archivo Narrow at 700/800 is the production choice.

### Type scale

| Role | Font | Size | Weight | Line-height | Letter-spacing | Transform |
|---|---|---|---|---|---|---|
| Masthead wordmark (`GYM SESSION,`) | display | 42px | 800 | 0.92 | -0.01em | uppercase |
| Section number (`01`) | display | 42px | 800 | 0.85 | -0.02em | — |
| Section title (`WARMUP`) | display | 26px | 700 | 0.95 | -0.01em | uppercase |
| Closure headline (`THAT'S THE SHAPE`) | display | 38px | 800 | 0.9 | -0.02em | uppercase |
| Spec-card headline | display | 20px | 700 | 1.1 | -0.005em | none |
| Aside headline (FIG. 02) | display | 22px | 700 | 1.05 | -0.005em | none |
| Exercise title | display | 18px | 700 | 1.15 | -0.005em | none |
| Sticky CTA label | display | 18px | 700 | — | -0.005em | uppercase |
| Exercise dosage | mono | 11px | 500 | — | 0.02em | — |
| Metadata (`CLIMB-AGENT`, timestamps, FIG labels) | mono | 9.5–10px | 500–600 | — | 0.08em | uppercase |
| Body copy (descriptions, cues) | body | 12.5–13.5px | 400 | 1.45–1.55 | — | — |
| Spec-card values | body | 12.5px | 400 | 1.25 | — | — |
| Timer digits | mono | 44px | 500 | 1 | -0.02em | — |

**Feature settings:** apply `font-feature-settings: "tnum" 1` to all monospace timestamps, set counts, and the timer so digits align.

### Spacing

The prototype uses a rough **4 / 8 / 10 / 12 / 14 / 16 / 18 / 20 / 24 / 28 / 32** scale. Map to Tailwind's defaults (`p-4`, `p-2`, `gap-3`, etc.) — no custom spacing tokens needed.

- Gutter (outer page padding): **16px** (`px-4`)
- Card internal padding: **12px 14px 14px**
- Section header top padding: **28px** (`pt-7`)
- Closure top padding: **32px**

### Borders, radii, shadows

- **Radius:** `4px` on cards and buttons (`rounded-[4px]`). Not zero, not the current 14px.
- **Borders:** hairlines at `rgba(245,241,234,0.14)`; strong rules at `0.28`.
- **Shadows:** none. The design is flat. Depth comes from the near-black card against near-black background, not elevation.
- **Orange stripe:** `border-left: 3px solid #FF4A1C` on main-work cards only (Max Hangs, Weighted Pull-ups, Limit Boulder, 4×4). Transparent 3px on other cards so card-body alignment stays consistent.

---

## Screens / Views

This is a **single scrolling page** at `/demo`. Components from top to bottom:

### 1. Masthead (fixed top of page)

Two stacked bars inside a wrapper with `border-bottom: 1px solid ink.rule`.

**Utility row** — `px-4 py-2`, `border-b ink.rule`, flex row space-between:
- Left: `▲` orange triangle (8px SVG) + `CLIMB-AGENT · N° 001 · DEMO` (mono 9.5px, 0.08em, uppercase, first two segments cream, last segment cream.dim)
- Right: `SPEC · V26` (mono 9.5px cream.dim)

**Title block** — `px-4 pt-[18px] pb-[14px]`:
- Top meta row: `A TRAINING BRIEF` (left) · `100 MIN · 08 PARTS` (right), both mono 9.5px cream.dim, uppercase, `margin-bottom: 8px`
- H1 wordmark: `GYM SESSION,` / `ENGINEERED.` (two lines), display 42/0.92, weight 800, uppercase, letter-spacing -0.01em, cream
- Bottom dateline row: 1px strong rule stretching to fill + `FIG. 00 — SESSION OVERVIEW` mono 9.5px cream.dim, `gap: 10px`, `margin-top: 10px`

### 2. Spec card (FIG. 01 — replaces current yellow "Sample session" box)

Wrapper `p-4`. Inner card:
- `border: 1px solid ink.ruleStrong`, `background: rgba(245,241,234,0.015)` (tiniest warm wash)
- Padding: `14px 14px 12px`
- Top row: `FIG. 01 — SPEC SHEET` (mono 9.5px, orange, weight 600) · `THIS IS A PREVIEW` (right, mono 9.5px cream.dim)
- Headline: "Your real plan is built around your grades, goals, days, and gym." (display 20px/1.1, weight 700, cream, not uppercase)
- 4-row spec grid, `grid-template-columns: 90px 1fr`, `row-gap: 6px column-gap: 12px`:
  - `CLIMBER` / Intermediate · 6b–7a
  - `MODALITY` / Lead + Boulder
  - `DURATION` / ~100 min · 08 parts
  - `STATUS` / Preview · Not personalized

**This replaces the current `~100 min` friction in the header** — duration is now a neutral spec line, not a commitment.

### 3. Section headers (repeated 01–08)

`px-4 pt-7 pb-[6px]`.

Top meta row:
- Left: `{start} · {tier}` where tier ∈ `PREP | MAIN WORK | SUPPORT`, cumulative timestamps starting 08:00 (Warmup 08:00, Fingers 08:12, Weighted Pull-ups 08:22, Limit 08:32, 4×4 08:52, Core 09:12, Antagonist 09:22, Cooldown 09:32)
- Right: `~{mins} MIN`
- Both mono 9.5px cream.faint uppercase

1px strong rule below meta, `margin-bottom: 10px`

Two-column grid `52px 1fr`:
- Left: section number (`01`, `02`, …) — display 42px/0.85, weight 800, letter-spacing -0.02em. **Orange for main-work sections (02, 03, 04, 05). Cream for prep/support (01, 06, 07, 08).**
- Right: section title uppercase, display 26px/0.95, weight 700, cream

### 4. Exercise cards

`px-4 mt-[10px]`.

Card:
- Background `ink.card` (`#121211`)
- **Orange 3px left border on main-work sections; transparent 3px on others** (preserves horizontal alignment between tiers)
- Padding `12px 14px 14px`

Header row: exercise title (display 18px/1.15 weight 700 cream) left; exercise index `01`, `02`, … (mono 9.5px cream.faint) right, baseline-aligned.

**Dosage line:** mono 11px, `letter-spacing: 0.02em`, weight 500, `tnum` on. **Orange in main-work cards, cream elsewhere.** `margin-bottom: 6px`.

**Description:** body 13px/1.45, cream.dim (`rgba(245,241,234,0.55)`).

**Action row** — flex, `margin-top: 12px`, `border-top: 1px solid ink.rule`, `padding-top: 10px`:
- `CUES` toggle (left, flex: 1): chevron (rotates 90° when open, 200ms) + mono 10px cream weight 600. Transparent button, no border.
- `TIMER` toggle (right): dot (●/○) + mono 10px label, `padding: 4px 10px`, `border: 1px solid ink.ruleStrong` normally, `border: 1px solid brand.orange` when active, label and dot orange when active.

These **replace the current "Show cues" / "Use timer" gray links**. They're designed affordances, not dev leftovers.

### 5. Cues expansion (inside exercise card, below action row)

When `CUES` toggle is open:
- `margin-top: 10px`, `padding-top: 10px`, `border-top: 1px dashed ink.rule`
- Label: `COACHING CUES · {NN}` (mono 9.5px cream.faint uppercase, count zero-padded, `margin-bottom: 6px`)
- Ordered list: grid `22px 1fr`, each row `padding: 4px 0` with bottom hairline (except last). Index column = mono 9.5px orange weight 600, zero-padded. Body column = body 12.5px/1.35 cream.

Cue content per exercise is in `demo.jsx`'s `SESSION` constant — copy the arrays into your backend resolver or inline-author them for the demo.

### 6. Timer (inside exercise card, below action row when `TIMER` active)

- `margin-top: 10px`, `border: 1px solid brand.orange`, `background: #0E0E0E`, `padding: 12px 14px`
- Top row: `REST TIMER` (mono 9.5px orange weight 600) left; `CLOSE ✕` button (mono 9.5px cream.dim, transparent) right
- Big digits: mono 44px/1 weight 500, `letter-spacing: -0.02em`, cream (turns orange and label becomes `REST COMPLETE` at 00:00)
- Progress bar: 2px tall, background `rgba(255,74,28,0.2)`, fill `brand.orange`, animates `width` over `1s linear`
- Two buttons (flex gap 8px, each `flex: 1`, `padding: 8px 10px`):
  - Primary (Pause/Resume): solid `brand.orange`, `#0A0A0A` text, mono 10.5px weight 600, 0.08em, uppercase
  - Secondary (Reset): transparent, cream text, `border: 1px solid ink.ruleStrong`

**Default duration:** parse from dosage string — `Rest M:SS` → MM*60+SS; else `N min` → N*60; else 180s fallback.

### 7. Personalization aside (FIG. 02 — between sections 04 and 05)

`px-4 pt-6 pb-1`. Grid `3px 1fr` with `gap: 12px`:
- Left: 3px-wide solid `brand.orange` vertical bar (full height)
- Right column:
  - `FIG. 02 — A NOTE ON PERSONALIZATION` (mono 9.5px orange weight 600)
  - Headline: "This session is generic. Yours won't be." (display 22px/1.05 weight 700 cream, not uppercase, `margin: 8px 0 6px`)
  - Body: "Your real plan is calibrated to your grades, goals, available days, and gym. Computed in 5 minutes. Adapts every week from your session feedback." (body 13px/1.5 cream.dim, `margin-bottom: 12px`)
  - CTA: `BUILD YOUR PLAN →` — inline-flex, solid orange background, `#0A0A0A` text, `padding: 11px 14px`, mono 11px weight 700 uppercase 0.1em, arrow 13px

**This replaces the current pink-outlined mid-page callout.**

### 8. Closure (END OF SESSION · 09)

`px-4 pt-8 pb-5`.
- 1px strong rule top, `margin-bottom: 10px`
- Meta row: `END OF SESSION · 09` left · `~100 MIN · COMPLETE` right, both mono 9.5px cream.dim, `margin-bottom: 18px`
- Headline: "THAT'S THE SHAPE / OF ONE SESSION." (display 38px/0.9 weight 800 uppercase letter-spacing -0.02em cream, `margin-bottom: 10px`)
- Body paragraph: "Every session in your real plan includes feedback tracking, automatic load adaptation, and week-over-week progression. Session logs shape next week." (body 13.5px/1.55 cream.dim, `max-width: 320px`, `margin-bottom: 20px`)
- Spec-sheet 2×2 grid, outer `1px solid ink.ruleStrong`, internal rules:
  - `FEEDBACK` / After each session
  - `ADAPTATION` / Automatic, weekly
  - `ENGINE` / Deterministic · No LLM
  - `READY` / 10 min to first plan
  - Each cell `padding: 10px 12px`, label mono 9px cream.faint `margin-bottom: 4px`, value body 12px/1.3 cream

**This replaces "Session complete. Great work."** Editorial closure, zero platitude.

### 9. Sticky bottom CTA

`position: sticky; bottom: 0; z-index: 10;` on a wrapper with `background: ink.DEFAULT`, `border-top: 1px solid ink.ruleStrong`.

Inner `px-4 pt-[10px] pb-[14px]`:
- Meta row above button: `PERIODIZED. STRENGTH + SKILL.` left · `10 MIN SETUP` right — both mono 9.5px, left cream.dim, right cream.faint, `margin-bottom: 8px`
- Button: full-width, flex row space-between baseline:
  - Label: `BUILD MY PLAN` (display 18px weight 700 uppercase letter-spacing -0.005em)
  - Arrow: `→` 20px
  - Background `brand.orange`, text `ink.DEFAULT` (`#0A0A0A`), `padding: 14px 16px`, no border

**This preserves the sticky-CTA affordance from the current design. Only the color (pink → orange) and type (sans → display) change.**

---

## Interactions & Behavior

### Expand / collapse cues
- State: `showCues: boolean` per exercise card
- Chevron rotates 0° → 90° on open, `transition: transform 200ms ease`
- Cues block renders conditionally below the action row; no height animation needed (the jump is acceptable on mobile)

### Timer
- State: `timerOn: boolean`, `left: number` (seconds), `running: boolean` per exercise card
- On open: initialize `left` from the dosage string (see §6 parse rule) and set `running = true`
- `setInterval` decrements `left` every 1000ms while running; clear on pause or unmount
- At `left === 0`: stop ticking, switch label to `REST COMPLETE`, digits turn orange. Do not auto-dismiss.
- Reset: `left = initial`, `running = true`
- Close: set `timerOn = false`; next open starts fresh from `initial`
- **Only one timer open per card is acceptable** (the current pattern). Optionally enforce "only one timer open on page" — user preference; default = per-card.

### Sticky CTA
- Always visible on scroll
- On click: route to `/signup` (or whatever the existing onboarding entry is)
- No hover state on mobile; add `active:opacity-90` for tap feedback

### Hover / focus (desktop mirror)
- Buttons: `hover:opacity-90` or `hover:brightness-110`
- Toggles: underline the label or brighten the border on hover
- Focus: use the codebase's existing focus-ring token (probably `ring-2 ring-offset-2`) but with `ring-brand-orange`

### Scroll behavior
- Single scroll container — the page. No nested scrollers.
- Masthead is **not sticky** (deliberate — it's an editorial cover). Only the bottom CTA sticks.

### Responsive
- **Mobile portrait is primary.** Design width is 390px; must work at 375px (iPhone SE).
- At ≥640px, cap content width at ~420px centered on a cream or black gutter (cream reads better — lets the editorial feel extend). Pick whichever matches the rest of the product's marketing pages.
- No tablet-specific layout needed for `/demo`. If the user opens it on desktop, it renders as a centered column.

---

## State Management

No global state. Each exercise card owns `showCues` and `timerOn`/`left`/`running` locally (React `useState` or equivalent). Session content comes from the backend resolver — pass it as props.

If you want the sticky CTA to gain urgency (e.g., change copy after scrolling past section 04), add an `IntersectionObserver` on the FIG. 02 aside — but that's a v2. Ship this first.

---

## Assets

- **Fonts**: `Archivo Narrow`, `JetBrains Mono`, `Inter` from Google Fonts. Load via `next/font/google` with `display: 'swap'`.
- **Icons**: all SVG inline. No icon library needed.
  - Triangle mark (▲): 10×10 viewBox, path `M5 1 L9 8 L1 8 Z`, fill currentColor
  - Chevron: 10×10 viewBox, path `M3 2 L7 5 L3 8`, stroke 1.2, fill none
  - Arrow `→`: literal Unicode character in display font
- **No images required** for /demo. If brand wants a hero photo later, it should be full-bleed monochrome with grain — never a gym stock shot.

---

## Files (in this bundle)

```
design_handoff_demo_redesign/
├── README.md                      ← you are here
└── prototype/
    ├── index.html                 ← entry; wraps demo in iOS frame for review
    ├── demo.jsx                   ← all design components (discard structure, lift values)
    └── ios-frame.jsx              ← device frame — DO NOT SHIP
```

`demo.jsx` is the source of truth for token values, copy, and component anatomy. Open it alongside this README.

---

## Acceptance checklist (for PR review)

- [ ] Zero pink/rose anywhere on `/demo`. Search `rose-`, `pink-`, `#EC` in the diff.
- [ ] Cream text (`#F5F1EA`) on near-black (`#0A0A0A`) — not pure white on pure black.
- [ ] Orange (`#FF4A1C`) appears on: main-work section numbers, main-work card stripes, main-work dosage lines, FIG. 02 aside rule + CTA, timer border + digits (when complete) + progress bar + primary button, sticky CTA.
- [ ] Masthead renders condensed display wordmark, not default sans.
- [ ] Timestamps and metadata are JetBrains Mono, uppercase, 0.08em tracked.
- [ ] Section numbers `01`–`08` present; closure reads `END OF SESSION · 09`.
- [ ] Cards have 4px radius (or sharp), not 14px.
- [ ] Cues expand as a numbered editorial list with orange indices.
- [ ] Timer ticks down in real time, shows `REST COMPLETE` at 00:00.
- [ ] Sticky CTA reads `BUILD MY PLAN →` in solid orange with black text.
- [ ] iPhone SE (375×667) layout does not horizontally scroll.
- [ ] Lighthouse mobile perf ≥ 90 (fonts should be preloaded via `next/font`).

---

## Deployment

Branch: `brief/A-DEMO-03-redesign`
Preview: Vercel auto-deploy. Share the preview URL for a visual diff against the flyer before merge.

Ping designer (the person who wrote this brief) before merging — they'll want to eyeball the preview next to the flyer page 3 mockup.
