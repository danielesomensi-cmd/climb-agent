/**
 * B-GOAL-DEADLINE-DERIVED (B414) — the end of the plan shown in Settings, from
 * the macrocycle (`end_date`, its last day), not `goal.deadline`: that one is
 * derived (the day the goal was saved + N weeks) and drifts from the real end
 * — a "Start new cycle" starts the next Monday, and the regeneration after a
 * goal edit keeps the cycle's own length.
 */
export function planEndLabel(endDate: string | null | undefined): string {
  if (!endDate || !/^\d{4}-\d{2}-\d{2}$/.test(endDate.slice(0, 10))) return "—";
  // A calendar day: read at noon UTC so no time zone moves it a day.
  return new Date(`${endDate.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
