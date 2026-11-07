/**
 * A319-FE (B414) — the quick-add filtered the catalog sessions on the gym's
 * RAW equipment list. After A319(d) `test_max_weighted_pullup` (pullup_bar +
 * weight) and `test_max_hang_pullup` (hangboard + pullup_bar + weight) are the
 * first catalog sessions that need `weight`: at a gym listing dumbbells /
 * kettlebells / a barbell but not the word "weight" (Daniele's Bkl) they
 * vanished from the quick-add while the planner places them. Now the filter
 * reads the expanded equipment, the planner's own reading (`expandEquipment`).
 */
import { describe, expect, it } from "vitest";

import { sessionFitsGym } from "@/lib/equipment-filter";

const BKL = ["hangboard", "dumbbell", "kettlebell", "spraywall", "boulder_wall"];

describe("sessionFitsGym — expanded gym equipment", () => {
  it("dumbbells mean weight: the weighted tests are offered at the Bkl", () => {
    expect(sessionFitsGym(BKL, ["pullup_bar", "weight"])).toBe(true);
    expect(sessionFitsGym(BKL, ["hangboard", "pullup_bar", "weight"])).toBe(true);
  });

  it("every gym has a pull-up bar; a loading pin is a hangboard", () => {
    expect(sessionFitsGym(["boulder_wall"], ["pullup_bar"])).toBe(true);
    expect(sessionFitsGym(["loading_pin"], ["hangboard"])).toBe(true);
  });

  it("still filters what the gym really lacks", () => {
    expect(sessionFitsGym(["boulder_wall"], ["pullup_bar", "weight"])).toBe(false);
    expect(sessionFitsGym(["boulder_wall", "dumbbell"], ["hangboard"])).toBe(false);
  });

  it("no requirement fits anywhere; case and spaces do not matter", () => {
    expect(sessionFitsGym([], [])).toBe(true);
    expect(sessionFitsGym([], undefined)).toBe(true);
    expect(sessionFitsGym([" Dumbbell "], ["Weight"])).toBe(true);
  });
});
