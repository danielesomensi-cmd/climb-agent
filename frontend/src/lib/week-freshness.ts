import type { WeekPlan } from "@/lib/types";
import { localToday } from "@/lib/key-sessions";

/**
 * B396 — is the cached week(0) still the week we are in?
 *
 * `week(0)` is persisted for up to 7 days (A245 B-2). On Monday morning the
 * cache therefore holds LAST week: today's date is in none of its days, no
 * later day exists either, and /today concluded "No sessions planned this
 * week — review availability" until the GET answered. Offline it said so with
 * no end. Every Monday, to every user.
 *
 * Two conditions, both needed:
 * - the plan is BEHIND: it starts before this Monday. A week that starts
 *   after it is legitimate (the macrocycle has not started: pre-start hero);
 * - the copy was fetched BEFORE this week began. The server itself can answer
 *   week(0) with a past week — a paused plan holds its week (A223), an ended
 *   cycle serves its last one (B257), and its clock is UTC — and what it said
 *   this week is shown as before. Only a copy from an earlier week is stale.
 *
 * Dates are compared in the athlete's local calendar.
 */

/** Monday (local calendar) of the week that contains `iso` (YYYY-MM-DD). */
export function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map((p) => parseInt(p, 10));
  if (!y || !m || !d) return iso;
  const date = new Date(y, m - 1, d);
  const offset = (date.getDay() + 6) % 7; // Mon=0 … Sun=6
  date.setDate(date.getDate() - offset);
  return localToday(date);
}

/** The Monday a week plan belongs to: `start_date`, else its first day. */
export function weekPlanMonday(plan: WeekPlan | null | undefined): string | null {
  if (!plan) return null;
  const first = plan.start_date ?? plan.weeks?.[0]?.days?.[0]?.date;
  return first ? mondayOf(first) : null;
}

/** Local midnight of the Monday of the week containing `now`, as epoch ms. */
export function startOfLocalWeek(now: Date = new Date()): number {
  const offset = (now.getDay() + 6) % 7; // Mon=0 … Sun=6
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - offset).getTime();
}

/**
 * The cached week(0) must not be shown as the current week: it is behind AND
 * it was fetched before this week began (`dataUpdatedAt`, React Query's own
 * timestamp, kept across the persisted restore).
 */
export function isCachedWeekStale(
  plan: WeekPlan | null | undefined,
  dataUpdatedAt: number,
  now: Date = new Date(),
): boolean {
  if (!isWeekPlanBehind(plan, localToday(now))) return false;
  return !(dataUpdatedAt >= startOfLocalWeek(now));
}

/** True when `plan` belongs to a week that ended before the current one. */
export function isWeekPlanBehind(
  plan: WeekPlan | null | undefined,
  today: string = localToday(),
): boolean {
  const planMonday = weekPlanMonday(plan);
  if (!planMonday) return false;
  return planMonday < mondayOf(today);
}

/**
 * What /today says while the cached week is stale:
 * - `loading`    — a fetch is running, or Clerk is still coming up online:
 *                  the skeleton, the real week is about to land;
 * - `offline`    — we cannot ask (no connection, or Clerk never loaded);
 * - `not_loaded` — online and not fetching, yet still holding last week's
 *                  copy (the refresh failed, or the copy is younger than the
 *                  staleTime across midnight): say so, offer Retry.
 */
export type BehindWeekNotice = "loading" | "offline" | "not_loaded";

export function behindWeekNotice(args: {
  online: boolean;
  authReady: boolean;
  authWaitExpired: boolean;
  isFetching: boolean;
}): BehindWeekNotice {
  if (!args.online || args.authWaitExpired) return "offline";
  if (args.isFetching || !args.authReady) return "loading";
  return "not_loaded";
}

const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * B396 — "updated 14:32" (or "updated Sat 14:32" when not today) for the line
 * that replaces the red error box when a refresh fails over a plan that is
 * still on screen. Empty when we do not know when the data arrived.
 */
export function updatedAtLabel(updatedAt: number, now: Date = new Date()): string {
  if (!updatedAt || !Number.isFinite(updatedAt)) return "";
  const at = new Date(updatedAt);
  const hh = String(at.getHours()).padStart(2, "0");
  const mm = String(at.getMinutes()).padStart(2, "0");
  const sameDay = localToday(at) === localToday(now);
  return sameDay ? `updated ${hh}:${mm}` : `updated ${WEEKDAY_SHORT[at.getDay()]} ${hh}:${mm}`;
}
