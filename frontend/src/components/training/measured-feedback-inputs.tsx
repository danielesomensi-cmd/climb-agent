"use client";

/**
 * A295 (R4) — the measured-feedback inputs shared by the post-session dialog,
 * the guided player, its summary and the custom-session player.
 *
 * Nothing is pre-selected and every input is optional: an untouched input
 * sends nothing and the server holds the load that was used. Touch targets
 * are ≥ 44 px (mobile-first).
 */

import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { tapFeedback } from "@/lib/haptics";
import type { FeedbackMeasure, HangMargin, PainSite, SessionPain } from "@/lib/types";
import {
  HANG_MARGIN_OPTIONS,
  PAIN_OPTIONS,
  PAIN_SITE_OPTIONS,
  lastSetStepperMax,
  stepperBounds,
} from "@/lib/measured-feedback";

const CHIP =
  "min-h-[44px] rounded-full px-3 text-sm font-medium transition-all active:scale-95 motion-reduce:active:scale-100";
const CHIP_ON = "bg-primary text-primary-foreground ring-2 ring-offset-1 ring-offset-background ring-primary";
const CHIP_OFF = "border border-border bg-muted text-foreground hover:bg-accent";

/** Reps on the last set: a stepper that starts EMPTY (untouched = not measured). */
export function LastSetRepsStepper({
  id,
  value,
  onChange,
  prescribedReps,
  targetReps,
  label,
  hint,
  max: maxOverride,
  unit = "rep",
  min = 0,
}: {
  id: string;
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  prescribedReps?: number;
  targetReps?: number;
  label: string;
  hint?: string;
  /** A298: upper bound for the non-rep measures (seconds, readjustments, fear). */
  max?: number;
  /** A298: unit word used in the +/- aria labels. */
  unit?: string;
  min?: number;
}) {
  const max = maxOverride ?? lastSetStepperMax(prescribedReps, targetReps);
  const start = targetReps ?? prescribedReps ?? 0;
  const dec = () => onChange(value == null ? Math.max(min, start - 1) : Math.max(min, value - 1));
  const inc = () => onChange(value == null ? Math.min(max, start) : Math.min(max, value + 1));
  return (
    <div className="space-y-1.5">
      <p id={`${id}-label`} className="text-xs text-muted-foreground">{label}</p>
      <div className="flex items-center gap-2" role="group" aria-labelledby={`${id}-label`}>
        <button
          type="button"
          aria-label={`One ${unit} fewer`}
          onClick={dec}
          onPointerDown={tapFeedback}
          className={cn(CHIP, CHIP_OFF, "w-11 px-0 flex items-center justify-center")}
        >
          <Minus className="size-4" />
        </button>
        <span
          className={cn(
            "min-w-[3rem] text-center text-lg font-semibold tabular-nums",
            value == null && "text-muted-foreground",
          )}
          aria-live="polite"
        >
          {value == null ? "—" : value}
        </span>
        <button
          type="button"
          aria-label={`One ${unit} more`}
          onClick={inc}
          onPointerDown={tapFeedback}
          className={cn(CHIP, CHIP_OFF, "w-11 px-0 flex items-center justify-center")}
        >
          <Plus className="size-4" />
        </button>
        {value != null && (
          <button
            type="button"
            onClick={() => onChange(undefined)}
            className="min-h-[44px] px-2 text-xs text-muted-foreground underline underline-offset-4"
          >
            Clear
          </button>
        )}
      </div>
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Seconds left on the last hang: Failed / 0–2 s / 3–5 s / >5 s, tap again to clear. */
export function HangMarginChips({
  value,
  onChange,
}: {
  value: HangMargin | undefined;
  onChange: (value: HangMargin | undefined) => void;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-muted-foreground">How much longer could you have held the last hang?</p>
      <div className="flex flex-wrap gap-1.5">
        {HANG_MARGIN_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            aria-pressed={value === opt.value}
            onClick={() => onChange(value === opt.value ? undefined : opt.value)}
            onPointerDown={tapFeedback}
            className={cn(CHIP, value === opt.value ? CHIP_ON : CHIP_OFF)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** The measure input matching `measure` (nothing for an exercise without one). */
export function MeasureInput({
  id,
  measure,
  prescribedReps,
  targetReps,
  lastSetReps,
  hangMargin,
  onLastSetReps,
  onHangMargin,
}: {
  id: string;
  measure: FeedbackMeasure | undefined;
  prescribedReps?: number;
  targetReps?: number;
  lastSetReps: number | undefined;
  hangMargin: HangMargin | undefined;
  onLastSetReps: (value: number | undefined) => void;
  onHangMargin: (value: HangMargin | undefined) => void;
}) {
  if (measure === "last_set_reps") {
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        prescribedReps={prescribedReps}
        label="Reps on your last set"
        hint="Last set: max clean reps, stop one short of failure."
      />
    );
  }
  if (measure === "dp_reps") {
    const target = targetReps ?? prescribedReps;
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        prescribedReps={prescribedReps}
        targetReps={target}
        label={target != null ? `Reps on your last set (target ${target})` : "Reps on your last set"}
      />
    );
  }
  if (measure === "hang_margin") {
    return <HangMarginChips value={hangMargin} onChange={onHangMargin} />;
  }
  // A298: bodyweight ladder rows and technique ladders — one optional number.
  if (measure === "bw_reps") {
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        prescribedReps={prescribedReps}
        max={stepperBounds(measure, prescribedReps).max}
        label="Clean reps on your weakest set"
        hint="Optional. It moves your level more precisely than the label alone."
      />
    );
  }
  if (measure === "bw_hold") {
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        prescribedReps={prescribedReps}
        max={stepperBounds(measure).max}
        unit="second"
        label="Seconds held on your weakest set"
        hint="Optional. Stop at the target: it only matters if you fell short."
      />
    );
  }
  if (measure === "feet_readjust") {
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        max={stepperBounds(measure).max}
        unit="readjustment"
        label="Foot readjustments on the sample problem"
        hint="One problem per session (video or partner). ≤ 1 twice in a row moves the feet ladder up."
      />
    );
  }
  if (measure === "fear_max") {
    return (
      <LastSetRepsStepper
        id={id}
        value={lastSetReps}
        onChange={onLastSetReps}
        max={stepperBounds(measure).max}
        unit="point"
        label="Max fear today (0–10)"
        hint="Once per session. ≤ 3 twice in a row moves the falls ladder up."
      />
    );
  }
  return null;
}

/** "Any pain?" 0-3 for the whole session; the zone appears from 2. */
export function PainPicker({
  value,
  onChange,
}: {
  value: SessionPain | null | undefined;
  onChange: (value: SessionPain | null) => void;
}) {
  const score = value?.score;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Any pain?</p>
      <div className="flex flex-wrap gap-1.5">
        {PAIN_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            aria-pressed={score === opt.value}
            onClick={() =>
              onChange(
                score === opt.value
                  ? null
                  : { score: opt.value, site: opt.value >= 2 ? (value?.site ?? null) : null },
              )
            }
            onPointerDown={tapFeedback}
            className={cn(CHIP, score === opt.value ? CHIP_ON : CHIP_OFF)}
          >
            {opt.value} {opt.label}
          </button>
        ))}
      </div>
      {score != null && score >= 2 && (
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">Where?</p>
          <div className="flex flex-wrap gap-1.5">
            {PAIN_SITE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                aria-pressed={value?.site === opt.value}
                onClick={() =>
                  onChange({ score: score as SessionPain["score"], site: value?.site === opt.value ? null : (opt.value as PainSite) })
                }
                onPointerDown={tapFeedback}
                className={cn(CHIP, value?.site === opt.value ? CHIP_ON : CHIP_OFF)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Loads on that zone drop for {score >= 3 ? "14" : "7"} days. Nothing is removed from your plan.
          </p>
        </div>
      )}
    </div>
  );
}
