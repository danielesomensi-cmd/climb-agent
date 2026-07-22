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

function axisLabel(axis: string | null): string {
  if (!axis) return "A test";
  return AXIS_LABEL[axis] ?? axis;
}

export function SkippedTestsCard({
  skipped,
  weekKey,
}: {
  skipped: SkippedTest[];
  weekKey: string;
}) {
  const placement = skipped.filter(
    (s) => s.reason === "no_placement_slot" && s.required,
  );
  const storageKey = `skipped-tests-dismissed:${weekKey}`;
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(storageKey) === "1";
  });

  if (dismissed || placement.length === 0) return null;

  function dismiss() {
    try {
      window.localStorage.setItem(storageKey, "1");
    } catch {
      // best-effort — a private-mode failure just means it reappears next load
    }
    setDismissed(true);
  }

  const axes = Array.from(new Set(placement.map((s) => axisLabel(s.axis))));

  return (
    <Card className="border-amber-500/30 bg-amber-500/5">
      <CardContent className="flex items-start gap-3 px-4 py-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-500/10">
          <CalendarX2 className="h-5 w-5 text-amber-600 dark:text-amber-500" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-semibold">Couldn&apos;t schedule a test this week</p>
          <p className="text-sm text-muted-foreground">
            {axes.join(", ")} {axes.length > 1 ? "tests" : "test"} couldn&apos;t fit your
            available days without breaking rest spacing. Free up a day or move a session,
            then use Replan to fit it in.
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="-mr-1 -mt-1 size-8 shrink-0 text-muted-foreground"
          onClick={dismiss}
          aria-label="Dismiss"
        >
          <X className="size-4" />
        </Button>
      </CardContent>
    </Card>
  );
}
