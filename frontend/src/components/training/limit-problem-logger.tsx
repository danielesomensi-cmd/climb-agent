"use client";

/**
 * A296 — limit problem logger (R6c).
 *
 * Replaces the free "Actual grade used" field on the limit-boulder family:
 * one row per problem (grade, attempts, outcome). The server moves the limit
 * target on these rows — two sends at the target (or one above) step it up
 * half a grade; one session without progress never lowers it, two in a row
 * do. Grades are stored in Font; `gradeSystem` only changes what is shown.
 */
import { AlertTriangle, ChevronLeft, ChevronRight, Minus, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BOULDER_GRADE_OPTIONS, displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";
import {
  HARD_ATTEMPTS_GUARD,
  MAX_ATTEMPTS,
  MAX_PROBLEMS,
  OUTCOME_OPTIONS,
  clampAttempts,
  hardAttempts,
  newProblem,
} from "@/lib/limit-problems";
import type { LimitProblem } from "@/lib/types";

interface LimitProblemLoggerProps {
  idPrefix: string;
  target?: string | null;
  targetLow?: string | null;
  problems: LimitProblem[];
  onChange: (problems: LimitProblem[]) => void;
  gradeSystem?: BoulderGradeSystem;
}

function stepGrade(grade: string, delta: number): string {
  const i = BOULDER_GRADE_OPTIONS.indexOf(grade.toUpperCase());
  if (i < 0) return grade;
  const j = Math.max(0, Math.min(BOULDER_GRADE_OPTIONS.length - 1, i + delta));
  return BOULDER_GRADE_OPTIONS[j];
}

export function LimitProblemLogger({
  idPrefix,
  target,
  targetLow,
  problems,
  onChange,
  gradeSystem = "font",
}: LimitProblemLoggerProps) {
  const show = (g: string) => displayBoulderGrade(g, gradeSystem);
  const update = (i: number, patch: Partial<LimitProblem>) =>
    onChange(problems.map((p, k) => (k === i ? { ...p, ...patch } : p)));
  const remove = (i: number) => onChange(problems.filter((_, k) => k !== i));
  const add = () => {
    if (problems.length >= MAX_PROBLEMS) return;
    const last = problems[problems.length - 1];
    onChange([...problems, last ? { ...newProblem(last.grade), outcome: "sent" } : newProblem(target)]);
  };
  const hard = hardAttempts(problems, target);

  return (
    <div className="space-y-2" id={`${idPrefix}-limit-log`}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">Problems climbed</p>
        {target && (
          <span className="text-[11px] text-muted-foreground">
            Target {targetLow && targetLow !== target ? `${show(targetLow)}–${show(target)}` : show(target)}
          </span>
        )}
      </div>

      {problems.length === 0 && (
        <p className="text-[11px] text-muted-foreground">
          Log each problem you tried: your next limit target moves on what you actually climbed.
        </p>
      )}

      {problems.map((p, i) => (
        <div key={i} className="rounded-md border bg-background/40 p-2 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1" aria-label={`Problem ${i + 1} grade`}>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                aria-label="Easier grade"
                onClick={() => update(i, { grade: stepGrade(p.grade, -1) })}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span className="min-w-[44px] text-center text-sm font-semibold tabular-nums">{show(p.grade)}</span>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                aria-label="Harder grade"
                onClick={() => update(i, { grade: stepGrade(p.grade, 1) })}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
            <div className="flex items-center gap-1" aria-label={`Problem ${i + 1} attempts`}>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                aria-label="Fewer attempts"
                disabled={p.attempts <= 1}
                onClick={() => update(i, { attempts: clampAttempts(p.attempts - 1) })}
              >
                <Minus className="size-3.5" />
              </Button>
              <span className="min-w-[52px] text-center text-xs tabular-nums">
                {p.attempts} {p.attempts === 1 ? "try" : "tries"}
              </span>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                aria-label="More attempts"
                disabled={p.attempts >= MAX_ATTEMPTS}
                onClick={() => update(i, { attempts: clampAttempts(p.attempts + 1) })}
              >
                <Plus className="size-3.5" />
              </Button>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground"
              aria-label={`Remove problem ${i + 1}`}
              onClick={() => remove(i)}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {OUTCOME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                aria-pressed={p.outcome === opt.value}
                onClick={() => update(i, { outcome: opt.value })}
                className={cn(
                  "px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors",
                  p.outcome === opt.value
                    ? opt.value === "sent"
                      ? "bg-emerald-600 text-white border-transparent"
                      : opt.value === "high_point"
                        ? "bg-amber-600 text-white border-transparent"
                        : "bg-muted-foreground/70 text-white border-transparent"
                    : "border-muted-foreground/30 text-muted-foreground hover:border-muted-foreground/60",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 text-xs"
        onClick={add}
        disabled={problems.length >= MAX_PROBLEMS}
      >
        <Plus className="size-3.5 mr-1" />
        Add problem
      </Button>

      {hard > HARD_ATTEMPTS_GUARD && (
        <p className="flex items-start gap-1.5 text-[11px] text-amber-500">
          <AlertTriangle className="size-3.5 shrink-0 mt-px" />
          {hard} hard attempts — a lot for your fingers. The target will hold this time; recover fully before the next limit session.
        </p>
      )}
    </div>
  );
}
