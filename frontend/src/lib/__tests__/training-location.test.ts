/**
 * B322 — the default that deleted a user's climbing week.
 *
 * The availability step defaulted every slot to "home". Because the planner
 * treats `preferred_location` as binding, a boulderer with a fully equipped
 * gym, `home_enabled=false` and an empty home kit got a week of stretching and
 * prehab — he opened /today once and never came back.
 */

import { describe, expect, it } from "vitest";

import { defaultTrainingLocation } from "../training-location";

describe("defaultTrainingLocation", () => {
  it("picks the gym when home is switched off", () => {
    // The exact production shape that produced the empty week.
    expect(
      defaultTrainingLocation({ home_enabled: false, home: [], gyms: [{ gym_id: "g" }] })
    ).toBe("gym");
  });

  it("picks the gym when home is on but empty", () => {
    expect(
      defaultTrainingLocation({ home_enabled: true, home: [], gyms: [{ gym_id: "g" }] })
    ).toBe("gym");
  });

  it("keeps home when there is a real home kit", () => {
    expect(
      defaultTrainingLocation({
        home_enabled: true,
        home: ["dumbbell", "resistance_band"],
        gyms: [{ gym_id: "g" }],
      })
    ).toBe("home");
  });

  it("keeps home when there is no gym to send the user to", () => {
    // Pointing at a gym that does not exist helps nobody.
    expect(defaultTrainingLocation({ home_enabled: false, home: [], gyms: [] })).toBe("home");
  });

  it("defaults to home on missing or empty input", () => {
    expect(defaultTrainingLocation({})).toBe("home");
    expect(defaultTrainingLocation(null)).toBe("home");
    expect(defaultTrainingLocation(undefined)).toBe("home");
  });

  it("treats an absent home_enabled as enabled", () => {
    expect(defaultTrainingLocation({ home: ["hangboard"], gyms: [{ gym_id: "g" }] })).toBe("home");
  });
});
