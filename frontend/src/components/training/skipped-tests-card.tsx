"use client";

import { useState } from "react";
import { CalendarX2, X } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { SkippedTest } from "@/lib/types";

/**
 * B297 (D211-F9) — surfaces tests the planner could not fit this week.
 *
 * Before B297 a test that couldn't be placed (no empty day, spacing/cap
 * conflict) simply vanished — the user silently lost a baseline retest. The
 * planner now records these as `skipped_tests` with reason "no_placement_slot".
 * We show ONLY those: the phase-gating skips (an axis a phase doesn't target)
 * are normal and would be noise here.
 *
 * Dismissal is local (per week key) — this is an informational nudge, not a
 * decision that must reach the engine, so no backend write.
 */
const AXIS_LABEL: Record<string, string> = {
  finger: "Finger strength",
  repeater: "Finger endurance",
  pulling: "Pulling strength",
};

/**
 * Placement failures only. `blocked:no_paired_slot` (A289; A319-FE: the
 * meaning A319 gave it): the pull-up test goes on the hang test's day — in
 * the pair's second slot, inside the combined test, or on the day of a test
 * that was kept (a change of gym without weights, B414) — and that day could
 * not take it there, with weights: it waits for its next turn. It is no
 * longer "no later day" (A319 removed the split over two days).
 * The policy's other `blocked:*` / `slipped:*` reasons (phase, minimum gap,
 * trip, very hard feedback) are decisions, not failures — the retest-status
 * card explains them.
 */
const PLACEMENT_FAILURES = new Set(["no_placement_slot", "blocked:no_paired_slot"]);

function axisLabel(axis: string | null): string {
  if (!axis) return "A test";
  return AXIS_LABEL[axis] ?? axis;
}

function storageKeyOf(weekKey: string): string {
  return `skipped-tests-dismissed:${weekKey}`;
}

function placementFailures(skipped: SkippedTest[] | null | undefined): SkippedTest[] {
  return (skipped ?? []).filter((s) => s.required && PLACEMENT_FAILURES.has(s.reason));
}

function readDismissed(weekKey: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(storageKeyOf(weekKey)) === "1";
  } catch {
    return false;
  }
}

/** A308 — whether the card renders anything (the /week notes count). */
export function skippedTestsVisible(skipped: SkippedTest[] | null | undefined, weekKey: string): boolean {
  return placementFailures(skipped).length > 0 && !readDismissed(weekKey);
}

export function SkippedTestsCard({
  skipped,
  weekKey,
  onDismiss,
}: {
  skipped: SkippedTest[];
  weekKey: string;
  /** A308 — lets the page update its notes count. */
  onDismiss?: () => void;
}) {
  const placement = placementFailures(skipped);
  const storageKey = storageKeyOf(weekKey);
  const [dismissed, setDismissed] = useState(() => readDismissed(weekKey));

  if (dismissed || placement.length === 0) return null;

  function dismiss() {
    try {
      window.localStorage.setItem(storageKey, "1");
    } catch {
      // best-effort — a private-mode failure just means it reappears next load
    }
    setDismissed(true);
    onDismiss?.();
  }

  const noSlot = placement.filter((s) => s.reason === "no_placement_slot");
  const noPair = placement.some((s) => s.reason === "blocked:no_paired_slot");
  const axes = Array.from(new Set(noSlot.map((s) => axisLabel(s.axis))));

  return (
    <Card className="border-warning/30 bg-warning/10">
      <CardContent className="flex items-start gap-3 px-4 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/10">
          <CalendarX2 className="h-5 w-5 text-warning" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-semibold">Couldn&apos;t schedule a test this week</p>
          {axes.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {axes.join(", ")} {axes.length > 1 ? "tests" : "test"} couldn&apos;t fit your
              available days without breaking rest spacing. Free up a day or move a session,
              then use Replan to fit it in.
            </p>
          )}
          {noPair && (
            <p className="text-sm text-muted-foreground">
              The pull-up test needs the hang test&apos;s day, with weights there: it waits for its next turn.
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="-mr-2 -mt-2 size-11 shrink-0 text-muted-foreground"
          onClick={dismiss}
          aria-label="Dismiss"
        >
          <X className="size-4" />
        </Button>
      </CardContent>
    </Card>
  );
}
