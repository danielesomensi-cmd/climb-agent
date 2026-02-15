"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
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
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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

export default function GoalsPage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const goal = data.goal;
  const grades = data.grades;

  const discipline = goal.discipline || "lead";
  const targetStyle = goal.target_style || "redpoint";

  // Derive the current grade based on discipline + style
  const currentGrade = useMemo(() => {
    if (discipline === "lead") {
      return targetStyle === "onsight" ? grades.lead_max_os : grades.lead_max_rp;
    }
    return targetStyle === "onsight"
      ? (grades.boulder_max_os ?? "")
      : (grades.boulder_max_rp ?? "");
  }, [discipline, targetStyle, grades]);

  // Derive goal_type from discipline
  const goalType = discipline === "lead" ? "lead_grade" : "boulder_grade";

  // Grade list for the chosen discipline
  const gradeList = discipline === "lead" ? LEAD_GRADES : BOULDER_GRADES;

  // Filter target grades: only those strictly above current
  const currentIdx = gradeIndex(currentGrade, gradeList);
  const targetGrades = currentIdx >= 0
    ? gradeList.slice(currentIdx + 1)
    : gradeList;

  // Gap in half-grades between current and target
  const targetIdx = gradeIndex(goal.target_grade, gradeList);
  const gap = targetIdx >= 0 && currentIdx >= 0 ? targetIdx - currentIdx : 0;

  // Warnings
  const isAmbitious = gap > 8;
  const isTooLow =
    goal.target_grade !== "" &&
    currentIdx >= 0 &&
    targetIdx >= 0 &&
    targetIdx <= currentIdx;

  const setGoal = (
    fields: Partial<typeof goal>,
  ) => {
    update("goal", {
      ...goal,
      ...fields,
      goal_type: fields.discipline
        ? fields.discipline === "lead"
          ? "lead_grade"
          : "boulder_grade"
        : goalType,
    });
  };

  // Sync current_grade whenever it changes
  const syncAndSetGoal = (fields: Partial<typeof goal>) => {
    const nextDiscipline = fields.discipline ?? discipline;
    const nextStyle = fields.target_style ?? targetStyle;

    let nextCurrent: string;
    if (nextDiscipline === "lead") {
      nextCurrent = nextStyle === "onsight" ? grades.lead_max_os : grades.lead_max_rp;
    } else {
      nextCurrent = nextStyle === "onsight"
        ? (grades.boulder_max_os ?? "")
        : (grades.boulder_max_rp ?? "");
    }

    setGoal({
      ...fields,
      current_grade: nextCurrent,
      // Reset target when discipline/style changes (it may no longer be valid)
      ...(fields.discipline !== undefined || fields.target_style !== undefined
        ? { target_grade: "" }
        : {}),
    });
  };

  const isValid =
    goal.target_grade !== "" &&
    goal.deadline !== "" &&
    !isTooLow;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Your goal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Discipline */}
          <div className="space-y-3">
            <Label>Discipline</Label>
            <RadioGroup
              value={discipline}
              onValueChange={(v) => syncAndSetGoal({ discipline: v })}
              className="flex gap-6"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="lead" id="disc-lead" />
                <Label htmlFor="disc-lead">Lead</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="boulder" id="disc-boulder" />
                <Label htmlFor="disc-boulder">Boulder</Label>
              </div>
            </RadioGroup>
          </div>

          {/* Target style */}
          <div className="space-y-3">
            <Label>Target style</Label>
            <RadioGroup
              value={targetStyle}
              onValueChange={(v) => syncAndSetGoal({ target_style: v })}
              className="flex gap-6"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="redpoint" id="style-rp" />
                <Label htmlFor="style-rp">Redpoint</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="onsight" id="style-os" />
                <Label htmlFor="style-os">Onsight</Label>
              </div>
            </RadioGroup>
          </div>

          {/* Current grade display */}
          {currentGrade && (
            <div className="rounded-md bg-muted px-3 py-2 text-sm">
              Your current grade ({discipline} {targetStyle}):{" "}
              <strong>{currentGrade}</strong>
            </div>
          )}

          {/* Target grade */}
          <div className="space-y-2">
            <Label>Target grade *</Label>
            <Select
              value={goal.target_grade}
              onValueChange={(v) => setGoal({ target_grade: v, current_grade: currentGrade })}
            >
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
            <Label htmlFor="deadline">Target date *</Label>
            <Input
              id="deadline"
              type="date"
              value={goal.deadline}
              onChange={(e) => setGoal({ deadline: e.target.value })}
            />
          </div>

          {/* Warnings */}
          {isAmbitious && (
            <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
              Ambitious goal! The plan will be aggressive
            </div>
          )}
          {isTooLow && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-600 dark:bg-red-950 dark:text-red-200">
              The target is equal to or lower than your current level
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/grades")}
        >
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => router.push("/onboarding/weaknesses")}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
