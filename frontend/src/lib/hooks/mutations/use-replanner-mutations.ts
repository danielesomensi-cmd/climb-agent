"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  applyEvents,
  applyOverride,
  quickAddSession,
  addExerciseToSession,
  removeExerciseFromSession,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { WeekPlan } from "@/lib/types";

/**
 * A187 — Replanner / week plan mutations.
 *
 * All endpoints in this file return `{ week_plan }` so we use setQueryData
 * for instant cache updates instead of refetching. The optional `weekNum`
 * variable lets the caller target a specific week (default 0 = current).
 */

type WeekPlanResponse = { week_plan: WeekPlan };

export function useReplannerEvents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      events: Array<Record<string, unknown>>;
      week_plan: WeekPlan;
      weekNum?: number;
    }) => applyEvents({ events: data.events, week_plan: data.week_plan }),
    onSuccess: (response: WeekPlanResponse, variables) => {
      const n = variables.weekNum ?? 0;
      qc.setQueryData(queryKeys.week(n), (old: WeekPlanResponse & { week_num: number } | undefined) =>
        old ? { ...old, week_plan: response.week_plan } : { week_num: n, week_plan: response.week_plan },
      );
      // Mark-done on the last slot may pre-generate week n+1 server-side.
      qc.invalidateQueries({ queryKey: queryKeys.week(n + 1) });
    },
  });
}

export function useReplannerOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof applyOverride>[0] & { weekNum?: number }) => {
      const { weekNum: _weekNum, ...rest } = data;
      void _weekNum;
      return applyOverride(rest);
    },
    onSuccess: (response: WeekPlanResponse, variables) => {
      const n = variables.weekNum ?? 0;
      qc.setQueryData(queryKeys.week(n), (old: WeekPlanResponse & { week_num: number } | undefined) =>
        old ? { ...old, week_plan: response.week_plan } : { week_num: n, week_plan: response.week_plan },
      );
    },
  });
}

export function useQuickAdd() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof quickAddSession>[0] & { weekNum?: number }) => {
      const { weekNum: _weekNum, ...rest } = data;
      void _weekNum;
      return quickAddSession(rest);
    },
    onSuccess: (response: WeekPlanResponse & { warnings: string[] }, variables) => {
      const n = variables.weekNum ?? 0;
      qc.setQueryData(queryKeys.week(n), (old: WeekPlanResponse & { week_num: number } | undefined) =>
        old ? { ...old, week_plan: response.week_plan } : { week_num: n, week_plan: response.week_plan },
      );
    },
  });
}

export function useAddExercise() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof addExerciseToSession>[0] & { weekNum?: number }) => {
      const { weekNum: _weekNum, ...rest } = data;
      void _weekNum;
      return addExerciseToSession(rest);
    },
    onSuccess: (response: WeekPlanResponse, variables) => {
      const n = variables.weekNum ?? 0;
      qc.setQueryData(queryKeys.week(n), (old: WeekPlanResponse & { week_num: number } | undefined) =>
        old ? { ...old, week_plan: response.week_plan } : { week_num: n, week_plan: response.week_plan },
      );
    },
  });
}

export function useRemoveExercise() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof removeExerciseFromSession>[0] & { weekNum?: number }) => {
      const { weekNum: _weekNum, ...rest } = data;
      void _weekNum;
      return removeExerciseFromSession(rest);
    },
    onSuccess: (response: WeekPlanResponse, variables) => {
      const n = variables.weekNum ?? 0;
      qc.setQueryData(queryKeys.week(n), (old: WeekPlanResponse & { week_num: number } | undefined) =>
        old ? { ...old, week_plan: response.week_plan } : { week_num: n, week_plan: response.week_plan },
      );
    },
  });
}
