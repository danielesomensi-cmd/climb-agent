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
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { startNewMacrocycle } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
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

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
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
  const initialDeadline = (currentGoal.deadline as string) || "";

  const [discipline, setDiscipline] = useState<Discipline>(initialDiscipline);
  const [targetGrade, setTargetGrade] = useState<string>(initialTargetGrade);
  const [deadline, setDeadline] = useState<string>(initialDeadline);

  useEffect(() => {
    if (open) {
      setStep("form");
      setError(null);
      setDiscipline(initialDiscipline);
      setTargetGrade(initialTargetGrade);
      setDeadline(initialDeadline);
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

  const minDeadline = useMemo(() => addDaysIso(todayIso(), 7 * 9), []);

  const validation = useMemo(() => {
    if (!targetGrade) return "Pick a target grade.";
    if (!deadline) return "Pick a deadline.";
    if (deadline < minDeadline)
      return `Deadline must be at least 9 weeks from today (≥ ${minDeadline}).`;
    return null;
  }, [targetGrade, deadline, minDeadline]);

  const gradeOptions = discipline === "boulder" ? BOULDER_GRADES : LEAD_GRADES;

  const isMidCycle = useMemo(() => {
    if (!macro?.end_date) return false;
    const days = daysBetween(todayIso(), macro.end_date);
    return days > 6; // strictly outside the last 7 days = mid-cycle warning territory.
  }, [macro?.end_date]);

  async function handleConfirm() {
    setStep("loading");
    setError(null);
    try {
      await startNewMacrocycle({
        goal: {
          discipline,
          target_grade: targetGrade,
          target_style: "redpoint",
          deadline,
        },
      });
      // Invalidate every cache that depends on macrocycle / week / state.
      qc.clear();
      onOpenChange(false);
      onSuccess?.();
      router.push("/plan");
    } catch (e) {
      setStep("confirm");
      const msg = e instanceof Error ? e.message : "Failed to start new cycle.";
      setError(msg);
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

              <div>
                <Label className="text-sm">Deadline</Label>
                <Input
                  type="date"
                  className="mt-2"
                  value={deadline}
                  min={minDeadline}
                  onChange={(e) => setDeadline(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  At least 9 weeks from today.
                </p>
              </div>

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
                  {discipline} · {targetGrade} by {formatDateLong(deadline)}
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

              {isMidCycle && (
                <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 text-xs">
                  <p className="font-medium">Heads up</p>
                  <p className="mt-1">
                    Your current cycle isn&apos;t finished. Remaining planned
                    sessions will be discarded. Sessions you&apos;ve already
                    completed stay in your history.
                  </p>
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
