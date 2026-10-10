/**
 * A309 — Warmup / Main / Cooldown grouping of the session builder's entries.
 *
 * The groups are a reading of `entry.tag`; the entries array stays the single
 * source of truth and is what gets saved. For the screen to tell the truth
 * about the playback order, the array is kept in group order (warmup → main →
 * cooldown) by the only operations that could break it:
 *
 * - a main exercise added after a cooldown block lands before the cooldown
 *   (it used to be appended after it, i.e. played after the stretches);
 * - reorder moves an entry only within its own group (a warmup row can no
 *   longer drift mid-session).
 *
 * Everything else — warmup prepended, cooldown appended, edit, remove — is
 * unchanged, so a session built warmup → main → cooldown saves exactly the
 * same exercises array as before.
 */

export type BuilderGroup = "warmup" | "main" | "cooldown";

export const GROUP_ORDER: readonly BuilderGroup[] = ["warmup", "main", "cooldown"];

interface Tagged {
  tag?: "warmup" | "cooldown";
}

export function entryGroup(entry: Tagged): BuilderGroup {
  return entry.tag ?? "main";
}

export interface GroupedEntry<T> {
  entry: T;
  /** Position in the entries array (what move/edit/remove act on). */
  index: number;
}

/** Entries split by group, each keeping its array index, in array order. */
export function groupEntries<T extends Tagged>(entries: T[]): Record<BuilderGroup, GroupedEntry<T>[]> {
  const groups: Record<BuilderGroup, GroupedEntry<T>[]> = { warmup: [], main: [], cooldown: [] };
  entries.forEach((entry, index) => {
    groups[entryGroup(entry)].push({ entry, index });
  });
  return groups;
}

/** Stable sort into group order (identity on an array already in order). */
export function normalizeGroupOrder<T extends Tagged>(entries: T[]): T[] {
  const g = groupEntries(entries);
  return GROUP_ORDER.flatMap((k) => g[k].map((x) => x.entry));
}

/** Add a main exercise: after the last main row, before any cooldown. */
export function insertMainEntry<T extends Tagged>(entries: T[], entry: T): T[] {
  const firstCooldown = entries.findIndex((e) => entryGroup(e) === "cooldown");
  if (firstCooldown === -1) return [...entries, entry];
  return [...entries.slice(0, firstCooldown), entry, ...entries.slice(firstCooldown)];
}

/** Can the entry at `index` move one step in `direction` without leaving its group? */
export function canMoveWithinGroup<T extends Tagged>(entries: T[], index: number, direction: -1 | 1): boolean {
  const to = index + direction;
  if (index < 0 || index >= entries.length || to < 0 || to >= entries.length) return false;
  return entryGroup(entries[index]) === entryGroup(entries[to]);
}

/** Swap with the neighbour in the same group; otherwise the array is returned as is. */
export function moveWithinGroup<T extends Tagged>(entries: T[], index: number, direction: -1 | 1): T[] {
  if (!canMoveWithinGroup(entries, index, direction)) return entries;
  const next = [...entries];
  const to = index + direction;
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

/** Undo of a remove: the entry goes back at its old index, then group order is restored. */
export function restoreEntryAt<T extends Tagged>(entries: T[], entry: T, index: number): T[] {
  const at = Math.max(0, Math.min(index, entries.length));
  return normalizeGroupOrder([...entries.slice(0, at), entry, ...entries.slice(at)]);
}

// ── Duration (moved here from session-builder.tsx, unchanged) ─────────

interface DurationExercise {
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_between_sets_seconds: number | null;
}

/** Estimated minutes (min 1) — mirrors the backend estimate. */
export function computeDuration(entries: Array<{ exercise: DurationExercise }>): number {
  let totalSeconds = 0;
  for (const { exercise: ex } of entries) {
    const sets = ex.sets || 1;
    const workPerSet = ex.work_seconds ?? (ex.reps ? ex.reps * 4 : 30);
    const rest = ex.rest_between_sets_seconds ?? 60;
    totalSeconds += sets * workPerSet + (sets - 1) * rest;
  }
  return Math.max(1, Math.round(totalSeconds / 60));
}
