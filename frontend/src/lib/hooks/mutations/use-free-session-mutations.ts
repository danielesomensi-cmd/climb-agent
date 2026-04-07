"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  startFreeSession,
  logFreeClimb,
  deleteFreeClimb,
  finishFreeSession,
  deleteFreeSession,
} from "@/lib/api";
import { invalidateFreeSessionHistory } from "@/lib/invalidation";

/**
 * A187 — Free session mutations.
 *
 * Start / log-climb / delete-climb don't touch any cached query — the
 * climb logger keeps state locally until finish. Only finish and delete
 * affect the history badges shown on today/week.
 */

export function useStartFreeSession() {
  return useMutation({ mutationFn: startFreeSession });
}

export function useLogFreeClimb() {
  return useMutation({
    mutationFn: ({
      sessionId,
      data,
    }: {
      sessionId: string;
      data: Parameters<typeof logFreeClimb>[1];
    }) => logFreeClimb(sessionId, data),
  });
}

export function useDeleteFreeClimb() {
  return useMutation({
    mutationFn: ({ sessionId, climbIndex }: { sessionId: string; climbIndex: number }) =>
      deleteFreeClimb(sessionId, climbIndex),
  });
}

export function useFinishFreeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      data,
    }: {
      sessionId: string;
      data: Parameters<typeof finishFreeSession>[1];
    }) => finishFreeSession(sessionId, data),
    onSuccess: () => invalidateFreeSessionHistory(qc),
  });
}

export function useDeleteFreeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteFreeSession,
    onSuccess: () => invalidateFreeSessionHistory(qc),
  });
}
