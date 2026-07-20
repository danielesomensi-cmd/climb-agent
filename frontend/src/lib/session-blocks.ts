/**
 * A245 G-7 (F20) — the one walk over a resolved session's blocks.
 *
 * `session-card.tsx` contained this algorithm TWICE, ~800 lines apart: once to
 * build the guided-session exercise list, once to lay the card out. Same
 * semantics, different output types, no shared code — so the order the user
 * sees while training and the order the guided player runs could drift apart
 * with any edit to either copy.
 *
 * The walk itself is the thing worth having in one place:
 *  - blocks are visited in order;
 *  - a block with no `selected_exercises` but with `instructions` is an
 *    instruction step (warmup notes and the like);
 *  - otherwise the block claims every not-yet-used instance whose `block_uid`
 *    matches it;
 *  - instances belonging to no block are appended at the end rather than
 *    dropped — that fallback is what keeps a resolver change from silently
 *    losing exercises.
 */

export type ResolvedBlockLike = Record<string, unknown>;
export type ResolvedInstanceLike = Record<string, unknown>;

export type SessionItem =
  | { kind: "instruction"; block: ResolvedBlockLike }
  | {
      kind: "exercise";
      instance: ResolvedInstanceLike;
      /** Ordinal among exercises only — instruction steps do not consume one. */
      exerciseIndex: number;
      /** `module_role` (falling back to `type`) of the block that claimed it. */
      moduleRole?: string;
    };

export function walkResolvedBlocks(
  blocks: ResolvedBlockLike[],
  instances: ResolvedInstanceLike[],
): SessionItem[] {
  const items: SessionItem[] = [];
  const used = new Set<number>();
  let exerciseIndex = 0;

  for (const block of blocks) {
    const blockUid = (block.block_uid as string) ?? "";
    const selected = (block.selected_exercises ?? []) as unknown[];
    const moduleRole = (block.module_role ?? block.type) as string | undefined;

    if (selected.length === 0 && block.instructions) {
      items.push({ kind: "instruction", block });
      continue;
    }

    for (let i = 0; i < instances.length; i++) {
      if (used.has(i)) continue;
      if ((instances[i].block_uid as string) !== blockUid) continue;
      items.push({ kind: "exercise", instance: instances[i], exerciseIndex: exerciseIndex++, moduleRole });
      used.add(i);
    }
  }

  // Orphans last: an instance whose block_uid matches nothing must still be
  // trained, not silently dropped.
  for (let i = 0; i < instances.length; i++) {
    if (used.has(i)) continue;
    items.push({ kind: "exercise", instance: instances[i], exerciseIndex: exerciseIndex++ });
  }

  return items;
}
