"use client";

import type { QueryClient } from "@tanstack/react-query";
import { applyEvents, getWeek } from "@/lib/api";
import { findDay, firstFreeSlot, type Slot } from "@/lib/day-slots";
import { queryKeys } from "@/lib/query-keys";
import { PERSIST_MAX_AGE_MS } from "@/lib/query-persist";
import { siblingsOf, writeWeekCache, type WeekCacheEntry } from "@/lib/week-cache";
import type { DayPlan, SessionSlot, WeekPlan } from "@/lib/types";

/**
 * B414 (INBOX-2026-11-04-ORPHAN) — a session played on the phone that is no
 * longer on that day of the plan (the 04/11 treadmill, replaced by a custom
 * while the player ran from a cached copy). The server refuses the log
 * (`SessionNotInPlanError`) and writes nothing; the athlete decides
 * (Daniele, decision 4f of 07/11):
 *
 *  - «Log it in place of X» — X leaves the day and the played session takes
 *    its slot, then the feedback goes out as usual (the coach did this by
 *    hand on 04/11);
 *  - «Log it as an extra» — only when the day has a free slot;
 *  - «Discard» — the feedback is dropped (with a confirmation).
 *
 * Placing the session is two plain replanner events on the fresh week; the
 * feedback is the SAME body the player saved, replayed by the single-flight
 * sender (`syncPendingGuidedFeedback`), so the closed loop sees exactly what a
 * normal Submit would have sent.
 */

/** A session the player can put back in the plan: a catalog session or a saved custom. */
export function canPlaceSession(sessionId: string): boolean {
  return !!sessionId && !sessionId.startsWith("generated_");
}

export interface OrphanOptions {
  /** Sessions of the day it can take the place of (still to do). */
  replace: SessionSlot[];
  /** A free slot for «as an extra», or null when the day is full. */
  extraSlot: Slot | null;
  /** False for a generated session: it cannot be rebuilt from the phone. */
  placeable: boolean;
}

/** What the box offers for this day. Pure. */
export function orphanOptions(day: DayPlan | null, playedSessionId: string): OrphanOptions {
  const placeable = canPlaceSession(playedSessionId);
  if (!day) return { replace: [], extraSlot: null, placeable };
  const replace = (day.sessions ?? []).filter(
    (s) => s.status !== "done" && s.status !== "skipped" && s.session_id !== playedSessionId && !!s.slot,
  );
  return { replace, extraSlot: firstFreeSlot(day), placeable };
}

export type OrphanPlacement = { kind: "replace"; target: SessionSlot } | { kind: "extra"; slot: Slot };

/** The replanner events that put the played session back on `date`. Pure. */
export function placementEvents(
  date: string,
  playedSessionId: string,
  placement: OrphanPlacement,
): Array<Record<string, unknown>> {
  const add = (slot: string, where: { location?: string; gym_id?: string | null } = {}) => {
    const loc = {
      ...(where.location ? { location: where.location } : {}),
      ...(where.gym_id ? { gym_id: where.gym_id } : {}),
    };
    return playedSessionId.startsWith("custom_")
      ? {
          event_type: "add_custom_session",
          custom_session_id: playedSessionId.slice("custom_".length),
          target_date: date,
          slot,
          ...loc,
        }
      : { event_type: "add_planned_session", session_id: playedSessionId, target_date: date, slot, ...loc };
  };
  if (placement.kind === "extra") return [add(placement.slot)];
  const target = placement.target;
  return [
    { event_type: "remove_session", date, session_ref: target.session_id, slot: target.slot },
    add(target.slot, { location: target.location, gym_id: target.gym_id ?? null }),
  ];
}

export interface DayOnServer {
  weekNum: number;
  weekPlan: WeekPlan;
  day: DayPlan | null;
}

function weekStartOf(plan: WeekPlan | null | undefined): string | null {
  return plan?.weeks?.[0]?.days?.[0]?.date ?? null;
}

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
}

async function fetchWeek(qc: QueryClient, weekNum: number): Promise<WeekCacheEntry | null> {
  const entry = await qc.fetchQuery<WeekCacheEntry>({
    queryKey: queryKeys.week(weekNum),
    queryFn: () => getWeek(weekNum) as Promise<WeekCacheEntry>,
    staleTime: 0,
    gcTime: PERSIST_MAX_AGE_MS,
  });
  return entry ?? null;
}

/**
 * The week holding `date`, read FRESH from the server (never the cached copy
 * that caused the orphan). The current week first; another week by its
 * distance in weeks from the current one.
 */
export async function loadDayFromServer(qc: QueryClient, date: string): Promise<DayOnServer | null> {
  const current = await fetchWeek(qc, 0);
  if (current?.week_plan && findDay(current.week_plan, date)) {
    return { weekNum: 0, weekPlan: current.week_plan, day: findDay(current.week_plan, date) };
  }
  const start = weekStartOf(current?.week_plan);
  const num = current?.week_num;
  if (!start || typeof num !== "number") return null;
  const delta = Math.floor(daysBetween(start, date) / 7);
  if (delta === 0 || num + delta < 1) return null;
  const other = await fetchWeek(qc, num + delta);
  if (!other?.week_plan) return null;
  return { weekNum: num + delta, weekPlan: other.week_plan, day: findDay(other.week_plan, date) };
}

/** The placement would not put the session on the day (e.g. a custom deleted from My Sessions). */
export class OrphanPlacementError extends Error {
  constructor() {
    super("This session can't be put back in your plan (it no longer exists) — nothing was changed.");
    this.name = "OrphanPlacementError";
  }
}

/**
 * Put the played session back on its day (the feedback is sent afterwards).
 * Dry run first: `add_custom_session` skips a custom that is gone without an
 * error, and «in place of X» must never remove X for nothing.
 */
export async function placeOrphanSession(
  qc: QueryClient,
  where: DayOnServer,
  date: string,
  playedSessionId: string,
  placement: OrphanPlacement,
): Promise<void> {
  const events = placementEvents(date, playedSessionId, placement);
  const preview = await applyEvents({ events, week_plan: where.weekPlan, dry_run: true });
  const placed = findDay(preview.week_plan as WeekPlan, date)?.sessions?.some(
    (s) => s.session_id === playedSessionId,
  );
  if (!placed) throw new OrphanPlacementError();
  const result = await applyEvents({ events, week_plan: where.weekPlan });
  writeWeekCache(qc, where.weekNum, result.week_plan as WeekPlan, siblingsOf(result));
}

/** Human label of a session of the day ("Treadmill HIIT 4x4 · lunch"). */
export function sessionLabel(s: Pick<SessionSlot, "session_id" | "slot"> & { name?: string | null }): string {
  const name = s.name || s.session_id.replace(/^custom_/, "").replace(/_/g, " ");
  return s.slot ? `${name} · ${s.slot}` : name;
}
