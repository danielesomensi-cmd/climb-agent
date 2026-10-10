/**
 * A310 — pure helpers for the coach chat (day separators, stale ad-hoc cards,
 * failed-send recovery). Kept out of the page so they are unit-tested.
 */

import { parseISODateLocal, shiftISODate, toISODateLocal } from "./dates";

const WEEKDAYS_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

/**
 * Client-local YYYY-MM-DD of a message timestamp (`created_at` is an ISO
 * instant from the server). Missing or unparsable → null.
 */
export function localDateOf(createdAt: string | null | undefined): string | null {
  if (!createdAt) return null;
  const d = new Date(createdAt);
  if (Number.isNaN(d.getTime())) return null;
  return toISODateLocal(d);
}

/** "Today" / "Yesterday" / "Tue 7 Oct" for a local YYYY-MM-DD. */
export function dayLabel(date: string, today: string): string {
  if (date === today) return "Today";
  if (date === shiftISODate(today, -1)) return "Yesterday";
  const d = parseISODateLocal(date);
  if (Number.isNaN(d.getTime())) return date;
  return `${WEEKDAYS_SHORT[d.getDay()]} ${d.getDate()} ${MONTHS_SHORT[d.getMonth()]}`;
}

/**
 * For each message, the day-divider label to render ABOVE it, or null.
 * A message without `created_at` was sent in this session, i.e. today.
 */
export function dayDividers(
  messages: ReadonlyArray<{ created_at?: string }>,
  today: string,
): Array<string | null> {
  let prev: string | null = null;
  return messages.map((m) => {
    const date = localDateOf(m.created_at) ?? today;
    if (date === prev) return null;
    prev = date;
    return dayLabel(date, today);
  });
}

/**
 * The date an ad-hoc card's loads were computed for: the preview's
 * `resolved_for_date` (A299), else the local day of the message (older rows
 * predate the field), else null (composed in this session → today).
 */
export function adhocCardDate(
  resolvedForDate: string | null | undefined,
  createdAt: string | null | undefined,
): string | null {
  return resolvedForDate || localDateOf(createdAt);
}

/**
 * A card built for another day must never be added to today: its loads,
 * ladder doses and key-session check belong to that day.
 */
export function isStaleAdhocCard(
  resolvedForDate: string | null | undefined,
  createdAt: string | null | undefined,
  today: string,
): boolean {
  const date = adhocCardDate(resolvedForDate, createdAt);
  return date != null && date !== today;
}

/** The user request that produced the message at `index` (nearest earlier user turn). */
export function requestBefore(
  messages: ReadonlyArray<{ role: string; content: string }>,
  index: number,
): string | null {
  for (let i = index - 1; i >= 0; i--) {
    if (messages[i].role === "user") return messages[i].content.trim() || null;
  }
  return null;
}

/**
 * After a failed send, drop the optimistic user bubble so a retry does not
 * show the question twice. Only an unsaved (no id) trailing user turn with the
 * same text is removed — anything else is left untouched.
 */
export function dropFailedUserTurn<T extends { id?: string; role: string; content: string }>(
  messages: T[],
  text: string,
): T[] {
  const last = messages[messages.length - 1];
  if (last && last.role === "user" && !last.id && last.content === text) {
    return messages.slice(0, -1);
  }
  return messages;
}

/** 429 (daily limit) and 402 (subscription) will fail again the same way: no Retry. */
export function isRetryableStatus(status: number | undefined): boolean {
  return status !== 429 && status !== 402;
}
