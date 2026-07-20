/**
 * A245 F-2 (F59) — shared display formatters.
 *
 * Each of these existed as several byte-identical copies. `formatDateShort` was
 * the worst case: five copies under two different names (`formatDateShort` and
 * `formatDateLabel`), which is how a duplicate survives a grep for its own name.
 */

const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

/** "strength_long" → "Strength Long" */
export function formatSessionName(sessionId: string): string {
  return sessionId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * "2026-07-20" → "20 Jul". Returns the input unchanged if it isn't an ISO date.
 *
 * Deliberately parses the string by hand rather than via `new Date()`: the
 * Date constructor treats a bare `YYYY-MM-DD` as UTC, which shows the previous
 * day to anyone west of UTC (that is finding F50, still open).
 */
export function formatDateShort(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const day = parseInt(parts[2], 10);
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${day} ${MONTHS_SHORT[monthIdx] ?? parts[1]}`;
}

/**
 * The five perceived-difficulty levels the engine consumes.
 *
 * NOT to be confused with the three-value list in `day-card.tsx`: that one is
 * for "other activity" feedback and carries badge styling, not these solid
 * background colours. They look like duplicates and are not — see A245 F-2.
 *
 * A245 F-3 (F60): `ring` is a LITERAL class, not derived at runtime. The chip
 * used to build its ring as `ring-${opt.color.replace("bg-","")}`. Tailwind
 * scans source text, so a class assembled at runtime is never emitted — the
 * selection ring simply did not exist. Nothing looked broken (the chip still
 * changed background), which is why it survived. Keeping the pair in the data
 * means the compiler sees both classes.
 */
export const FEEDBACK_OPTIONS = [
  { value: "very_easy", label: "Very easy", color: "bg-green-600", ring: "ring-green-600" },
  { value: "easy", label: "Easy", color: "bg-green-500", ring: "ring-green-500" },
  { value: "ok", label: "OK", color: "bg-yellow-500", ring: "ring-yellow-500" },
  { value: "hard", label: "Hard", color: "bg-orange-500", ring: "ring-orange-500" },
  { value: "very_hard", label: "Very hard", color: "bg-red-500", ring: "ring-red-500" },
] as const;
