import { describe, it, expect } from "vitest";

import { walkResolvedBlocks } from "@/lib/session-blocks";

/**
 * A245 G-7 (F20) — behaviour snapshot for the block walk that existed twice
 * inside session-card.tsx (once for the guided player, once for the card
 * layout). Pinned here BEFORE the two copies were replaced by one, so the
 * extraction can be checked rather than trusted.
 */
const ex = (id: string, blockUid?: string) => ({ exercise_id: id, block_uid: blockUid });
const block = (uid: string, extra: Record<string, unknown> = {}) => ({
  block_uid: uid,
  selected_exercises: [{}],
  ...extra,
});

const ids = (items: ReturnType<typeof walkResolvedBlocks>) =>
  items.map((i) => (i.kind === "exercise" ? i.instance.exercise_id : "[instruction]"));

describe("walkResolvedBlocks", () => {
  it("visits blocks in order and claims their instances", () => {
    const items = walkResolvedBlocks(
      [block("warmup"), block("main")],
      [ex("pullup", "main"), ex("mobility", "warmup")],
    );
    // Block order wins over instance order.
    expect(ids(items)).toEqual(["mobility", "pullup"]);
  });

  it("keeps several instances of the same block in their original order", () => {
    const items = walkResolvedBlocks(
      [block("main")],
      [ex("a", "main"), ex("b", "main"), ex("c", "main")],
    );
    expect(ids(items)).toEqual(["a", "b", "c"]);
  });

  it("never assigns an instance to two blocks", () => {
    const items = walkResolvedBlocks([block("main"), block("main")], [ex("a", "main")]);
    expect(ids(items)).toEqual(["a"]);
  });

  it("emits an instruction step for a block with notes and no exercises", () => {
    const items = walkResolvedBlocks(
      [{ block_uid: "warmup", selected_exercises: [], instructions: { notes: ["go easy"] } }],
      [],
    );
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe("instruction");
  });

  it("does NOT emit an instruction step for an empty block without notes", () => {
    const items = walkResolvedBlocks([{ block_uid: "x", selected_exercises: [] }], []);
    expect(items).toEqual([]);
  });

  it("appends orphan instances instead of dropping them", () => {
    // The safety net: a resolver change that stops emitting a block must not
    // make its exercises vanish from the workout.
    const items = walkResolvedBlocks([block("main")], [ex("a", "main"), ex("orphan", "gone")]);
    expect(ids(items)).toEqual(["a", "orphan"]);
  });

  it("handles a session with no blocks at all", () => {
    expect(ids(walkResolvedBlocks([], [ex("a"), ex("b")]))).toEqual(["a", "b"]);
  });

  it("numbers exercises consecutively, skipping instruction steps", () => {
    const items = walkResolvedBlocks(
      [
        { block_uid: "w", selected_exercises: [], instructions: { notes: ["x"] } },
        block("main"),
      ],
      [ex("a", "main"), ex("b", "main")],
    );
    const indices = items.flatMap((i) => (i.kind === "exercise" ? [i.exerciseIndex] : []));
    // An instruction must not consume an ordinal, or removal-by-index breaks.
    expect(indices).toEqual([0, 1]);
  });

  it("carries module_role, falling back to type", () => {
    const withRole = walkResolvedBlocks([block("m", { module_role: "primary" })], [ex("a", "m")]);
    expect(withRole[0].kind === "exercise" && withRole[0].moduleRole).toBe("primary");

    const withType = walkResolvedBlocks([block("m", { type: "complementary" })], [ex("a", "m")]);
    expect(withType[0].kind === "exercise" && withType[0].moduleRole).toBe("complementary");
  });

  it("leaves orphans without a module role", () => {
    const items = walkResolvedBlocks([], [ex("a")]);
    expect(items[0].kind === "exercise" && items[0].moduleRole).toBeUndefined();
  });
});
