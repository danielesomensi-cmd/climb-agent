/**
 * A245 G-1 (F50) — one way to turn a `YYYY-MM-DD` into a Date.
 *
 * `new Date("2026-07-20")` is parsed by the spec as **UTC midnight**. West of
 * Greenwich that instant is still the 19th locally, so anything that formatted
 * or compared it showed the wrong day: a macrocycle appeared to start a day
 * early, `computeCurrentWeek` could land on the previous week, and the phase
 * celebration could fire a day off.
 *
 * `new Date("2026-07-20T00:00:00")` — no timezone suffix — is parsed as **local
 * midnight**, which is what a plain calendar date means to a user. Some call
 * sites already appended the suffix and some did not, which is exactly the kind
 * of split that produces bugs only for users in certain timezones.
 *
 * The engine stores plain dates with no timezone (see the `B5` finding, still
 * open): until that changes, "local midnight" is the only interpretation that
 * matches what the user sees on their calendar.
 */

/** Parse a `YYYY-MM-DD` as LOCAL midnight. Invalid input yields an Invalid Date. */
export function parseISODateLocal(iso: string): Date {
  if (typeof iso !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(iso)) {
    return new Date(NaN);
  }
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  // The numeric constructor is local-time by definition, and unlike string
  // concatenation it cannot be re-interpreted as UTC by an engine quirk.
  return new Date(y, m - 1, d);
}

/** `YYYY-MM-DD` for a Date, in LOCAL time (never `toISOString`, which is UTC). */
export function toISODateLocal(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Shift a `YYYY-MM-DD` by whole days, staying in local time. */
export function shiftISODate(iso: string, days: number): string {
  const d = parseISODateLocal(iso);
  if (Number.isNaN(d.getTime())) return iso;
  d.setDate(d.getDate() + days);
  return toISODateLocal(d);
}
