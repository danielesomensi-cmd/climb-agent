"use client";

/**
 * Shared cycle-duration slider.
 *
 * A218: hard cap at 16 weeks (KB consensus). Per-discipline floors:
 *   - lead / both / all_round: 11 (engine `_MIN_TOTAL_WEEKS_LEAD`)
 *   - boulder: 8 (engine `_MIN_TOTAL_WEEKS_BOULDER`)
 *
 * Callers pass `min` per discipline. Default `min` is 11 (lead floor) since
 * the lead path is the most common.
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
  min = 11,
  max = 16,
  step = 1,
}: DeadlineWeeksSelectorProps) {
  const endDate = useMemo(() => computeEndDateIso(weeks), [weeks]);
  // A218: "short plan" warning fires below the lead default (12 weeks).
  // Boulder users at 8-10 weeks will also see it — that's intentional, since
  // any cycle below the discipline default compresses phases.
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
  min = 11,
  max = 16,
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
