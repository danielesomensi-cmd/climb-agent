// @vitest-environment jsdom
/**
 * B380: a dumbbell load is the weight of ONE dumbbell, and the app says so.
 *
 * Before B380 every load read "+34 kg" — the athlete could not tell a
 * per-hand dumbbell number from a barbell total, and the engine converted
 * between the two with a wrong 0.85 factor.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { formatPrescription } from "@/components/guided/guided-exercise-step";
import { ExerciseCard } from "@/components/training/exercise-card";
import { extractFeedbackExercises } from "@/lib/feedback-items";
import { buildGuidedStateFromExercises } from "@/lib/guided-session-utils";
import { formatLoad, loadInputLabel, normalizeLoadUnit, pickLoadUnit } from "@/lib/load-units";

describe("formatLoad", () => {
  it("per dumbbell: no '+', says per dumbbell", () => {
    expect(formatLoad(34, "per_dumbbell", { signed: true })).toBe("34 kg per dumbbell");
    expect(formatLoad(34, "per_dumbbell")).toBe("34 kg per dumbbell");
  });

  it("implement: plain kg, never '+'", () => {
    expect(formatLoad(12, "implement", { signed: true })).toBe("12 kg");
  });

  it("total or missing: the pre-B380 rendering", () => {
    expect(formatLoad(70, "total", { signed: true })).toBe("+70 kg");
    expect(formatLoad(70, undefined, { signed: true })).toBe("+70 kg");
    expect(formatLoad(70, undefined)).toBe("70 kg");
  });
});

describe("input label and unit picking", () => {
  it("labels the per-dumbbell input", () => {
    expect(loadInputLabel("per_dumbbell", "Actual load used (kg)")).toBe("Load per dumbbell (kg)");
    expect(loadInputLabel("implement", "Actual load used (kg)")).toBe("Actual load used (kg)");
    expect(loadInputLabel(undefined, "Actual load used (kg)")).toBe("Actual load used (kg)");
  });

  it("takes the first valid unit and treats junk as total", () => {
    expect(pickLoadUnit(undefined, "per_dumbbell")).toBe("per_dumbbell");
    expect(pickLoadUnit("implement", "per_dumbbell")).toBe("implement");
    expect(pickLoadUnit(null, "per_hand")).toBeUndefined();
    expect(normalizeLoadUnit("per_hand")).toBe("total");
  });
});

describe("guided player and feedback carry the unit", () => {
  it("custom rows: the prescription line says per dumbbell", () => {
    const state = buildGuidedStateFromExercises("custom_x", "Push", "2026-10-17", [
      { exercise_id: "dumbbell_bench_press", sets: 4, reps: 6, load_kg: 34, load_unit: "per_dumbbell" },
      { exercise_id: "bench_press", sets: 4, reps: 6, load_kg: 70 },
    ]);
    expect(state?.exercises[0].loadUnit).toBe("per_dumbbell");
    expect(formatPrescription(state!.exercises[0])).toContain("Load: 34 kg per dumbbell");
    expect(formatPrescription(state!.exercises[1])).toContain("Load: 70 kg");
  });

  it("planned sessions: the post-session dialog knows the unit from suggested", () => {
    const items = extractFeedbackExercises({ resolved: { resolved_session: {
      exercise_instances: [
        {
          exercise_id: "dumbbell_bench_press",
          load_model: "external_load",
          suggested: { suggested_external_load_kg: 35, load_unit: "per_dumbbell" },
        },
      ],
    } } });
    expect(items[0].loadUnit).toBe("per_dumbbell");
  });
});

describe("ExerciseCard", () => {
  it("shows '35 kg per dumbbell' for a dumbbell press and '+70 kg' for the barbell", () => {
    render(
      <>
        <ExerciseCard
          exercise={{ exercise_id: "dumbbell_bench_press", name: "Dumbbell Bench Press",
                      suggested_external_load_kg: 35, load_unit: "per_dumbbell" }}
        />
        <ExerciseCard exercise={{ exercise_id: "bench_press", name: "Bench Press", suggested_external_load_kg: 70 }} />
      </>,
    );
    expect(screen.getByText(/35 kg per dumbbell/)).toBeTruthy();
    expect(screen.getByText(/\+70 kg/)).toBeTruthy();
    expect(screen.queryByText(/\+35 kg/)).toBeNull();
  });
});
