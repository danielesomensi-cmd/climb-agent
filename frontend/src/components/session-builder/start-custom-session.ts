"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { applyEvents, checkKeyConflicts, getWeek } from "@/lib/api";
import { firstFreeSlot, findDay, type Slot } from "@/lib/day-slots";
import { localToday } from "@/lib/key-sessions";
import { queryKeys } from "@/lib/query-keys";
import { PERSIST_MAX_AGE_MS } from "@/lib/query-persist";
import { useKeyConflictGate } from "@/lib/hooks/use-key-conflict-gate";
import type { DayPlan, WeekPlan } from "@/lib/types";

/**
 * A309 — "Start" on a saved custom session opens the real player
 * (/session-builder/[id]/play?date=today), not the old checklist.
 *
 * The player logs the session by marking `custom_<id>` done on that date in the
 * cached week plan, then posting the feedback — so the session must be on
 * today's plan before the player opens, or the athlete trains for an hour and
 * the save fails at the end. Same insertion as /today's quick add and the
 * coach's "Add to today & run": first free slot, A294 key-session dry run
 * (confirm, never block), then `add_custom_session`.
 */

export type StartDecision =
  | { kind: "play" }
  | { kind: "already_done" }
  | { kind: "insert"; slot: Slot }
  | { kind: "full" }
  | { kind: "no_day" };

/** What starting this custom session today requires. Pure. */
export function decideCustomStart(day: DayPlan | null, customSessionId: string): StartDecision {
  if (!day) return { kind: "no_day" };
  const ref = `custom_${customSessionId}`;
  const onDay = (day.sessions ?? []).filter(
    (s) => s.session_id === ref || s.custom_session_id === customSessionId,
  );
  if (onDay.some((s) => s.status !== "done" && s.status !== "skipped")) return { kind: "play" };
  // Done (or skipped) today: a second copy would share the same session_ref.
  if (onDay.length > 0) return { kind: "already_done" };
  const slot = firstFreeSlot(day);
  return slot ? { kind: "insert", slot } : { kind: "full" };
}

export function playHref(customSessionId: string, date: string): string {
  return `/session-builder/${customSessionId}/play?date=${date}`;
}

type CachedWeek = { week_num: number; phase_id?: string | null; week_plan: WeekPlan | null };

export function useStartCustomSession() {
  const router = useRouter();
  const qc = useQueryClient();
  const { gate, dialogProps } = useKeyConflictGate();
  const [startingId, setStartingId] = useState<string | null>(null);

  const start = useCallback(
    async (customSessionId: string) => {
      if (startingId) return;
      setStartingId(customSessionId);
      const today = localToday();
      const fail = (msg: string) => {
        toast.error(msg.includes("already occupied")
          ? "Today is fully booked. Free a slot from This Week, then retry."
          : msg);
        setStartingId(null);
      };
      try {
        // Through the query cache (with the week query's long gcTime): the
        // player reads this entry back when it saves, possibly an hour later.
        const week = await qc.fetchQuery<CachedWeek>({
          queryKey: queryKeys.week(0),
          queryFn: () => getWeek(0),
          staleTime: 0,
          gcTime: PERSIST_MAX_AGE_MS,
        });
        const plan = week.week_plan;
        if (!plan) {
          fail("No current week plan — open This Week once, then retry.");
          return;
        }
        const decision = decideCustomStart(findDay(plan, today), customSessionId);
        switch (decision.kind) {
          case "play":
            router.push(playHref(customSessionId, today));
            return;
          case "already_done":
            toast("Already done today", { description: "You'll find it on Today." });
            setStartingId(null);
            return;
          case "no_day":
            fail("Today isn't in the current week plan — open This Week once, then retry.");
            return;
          case "full":
            fail("Today is fully booked (morning, lunch and evening). Free a slot from This Week, then retry.");
            return;
        }
        const event = {
          event_type: "add_custom_session",
          custom_session_id: customSessionId,
          target_date: today,
          slot: decision.slot,
        };
        await gate(
          () => checkKeyConflicts({ events: [event], week_plan: plan }),
          async () => {
            try {
              const result = await applyEvents({ events: [event], week_plan: plan });
              qc.setQueryData<CachedWeek>(queryKeys.week(0), (old) => ({
                ...(old ?? week),
                week_plan: result.week_plan,
              }));
              // Stale, not refetched: /today reloads it (key status, alerts) on its next visit.
              void qc.invalidateQueries({ queryKey: queryKeys.weekAll, refetchType: "none" });
              router.push(playHref(customSessionId, today));
            } catch (e) {
              fail(e instanceof Error ? e.message : "Couldn't add the session to today.");
            }
          },
          () => setStartingId(null),
        );
      } catch (e) {
        fail(e instanceof Error ? e.message : "Couldn't start the session.");
      }
    },
    [startingId, qc, router, gate],
  );

  return { start, startingId, keyDialogProps: dialogProps };
}
