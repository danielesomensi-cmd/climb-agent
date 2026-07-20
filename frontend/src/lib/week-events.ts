/**
 * A245 G-5 (F19) — the replanner event payloads, in one place.
 *
 * `/today` and `/week` each carried their own copy of ~20 handlers whose only
 * real content is "build this event object and post it". The copies had already
 * drifted: three of the other-activity handlers differed by a missing
 * `setError(null)` on /today, so a stale error banner survived a retry there
 * but not on /week. History shows the rest of the drift too — B186, D134 and
 * B276 each had to be applied twice.
 *
 * These are deliberately PURE: an event is a value, so it can be pinned by a
 * test without rendering anything. That is the behaviour snapshot the phase
 * acceptance asks for before the extraction, and it is what makes the
 * extraction safe rather than hopeful.
 *
 * Keys are omitted rather than sent as `undefined`: the backend distinguishes
 * "absent" from "null" on `slot`, and `JSON.stringify` drops undefined values
 * anyway — building the object explicitly keeps that intent visible.
 */

export type ReplannerEvent = Record<string, unknown>;

export function replanOverrideEvent(data: {
  intent: string;
  location: string;
  gym_id?: string;
  session_index?: number;
  date: string;
}): ReplannerEvent {
  return {
    date: data.date,
    intent: data.intent,
    location: data.location,
    ...(data.gym_id ? { gym_id: data.gym_id } : {}),
    ...(data.session_index != null ? { session_index: data.session_index } : {}),
  };
}

export function moveSessionEvent(data: {
  from_date: string;
  from_slot: string;
  to_date: string;
  to_slot: string;
}): ReplannerEvent {
  return { event_type: "move_session", ...data };
}

export function addCustomSessionEvent(data: {
  custom_session_id: string;
  target_date: string;
  slot: string;
  location: string;
  gym_id?: string;
}): ReplannerEvent {
  return { event_type: "add_custom_session", ...data };
}

export function completeOtherActivityEvent(
  date: string,
  slot: string | undefined,
  feedback: string,
  durationMinutes?: number,
): ReplannerEvent {
  return {
    event_type: "complete_other_activity",
    date,
    feedback,
    ...(slot ? { slot } : {}),
    ...(durationMinutes != null ? { duration_minutes: durationMinutes } : {}),
  };
}

export function undoOtherActivityEvent(date: string, slot?: string): ReplannerEvent {
  return { event_type: "undo_other_activity", date, ...(slot ? { slot } : {}) };
}

export function removeOtherActivityEvent(date: string, slot?: string): ReplannerEvent {
  return { event_type: "remove_other_activity", date, ...(slot ? { slot } : {}) };
}

export function editOtherActivityEvent(
  date: string,
  slot: string | undefined,
  fields: { activity_name?: string; feedback?: string; duration_minutes?: number },
): ReplannerEvent {
  return {
    event_type: "edit_other_activity",
    date,
    ...(slot ? { slot } : {}),
    ...fields,
  };
}

export function undoOutdoorEvent(date: string): ReplannerEvent {
  return { event_type: "undo_outdoor", date };
}

export function removeOutdoorEvent(date: string): ReplannerEvent {
  return { event_type: "remove_outdoor", date };
}

export function markSessionEvent(
  status: "done" | "skipped" | "planned",
  date: string,
  sessionId: string,
): ReplannerEvent {
  const eventType =
    status === "done" ? "mark_done" : status === "skipped" ? "mark_skipped" : "mark_planned";
  return { event_type: eventType, date, session_ref: sessionId };
}
