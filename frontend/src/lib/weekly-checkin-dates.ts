/**
 * Returns the target Monday (YYYY-MM-DD) for the weekly check-in banner.
 *
 * - Sunday → next Monday (tomorrow), so the user plans the upcoming week.
 * - Monday → today, so the user can still adjust the week they are entering.
 * - Tue–Sat → null (banner not shown mid-week).
 *
 * The Monday distinction is the whole point of B245: returning "next Monday"
 * on Mondays silently retargeted overrides one week into the future.
 */
export function getTargetMonday(from: Date = new Date()): string | null {
  const day = from.getDay(); // 0=Sun, 1=Mon, ... 6=Sat
  if (day !== 0 && day !== 1) return null;
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  if (day === 0) d.setDate(d.getDate() + 1); // Sun → Mon (tomorrow)
  // Mon → today (no shift)
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}
