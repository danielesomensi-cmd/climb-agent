import type { OutdoorAttempt } from "./types";

/**
 * A241 — derive per-try rest/climb timings from timestamps. Pure, render-time.
 *
 * Rest attribution is SESSION-WIDE, not per-route: rest before try N = elapsed
 * time from the end of the previous burn on ANY route (chronological across the
 * whole session) to the start of try N. Try start = logged_at − climb_seconds
 * when the climb timer was used, else logged_at (point event). The first burn
 * of the session has no rest (null). Tries without a valid logged_at (legacy
 * A227/B279 data) don't participate in the chain and derive nothing.
 *
 * Deriving (never storing) keeps the numbers consistent when a try is deleted.
 */

export interface TryTiming {
  rest_before_seconds: number | null;
  climb_seconds: number | null;
}

interface RouteLike {
  attempts: OutdoorAttempt[];
}

/** Per-try timings, aligned with routes[i].attempts[j]. */
export function deriveTryTimings(routes: RouteLike[]): TryTiming[][] {
  const out: TryTiming[][] = routes.map((route) =>
    route.attempts.map((att) => ({
      rest_before_seconds: null,
      climb_seconds: typeof att.climb_seconds === "number" ? att.climb_seconds : null,
    })),
  );

  const events: { r: number; a: number; startMs: number; endMs: number }[] = [];
  routes.forEach((route, r) => {
    route.attempts.forEach((att, a) => {
      if (!att.logged_at) return;
      const endMs = Date.parse(att.logged_at);
      if (Number.isNaN(endMs)) return;
      const startMs = endMs - (typeof att.climb_seconds === "number" ? att.climb_seconds : 0) * 1000;
      events.push({ r, a, startMs, endMs });
    });
  });
  events.sort((x, y) => x.endMs - y.endMs);

  let prevEnd: number | null = null;
  for (const ev of events) {
    out[ev.r][ev.a].rest_before_seconds =
      prevEnd == null ? null : Math.max(0, Math.round((ev.startMs - prevEnd) / 1000));
    prevEnd = ev.endMs;
  }
  return out;
}

/** True when at least one try carries a usable timestamp. */
export function routeHasTimestamps(route: RouteLike): boolean {
  return route.attempts.some((a) => !!a.logged_at && !Number.isNaN(Date.parse(a.logged_at)));
}

/** ms timestamp of the latest try on a route, or null (for "since last try"). */
export function lastTryMs(route: RouteLike): number | null {
  let last: number | null = null;
  for (const a of route.attempts) {
    if (!a.logged_at) continue;
    const ms = Date.parse(a.logged_at);
    if (!Number.isNaN(ms) && (last == null || ms > last)) last = ms;
  }
  return last;
}
