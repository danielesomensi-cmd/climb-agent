import { describe, it, expect } from "vitest";
import {
  computeTooltipShift,
  shouldFlipAbove,
  buildAxisTooltipCopy,
} from "../radarTooltip";

const AXES = [
  "finger_strength",
  "pulling_strength",
  "power_endurance",
  "technique",
  "endurance",
] as const;

describe("computeTooltipShift — viewport clamping (D260 Scope A)", () => {
  it("returns 0 when the popover already fits", () => {
    // 288px box centered in a 390px viewport, comfortably inside.
    expect(
      computeTooltipShift({ left: 50, right: 338, viewportWidth: 390 }),
    ).toBe(0);
  });

  it("shifts right when the left-column popover overflows the left edge (390px)", () => {
    // Left-column axis: box centered on a ~120px cell → left = -24.
    expect(
      computeTooltipShift({ left: -24, right: 264, viewportWidth: 390 }),
    ).toBe(36); // 12 - (-24)
  });

  it("shifts left when the right-column popover overflows the right edge (390px)", () => {
    expect(
      computeTooltipShift({ left: 126, right: 414, viewportWidth: 390 }),
    ).toBe(-36); // (390 - 12) - 414
  });

  it("worst case 320px: pins overflowing box to the left margin", () => {
    // Left-overflow wins even when the box is also wider than the viewport.
    expect(
      computeTooltipShift({ left: -40, right: 340, viewportWidth: 320 }),
    ).toBe(52); // 12 - (-40)
  });

  it("desktop 1280px: a centered tooltip never needs shifting", () => {
    expect(
      computeTooltipShift({ left: 500, right: 788, viewportWidth: 1280 }),
    ).toBe(0);
  });

  it("tablet 768px: fits without shifting", () => {
    expect(
      computeTooltipShift({ left: 240, right: 528, viewportWidth: 768 }),
    ).toBe(0);
  });

  it("respects safe-area insets on the left (landscape notch)", () => {
    // minLeft = 12 + 44 = 56; box left = 10 → dx = 46.
    expect(
      computeTooltipShift({
        left: 10,
        right: 200,
        viewportWidth: 812,
        insetLeft: 44,
      }),
    ).toBe(46);
  });

  it("respects safe-area insets on the right", () => {
    // maxRight = 812 - 12 - 44 = 756; box right = 800 → dx = -44.
    expect(
      computeTooltipShift({
        left: 500,
        right: 800,
        viewportWidth: 812,
        insetRight: 44,
      }),
    ).toBe(-44);
  });
});

describe("shouldFlipAbove — bottom tab bar avoidance", () => {
  it("stays below when there is room above the tab bar", () => {
    expect(
      shouldFlipAbove({ bottom: 600, viewportHeight: 800 }),
    ).toBe(false);
  });

  it("flips above when the popover would render under the tab bar", () => {
    expect(
      shouldFlipAbove({ bottom: 760, viewportHeight: 800 }),
    ).toBe(true);
  });

  it("accounts for extra bottom safe-area inset", () => {
    // limit = 812 - (64 + 34) = 714; bottom 780 > 714 → flip.
    expect(
      shouldFlipAbove({ bottom: 780, viewportHeight: 812, bottomSafe: 98 }),
    ).toBe(true);
  });
});

describe("buildAxisTooltipCopy — target-relative framing (D260 Scope B)", () => {
  it("interpolates the target grade into the roadmap line and relative sentence", () => {
    const copy = buildAxisTooltipCopy("finger_strength", "lead", "8a+");
    expect(copy).toBeDefined();
    expect(copy!.relative).toContain("8a+");
    expect(copy!.relative).toContain("100 means you're already there");
    expect(copy!.low).toContain("8a+");
    expect(copy!.low).not.toContain("{target}");
  });

  it("falls back to a generic goal phrase when no target grade is known", () => {
    const copy = buildAxisTooltipCopy("finger_strength", "lead", null);
    expect(copy!.relative).toContain("your goal grade");
    expect(copy!.low).toContain("your goal grade");
    expect(copy!.low).not.toContain("{target}");
  });

  it("treats a blank/whitespace target grade as missing", () => {
    const copy = buildAxisTooltipCopy("finger_strength", "lead", "   ");
    expect(copy!.relative).toContain("your goal grade");
    expect(copy!.low).not.toContain("{target}");
  });

  it("returns undefined for an unknown axis", () => {
    expect(buildAxisTooltipCopy("not_an_axis", "lead", "8a")).toBeUndefined();
  });

  it.each(AXES)("gives every axis a roadmap-framed low line (lead): %s", (axis) => {
    const copy = buildAxisTooltipCopy(axis, "lead", "8a");
    expect(copy).toBeDefined();
    expect(copy!.low.startsWith("A lower score")).toBe(true);
    expect(copy!.low).toContain("8a");
    // Legacy judgmental phrasing must be gone.
    expect(copy!.low.toLowerCase()).not.toContain("bottleneck");
    expect(copy!.low.toLowerCase()).not.toContain("run out of gas");
  });

  it.each(AXES)("gives every axis a roadmap-framed low line (boulder): %s", (axis) => {
    const copy = buildAxisTooltipCopy(axis, "boulder", "7C");
    expect(copy).toBeDefined();
    expect(copy!.low.startsWith("A lower score")).toBe(true);
    expect(copy!.low).toContain("7C");
  });

  it("no longer sells the technique axis as a gap measurement (A270)", () => {
    // D266 demoted the redpoint-onsight gap to a tactical hint. The copy used
    // to say "a big gap between your onsight and redpoint suggests…", which
    // described a scoring rule that no longer exists.
    for (const disc of ["lead", "boulder"] as const) {
      const copy = buildAxisTooltipCopy("technique", disc, "8a")!;
      const text = `${copy.description} ${copy.low}`.toLowerCase();
      expect(text).not.toContain("gap");
      expect(text).not.toContain("redpoint");
      expect(text).not.toContain("onsight");
      // …and says plainly what it is instead.
      expect(copy.description.toLowerCase()).toContain("not a measurement");
    }
  });

  it("keeps each copy section within the 300-char budget (D260 A.4)", () => {
    for (const axis of AXES) {
      for (const disc of ["lead", "boulder"] as const) {
        const copy = buildAxisTooltipCopy(axis, disc, "8a+")!;
        expect(copy.description.length).toBeLessThanOrEqual(300);
        expect(copy.relative.length).toBeLessThanOrEqual(300);
        expect(copy.low.length).toBeLessThanOrEqual(300);
      }
    }
  });
});
