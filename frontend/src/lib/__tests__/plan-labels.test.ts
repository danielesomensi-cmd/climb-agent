import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import path from "path";
import {
  domainWeightRows,
  formatCycleHeadline,
  formatWeeksLeftInPhase,
  getCyclePosition,
  getDomainLabel,
  getIntensityCapLabel,
  getSessionLabel,
} from "../plan-labels";
import type { Macrocycle, Phase } from "../types";

const phase = (phase_id: string, duration_weeks: number): Phase => ({
  phase_id,
  phase_name: phase_id,
  duration_weeks,
  energy_system: "",
  domain_weights: {},
  session_pool: [],
  intensity_cap: "max",
});

const macro: Macrocycle = {
  start_date: "2026-09-07",
  total_weeks: 12,
  phases: [
    phase("base", 3),
    phase("strength_power", 4),
    phase("power_endurance", 3),
    phase("performance", 1),
    phase("deload", 1),
  ],
  goal_snapshot: {},
  profile_snapshot: {},
};

describe("A311 — getIntensityCapLabel", () => {
  it("maps every engine intensity_cap", () => {
    expect(getIntensityCapLabel("low")).toBe("Low intensity");
    expect(getIntensityCapLabel("medium")).toBe("Moderate intensity");
    expect(getIntensityCapLabel("high")).toBe("High intensity");
    expect(getIntensityCapLabel("max")).toBe("Max intensity");
  });
  it("prettifies an unknown value and blanks a missing one", () => {
    expect(getIntensityCapLabel("very_high")).toBe("Very High");
    expect(getIntensityCapLabel("")).toBe("");
    expect(getIntensityCapLabel(undefined)).toBe("");
  });
});

describe("A311 — domain weights", () => {
  it("labels known domains and prettifies unknown ones", () => {
    expect(getDomainLabel("finger_strength")).toBe("Finger strength");
    expect(getDomainLabel("core_stability")).toBe("Core Stability");
  });
  it("turns fractions into rounded percentages, heaviest first, stable ties", () => {
    const rows = domainWeightRows({
      technique: 0.2,
      finger_strength: 0.35,
      endurance: 0.2,
      power_endurance: 0.254,
    });
    expect(rows.map((r) => [r.domain, r.pct])).toEqual([
      ["finger_strength", 35],
      ["power_endurance", 25],
      ["endurance", 20],
      ["technique", 20],
    ]);
  });
  it("clamps out-of-range and non-numeric weights", () => {
    const rows = domainWeightRows({
      a: 1.4,
      b: -0.2,
      c: Number.NaN,
    } as Record<string, number>);
    expect(rows.find((r) => r.domain === "a")?.pct).toBe(100);
    expect(rows.find((r) => r.domain === "b")?.pct).toBe(0);
    expect(rows.find((r) => r.domain === "c")?.pct).toBe(0);
  });
  it("returns nothing for an empty map", () => {
    expect(domainWeightRows({})).toEqual([]);
  });
});

describe("A311 — getSessionLabel", () => {
  const names = new Map([["strength_long", "Strength — long"], ["blank", "  "]]);
  it("uses the catalog name when present", () => {
    expect(getSessionLabel("strength_long", names)).toBe("Strength — long");
  });
  it("falls back to the prettified id when the name is missing or blank", () => {
    expect(getSessionLabel("power_endurance_intervals", names)).toBe("Power Endurance Intervals");
    expect(getSessionLabel("blank", names)).toBe("Blank");
    expect(getSessionLabel("lunch_hiit", null)).toBe("Lunch Hiit");
  });
});

describe("A311 — cycle position headline", () => {
  it("first week of the cycle", () => {
    const pos = getCyclePosition(macro, 1);
    expect(pos).toMatchObject({ phaseId: "base", weeksLeftInPhase: 3 });
    expect(formatCycleHeadline(pos)).toBe("Week 1 of 12 · Endurance Base · 3 weeks left in phase");
  });
  it("counts the current week as left, and names the last one", () => {
    // strength_power covers weeks 4–7
    expect(getCyclePosition(macro, 6).weeksLeftInPhase).toBe(2);
    expect(formatCycleHeadline(getCyclePosition(macro, 6))).toBe(
      "Week 6 of 12 · Strength & Power · 2 weeks left in phase",
    );
    expect(formatCycleHeadline(getCyclePosition(macro, 7))).toBe(
      "Week 7 of 12 · Strength & Power · last week of phase",
    );
  });
  it("uses the discipline-aware phase name", () => {
    expect(getCyclePosition(macro, 6, "boulder").phaseLabel).toBe("Max Strength & Power");
  });
  it("one-week phases and the final week", () => {
    expect(formatCycleHeadline(getCyclePosition(macro, 12))).toBe(
      "Week 12 of 12 · Deload · last week of phase",
    );
  });
  it("degrades to 'Week N of M' when no phase covers the week", () => {
    const short = { ...macro, phases: [phase("base", 2)] };
    const pos = getCyclePosition(short, 5);
    expect(pos.phaseId).toBeNull();
    expect(formatCycleHeadline(pos)).toBe("Week 5 of 12");
  });
  it("formatWeeksLeftInPhase", () => {
    expect(formatWeeksLeftInPhase(1)).toBe("last week of phase");
    expect(formatWeeksLeftInPhase(4)).toBe("4 weeks left in phase");
  });
});

describe("A311 — /plan uses design tokens only", () => {
  const root = path.resolve(__dirname, "../../");
  const RAW_PALETTE = /(amber|zinc|slate|sky|yellow|green|purple|red|blue|orange|gray|neutral)-[0-9]+/g;
  it.each(["app/(main)/plan/page.tsx", "components/training/macrocycle-timeline.tsx"])(
    "%s has no raw palette classes",
    (rel) => {
      const src = readFileSync(path.join(root, rel), "utf8");
      expect(src.match(RAW_PALETTE) ?? []).toEqual([]);
    },
  );
});
