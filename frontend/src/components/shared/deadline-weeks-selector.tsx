"use client";

/**
 * Shared cycle-duration slider.
 *
 * Used by:
 *  - onboarding/goals/page.tsx — `min={8}`, picks the first macrocycle's length.
 *  - settings/start-new-macrocycle-dialog.tsx — `min={9}` (lead engine floor),
 *    picks the next cycle's length when starting fresh.
 *
 * UX is intentionally identical between the two contexts: same Slider shape,
 * same recommended-marker, same warning copy. Only the floor differs.
 */

import { useMemo } from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

interface DeadlineWeeksSelectorProps {
  weeks: number;
  onWeeksChange: (weeks: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

function computeEndDateIso(weeks: number): string {
  const d = new Date();
  d.setDate(d.getDate() + weeks * 7);
  return d.toISOString().split("T")[0];
}

export function DeadlineWeeksSelector({
  weeks,
  onWeeksChange,
  min = 8,
  max = 24,
  step = 1,
}: DeadlineWeeksSelectorProps) {
  const endDate = useMemo(() => computeEndDateIso(weeks), [weeks]);
  const isShortPlan = weeks < 12;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label>Plan duration (weeks) *</Label>
        <span className="text-sm font-medium tabular-nums">
          {weeks} weeks
        </span>
      </div>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[weeks]}
        onValueChange={([v]) => onWeeksChange(v)}
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{min} wk</span>
        <span className="font-medium text-primary">12 wk recommended</span>
        <span>{max} wk</span>
      </div>
      <p className="text-xs text-muted-foreground">
        Your plan ends: <strong>{endDate}</strong>
      </p>
      <p className="text-xs text-muted-foreground">
        A full periodization cycle is 12+ weeks: base → strength-power →
        power-endurance → performance → deload. Shorter plans compress phases.
      </p>
      {isShortPlan && (
        <div className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
          Short plan — some training phases will be compressed
        </div>
      )}
    </div>
  );
}

/** Compute the ISO deadline string from a weeks count (today + N×7 days). */
export function weeksToDeadlineIso(weeks: number): string {
  return computeEndDateIso(weeks);
}

/** Inverse: derive weeks from a deadline ISO. Falls back to `defaultWeeks` if
 * the input is missing, malformed, or outside [min, max]. */
export function deadlineIsoToWeeks(
  deadlineIso: string | undefined,
  defaultWeeks: number,
  min = 8,
  max = 24,
): number {
  if (!deadlineIso) return defaultWeeks;
  const today = new Date();
  const d = new Date(deadlineIso);
  if (Number.isNaN(d.getTime())) return defaultWeeks;
  const days = Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  const weeks = Math.round(days / 7);
  if (weeks < min || weeks > max) return defaultWeeks;
  return weeks;
}
