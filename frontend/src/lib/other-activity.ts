import type { DayPlan, OtherActivity } from "@/lib/types";

/**
 * Normalize a day's "other activities" into a list (B276).
 *
 * Prefers the new `other_activities` array emitted by the engine. Falls back to
 * synthesizing a single-item list from the legacy scalar fields so that
 * preserved (immutable) pre-B276 days still render. Returns [] when the day has
 * no other activity.
 */
export function normalizeOtherActivities(day: DayPlan): OtherActivity[] {
  if (Array.isArray(day.other_activities)) return day.other_activities;
  if (day.other_activity) {
    return [
      {
        slot: day.other_activity_slot,
        name: day.other_activity_name,
        status: day.other_activity_status,
        feedback: day.other_activity_feedback,
        load: day.other_activity_load,
        duration_minutes: day.other_activity_duration_minutes,
      },
    ];
  }
  return [];
}

/** True when the day carries at least one other activity (list or legacy). */
export function hasOtherActivity(day: DayPlan): boolean {
  return normalizeOtherActivities(day).length > 0;
}
