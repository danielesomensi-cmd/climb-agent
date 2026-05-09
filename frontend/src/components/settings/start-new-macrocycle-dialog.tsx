"use client";

/**
 * A-NEW-MACRO — multi-step dialog that orchestrates the user-facing "Plan Next
 * Cycle" flow. Shared between Settings (Card) and Today (banner).
 *
 * Three steps:
 *   1. goal review (mandatory edit/confirm of discipline / target / deadline)
 *   2. confirm summary with optional mid-cycle warning
 *   3. loading + post-success redirect handled by the parent
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DeadlineWeeksSelector,
  deadlineIsoToWeeks,
  weeksToDeadlineIso,
} from "@/components/shared/deadline-weeks-selector";
import { startNewMacrocycle } from "@/lib/api";
import type { UserState } from "@/lib/types";

const LEAD_GRADES = [
  "5a", "5a+", "5b", "5b+", "5c", "5c+",
  "6a", "6a+", "6b", "6b+", "6c", "6c+",
  "7a", "7a+", "7b", "7b+", "7c", "7c+",
  "8a", "8a+", "8b", "8b+", "8c", "8c+",
  "9a", "9a+",
];

const BOULDER_GRADES = [
  "4A", "4B", "4C",
  "5A", "5A+", "5B", "5B+", "5C", "5C+",
  "6A", "6A+", "6B", "6B+", "6C", "6C+",
  "7A", "7A+", "7B", "7B+", "7C", "7C+",
  "8A", "8A+", "8B", "8B+", "8C", "8C+",
];

// Mirror of backend BOULDER_TO_LEAD / LEAD_TO_BOULDER (highest-boulder-per-lead).
const BOULDER_TO_LEAD: Record<string, string> = {
  "4A": "5c", "4B": "6a", "4C": "6a+",
  "5A": "6a+", "5A+": "6b", "5B": "6b", "5B+": "6b+", "5C": "6c", "5C+": "6c+",
  "6A": "6c+", "6A+": "7a", "6B": "7a", "6B+": "7a+", "6C": "7b", "6C+": "7b+",
  "7A": "7b+", "7A+": "7c", "7B": "7c+", "7B+": "8a", "7C": "8a", "7C+": "8a+",
  "8A": "8b", "8A+": "8b+", "8B": "8c", "8B+": "8c+", "8C": "9a", "8C+": "9a+",
};

const LEAD_TO_BOULDER: Record<string, string> = {
  "5c": "4A", "6a": "4B", "6a+": "5A", "6b": "5B", "6b+": "5B+",
  "6c": "5C", "6c+": "6A", "7a": "6B", "7a+": "6B+", "7b": "6C",
  "7b+": "7A", "7c": "7A+", "7c+": "7B", "8a": "7C", "8a+": "7C+",
  "8b": "8A", "8b+": "8A+", "8c": "8B", "8c+": "8B+", "9a": "8C", "9a+": "8C+",
};

type Discipline = "lead" | "boulder" | "both";

interface StartNewMacrocycleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: UserState | null;
  onSuccess?: () => void;
}

// A218 / A-MACRO-CAPS: per-discipline floors. Lead is the conservative default
// for the dialog header; the slider min flips to 8 when the user picks boulder.
const MIN_WEEKS_LEAD = 11;
const MIN_WEEKS_BOULDER = 8;
const MAX_WEEKS = 16;
const DEFAULT_WEEKS = 12;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

function formatDateLong(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

/**
 * Compute the mid-cycle warning shown in step 2 of the dialog.
 *
 * Returns null when no warning is needed (no current macrocycle, or its
 * end_date is today/past). Otherwise returns the weeks-remaining count and
 * the user-facing copy. B-NEWMACRO-STARTDATE-FIX: with the new strict-next-
 * Monday semantics every click discards remaining sessions, so this fires
 * whenever the current cycle is still in flight.
 */
