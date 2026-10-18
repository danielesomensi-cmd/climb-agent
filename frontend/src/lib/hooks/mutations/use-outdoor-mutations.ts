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
      // B398 review (round 2) — this hook is used by /settings now (B398 O11)
      // and the spots list stays fresh for 5 minutes. Seeding an EMPTY or
      // failed cache with the new spot alone made the athlete's other spots
      // disappear (and invited re-adding them); a GET still in flight would
      // overwrite the insert with a list that lacks it. In both cases re-read
      // the whole list instead.
      const query = qc.getQueryState<{ spots: OutdoorSpot[] }>(queryKeys.outdoorSpots);
      if (!query?.data || query.fetchStatus === "fetching") {
        void qc.invalidateQueries({ queryKey: queryKeys.outdoorSpots });
        return;
      }
      qc.setQueryData(queryKeys.outdoorSpots, (old: { spots: OutdoorSpot[] } | undefined) => {
        if (!old) return old;
        if (old.spots.some((s) => s.id === response.spot.id)) return old;
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
