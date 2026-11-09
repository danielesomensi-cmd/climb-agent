import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { CATALOG_EXERCISE_IMAGES, exerciseImage, mobilityStepImage } from "@/lib/exercise-images";

const PUBLIC = join(process.cwd(), "public");
const STRETCH = join(PUBLIC, "exercises", "stretch");

type MobilityEntry = { id: string; unilateral: boolean; image?: string | null };
const mobility: MobilityEntry[] = JSON.parse(
  readFileSync(join(process.cwd(), "..", "backend", "catalog", "mobility", "v1", "mobility.json"), "utf8"),
).entries;
const catalog: Array<{ id: string; alt_sides?: boolean }> = (() => {
  const raw = JSON.parse(
    readFileSync(join(process.cwd(), "..", "backend", "catalog", "exercises", "v1", "exercises.json"), "utf8"),
  );
  return Array.isArray(raw) ? raw : raw.exercises;
})();

const shipped = (publicPath: string) => existsSync(join(PUBLIC, publicPath));

// The model kept drawing folded arms instead of the vertical forearm: a wrong
// pose misleads more than the region silhouette the player falls back to.
// C285 (vector batch) removed three more for the same reason: the pigeon was
// drawn as a low lunge, the wall soleus stretch with the back heel off the
// floor and the knee straight, thread the needle as a twisted bridge.
const NO_PICTURE = new Set([
  "stretch_sleeper",
  "stretch_pigeon",
  "stretch_wall_soleus",
  "stretch_thread_the_needle",
]);

/** C281 — one illustration per Mobility stretch, mirrored for the left side. */
describe("Mobility stretch illustrations", () => {
  it("gives every stretch in the mobility catalog its own picture", () => {
    const wrong = mobility
      .filter((e) => !NO_PICTURE.has(e.id))
      .filter((e) => e.image !== `/exercises/stretch/${e.id}.webp` || !shipped(e.image))
      .map((e) => e.id);
    expect(wrong).toEqual([]);
    expect(mobility.filter((e) => NO_PICTURE.has(e.id) && e.image).map((e) => e.id)).toEqual([]);
  });

  it("ships the mirrored picture for every one-sided stretch", () => {
    const missing = mobility
      .filter((e) => e.unilateral && e.image && !shipped(mobilityStepImage(e.image, "left")!))
      .map((e) => e.id);
    expect(missing).toEqual([]);
  });

  it("ships no orphan file in the stretch folder", () => {
    const used = new Set<string>();
    for (const e of mobility) {
      if (!e.image) continue;
      used.add(e.image);
      if (e.unilateral) used.add(mobilityStepImage(e.image, "left")!);
    }
    for (const id of Object.keys(CATALOG_EXERCISE_IMAGES)) {
      used.add(exerciseImage(id)!);
      if (catalog.find((c) => c.id === id)?.alt_sides) used.add(exerciseImage(id, "LEFT")!);
    }
    const orphans = readdirSync(STRETCH)
      .filter((f) => !f.startsWith("."))
      .map((f) => `/exercises/stretch/${f}`)
      .filter((p) => !used.has(p));
    expect(orphans).toEqual([]);
  });

  it("keeps every stretch picture small (gym 3G, A245 F-4)", () => {
    const big = readdirSync(STRETCH).filter((f) => statSync(join(STRETCH, f)).size > 100_000);
    expect(big).toEqual([]);
  });

  it("mirrors only on the left side's turn", () => {
    expect(mobilityStepImage("/exercises/stretch/stretch_piriformis.webp", "left")).toBe(
      "/exercises/stretch/stretch_piriformis_l.webp",
    );
    expect(mobilityStepImage("/exercises/stretch/stretch_piriformis.webp", "right")).toBe(
      "/exercises/stretch/stretch_piriformis.webp",
    );
    expect(mobilityStepImage("/exercises/stretch/stretch_cobra.webp", null)).toBe(
      "/exercises/stretch/stretch_cobra.webp",
    );
    expect(mobilityStepImage(null, "left")).toBeNull();
    expect(mobilityStepImage(undefined, null)).toBeNull();
  });
});

describe("exerciseImage — cooldown stretches in the guided and custom players", () => {
  it("shows the left-side picture of a one-sided stretch on the left side's turn", () => {
    const missing = Object.keys(CATALOG_EXERCISE_IMAGES)
      .filter((id) => catalog.find((c) => c.id === id)?.alt_sides)
      .map((id) => exerciseImage(id, "LEFT")!)
      .filter((p) => !shipped(p));
    expect(missing).toEqual([]);
    expect(exerciseImage("hip_flexor_couch_stretch", "LEFT")).toBe(
      "/exercises/stretch/hip_flexor_couch_stretch_l.webp",
    );
    expect(exerciseImage("hip_flexor_couch_stretch")).toBe("/exercises/stretch/hip_flexor_couch_stretch.webp");
    // C285: the pigeon picture showed a low lunge and was removed
    expect(exerciseImage("cooldown_hip_pigeon")).toBeNull();
    expect(exerciseImage("cooldown_hip_pigeon", "LEFT")).toBeNull();
  });
});