export function buildMidCycleWarning(
  endDateIso: string | undefined | null,
  today: string,
): { weeksRemaining: number; text: string } | null {
  if (!endDateIso) return null;
  const ms = new Date(endDateIso).getTime() - new Date(today).getTime();
  const days = Math.floor(ms / (1000 * 60 * 60 * 24));
  if (days <= 0) return null;
  const weeks = Math.ceil(days / 7);
  return {
    weeksRemaining: weeks,
    text:
      `Your current cycle isn't finished — about ${weeks} ` +
      `${weeks === 1 ? "week" : "weeks"} of planned sessions will be skipped. ` +
      `Sessions you've already completed remain in your history.`,
  };
}

/** Map a thrown Error from `request()` to a user-facing message + console
 * trace. Status code is parsed from the error message (`API <code>: ...`). */
export function classifyApiError(err: unknown): {
  userMessage: string;
  status: number | null;
} {
  const raw = err instanceof Error ? err.message : String(err);
  const match = /^API (\d+):/.exec(raw);
  const status = match ? Number(match[1]) : null;
  if (status === 402) {
    return {
      userMessage:
        "Your subscription is required to start a new cycle. Tap Settings → Subscription to manage.",
      status,
    };
  }
  return {
    userMessage:
      "Couldn't start the new cycle. Please try again, or contact support if the issue persists.",
    status,
  };
}

