import { describe, it, expect } from "vitest";
import { getPhaseName, getPhaseNameShort } from "../phase-labels";

describe("getPhaseName", () => {
  it("returns lead labels by default", () => {
    expect(getPhaseName("base")).toBe("Endurance Base");
    expect(getPhaseName("strength_power")).toBe("Strength & Power");
    expect(getPhaseName("power_endurance")).toBe("Power Endurance");
    expect(getPhaseName("performance")).toBe("Performance");
    expect(getPhaseName("deload")).toBe("Deload");
  });

  it("returns boulder labels for boulder discipline", () => {
    expect(getPhaseName("base", "boulder")).toBe("Movement & Volume Base");
    expect(getPhaseName("strength_power", "boulder")).toBe("Max Strength & Power");
    expect(getPhaseName("power_endurance", "boulder")).toBe("Work Capacity");
    expect(getPhaseName("performance", "boulder")).toBe("Projecting & Peak");
    expect(getPhaseName("deload", "boulder")).toBe("Deload");
  });

  it("returns boulder labels for all_round discipline", () => {
    expect(getPhaseName("base", "all_round")).toBe("Movement & Volume Base");
    expect(getPhaseName("strength_power", "all_round")).toBe("Max Strength & Power");
  });

  it("returns lead labels for lead discipline", () => {
    expect(getPhaseName("base", "lead")).toBe("Endurance Base");
  });

  it("falls back to formatted phase_id for unknown phases", () => {
    expect(getPhaseName("unknown_phase")).toBe("unknown phase");
  });
});

describe("getPhaseNameShort", () => {
  it("returns short lead labels by default", () => {
    expect(getPhaseNameShort("base")).toBe("Base");
    expect(getPhaseNameShort("strength_power")).toBe("Strength");
    expect(getPhaseNameShort("power_endurance")).toBe("Power End.");
  });

  it("returns short boulder labels for boulder discipline", () => {
    expect(getPhaseNameShort("base", "boulder")).toBe("Volume");
    expect(getPhaseNameShort("strength_power", "boulder")).toBe("Max Str.");
    expect(getPhaseNameShort("power_endurance", "boulder")).toBe("Work Cap.");
    expect(getPhaseNameShort("performance", "boulder")).toBe("Projecting");
  });
});
