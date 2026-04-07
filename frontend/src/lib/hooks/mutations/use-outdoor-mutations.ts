"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  postOutdoorLog,
  putOutdoorLog,
  deleteOutdoorLog,
  addOutdoorSpot,
  deleteOutdoorSpot,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { invalidateOutdoor } from "@/lib/invalidation";
import type { OutdoorSpot } from "@/lib/types";

/**
 * A187 — Outdoor mutations.
 */

export function useLogOutdoor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: postOutdoorLog,
    onSuccess: () => invalidateOutdoor(qc),
  });
}

export function useUpdateOutdoorLog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: putOutdoorLog,
    onSuccess: () => invalidateOutdoor(qc),
  });
}

export function useDeleteOutdoorLog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteOutdoorLog,
    onSuccess: () => invalidateOutdoor(qc),
  });
}

export function useAddOutdoorSpot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: addOutdoorSpot,
    onSuccess: (response) => {
      // optimistic insert into cached spots list
      qc.setQueryData(queryKeys.outdoorSpots, (old: { spots: OutdoorSpot[] } | undefined) => {
        if (!old) return { spots: [response.spot] };
        return { spots: [...old.spots, response.spot] };
      });
    },
  });
}

export function useDeleteOutdoorSpot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteOutdoorSpot,
    onSuccess: (_response, spotId) => {
      qc.setQueryData(queryKeys.outdoorSpots, (old: { spots: OutdoorSpot[] } | undefined) => {
        if (!old) return old;
        return { spots: old.spots.filter((s) => s.id !== spotId) };
      });
    },
  });
}
