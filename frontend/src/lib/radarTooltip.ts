// B304 — pure, testable helpers for the radar axis tooltip.
//
// The DOM measurement (getBoundingClientRect, safe-area probe) lives in the
// component; everything here is side-effect-free so it can be unit-tested at
// arbitrary viewport widths without a real layout engine (D260 Scope A fix).

import { getAxisDescription, type Discipline } from "@/lib/gradeUtils";
import { ELITE_ANCHORS_V1, type AxisKey } from "@/lib/eliteAnchors";

export const TOOLTIP_MARGIN = 12; // min gap from the viewport edge, px

export interface ClampInput {
  /** Popover bounding rect left/right in viewport px (as-if centered). */
  left: number;
  right: number;
  viewportWidth: number;
  insetLeft?: number;
  insetRight?: number;
  margin?: number;
}

/**
 * Horizontal pixels to ADD to the popover's transform so it stays fully
 * on-screen with `margin` (+ safe-area inset) clearance on both sides.
 * Returns 0 when the popover already fits. Left-edge overflow wins over
 * right-edge overflow (a box wider than the viewport is pinned to the left).
 */
export function computeTooltipShift({
  left,
  right,
  viewportWidth,
  insetLeft = 0,
  insetRight = 0,
  margin = TOOLTIP_MARGIN,
}: ClampInput): number {
  const minLeft = margin + insetLeft;
  const maxRight = viewportWidth - margin - insetRight;
  if (left < minLeft) return minLeft - left;
  if (right > maxRight) return maxRight - right;
  return 0;
}

export interface FlipInput {
  /** Popover bounding rect bottom in viewport px (opening downward). */
  bottom: number;
  viewportHeight: number;
  /** Space reserved at the bottom for the fixed tab bar + safe area, px. */
  bottomSafe?: number;
}

/** True when a downward-opening popover would render under the bottom tab bar. */
export function shouldFlipAbove({
  bottom,
  viewportHeight,
  bottomSafe = 72,
}: FlipInput): boolean {
  return bottom > viewportHeight - bottomSafe;
}

export interface AxisTooltipCopy {
  label: string;
  /** What the axis measures. */
  description: string;
  /** Target-relative framing sentence. */
  relative: string;
  /** Low-score line, reframed as a roadmap (target grade interpolated). */
  low: string;
}

/**
 * Assemble the tooltip copy for an axis, making the target-relative framing
 * explicit and interpolating the user's goal grade into the roadmap line.
 * Scores are readiness-for-goal, not absolute ability (D260 Scope B).
 */
export function buildAxisTooltipCopy(
  axis: string,
  discipline: Discipline,
  targetGrade?: string | null,
): AxisTooltipCopy | undefined {
  const info = getAxisDescription(axis, discipline);
  if (!info) return undefined;
  const hasGrade = !!(targetGrade && targetGrade.trim());
  const goal = hasGrade ? (targetGrade as string).trim() : "your goal grade";
  const relative = hasGrade
    ? `Scored against what ${goal} typically demands — 100 means you're already there.`
    : `Scored against your goal grade — 100 means you're already there.`;
  return {
    label: info.label,
    description: info.description,
    relative,
    low: info.low.replace(/\{target\}/g, goal),
  };
}

/** A267 — the one line every elite-mode tooltip carries, live or greyed. */
export const ELITE_SCALE_LINE =
  "Elite = benchmarks around 8b–9a level performance.";

/** A267 — shown on the three axes with no defensible elite anchor (D262). */
export const ELITE_UNAVAILABLE_LINE =
  "Elite benchmark not available for this axis — shown for your goal only.";

/**
 * Tooltip copy for the radar's Elite mode (A267).
 *
 * Same shape as `buildAxisTooltipCopy` so the popover renders one way. The
 * target-relative sentence is replaced — in Elite mode the scale is the top of
 * the sport, not the user's goal, and mixing the two framings is what made the
 * bare 0-100 unreadable in the first place (D260 Scope B).
 */
export function buildEliteAxisTooltipCopy(
  axis: string,
  discipline: Discipline,
): AxisTooltipCopy | undefined {
  const info = getAxisDescription(axis, discipline);
  if (!info) return undefined;
  const anchor = ELITE_ANCHORS_V1[axis as AxisKey];
  const greyed = !anchor || anchor.status !== "live";
  return {
    label: info.label,
    description: info.description,
    relative: greyed
      ? ELITE_UNAVAILABLE_LINE
      : "Scored against elite benchmarks — 100 means elite level.",
    low: greyed ? ELITE_SCALE_LINE : `${ELITE_SCALE_LINE} ${anchor.note}`,
  };
}
