import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { CORE_EXERCISES } from "@/components/circuit/circuit-exercises";
import { CATALOG_EXERCISE_IMAGES, exerciseImage } from "@/lib/exercise-images";

const CORE = join(process.cwd(), "public", "exercises", "core");

/** C280 — one illustration set for the circuit, reused by the guided players. */
describe("core circuit illustrations", () => {
  it("gives every circuit exercise an image (no TODO placeholders left)", () => {
    const without = CORE_EXERCISES.filter((e) => !e.image).map((e) => e.id);
    expect(without).toEqual([]);
  });

  it("ships no orphan file: every image in the folder is referenced", () => {
    const referenced = new Set(CORE_EXERCISES.map((e) => e.image));
    const orphans = readdirSync(CORE).filter((f) => !f.startsWith(".") && !referenced.has(f));
    expect(orphans).toEqual([]);
  });

  it("uses one format, WebP", () => {
    const other = CORE_EXERCISES.map((e) => e.image!).filter((f) => !f.endsWith(".webp"));
    expect(other).toEqual([]);
  });
});

describe("exerciseImage (guided and custom players)", () => {
  const catalog = JSON.parse(
    readFileSync(join(process.cwd(), "..", "backend", "catalog", "exercises", "v1", "exercises.json"), "utf8"),
  );
  const ids = new Set(
    (Array.isArray(catalog) ? catalog : catalog.exercises).map((e: { id: string }) => e.id),
  );

  it("maps only exercises that exist in the catalog", () => {
    const unknown = Object.keys(CATALOG_EXERCISE_IMAGES).filter((id) => !ids.has(id));
    expect(unknown).toEqual([]);
  });

  it("points every mapped exercise to a shipped circuit image", () => {
    const missing = Object.values(CATALOG_EXERCISE_IMAGES).filter((f) => !existsSync(join(CORE, f)));
    expect(missing).toEqual([]);
  });

  it("shows the left-side picture on the left side's turn", () => {
    expect(exerciseImage("side_plank")).toBe("/exercises/core/10_side_plank_r.webp");
    expect(exerciseImage("side_plank", "RIGHT")).toBe("/exercises/core/10_side_plank_r.webp");
    expect(exerciseImage("side_plank", "LEFT")).toBe("/exercises/core/11_side_plank_l.webp");
    expect(exerciseImage("copenhagen_plank", "LEFT")).toBe("/exercises/core/13_copenhagen_l.webp");
    expect(exerciseImage("side_plank_star", "LEFT")).toBe("/exercises/core/35_star_side_plank_l.webp");
    // symmetric exercises ignore the side
    expect(exerciseImage("dead_bug", "LEFT")).toBe("/exercises/core/02_dead_bug.webp");
  });

  it("returns null for exercises without an illustration", () => {
    expect(exerciseImage("max_hang_20mm")).toBeNull();
    expect(exerciseImage(undefined)).toBeNull();
    expect(exerciseImage(null)).toBeNull();
  });
});
