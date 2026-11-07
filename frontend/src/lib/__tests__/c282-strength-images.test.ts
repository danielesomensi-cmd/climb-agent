import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { CATALOG_EXERCISE_IMAGES, exerciseImage } from "@/lib/exercise-images";

const PUBLIC = join(process.cwd(), "public");
const STRENGTH = join(PUBLIC, "exercises", "strength");

const catalog: Array<{ id: string; alt_sides?: boolean }> = (() => {
  const raw = JSON.parse(
    readFileSync(join(process.cwd(), "..", "backend", "catalog", "exercises", "v1", "exercises.json"), "utf8"),
  );
  return Array.isArray(raw) ? raw : raw.exercises;
})();
const altSides = new Set(catalog.filter((e) => e.alt_sides).map((e) => e.id));

const strengthIds = Object.entries(CATALOG_EXERCISE_IMAGES)
  .filter(([, file]) => file.startsWith("strength/"))
  .map(([id]) => id);

const shipped = (publicPath: string) => existsSync(join(PUBLIC, publicPath));

/** C282 — strength and prehab illustrations in the guided and custom players. */
describe("strength illustrations", () => {
  it("points every mapped strength exercise to a shipped picture", () => {
    expect(strengthIds.length).toBeGreaterThan(0);
    const missing = strengthIds.filter((id) => !shipped(exerciseImage(id)!));
    expect(missing).toEqual([]);
  });

  it("ships a mirrored picture for every one-sided (alt_sides) exercise", () => {
    const wrong = strengthIds
      .filter((id) => altSides.has(id))
      .filter((id) => {
        const left = exerciseImage(id, "LEFT")!;
        return left === exerciseImage(id) || !shipped(left);
      });
    expect(wrong).toEqual([]);
  });

  it("ships no orphan file in the strength folder", () => {
    const used = new Set<string>();
    for (const id of strengthIds) {
      used.add(exerciseImage(id)!);
      used.add(exerciseImage(id, "LEFT")!);
    }
    const orphans = readdirSync(STRENGTH)
      .filter((f) => !f.startsWith("."))
      .map((f) => `/exercises/strength/${f}`)
      .filter((p) => !used.has(p));
    expect(orphans).toEqual([]);
  });

  it("keeps every strength picture small (gym 3G, A245 F-4)", () => {
    const big = readdirSync(STRENGTH).filter((f) => statSync(join(STRENGTH, f)).size > 100_000);
    expect(big).toEqual([]);
  });

  it("mirrors only on the left side's turn, and only one-sided moves", () => {
    expect(exerciseImage("archer_pullup")).toBe("/exercises/strength/archer_pullup.webp");
    expect(exerciseImage("archer_pullup", "RIGHT")).toBe("/exercises/strength/archer_pullup.webp");
    expect(exerciseImage("archer_pullup", "LEFT")).toBe("/exercises/strength/archer_pullup_l.webp");
    expect(exerciseImage("toes_to_bar", "LEFT")).toBe("/exercises/strength/toes_to_bar.webp");
  });

  it("shows toes-to-bar for the legs-to-the-bar raise and leaves inexact moves without a picture", () => {
    expect(exerciseImage("hanging_leg_raise")).toBe("/exercises/strength/toes_to_bar.webp");
    expect(exerciseImage("knees_to_elbows")).toBeNull();
    expect(exerciseImage("elbow_eccentric_curl")).toBeNull();
  });
});
