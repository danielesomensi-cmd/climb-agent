// B309 — slot availability for a day of the week plan.
//
// The engine rejects an insert whose slot is already taken
// (`add_custom_session` raises "Slot 'x' already occupied"), counting both
// planned sessions and "other activities" (B276). Callers that pick a slot on
// the user's behalf — the coach's "Add to today & run" CTA — must therefore
// resolve a FREE slot client-side instead of hardcoding one, or the insert
// fails and the just-created custom session is left orphaned.

import { normalizeOtherActivities } from "@/lib/other-activity";
import type { DayPlan, WeekPlan } from "@/lib/types";

export type Slot = "morning" | "lunch" | "evening";

/** Preference order when picking a slot automatically.
 *
 * `evening` first: it is where training sessions land by default (and was the
 * hardcoded value before B309, so the common case is unchanged). Falls back to
 * the canonical planner order for the remaining slots. */
export const AUTO_SLOT_ORDER: readonly Slot[] = ["evening", "morning", "lunch"];

/** The day with this date in the week plan, or null. */
export function findDay(week: WeekPlan, date: string): DayPlan | null {
  for (const w of week.weeks ?? []) {
    for (const day of w.days ?? []) {
      if (day.date === date) return day;
    }
  }
  return null;
}

/** Slots taken on this day — by a session or by an other activity (B276). */
export function occupiedSlots(day: DayPlan): Set<string> {
  const taken = new Set<string>();
  for (const s of day.sessions ?? []) {
    if (s.slot) taken.add(s.slot);
  }
  for (const a of normalizeOtherActivities(day)) {
    if (a.slot) taken.add(a.slot);
  }
  return taken;
}

/** First free slot in preference order, or null when the day is full. */
export function firstFreeSlot(day: DayPlan): Slot | null {
  const taken = occupiedSlots(day);
  return AUTO_SLOT_ORDER.find((slot) => !taken.has(slot)) ?? null;
}
