"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  putState,
  deleteState,
  computeAssessment,
  generateMacrocycle,
  importUserState,
  completeOnboarding,
  setStartWeek,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { invalidateAll } from "@/lib/invalidation";
import type { UserState } from "@/lib/types";

/**
 * A187 — State / settings / onboarding mutations.
 */

export function useUpdateState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: putState,
    onSuccess: (response: UserState) => {
      qc.setQueryData(queryKeys.state, response);
      // equipment / availability / goal can change the planner output
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
      qc.invalidateQueries({ queryKey: queryKeys.freeSessionSurfaces });
    },
  });
}

export function useDeleteState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteState,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useImportState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: importUserState,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useAssessmentCompute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      assessment,
      goal,
    }: {
      assessment?: Record<string, unknown>;
      goal?: Record<string, unknown>;
    }) => computeAssessment(assessment, goal),
    onSuccess: (response) => {
      // merge profile into cached state
      qc.setQueryData(queryKeys.state, (old: any) =>
        old
          ? {
              ...old,
              assessment: { ...(old.assessment ?? {}), profile: response.profile },
            }
          : old,
      );
    },
  });
}

export function useGenerateMacrocycle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      startDate,
      totalWeeks,
      fromPhase,
    }: {
      startDate?: string;
      totalWeeks?: number;
      fromPhase?: string;
    }) => generateMacrocycle(startDate, totalWeeks, fromPhase),
    onSuccess: (response) => {
      qc.setQueryData(queryKeys.state, (old: any) =>
        old ? { ...old, macrocycle: response.macrocycle } : old,
      );
      // every week plan is regenerated server-side
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    },
  });
}

export function useCompleteOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof completeOnboarding>[0]) => completeOnboarding(data),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSetStartWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setStartWeek,
    onSuccess: () => {
      // start_date shifts → every week number maps to a different real week
      qc.invalidateQueries({ queryKey: queryKeys.state });
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    },
  });
}
