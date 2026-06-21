"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { pausePlan, resumePlan } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { UserState } from "@/lib/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Format an ISO date (YYYY-MM-DD) as "15 June 2026" (or the raw string if
 * unparseable / empty). Shared by the pause UI surfaces. */
export function formatPauseDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  const [y, m, d] = parts.map((p) => parseInt(p, 10));
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS[m - 1] ?? ""} ${y}`.trim();
}

/**
 * A223 — Plan pause / resume.
 *
 * Reads pause state off the passed-in user state and exposes pause()/resume()
 * actions that hit the backend and invalidate both the state and every week
 * cache (the resume shifts future weeks, so week plans must refetch).
 */
export function usePlanPause(state: UserState | null) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pause = state?.macrocycle?.pause ?? null;
  const activeSince = pause?.active_since ?? null;
  const isPaused = !!activeSince;

  const refetchAll = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.state }),
      qc.invalidateQueries({ queryKey: queryKeys.weekAll }),
    ]);
  }, [qc]);

  const doPause = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await pausePlan();
      await refetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to pause plan");
    } finally {
      setBusy(false);
    }
  }, [refetchAll]);

  const doResume = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await resumePlan();
      await refetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to resume plan");
    } finally {
      setBusy(false);
    }
  }, [refetchAll]);

  return {
    isPaused,
    activeSince,
    offsetDays: pause?.offset_days ?? 0,
    pause: doPause,
    resume: doResume,
    busy,
    error,
  };
}
