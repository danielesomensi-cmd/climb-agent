/**
 * B371 — optimistic concurrency on the week plan (client side).
 *
 * Every write that ships the whole week plan (`/api/replanner/events`,
 * `/override`, `/quick-add`, `/api/session/add-exercise`, `/remove-exercise`,
 * `/surface-override`) sends the `plan_revision` it is editing as
 * `base_revision`. If another device (or a regeneration) wrote the week in the
 * meantime the server answers 409 `{detail, current_revision, week_plan}` and
 * saves nothing — before B371 the old copy silently overwrote the newer one.
 *
 * On a 409 the week is refetched and a toast says so. Only an action that is
 * idempotent on the fresh plan is retried by itself (see `isRetrySafeEvents`);
 * everything else is left for the user to redo on the reloaded week.
 */
import type { WeekPlan } from "@/lib/types";

export const STALE_PLAN_MESSAGE = "The plan changed on another device — reloaded";

/** The 409 body of a stale write, or null when the body is something else. */
export type StalePlanBody = {
  detail: string;
  current_revision: number;
  week_start?: string | null;
  week_plan?: WeekPlan | null;
};

export function parseStalePlanBody(raw: string): StalePlanBody | null {
  try {
    const body = JSON.parse(raw) as Partial<StalePlanBody> & { code?: string };
    if (typeof body?.current_revision === "number") {
      return {
        detail: typeof body.detail === "string" ? body.detail : STALE_PLAN_MESSAGE,
        current_revision: body.current_revision,
        week_start: body.week_start ?? null,
        week_plan: body.week_plan ?? null,
      };
    }
  } catch {
    /* not JSON → not ours */
  }
  return null;
}

/** Adds `base_revision` from the plan being edited. A plan without one sends
 * null, which the server treats like a pre-B371 client (accepted). */
export function withBaseRevision<T extends { week_plan?: WeekPlan | null }>(
  data: T,
): T & { base_revision: number | null } {
  const rev = data.week_plan?.plan_revision;
  return { ...data, base_revision: typeof rev === "number" ? rev : null };
}

const PLAYED = new Set(["done", "skipped"]);

function findDay(plan: WeekPlan, date: unknown) {
  if (typeof date !== "string") return undefined;
  for (const w of plan.weeks ?? []) {
    for (const d of w.days ?? []) {
      if (d.date === date) return d;
    }
  }
  return undefined;
}

/**
 * Can these events be re-sent, unchanged, on the fresh plan the 409 returned?
 *
 * Only when the result cannot differ from what the user asked for:
 *  - `mark_done` / `mark_skipped` on a session that still exists on the fresh
 *    plan and is still pending (marking it again would double the completion
 *    log; marking a session the other device moved or removed would hit the
 *    wrong one);
 *  - `set_outdoor_plan` on a day that is still an outdoor day not yet done
 *    (it sets a value — applying it twice is applying it once).
 * Anything else — moves, overrides, adds, removes, undo — depends on the plan
 * it was decided on, so the user redoes it on the reloaded week.
 */
export function isRetrySafeEvents(
  events: Array<Record<string, unknown>>,
  fresh: WeekPlan | null | undefined,
): boolean {
  if (!fresh || !events.length) return false;
  for (const ev of events) {
    const type = ev.event_type;
    const day = findDay(fresh, ev.date);
    if (!day) return false;
    if (type === "mark_done" || type === "mark_skipped") {
      const ref = ev.session_ref;
      const slot = ev.slot;
      const target = (day.sessions ?? []).find(
        (s) => (!ref || s.session_id === ref) && (!slot || s.slot === slot),
      );
      if (!target || PLAYED.has(String(target.status ?? ""))) return false;
    } else if (type === "set_outdoor_plan") {
      const d = day as unknown as { outdoor_spot_name?: string; outdoor_session_status?: string };
      if (!d.outdoor_spot_name || d.outdoor_session_status === "done") return false;
    } else {
      return false;
    }
  }
  return true;
}

export type StalePlanEvent = {
  /** true → the action was re-applied on the fresh plan and succeeded. */
  retried: boolean;
  weekStart?: string | null;
};

type Listener = (e: StalePlanEvent) => void;
const listeners = new Set<Listener>();

/** Subscribe to stale-plan conflicts (the app-level watcher refetches + toasts). */
export function onStalePlan(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function emitStalePlan(e: StalePlanEvent): void {
  listeners.forEach((fn) => {
    try {
      fn(e);
    } catch {
      /* a listener must never break the caller's error path */
    }
  });
}
