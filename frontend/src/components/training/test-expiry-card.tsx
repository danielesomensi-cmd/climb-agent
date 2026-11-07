"use client";

import { Hourglass } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { RetestActions, axesLabel, coveredAxes } from "@/components/training/retest-actions";
import { formatDateShort } from "@/lib/format";
import type { RetestAxisStatus, RetestStatus } from "@/lib/types";

/**
 * B414 (B414-4) — the Today card of a tested max that expires (model A,
 * Daniele 07/11). From 14 days before `valid_until`, and after it until a
 * choice is made, it proposes the only two ways out: «Do the test» or
 * «Postpone the expiry». Not dismissable (like the retest reminder): the
 * buttons are the way out. At the expiry nothing switches off — ladders,
 * anchored loads, phase rotation and coach keep going and keep progressing.
 *
 * A choice already made hides it: a test in the plan, an active request, or a
 * postpone — which moves `valid_until`, so the card comes back 14 days before
 * the NEW date. B414 review: a 2-week postpone of a max that already expired
 * starts from today, so its new date is already inside the window and the
 * card stays (with the new date): open point for Daniele, not a bug of the
 * rule as written.
 */
export function expiryAxes(status?: RetestStatus | null): RetestAxisStatus[] {
  return coveredAxes(status).filter(
    (s) => (s.expiring || s.expired) && !s.request && s.next_test?.source !== "planned",
  );
}

export function testExpiryVisible(status?: RetestStatus | null): boolean {
  return expiryAxes(status).length > 0;
}

export function TestExpiryCard({
  status,
  onChanged,
  onCycleEnded,
}: {
  status?: RetestStatus | null;
  onChanged: () => void;
  onCycleEnded?: () => void;
}) {
  const axes = expiryAxes(status);
  if (axes.length === 0) return null;
  const expired = axes.some((s) => s.expired);
  const days = axes.map((s) => s.valid_until).filter((d): d is string => !!d).sort();
  const day = days[0] ? formatDateShort(days[0]) : null;
  const what = `Your ${axesLabel(axes.map((s) => s.axis))} test`;

  return (
    <Card className="border-warning/30 bg-warning/5">
      <CardContent className="flex gap-3 py-3">
        <Hourglass className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-semibold">
              {expired
                ? `${what} expired${day ? ` after ${day}` : ""}`
                : `${what} is valid until ${day ?? "soon"}`}
            </p>
            <p className="text-xs text-muted-foreground">
              {expired
                ? "Your ladders and loads stay where they are and keep progressing. Do the test to update your max, or postpone the expiry."
                : "Do the test to update your max, or postpone the expiry. Nothing stops at the expiry: your ladders and loads keep going."}
            </p>
          </div>
          <RetestActions onChanged={onChanged} onCycleEnded={onCycleEnded} />
        </div>
      </CardContent>
    </Card>
  );
}
