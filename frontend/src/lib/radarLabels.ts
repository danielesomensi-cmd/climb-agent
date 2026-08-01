/**
 * B318 — geometry for the radar's axis labels.
 *
 * The bug: `radar-chart.tsx` drew into `viewBox="0 0 280 280"` and anchored the
 * labels at 1.2×r from the centre with `textAnchor="middle"`. The right-hand
 * axis lands at x≈254; "Pulling Strength" at 10px is ~88px wide, so it reached
 * ~298 and the SVG clipped it — the "Pulling Strenç" Daniele photographed on
 * iOS. Note this was never viewport-dependent: the label overflowed the SVG's
 * own coordinate box, so it was cut at every screen width. The phone only made
 * it obvious.
 *
 * Two independent fixes, because either alone leaves a label near the edge:
 *   1. the viewBox gets horizontal padding, so the drawing area is narrower
 *      than the box it is painted into;
 *   2. multi-word labels wrap onto two lines, which roughly halves their width.
 *
 * Pure functions with unit tests, mirroring `lib/radarTooltip.ts` from B304 —
 * same problem family (things escaping their box on a small screen), so the
 * same shape of solution: measure in a testable function, not by eye in JSX.
 */

/** Horizontal breathing room added around the drawing, in SVG units. Sized for
 *  half of the widest single wrapped line, so a centred label cannot escape. */
export const LABEL_PAD_X = 38;
/** Vertical padding: the top and bottom labels only need one line of slack. */
export const LABEL_PAD_Y = 18;

/** Axis label font size in SVG units — kept in one place because the width
 *  estimate below depends on it. */
export const LABEL_FONT_PX = 10;

/** Baseline-to-baseline distance for a wrapped label, in SVG units. */
export const LABEL_LINE_HEIGHT = 11;

/**
 * Approximate rendered width of a label line.
 *
 * SVG has no layout pass we can query synchronously, and the exact width
 * depends on the font the device actually resolves. 0.55em per character is a
 * deliberately *generous* average for a UI sans at this size: overestimating
 * costs a few pixels of padding, underestimating puts us back where we started.
 */
export function estimateLabelWidth(line: string, fontPx = LABEL_FONT_PX): number {
  return line.length * fontPx * 0.55;
}

/**
 * Split a label into at most two balanced lines.
 *
 * Balanced rather than greedy: "Technique & Tactics" greedy-wrapped gives
 * "Technique & / Tactics", whose first line is barely narrower than the whole
 * string — no help. Choosing the split point that minimises the longest line
 * gives "Technique / & Tactics" instead.
 *
 * Single words are never broken: hyphenating "Endurance" would be worse than
 * the overflow it fixes, and the vocabulary is closed (docs/vocabulary_v1.md)
 * so abbreviating is not an option either.
 */
export function splitAxisLabel(label: string): string[] {
  const words = label.trim().split(/\s+/);
  if (words.length < 2) return [label];

  let best: string[] = [words.join(" ")];
  let bestWidth = Infinity;
  for (let i = 1; i < words.length; i++) {
    const lines = [words.slice(0, i).join(" "), words.slice(i).join(" ")];
    const widest = Math.max(...lines.map((l) => estimateLabelWidth(l)));
    if (widest < bestWidth) {
      bestWidth = widest;
      best = lines;
    }
  }
  return best;
}

/** The viewBox that gives the labels room. The drawing still uses 0..size. */
export function radarViewBox(size: number): string {
  return `${-LABEL_PAD_X} ${-LABEL_PAD_Y} ${size + 2 * LABEL_PAD_X} ${size + 2 * LABEL_PAD_Y}`;
}

/** Total width of the padded box — the SVG's max rendered width. */
export function radarOuterWidth(size: number): number {
  return size + 2 * LABEL_PAD_X;
}

/**
 * Centre point of axis `i`'s label, in the same coordinates the chart draws in.
 * Mirrors `point(i, 120)` in radar-chart.tsx: labels sit at 1.2× the polygon
 * radius, outside the outermost grid ring.
 */
export function radarLabelAnchor(
  size: number,
  i: number,
  n: number,
): [number, number] {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 40;
  const angle = -Math.PI / 2 + i * ((2 * Math.PI) / n);
  const dist = 1.2 * r;
  return [cx + dist * Math.cos(angle), cy + dist * Math.sin(angle)];
}

/**
 * Horizontal extent a centred, wrapped label occupies. What the test asserts
 * against the viewBox — the single check that would have caught the original
 * bug.
 */
export function labelHorizontalBounds(
  size: number,
  i: number,
  n: number,
  label: string,
): { left: number; right: number } {
  const [x] = radarLabelAnchor(size, i, n);
  const widest = Math.max(...splitAxisLabel(label).map((l) => estimateLabelWidth(l)));
  return { left: x - widest / 2, right: x + widest / 2 };
}
