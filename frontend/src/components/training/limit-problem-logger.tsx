"use client";

/**
 * A296 — limit problem logger (R6c).
 *
 * Replaces the free "Actual grade used" field on the limit-boulder family:
 * one row per problem (grade, attempts, outcome). The server moves the limit
 * target on these rows — two sends at the target (or one above) step it up
 * half a grade; one session without progress never lowers it, two in a row
 * do. Grades are stored in Font; `gradeSystem` only changes what is shown.
 *
 * Review fixes: a new row has NO outcome (an untouched row is not a send and
 * is never sent); "No progress"/"High point" rows can record crux moves (crux
 * done at the target holds it); with `surfaceOptions` the athlete says which
 * wall he is on (custom sessions have no gym).
 */
import { AlertTriangle, ChevronLeft, ChevronRight, Minus, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BOULDER_GRADE_OPTIONS, displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";
import {
  HARD_ATTEMPTS_GUARD,
  MAX_ATTEMPTS,
  MAX_CRUX_MOVES,
  MAX_PROBLEMS,
  OUTCOME_OPTIONS,
  clampAttempts,
  clampCrux,
  hardAttempts,
  newProblem,
  surfaceLabel,
  unratedCount,
} from "@/lib/limit-problems";
import type { LimitProblemDraft } from "@/lib/types";

interface LimitProblemLoggerProps {
  idPrefix: string;
  target?: string | null;
  targetLow?: string | null;
  problems: LimitProblemDraft[];
  onChange: (problems: LimitProblemDraft[]) => void;
  gradeSystem?: BoulderGradeSystem;
  /** Surfaces to choose from (shown only with more than one). */
  surfaceOptions?: string[];
  surface?: string | null;
  onSurfaceChange?: (surface: string) => void;
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
  surfaceOptions,
  surface,
  onSurfaceChange,
}: LimitProblemLoggerProps) {
  const show = (g: string) => displayBoulderGrade(g, gradeSystem);
  const update = (i: number, patch: Partial<LimitProblemDraft>) =>
    onChange(problems.map((p, k) => (k === i ? { ...p, ...patch } : p)));
  const remove = (i: number) => onChange(problems.filter((_, k) => k !== i));
  const add = () => {
    if (problems.length >= MAX_PROBLEMS) return;
    const last = problems[problems.length - 1];
    onChange([...problems, newProblem(last ? last.grade : target)]);
  };
  const hard = hardAttempts(problems, target);
  const unrated = unratedCount(problems);
  const showSurfaces = !!onSurfaceChange && (surfaceOptions?.length ?? 0) > 1;

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

      {showSurfaces && (
        <div className="space-y-1">
          <p className="text-[11px] text-muted-foreground">Where are you climbing?</p>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Surface">
            {surfaceOptions!.map((opt) => (
              <button
                key={opt}
                type="button"
                role="radio"
                aria-checked={surface === opt}
                onClick={() => onSurfaceChange!(opt)}
                className={cn(
                  "px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors",
                  surface === opt
                    ? "bg-primary text-primary-foreground border-transparent"
                    : "border-muted-foreground/30 text-muted-foreground hover:border-muted-foreground/60",
                )}
              >
                {surfaceLabel(opt)}
              </button>
            ))}
          </div>
        </div>
      )}

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
                onClick={() =>
                  update(i, opt.value === "sent" ? { outcome: opt.value, crux_moves: undefined } : { outcome: opt.value })
                }
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
          {p.outcome && p.outcome !== "sent" && (
            <div className="flex items-center gap-1.5" aria-label={`Problem ${i + 1} crux moves`}>
              <span className="text-[11px] text-muted-foreground">Crux moves done</span>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-7 w-7"
                aria-label="Fewer crux moves"
                disabled={(p.crux_moves ?? 0) <= 0}
                onClick={() => update(i, { crux_moves: clampCrux((p.crux_moves ?? 0) - 1) || undefined })}
              >
                <Minus className="size-3" />
              </Button>
              <span className="min-w-[20px] text-center text-xs tabular-nums">{p.crux_moves ?? 0}</span>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-7 w-7"
                aria-label="More crux moves"
                disabled={(p.crux_moves ?? 0) >= MAX_CRUX_MOVES}
                onClick={() => update(i, { crux_moves: clampCrux((p.crux_moves ?? 0) + 1) })}
              >
                <Plus className="size-3" />
              </Button>
            </div>
          )}
        </div>
      ))}

      {unrated > 0 && (
        <p className="text-[11px] text-amber-500">
          Pick an outcome for every problem — {unrated === 1 ? "a row" : `${unrated} rows`} without one {unrated === 1 ? "is" : "are"} not counted.
        </p>
      )}

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
          {hard} hard attempts — a lot for your fingers. The target cannot go up after this session; recover fully before the next limit session.
        </p>
      )}
    </div>
  );
}
