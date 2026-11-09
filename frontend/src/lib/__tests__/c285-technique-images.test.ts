import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import {
  CATALOG_EXERCISE_EXTRA_PANELS,
  CATALOG_EXERCISE_IMAGES,
  exerciseImage,
  exerciseImagePanels,
} from "@/lib/exercise-images";
import { CORE_EXERCISES } from "@/components/circuit/circuit-exercises";

const PUBLIC = join(process.cwd(), "public");
const TECHNIQUE = join(PUBLIC, "exercises", "technique");
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
    expect(exerciseImage("hip_rotation_drill")).toBe("/exercises/technique/hip_rotation.webp");
    expect(exerciseImage("tech_hard_target")).toBe("/exercises/technique/hard_target_profile.webp");
  });

  it("returns no panels for an exercise without a picture", () => {
    expect(exerciseImagePanels("three_attempt_comp")).toEqual([]);
    expect(exerciseImagePanels(null)).toEqual([]);
  });

  it("no longer shows the pictures of a different exercise", () => {
    expect(exerciseImage("straddle_l_sit")).toBeNull();
    expect(exerciseImage("hanging_leg_raise")).toBe("/exercises/strength/toes_to_bar.webp");
    const circuit = new Map(CORE_EXERCISES.map((e) => [e.id, e.image]));
    expect(circuit.get("ce_straddle_l_sit")).toBeUndefined();
    // vector batch: six more removed until they are redrawn
    for (const id of ["kneeling_superman", "cooldown_hip_pigeon", "face_pull"]) {
      expect(exerciseImage(id)).toBeNull();
    }
    expect(circuit.get("ce_bird_dog")).toBeUndefined();
    expect(circuit.get("ce_plank_hip_dips")).toBeUndefined();
  });
});

/** C285 (vector batch) — pictures drawn by scripts/illustrations/vector/. */
describe("vector illustrations", () => {
  const circuit = new Map(CORE_EXERCISES.map((e) => [e.id, e.image]));

  it("shows the new drawing for every exercise of the batch", () => {
    const expected: Record<string, string> = {
      tech_hard_target: "technique/hard_target_profile.webp",
      glued_feet_board: "technique/glued_feet.webp",
      tech_talon_feet: "technique/glued_feet.webp",
      small_feet_press_hold: "technique/small_feet_press.webp",
      rest_and_clip_drill: "technique/kneebar_rest.webp",
      fall_practice: "technique/fall_practice.webp",
      fall_ladder: "technique/fall_practice.webp",
      pocket_rampup_hangboard: "strength/pocket_rampup.webp",
      single_finger_pocket_rampup: "strength/pocket_rampup_mono.webp",
      v_sit: "strength/v_sit.webp",
      v_sit_45: "strength/v_sit_45.webp",
      elevated_pike_pushup: "strength/elevated_pike_pushup.webp",
      ring_fallout: "strength/ring_fallout.webp",
      pistol_squat: "strength/pistol_squat.webp",
      dragon_flag_tuck: "core/41_dragon_flag_tuck.webp",
      dragon_flag_tuck_negative: "core/41_dragon_flag_tuck.webp",
    };
    for (const [id, file] of Object.entries(expected)) {
      expect(exerciseImage(id), id).toBe(`/exercises/${file}`);
      expect(shipped(`/exercises/${file}`), file).toBe(true);
    }
    expect(circuit.get("ce_dragon_flag_tuck")).toBe("41_dragon_flag_tuck.webp");
  });

  it("never shows a two-finger pocket for the one-finger drill, nor the reverse", () => {
    expect(exerciseImage("single_finger_pocket_rampup")).not.toBe(exerciseImage("pocket_rampup_hangboard"));
  });

  it("mirrors the one-sided drawings on the left side's turn", () => {
    expect(exerciseImage("small_feet_press_hold", "LEFT")).toBe("/exercises/technique/small_feet_press_l.webp");
    expect(exerciseImage("small_feet_press_hold", "RIGHT")).toBe("/exercises/technique/small_feet_press.webp");
    expect(shipped("/exercises/technique/small_feet_press_l.webp")).toBe(true);
    expect(exerciseImage("pistol_squat", "LEFT")).toBe("/exercises/strength/pistol_squat_l.webp");
    expect(shipped("/exercises/strength/pistol_squat_l.webp")).toBe(true);
    // two-sided positions ignore the side
    expect(exerciseImage("glued_feet_board", "LEFT")).toBe("/exercises/technique/glued_feet.webp");
  });

  it("ships a changed picture under a new file name (the image cache is keyed by URL for 7 days)", () => {
    expect(shipped("/exercises/technique/hard_target.webp")).toBe(false);
    expect(shipped("/exercises/core/31_dragon_flag_tuck.webp")).toBe(false);
  });

  it("ships no orphan file in the technique folder, and keeps every picture small", () => {
    const used = new Set<string>();
    for (const id of Object.keys(CATALOG_EXERCISE_IMAGES)) {
      for (const p of exerciseImagePanels(id)) used.add(p);
      used.add(exerciseImage(id, "LEFT")!);
    }
    const files = readdirSync(TECHNIQUE).filter((f) => !f.startsWith("."));
    expect(files.map((f) => `/exercises/technique/${f}`).filter((p) => !used.has(p))).toEqual([]);
    expect(files.filter((f) => statSync(join(TECHNIQUE, f)).size > 100_000)).toEqual([]);
  });
});
