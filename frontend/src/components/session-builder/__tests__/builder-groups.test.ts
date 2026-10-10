/**
 * A309 — Warmup / Main / Cooldown grouping of the session builder.
 *
 * The groups are a reading of `entry.tag` over one array, which is what gets
 * saved. These tests pin the two places where the order semantics changed
 * (a main add lands before the cooldown, reorder stays inside a group) and the
 * ones that must not change (warmup → main → cooldown builds save as before).
 */

import { describe, it, expect } from "vitest";
import {
  canMoveWithinGroup,
  computeDuration,
  groupEntries,
  insertMainEntry,
  moveWithinGroup,
  normalizeGroupOrder,
  restoreEntryAt,
} from "../builder-groups";

type E = { id: string; tag?: "warmup" | "cooldown" };
const w = (id: string): E => ({ id, tag: "warmup" });
const m = (id: string): E => ({ id });
const c = (id: string): E => ({ id, tag: "cooldown" });
const ids = (es: E[]) => es.map((e) => e.id);

describe("groupEntries", () => {
  it("splits by tag, keeps array order and array indices", () => {
    const g = groupEntries([w("w1"), w("w2"), m("m1"), m("m2"), c("c1")]);
    expect(g.warmup.map((x) => [x.entry.id, x.index])).toEqual([["w1", 0], ["w2", 1]]);
    expect(g.main.map((x) => [x.entry.id, x.index])).toEqual([["m1", 2], ["m2", 3]]);
    expect(g.cooldown.map((x) => [x.entry.id, x.index])).toEqual([["c1", 4]]);
  });

  it("an untagged entry (e.g. a saved session reopened in edit mode) is main", () => {
    const g = groupEntries([m("a"), m("b")]);
    expect(g.warmup).toEqual([]);
    expect(g.main).toHaveLength(2);
    expect(g.cooldown).toEqual([]);
  });
});

describe("insertMainEntry", () => {
  it("appends when there is no cooldown — same array as before A309", () => {
    expect(ids(insertMainEntry([w("w1"), m("m1")], m("m2")))).toEqual(["w1", "m1", "m2"]);
    expect(ids(insertMainEntry([], m("m1")))).toEqual(["m1"]);
  });

  it("lands before the cooldown block (was appended after the stretches)", () => {
    expect(ids(insertMainEntry([w("w1"), m("m1"), c("c1"), c("c2")], m("m2")))).toEqual([
      "w1", "m1", "m2", "c1", "c2",
    ]);
  });

  it("does not mutate its input", () => {
    const src = [m("m1"), c("c1")];
    insertMainEntry(src, m("m2"));
    expect(ids(src)).toEqual(["m1", "c1"]);
  });
});

describe("moveWithinGroup", () => {
  const list = [w("w1"), w("w2"), m("m1"), m("m2"), c("c1")];

  it("swaps with the neighbour of the same group", () => {
    expect(ids(moveWithinGroup(list, 3, -1))).toEqual(["w1", "w2", "m2", "m1", "c1"]);
    expect(ids(moveWithinGroup(list, 0, 1))).toEqual(["w2", "w1", "m1", "m2", "c1"]);
  });

  it("never crosses a group boundary", () => {
    expect(moveWithinGroup(list, 2, -1)).toBe(list); // first main can't go into warmup
    expect(moveWithinGroup(list, 1, 1)).toBe(list); // last warmup can't go into main
    expect(moveWithinGroup(list, 4, -1)).toBe(list); // cooldown can't go into main
    expect(canMoveWithinGroup(list, 2, -1)).toBe(false);
    expect(canMoveWithinGroup(list, 2, 1)).toBe(true);
  });

  it("is a no-op at the ends of the array", () => {
    expect(moveWithinGroup(list, 0, -1)).toBe(list);
    expect(moveWithinGroup(list, 4, 1)).toBe(list);
    expect(canMoveWithinGroup(list, 9, -1)).toBe(false);
  });

  it("an all-main list (edit mode) reorders freely, exactly as before", () => {
    const all = [m("a"), m("b"), m("c")];
    expect(ids(moveWithinGroup(all, 0, 1))).toEqual(["b", "a", "c"]);
    expect(ids(moveWithinGroup(all, 2, -1))).toEqual(["a", "c", "b"]);
  });
});

describe("restoreEntryAt (Undo of a remove)", () => {
  it("puts the entry back at its old index", () => {
    const before = [w("w1"), m("m1"), m("m2"), c("c1")];
    const removed = before[2];
    const after = before.filter((_, i) => i !== 2);
    expect(ids(restoreEntryAt(after, removed, 2))).toEqual(ids(before));
  });

  it("keeps group order even if the list changed in between", () => {
    // m2 was at index 3, but the warmup was removed meanwhile: index 3 is now past the cooldown.
    expect(ids(restoreEntryAt([m("m1"), c("c1"), c("c2")], m("m2"), 3))).toEqual(["m1", "m2", "c1", "c2"]);
  });

  it("clamps an out-of-range index", () => {
    expect(ids(restoreEntryAt([m("m1")], m("m0"), -3))).toEqual(["m0", "m1"]);
    expect(ids(restoreEntryAt([m("m1")], m("m2"), 99))).toEqual(["m1", "m2"]);
  });
});

describe("normalizeGroupOrder", () => {
  it("is the identity on a list already in group order", () => {
    const list = [w("w1"), m("m1"), c("c1")];
    expect(ids(normalizeGroupOrder(list))).toEqual(["w1", "m1", "c1"]);
  });

  it("is a stable partition otherwise", () => {
    expect(ids(normalizeGroupOrder([c("c1"), m("m1"), w("w1"), m("m2"), w("w2")]))).toEqual([
      "w1", "w2", "m1", "m2", "c1",
    ]);
  });
});

describe("computeDuration (moved, unchanged)", () => {
  const ex = (sets: number, reps: number | null, work: number | null, rest: number | null) => ({
    exercise: { sets, reps, work_seconds: work, rest_between_sets_seconds: rest },
  });

  it("sums sets × work + rests between sets", () => {
    // 3×10s + 2×180s = 390s → 7 min (6.5 rounds up)
    expect(computeDuration([ex(3, null, 10, 180)])).toBe(7);
  });

  it("reps count 4 s each, defaults 30 s work and 60 s rest", () => {
    // 2×(5×4) + 1×60 = 100s ; 1×30 = 30s → 130s → 2 min
    expect(computeDuration([ex(2, 5, null, null), ex(1, null, null, null)])).toBe(2);
  });

  it("never reports less than one minute", () => {
    expect(computeDuration([])).toBe(1);
  });
});
