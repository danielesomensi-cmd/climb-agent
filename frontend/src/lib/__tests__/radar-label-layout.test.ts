import { describe, expect, it } from "vitest";
import {
  LABEL_PAD_X,
  estimateLabelWidth,
  labelHorizontalBounds,
  radarOuterWidth,
  radarViewBox,
  splitAxisLabel,
} from "@/lib/radarLabels";
import { getRadarLabels } from "@/lib/gradeUtils";

/**
 * B318 — reported from a real iPhone: the right-hand axis rendered as
 * "Pulling Strenç", clipped mid-word.
 *
 * The bug was not responsive layout — the label overflowed the SVG's own
 * coordinate box, so it was cut at every width. That is exactly the kind of
 * thing an eyeball test misses on a laptop, so the geometry is asserted here
 * instead: every axis label of every discipline must fit inside the box it is
 * painted into, at every size the chart is used at.
 */

const AXIS_KEYS = [
  "finger_strength",
  "pulling_strength",
  "power_endurance",
  "technique",
  "endurance",
] as const;

/** Sizes the chart renders at: default 280, plus the smaller values a 320px
 *  viewport can force through `maxWidth`. */
const SIZES = [220, 240, 280];
const DISCIPLINES = ["lead", "boulder"] as const;

describe("splitAxisLabel", () => {
  it("leaves single words alone rather than hyphenating them", () => {
    expect(splitAxisLabel("Endurance")).toEqual(["Endurance"]);
    expect(splitAxisLabel("Technique")).toEqual(["Technique"]);
  });

  it("splits two-word labels onto two lines", () => {
    expect(splitAxisLabel("Pulling Strength")).toEqual(["Pulling", "Strength"]);
    expect(splitAxisLabel("Power Endurance")).toEqual(["Power", "Endurance"]);
  });

  it("balances the split instead of wrapping greedily", () => {
    /* Greedy wrapping of "Technique & Tactics" yields "Technique &" first,
       which is barely narrower than the whole string and fixes nothing. */
    const lines = splitAxisLabel("Technique & Tactics");
    expect(lines).toEqual(["Technique", "& Tactics"]);
    expect(Math.max(...lines.map(estimateLabelWidth)))
      .toBeLessThan(estimateLabelWidth("Technique & Tactics"));
  });

  it("never drops or reorders words", () => {
    for (const discipline of DISCIPLINES) {
      const labels = getRadarLabels(discipline);
      for (const key of AXIS_KEYS) {
        const label = labels[key];
        expect(splitAxisLabel(label).join(" ")).toBe(label);
      }
    }
  });
});

describe("label bounds inside the viewBox", () => {
  it.each(DISCIPLINES)("keeps every %s axis label inside the box", (discipline) => {
    const labels = getRadarLabels(discipline);
    for (const size of SIZES) {
      const [minX] = radarViewBox(size).split(" ").map(Number);
      const maxX = minX + radarOuterWidth(size);
      AXIS_KEYS.forEach((key, i) => {
        const { left, right } = labelHorizontalBounds(size, i, AXIS_KEYS.length, labels[key]);
        expect(left, `${discipline}/${key} @${size} left`).toBeGreaterThanOrEqual(minX);
        expect(right, `${discipline}/${key} @${size} right`).toBeLessThanOrEqual(maxX);
      });
    }
  });

  it("the original geometry would have failed this test", () => {
    /* Regression anchor: the pre-B318 box was `0 0 280 280` and the label was
       drawn on one line. Recomputing that case must overflow, otherwise this
       test is not actually measuring the thing that broke. */
    const size = 280;
    const oneLineWidth = estimateLabelWidth("Pulling Strength");
    const anchorX = size / 2 + 1.2 * (size / 2 - 40) * Math.cos(-Math.PI / 2 + (2 * Math.PI) / 5);
    expect(anchorX + oneLineWidth / 2).toBeGreaterThan(size);
  });
});

describe("radarViewBox", () => {
  it("pads the drawing horizontally so a centred label has room", () => {
    expect(radarViewBox(280)).toBe(`${-LABEL_PAD_X} -18 ${280 + 2 * LABEL_PAD_X} ${280 + 36}`);
    expect(radarOuterWidth(280)).toBe(280 + 2 * LABEL_PAD_X);
  });
});
