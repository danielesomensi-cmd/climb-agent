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

export async function resolveOutdoorLogTarget(date: string): Promise<OutdoorLogTarget> {
  // Spots are best-effort: a missing list degrades the form but does not make
  // it wrong. The caller is told so it can say so.
  let spots: OutdoorSpot[] = [];
  let spotsFailed = false;
  try {
    spots = (await getOutdoorSpots()).spots;
  } catch (err) {
    spotsFailed = true;
    console.error("Failed to load outdoor spots:", err);
  }

  try {
    const existing = await getOutdoorLogByDate(date);
    return { kind: "edit", session: existing.session, spots };
  } catch (err) {
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
}
