"use client";

import { useMemo, useState } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const LEAD_GRADES = [
  "5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

const BOULDER_GRADES = [
  "5A","5A+","5B","5B+","5C","5C+",
  "6A","6A+","6B","6B+","6C","6C+",
  "7A","7A+","7B","7B+","7C","7C+",
  "8A","8A+","8B","8B+","8C","8C+",
];

function gradeIndex(grade: string, list: string[]): number {
  return list.indexOf(grade);
}

interface GoalEditorProps {
  open: boolean;
  currentGoal: Record<string, unknown>;
  grades: Record<string, string>;
  onConfirm: (newGoal: Record<string, unknown>) => void;
  onCancel: () => void;
  saving: boolean;
}

export function GoalEditor({
  open,
  currentGoal,
  grades,
  onConfirm,
  onCancel,
  saving,
}: GoalEditorProps) {
  const [step, setStep] = useState<"form" | "confirm">("form");
  const [discipline, setDiscipline] = useState<string>(
    (currentGoal.discipline as string) || "lead",
  );
  const [targetStyle, setTargetStyle] = useState<string>(
    (currentGoal.target_style as string) || "redpoint",
  );
  const [targetGrade, setTargetGrade] = useState<string>(
    (currentGoal.target_grade as string) || "",
  );
  const [deadline, setDeadline] = useState<string>(
    (currentGoal.deadline as string) || "",
  );

  // Derive current grade from grades + discipline + style
  const currentGrade = useMemo(() => {
    if (discipline === "lead") {
      return targetStyle === "onsight" ? (grades.lead_max_os ?? "") : (grades.lead_max_rp ?? "");
    }
    return targetStyle === "onsight"
      ? (grades.boulder_max_os ?? "")
      : (grades.boulder_max_rp ?? "");
  }, [discipline, targetStyle, grades]);

  const gradeList = discipline === "lead" ? LEAD_GRADES : BOULDER_GRADES;
  const currentIdx = gradeIndex(currentGrade, gradeList);
  const targetGrades = currentIdx >= 0 ? gradeList.slice(currentIdx + 1) : gradeList;

  const targetIdx = gradeIndex(targetGrade, gradeList);
  const gap = targetIdx >= 0 && currentIdx >= 0 ? targetIdx - currentIdx : 0;

  // Deadline validation
  const today = new Date();
  const todayISO = today.toISOString().split("T")[0];
  const minDeadline = (() => {
    const d = new Date(today);
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  })();
  const isDeadlinePast = deadline !== "" && deadline <= todayISO;
  const isDeadlineShort = (() => {
    if (!deadline || isDeadlinePast) return false;
    const dl = new Date(deadline);
    const nineWeeks = new Date(today);
    nineWeeks.setDate(nineWeeks.getDate() + 63);
    return dl < nineWeeks;
  })();

  const isAmbitious = gap > 8;
  const isTooLow =
    targetGrade !== "" && currentIdx >= 0 && targetIdx >= 0 && targetIdx <= currentIdx;

  const isValid = targetGrade !== "" && deadline !== "" && !isTooLow && !isDeadlinePast;

  const goalType = discipline === "lead" ? "lead_grade" : "boulder_grade";

  const handleDisciplineChange = (v: string) => {
    setDiscipline(v);
    setTargetGrade(""); // reset target when discipline changes
  };

  const handleStyleChange = (v: string) => {
    setTargetStyle(v);
    setTargetGrade(""); // reset target when style changes
  };

  const handleSaveClick = () => {
    setStep("confirm");
  };

  const handleConfirm = () => {
    onConfirm({
      goal_type: goalType,
      discipline,
      target_style: targetStyle,
      target_grade: targetGrade,
      current_grade: currentGrade,
      deadline,
    });
  };

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen && !saving) {
      setStep("form");
      onCancel();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        {step === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>Edit goal</DialogTitle>
              <DialogDescription>
                Update your climbing target
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-5 py-2">
              {/* Discipline */}
              <div className="space-y-2">
                <Label>Discipline</Label>
                <RadioGroup
                  value={discipline}
                  onValueChange={handleDisciplineChange}
                  className="flex gap-6"
                >
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="lead" id="goal-disc-lead" />
                    <Label htmlFor="goal-disc-lead">Lead</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="boulder" id="goal-disc-boulder" />
                    <Label htmlFor="goal-disc-boulder">Boulder</Label>
                  </div>
                </RadioGroup>
              </div>

              {/* Target style */}
              <div className="space-y-2">
                <Label>Target style</Label>
                <RadioGroup
                  value={targetStyle}
                  onValueChange={handleStyleChange}
                  className="flex gap-6"
                >
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="redpoint" id="goal-style-rp" />
                    <Label htmlFor="goal-style-rp">Redpoint</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="onsight" id="goal-style-os" />
                    <Label htmlFor="goal-style-os">Onsight</Label>
                  </div>
                </RadioGroup>
              </div>

              {/* Current grade display */}
              {currentGrade && (
                <div className="rounded-md bg-muted px-3 py-2 text-sm">
                  Current grade ({discipline} {targetStyle}):{" "}
                  <strong>{currentGrade}</strong>
                </div>
              )}

              {/* Target grade */}
              <div className="space-y-2">
                <Label>Target grade</Label>
                <Select value={targetGrade} onValueChange={setTargetGrade}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select grade" />
                  </SelectTrigger>
                  <SelectContent>
                    {targetGrades.map((g) => (
                      <SelectItem key={g} value={g}>
                        {g}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Deadline */}
              <div className="space-y-2">
                <Label htmlFor="goal-deadline">Target date</Label>
                <Input
                  id="goal-deadline"
                  type="date"
                  value={deadline}
                  min={minDeadline}
                  onChange={(e) => setDeadline(e.target.value)}
                />
                {isDeadlinePast && (
                  <p className="text-xs text-red-500">Deadline must be in the future</p>
                )}
                {isDeadlineShort && (
                  <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
                    Short timeframe. The macrocycle may be compressed.
                  </div>
                )}
              </div>

              {/* Warnings */}
              {isAmbitious && (
                <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
                  Ambitious goal! The plan will be aggressive
                </div>
              )}
              {isTooLow && (
                <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-600 dark:bg-red-950 dark:text-red-200">
                  Target is equal to or lower than your current level
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button onClick={handleSaveClick} disabled={!isValid}>
                Save
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Confirm changes</DialogTitle>
              <DialogDescription>
                Changing your goal will regenerate your entire training plan.
                This cannot be undone. Continue?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("form")} disabled={saving}>
                Back
              </Button>
              <Button onClick={handleConfirm} disabled={saving}>
                {saving ? "Regenerating..." : "Yes, regenerate"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
