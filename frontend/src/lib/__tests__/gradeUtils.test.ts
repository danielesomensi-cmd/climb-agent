import { describe, it, expect } from "vitest";
import {
  displayBoulderGrade,
  getRadarLabels,
  getDiscipline,
} from "@/lib/gradeUtils";

// ── displayBoulderGrade ──────────────────────────────────────────────────

describe("displayBoulderGrade", () => {
  it("returns input unchanged when preference is font", () => {
    expect(displayBoulderGrade("7A", "font")).toBe("7A");
    expect(displayBoulderGrade("6B+", "font")).toBe("6B+");
  });

  it("converts font to v_scale", () => {
    expect(displayBoulderGrade("7A", "v_scale")).toBe("V6");
    expect(displayBoulderGrade("6A+", "v_scale")).toBe("V4");
    expect(displayBoulderGrade("8B+", "v_scale")).toBe("V14");
  });

  it("handles lowercase input", () => {
    expect(displayBoulderGrade("7a", "v_scale")).toBe("V6");
    expect(displayBoulderGrade("6a+", "v_scale")).toBe("V4");
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

// ── getRadarLabels ───────────────────────────────────────────────────────

describe("getRadarLabels", () => {
  it("returns lead labels for lead discipline", () => {
    const labels = getRadarLabels("lead");
    expect(labels.technique).toBe("Technique & Tactics");
    expect(labels.endurance).toBe("Endurance");
  });

  it("returns boulder labels for boulder discipline", () => {
    const labels = getRadarLabels("boulder");
    expect(labels.pulling_strength).toBe("Contact");
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
