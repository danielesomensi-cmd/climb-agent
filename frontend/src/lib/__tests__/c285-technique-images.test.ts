import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import {
  CATALOG_EXERCISE_EXTRA_PANELS,
  CATALOG_EXERCISE_IMAGES,
  exerciseImage,
  exerciseImagePanels,
} from "@/lib/exercise-images";
import { CORE_EXERCISES } from "@/components/circuit/circuit-exercises";

const PUBLIC = join(process.cwd(), "public");
const shipped = (publicPath: string) => existsSync(join(PUBLIC, publicPath));

const catalogIds = new Set<string>(
  (() => {
    const raw = JSON.parse(
      readFileSync(join(process.cwd(), "..", "backend", "catalog", "exercises", "v1", "exercises.json"), "utf8"),
    );
    return (Array.isArray(raw) ? raw : raw.exercises).map((e: { id: string }) => e.id);
  })(),
);

/** C285 — technique illustrations, extra panels, and the pictures that showed another exercise. */
describe("technique illustrations", () => {
  it("maps only real catalog ids", () => {
    const unknown = [
      ...Object.keys(CATALOG_EXERCISE_IMAGES),
      ...Object.keys(CATALOG_EXERCISE_EXTRA_PANELS),
    ].filter((id) => !catalogIds.has(id));
    expect(unknown).toEqual([]);
  });

  it("ships every main picture and every extra panel", () => {
    const missing = Object.keys(CATALOG_EXERCISE_IMAGES)
      .flatMap((id) => exerciseImagePanels(id))
      .filter((p) => !shipped(p));
    expect(missing).toEqual([]);
  });

  it("gives extra panels only to exercises that have a main picture", () => {
    const orphans = Object.keys(CATALOG_EXERCISE_EXTRA_PANELS).filter((id) => !exerciseImage(id));
    expect(orphans).toEqual([]);
  });

  it("shows the backstep first and the drop knee as a second panel", () => {
    expect(exerciseImagePanels("twist_lock_drill")).toEqual([
      "/exercises/technique/twist_lock_backstep.webp",
      "/exercises/technique/drop_knee.webp",
    ]);
    expect(exerciseImage("twist_lock_drill")).toBe("/exercises/technique/twist_lock_backstep.webp");
    expect(exerciseImagePanels("flag_practice")).toEqual(["/exercises/technique/flag_outside.webp"]);
  });

  it("returns no panels for an exercise without a picture", () => {
    expect(exerciseImagePanels("three_attempt_comp")).toEqual([]);
    expect(exerciseImagePanels(null)).toEqual([]);
  });

  it("no longer shows the pictures of a different exercise", () => {
    expect(exerciseImage("straddle_l_sit")).toBeNull();
    expect(exerciseImage("dragon_flag_tuck")).toBeNull();
    expect(exerciseImage("hanging_leg_raise")).toBe("/exercises/strength/toes_to_bar.webp");
    const circuit = new Map(CORE_EXERCISES.map((e) => [e.id, e.image]));
    expect(circuit.get("ce_straddle_l_sit")).toBeUndefined();
    expect(circuit.get("ce_dragon_flag_tuck")).toBeUndefined();
  });
});
