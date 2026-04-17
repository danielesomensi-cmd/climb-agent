"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCustomSession,
  updateCustomSession,
  deleteCustomSession,
} from "@/lib/api";
import { invalidateCustomSessions } from "@/lib/invalidation";
import type { CustomSessionExercise } from "@/lib/types";

/** Create a new custom session. */
export function useCreateCustomSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; tags: string[]; exercises: CustomSessionExercise[] }) =>
      createCustomSession(data),
    onSuccess: () => invalidateCustomSessions(qc),
  });
}

/** Update an existing custom session. */
export function useUpdateCustomSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; tags: string[]; exercises: CustomSessionExercise[] } }) =>
      updateCustomSession(id, data),
    onSuccess: () => invalidateCustomSessions(qc),
  });
}

/** Delete a custom session. */
export function useDeleteCustomSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteCustomSession,
    onSuccess: () => invalidateCustomSessions(qc),
  });
}
