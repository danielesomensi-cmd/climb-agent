import type { OutdoorSession } from "@/lib/types";

/**
 * B410 (B-OUTDOOR-CRAG-PICKER point 3) — a day can hold several crags (B341),
 * and Edit / «Log routes» / «Quick log» used to open the last one only.
 *
 * - `edit` (the pencil on a done day): straight to the form when the day has
 *   one crag, otherwise ask which one.
 * - `log` («Log routes», «Quick log»): the day already has a log, so the tap
 *   means either "change it" or "add another crag" — always ask.
 */
export type CragChoiceIntent = "edit" | "log";

export function needsCragPicker(sessions: readonly OutdoorSession[], intent: CragChoiceIntent): boolean {
  if (sessions.length === 0) return false;
  return intent === "log" || sessions.length > 1;
}

/** The day's crags from `GET /api/outdoor/log/{date}`: `sessions`, else the one `session`. */
export function sessionsOfDay(res: { session?: OutdoorSession | null; sessions?: OutdoorSession[] | null }): OutdoorSession[] {
  if (res.sessions?.length) return res.sessions;
  return res.session ? [res.session] : [];
}