export function StartNewMacrocycleDialog({
  open,
  onOpenChange,
  state,
  onSuccess,
}: StartNewMacrocycleDialogProps) {
  const router = useRouter();
  const qc = useQueryClient();

  const [step, setStep] = useState<"form" | "confirm" | "loading">("form");
  const [error, setError] = useState<string | null>(null);

  const currentGoal = (state?.goal ?? {}) as Record<string, unknown>;
  const macro = (state as { macrocycle?: { end_date?: string } } | null)?.macrocycle ?? null;

  // Pre-fill from current goal each time the dialog opens.
  const initialDiscipline = ((currentGoal.discipline as string) || "lead") as Discipline;
  const initialTargetGrade =
    initialDiscipline === "boulder"
      ? ((currentGoal.target_boulder_grade as string) || (currentGoal.target_grade as string) || "")
      : ((currentGoal.target_grade as string) || "");
  // Use the lower of the two minima for the seed conversion — the user can
  // adjust afterwards and the slider re-clamps if needed.
  const initialWeeks = deadlineIsoToWeeks(
    currentGoal.deadline as string | undefined,
    DEFAULT_WEEKS,
    MIN_WEEKS_BOULDER,
    MAX_WEEKS,
  );

  const [discipline, setDiscipline] = useState<Discipline>(initialDiscipline);
  const [targetGrade, setTargetGrade] = useState<string>(initialTargetGrade);
  const [deadlineWeeks, setDeadlineWeeks] = useState<number>(initialWeeks);

  useEffect(() => {
    if (open) {
      setStep("form");
      setError(null);
      setDiscipline(initialDiscipline);
      setTargetGrade(initialTargetGrade);
      setDeadlineWeeks(initialWeeks);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Live remap when the user flips discipline mid-form: convert the current
  // grade into the new discipline's storage convention.
  function handleDisciplineChange(next: Discipline) {
    setDiscipline(next);
    if (!targetGrade) return;
    if (next === "boulder" && (discipline === "lead" || discipline === "both")) {
      const remapped = LEAD_TO_BOULDER[targetGrade];
      if (remapped) setTargetGrade(remapped);
    } else if (
      (next === "lead" || next === "both") &&
      discipline === "boulder"
    ) {
      const remapped = BOULDER_TO_LEAD[targetGrade];
      if (remapped) setTargetGrade(remapped);
    }
  }

  const computedDeadline = useMemo(
    () => weeksToDeadlineIso(deadlineWeeks),
    [deadlineWeeks],
  );

  const minWeeks = discipline === "boulder" ? MIN_WEEKS_BOULDER : MIN_WEEKS_LEAD;

  const validation = useMemo(() => {
    if (!targetGrade) return "Pick a target grade.";
    if (deadlineWeeks < minWeeks) {
      return `Plan must be at least ${minWeeks} weeks long.`;
    }
    return null;
  }, [targetGrade, deadlineWeeks, minWeeks]);

  const gradeOptions = discipline === "boulder" ? BOULDER_GRADES : LEAD_GRADES;

  // B-NEWMACRO-STARTDATE-FIX: every "Start New Cycle" click now starts next
  // Monday — so any current cycle whose end_date is still in the future will
  // have remaining planned sessions skipped. The helper returns null when no
  // warning is needed (no cycle / cycle already past).
  const midCycleWarning = useMemo(
    () => buildMidCycleWarning(macro?.end_date, todayIso()),
    [macro?.end_date],
  );

  async function handleConfirm() {
    setStep("loading");
    setError(null);
    try {
      await startNewMacrocycle({
        goal: {
          discipline,
          target_grade: targetGrade,
          target_style: "redpoint",
          deadline: weeksToDeadlineIso(deadlineWeeks),
        },
        total_weeks: deadlineWeeks,
      });
      // Invalidate every cache that depends on macrocycle / week / state.
      qc.clear();
      onOpenChange(false);
      onSuccess?.();
      router.push("/plan");
    } catch (e) {
      // Keep the technical detail in the console for debugging — never user-visible.
      console.error("[start-new-cycle] API error:", e);
      setStep("confirm");
      setError(classifyApiError(e).userMessage);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {step === "form" && (
          <>
            <DialogHeader>
              <DialogTitle>Plan Next Cycle</DialogTitle>
              <DialogDescription>
                Review your goal. Week 1 will include test sessions to
                recalibrate your baselines. Your training history is preserved.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div>
                <Label className="text-sm">Discipline</Label>
                <RadioGroup
                  value={discipline}
                  onValueChange={(v) => handleDisciplineChange(v as Discipline)}
                  className="mt-2 flex gap-4"
                >
                  {(["lead", "boulder", "both"] as Discipline[]).map((d) => (
                    <div key={d} className="flex items-center gap-2">
                      <RadioGroupItem id={`disc-${d}`} value={d} />
                      <Label htmlFor={`disc-${d}`} className="text-sm capitalize">
                        {d}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>

              <div>
                <Label className="text-sm">Target grade</Label>
                <Select value={targetGrade} onValueChange={setTargetGrade}>
                  <SelectTrigger className="mt-2">
                    <SelectValue placeholder="Pick a grade" />
                  </SelectTrigger>
                  <SelectContent className="max-h-60">
                    {gradeOptions.map((g) => (
                      <SelectItem key={g} value={g}>
                        {g}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <DeadlineWeeksSelector
                weeks={deadlineWeeks}
                onWeeksChange={setDeadlineWeeks}
                min={minWeeks}
                max={MAX_WEEKS}
              />

              {validation && (
                <p className="text-xs text-destructive">{validation}</p>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => setStep("confirm")}
                disabled={!!validation}
              >
                Continue
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "confirm" && (
          <>
            <DialogHeader>
              <DialogTitle>Confirm new cycle</DialogTitle>
              <DialogDescription>
                Review the details below. You can still go back to edit.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-sm">
              <div>
                <p className="text-muted-foreground">Goal</p>
                <p className="font-medium capitalize">
                  {discipline} · {targetGrade} by {formatDateLong(computedDeadline)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Week 1</p>
                <p className="font-medium">
                  Test sessions scheduled (Max Hang, Repeater, Weighted Pull-Up)
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">History</p>
                <p className="font-medium">
                  Current cycle will be archived — feedback, working loads, and
                  outdoor sessions stay intact.
                </p>
              </div>

              {midCycleWarning && (
                <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 text-xs">
                  <p className="font-medium">Heads up</p>
                  <p className="mt-1">{midCycleWarning.text}</p>
                </div>
              )}

              {error && (
                <p className="text-xs text-destructive">{error}</p>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("form")}>
                Back
              </Button>
              <Button onClick={handleConfirm}>Start new cycle</Button>
            </DialogFooter>
          </>
        )}

        {step === "loading" && (
          <>
            <DialogHeader>
              <DialogTitle>Generating your new macrocycle…</DialogTitle>
              <DialogDescription>
                This usually takes a couple of seconds.
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center justify-center py-8">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
