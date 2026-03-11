import { describe, it, expect } from "vitest";
import { expandEquipment, isExerciseCompatible } from "@/lib/equipment-filter";
import type { Exercise } from "@/lib/types";

// ─── Helper ──────────────────────────────────────────────────────────

function makeExercise(
  overrides: Partial<Exercise> & { equipment_required: string[] },
): Exercise {
  return {
    id: "test",
    exercise_id: "test_exercise",
    name: "Test Exercise",
    domain: ["strength"],
    role: "primary",
    equipment_required: [],
    prescription_defaults: {},
    ...overrides,
  };
}

// ─── expandEquipment ─────────────────────────────────────────────────

describe("expandEquipment", () => {
  it("always includes floor", () => {
    const result = expandEquipment([], "home");
    expect(result.has("floor")).toBe(true);
  });

  it("normalizes to lowercase and trims", () => {
    const result = expandEquipment(["  Hangboard ", "PULLUP_BAR"], "home");
    expect(result.has("hangboard")).toBe(true);
    expect(result.has("pullup_bar")).toBe(true);
  });

  it("dumbbell implies weight", () => {
    const result = expandEquipment(["dumbbell"], "home");
    expect(result.has("weight")).toBe(true);
    expect(result.has("dumbbell")).toBe(true);
  });

  it("kettlebell implies weight", () => {
    const result = expandEquipment(["kettlebell"], "home");
    expect(result.has("weight")).toBe(true);
  });

  it("barbell implies weight", () => {
    const result = expandEquipment(["barbell"], "home");
    expect(result.has("weight")).toBe(true);
  });

  it("loading_pin implies hangboard", () => {
    const result = expandEquipment(["loading_pin"], "home");
    expect(result.has("hangboard")).toBe(true);
    expect(result.has("loading_pin")).toBe(true);
  });

  it("gym location always has pullup_bar", () => {
    const result = expandEquipment([], "gym");
    expect(result.has("pullup_bar")).toBe(true);
  });

  it("home location does NOT auto-add pullup_bar", () => {
    const result = expandEquipment([], "home");
    expect(result.has("pullup_bar")).toBe(false);
  });

  it("gym with full equipment expands all implicit items", () => {
    const result = expandEquipment(
      ["hangboard", "dumbbell", "loading_pin", "cable_machine"],
      "gym",
    );
    expect(result.has("floor")).toBe(true);
    expect(result.has("weight")).toBe(true);
    expect(result.has("hangboard")).toBe(true);
    expect(result.has("pullup_bar")).toBe(true);
    expect(result.has("cable_machine")).toBe(true);
  });
});

// ─── isExerciseCompatible ────────────────────────────────────────────

describe("isExerciseCompatible", () => {
  it("bodyweight exercise (empty equipment_required) always compatible", () => {
    const ex = makeExercise({ equipment_required: [] });
    const available = new Set(["floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(true);
  });

  it("exercise requiring cable_machine hidden when not available", () => {
    const ex = makeExercise({ equipment_required: ["cable_machine"] });
    const available = expandEquipment(["hangboard", "pullup_bar"], "home");
    expect(isExerciseCompatible(ex, available)).toBe(false);
  });

  it("exercise requiring cable_machine shown when available", () => {
    const ex = makeExercise({ equipment_required: ["cable_machine"] });
    const available = expandEquipment(["cable_machine"], "gym");
    expect(isExerciseCompatible(ex, available)).toBe(true);
  });

  it("AND logic: all equipment_required items must be present", () => {
    const ex = makeExercise({
      equipment_required: ["hangboard", "loading_pin"],
    });
    // Only hangboard, no loading_pin
    const available = new Set(["hangboard", "floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(false);
  });

  it("AND logic: passes when all required items present", () => {
    const ex = makeExercise({
      equipment_required: ["hangboard", "loading_pin"],
    });
    const available = new Set(["hangboard", "loading_pin", "floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(true);
  });

  it("equipment_required_any (OR): shown if user has any one", () => {
    const ex = makeExercise({
      equipment_required: [],
      equipment_required_any: ["board_kilter", "board_moonboard", "board_other"],
    });
    const available = new Set(["board_kilter", "floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(true);
  });

  it("equipment_required_any (OR): hidden if user has none", () => {
    const ex = makeExercise({
      equipment_required: [],
      equipment_required_any: ["board_kilter", "board_moonboard", "board_other"],
    });
    const available = new Set(["hangboard", "floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(false);
  });

  it("combined AND + OR: both must pass", () => {
    const ex = makeExercise({
      equipment_required: ["hangboard"],
      equipment_required_any: ["board_kilter", "board_moonboard"],
    });
    // Has hangboard but no board
    const available = new Set(["hangboard", "floor"]);
    expect(isExerciseCompatible(ex, available)).toBe(false);

    // Has both
    const available2 = new Set(["hangboard", "board_kilter", "floor"]);
    expect(isExerciseCompatible(ex, available2)).toBe(true);
  });
});

// ─── Integration: home vs gym scenario ───────────────────────────────

describe("home vs gym filtering scenario", () => {
  const bodyweightEx = makeExercise({
    exercise_id: "pushup",
    name: "Push-up",
    equipment_required: [],
  });

  const cableMachineEx = makeExercise({
    exercise_id: "cable_fly",
    name: "Cable Fly",
    equipment_required: ["cable_machine"],
  });

  const hangboardEx = makeExercise({
    exercise_id: "max_hang",
    name: "Max Hang",
    equipment_required: ["hangboard"],
  });

  const boardEx = makeExercise({
    exercise_id: "board_session",
    name: "Board Session",
    equipment_required: [],
    equipment_required_any: ["board_kilter", "board_moonboard", "board_other"],
  });

  it("home with hangboard + pullup_bar: shows bodyweight and hangboard, hides cable", () => {
    const homeEquip = expandEquipment(["hangboard", "pullup_bar"], "home");

    expect(isExerciseCompatible(bodyweightEx, homeEquip)).toBe(true);
    expect(isExerciseCompatible(hangboardEx, homeEquip)).toBe(true);
    expect(isExerciseCompatible(cableMachineEx, homeEquip)).toBe(false);
    expect(isExerciseCompatible(boardEx, homeEquip)).toBe(false);
  });

  it("gym with full equipment: shows more exercises", () => {
    const gymEquip = expandEquipment(
      ["hangboard", "cable_machine", "dumbbell", "board_kilter"],
      "gym",
    );

    expect(isExerciseCompatible(bodyweightEx, gymEquip)).toBe(true);
    expect(isExerciseCompatible(hangboardEx, gymEquip)).toBe(true);
    expect(isExerciseCompatible(cableMachineEx, gymEquip)).toBe(true);
    expect(isExerciseCompatible(boardEx, gymEquip)).toBe(true);
  });

  it("gym without cable_machine: hides cable exercises", () => {
    const gymEquip = expandEquipment(["hangboard", "dumbbell"], "gym");
    expect(isExerciseCompatible(cableMachineEx, gymEquip)).toBe(false);
  });
});
