import { describe, it, expect } from "vitest";
import {
  displayBoulderGrade,
  getRadarLabels,
  getDiscipline,
  vScaleToFont,
  V_SCALE_GRADES,
  gradeRank,
  compareGrades,
  hardestGrade,
} from "@/lib/gradeUtils";

// ── displayBoulderGrade ──────────────────────────────────────────────────

describe("displayBoulderGrade", () => {
  it("returns input unchanged when preference is font", () => {
    expect(displayBoulderGrade("7A", "font")).toBe("7A");
    expect(displayBoulderGrade("6B+", "font")).toBe("6B+");
  });

  it("converts font to v_scale", () => {
    expect(displayBoulderGrade("7A", "v_scale")).toBe("V6");
    expect(displayBoulderGrade("6A+", "v_scale")).toBe("V3");
    expect(displayBoulderGrade("8B+", "v_scale")).toBe("V14");
  });

  it("handles lowercase input", () => {
    expect(displayBoulderGrade("7a", "v_scale")).toBe("V6");
    expect(displayBoulderGrade("6a+", "v_scale")).toBe("V3");
  });

  it("returns input unchanged for unknown grades", () => {
    expect(displayBoulderGrade("unknown", "v_scale")).toBe("unknown");
    expect(displayBoulderGrade("9A", "v_scale")).toBe("9A");
  });

  it("converts boundary grades correctly", () => {
    expect(displayBoulderGrade("4A", "v_scale")).toBe("V0");
    expect(displayBoulderGrade("8C+", "v_scale")).toBe("V16");
  });
});

// ── B248: full Font→V table coverage (international standard) ──────────────
//
// Pre-B248, the FONT_TO_V table had a systematic +1 inflation in 5A..7A
// (e.g. 7A → V7 instead of V6). This parametric test pins every entry of the
// table so any future drift is caught immediately. Source: Wikipedia "Grade
// (climbing)" + Mountain Project conversion.

const FONT_TO_V_EXPECTED: Array<[string, string]> = [
  ["4A", "V0"], ["4B", "V0"], ["4C", "V1"],
  ["5A", "V1"], ["5A+", "V1"], ["5B", "V2"], ["5B+", "V2"], ["5C", "V2"], ["5C+", "V3"],
  ["6A", "V3"], ["6A+", "V3"], ["6B", "V4"], ["6B+", "V4"], ["6C", "V5"], ["6C+", "V5"],
  ["7A", "V6"], ["7A+", "V7"], ["7B", "V8"], ["7B+", "V8"], ["7C", "V9"], ["7C+", "V10"],
  ["8A", "V11"], ["8A+", "V12"], ["8B", "V13"], ["8B+", "V14"], ["8C", "V15"], ["8C+", "V16"],
];

describe("displayBoulderGrade — full Font→V table (B248)", () => {
  it.each(FONT_TO_V_EXPECTED)("Font %s converts to %s", (font, vExpected) => {
    expect(displayBoulderGrade(font, "v_scale")).toBe(vExpected);
  });
});

// ── B248: round-trip V → Font → V — onboarding picker invariant ────────────
//
// When a V-scale user picks Vn in onboarding, vScaleToFont(Vn) is what we
// store. Re-displaying that stored Font as V-scale must round-trip back to
// Vn for every supported V0..V16, otherwise the picker would silently shift
// the user's grade between selection and review.

describe("V → Font → V round-trip (B248)", () => {
  it.each(V_SCALE_GRADES)("V-scale %s round-trips through Font", (vGrade) => {
    const stored = vScaleToFont(vGrade);
    expect(displayBoulderGrade(stored, "v_scale")).toBe(vGrade);
  });

  it("V-scale grades list covers V0..V15 (V_SCALE_GRADES is the picker source)", () => {
    expect(V_SCALE_GRADES).toEqual([
      "V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7",
      "V8", "V9", "V10", "V11", "V12", "V13", "V14", "V15",
    ]);
  });
});

// ── getRadarLabels ───────────────────────────────────────────────────────

describe("getRadarLabels", () => {
  it("returns lead labels for lead discipline", () => {
    const labels = getRadarLabels("lead");
    expect(labels.technique).toBe("Technique & Tactics");
    expect(labels.endurance).toBe("Endurance");
  });

  it("returns boulder labels for boulder discipline", () => {
    const labels = getRadarLabels("boulder");
    expect(labels.pulling_strength).toBe("Pulling Power");
    expect(labels.power_endurance).toBe("Work Capacity");
    expect(labels.technique).toBe("Movement & Reading");
    expect(labels.endurance).toBe("Recovery");
  });

  it("returns lead labels for all_round", () => {
    const labels = getRadarLabels("all_round");
    expect(labels.technique).toBe("Technique & Tactics");
  });

  it("defaults to lead labels when undefined", () => {
    const labels = getRadarLabels();
    expect(labels.technique).toBe("Technique & Tactics");
  });
});

// ── getDiscipline ────────────────────────────────────────────────────────

describe("getDiscipline", () => {
  it("maps lead_grade to lead", () => {
    expect(getDiscipline("lead_grade")).toBe("lead");
  });

  it("maps boulder_grade to boulder", () => {
    expect(getDiscipline("boulder_grade")).toBe("boulder");
  });

  it("maps all_round to all_round", () => {
    expect(getDiscipline("all_round")).toBe("all_round");
  });

  it("defaults to lead for undefined", () => {
    expect(getDiscipline(undefined)).toBe("lead");
  });

  it("defaults to lead for unknown goal types", () => {
    expect(getDiscipline("something_else")).toBe("lead");
  });
});

// ── canonical grade ordering (A227 / B2) ─────────────────────────────────

describe("gradeRank / compareGrades / hardestGrade", () => {
  it("orders French sport grades by difficulty, not lexicographically", () => {
    expect(gradeRank("7a")).toBeGreaterThan(gradeRank("6c+"));
    expect(gradeRank("6b")).toBeGreaterThan(gradeRank("6a+"));
    expect(gradeRank("9a")).toBeGreaterThan(gradeRank("8c+"));
  });

  it("orders Font boulder bare-number grades below lettered grades", () => {
    expect(gradeRank("5+")).toBeGreaterThan(gradeRank("5"));
    expect(gradeRank("6a")).toBeGreaterThan(gradeRank("5+"));
  });

  it("is case-insensitive", () => {
    expect(gradeRank("7A")).toBe(gradeRank("7a"));
  });

  it("ranks unknown/empty grades as -1 (sort below everything)", () => {
    expect(gradeRank("")).toBe(-1);
    expect(gradeRank("V5")).toBe(-1); // never V-scale
    expect(gradeRank("xyz")).toBe(-1);
  });

  it("compareGrades sorts ascending by difficulty", () => {
    const sorted = ["7a", "6a", "8b", "6c+"].sort(compareGrades);
    expect(sorted).toEqual(["6a", "6c+", "7a", "8b"]);
  });

  it("hardestGrade returns the toughest grade", () => {
    expect(hardestGrade(["6a", "7a+", "6c+"])).toBe("7a+");
    expect(hardestGrade(["6b", "6b"])).toBe("6b");
  });

  it("hardestGrade returns null when no grade ranks", () => {
    expect(hardestGrade([])).toBeNull();
    expect(hardestGrade(["", "V3"])).toBeNull();
  });
});
