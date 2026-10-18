"use client";

import { ApiError, getOutdoorLogByDate, getOutdoorSpots } from "@/lib/api";
import type { OutdoorSession, OutdoorSpot } from "@/lib/types";

/**
 * A245 C-5 (F37) — deciding whether a day already has an outdoor log.
 *
 * The old code did `try { getOutdoorLogByDate() } catch { openNewLogForm() }`,
 * so ANY failure — offline, timeout, 500 — was read as "no log for this day"
 * and the user was shown an empty new-log form for a day that already had one.
 * Filling it in then either duplicates or overwrites a real session.
 *
 * Only a genuine 404 means "no log yet". Everything else means "we don't know",
 * and not knowing must never be presented as knowing.
 *
 * Shared by /today and /week because both had a byte-identical copy of this
 * handler — the kind of duplication that eventually diverges (see F35).
 */
export type OutdoorLogTarget =
  | { kind: "edit"; session: OutdoorSession; spots: OutdoorSpot[] }
  | { kind: "new"; spots: OutdoorSpot[]; spotsFailed: boolean }
  | { kind: "unavailable"; message: string };

/**
 * B398 (O5) — the two reads run in parallel (they were in series: two round
 * trips before the dialog opened), and the spots can come from a cache: pass
 * `loadSpots` (e.g. `() => fetchOutdoorSpots(qc)`); the default is the plain GET.
 */
export async function resolveOutdoorLogTarget(
  date: string,
  loadSpots: () => Promise<{ spots: OutdoorSpot[] }> = getOutdoorSpots,
): Promise<OutdoorLogTarget> {
  const [spotsResult, logResult] = await Promise.allSettled([
    loadSpots(),
    getOutdoorLogByDate(date),
  ]);

  // Spots are best-effort: a missing list degrades the form but does not make
  // it wrong. The caller is told so it can say so.
  let spots: OutdoorSpot[] = [];
  let spotsFailed = false;
  if (spotsResult.status === "fulfilled") {
    spots = spotsResult.value.spots;
  } else {
    spotsFailed = true;
    console.error("Failed to load outdoor spots:", spotsResult.reason);
  }

  if (logResult.status === "fulfilled") {
    return { kind: "edit", session: logResult.value.session, spots };
  }
  const err = logResult.reason;
  if (err instanceof ApiError && err.status === 404) {
    return { kind: "new", spots, spotsFailed };
  }
  return {
    kind: "unavailable",
    message:
      err instanceof ApiError && err.status === 0
        ? "Can't reach the server — try again when you're back online."
        : "Couldn't check this day's outdoor log. Please try again.",
  };
}
