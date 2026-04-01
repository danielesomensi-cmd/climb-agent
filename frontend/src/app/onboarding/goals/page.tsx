"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
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
  const showLeadTarget = discipline === "lead" || discipline === "both";
  const showBoulderTarget = discipline === "boulder" || discipline === "both";
  const showTargetStyle = discipline !== "boulder";
  const targetStyle = goal.target_style || "redpoint";
  const totalWeeks = goal.total_weeks ?? 12;

  // Derive the current grade for lead target (used for assessment)
  const currentLeadGrade = useMemo(() => {
    return targetStyle === "onsight" ? grades.lead_max_os : grades.lead_max_rp;
  }, [targetStyle, grades]);

  // Derive the current grade for boulder target
  const currentBoulderGrade = useMemo(() => {
    return grades.boulder_max_rp ?? "";
  }, [grades]);

  // The "main" current grade (for display and gap computation)
  const currentGrade = discipline === "boulder" ? currentBoulderGrade : currentLeadGrade;

  // Derive goal_type from discipline
  const goalType = discipline === "lead"
    ? "lead_grade"
    : discipline === "boulder"
      ? "boulder_grade"
      : "all_round";

  // Lead target grades (above current)
  const leadCurrentIdx = gradeIndex(currentLeadGrade, LEAD_GRADES);
  const leadTargetGrades = leadCurrentIdx >= 0
    ? LEAD_GRADES.slice(leadCurrentIdx + 1)
    : LEAD_GRADES;

  // Boulder target grades (above current)
  const boulderCurrentIdx = gradeIndex(currentBoulderGrade, BOULDER_GRADES);
  const boulderTargetGrades = boulderCurrentIdx >= 0
    ? BOULDER_GRADES.slice(boulderCurrentIdx + 1)
    : BOULDER_GRADES;

  // For single-discipline: use the discipline's grade list
  const gradeList = discipline === "boulder" ? BOULDER_GRADES : LEAD_GRADES;
  const currentIdx = discipline === "boulder" ? boulderCurrentIdx : leadCurrentIdx;
  const targetIdx = gradeIndex(goal.target_grade, gradeList);
  const gap = targetIdx >= 0 && currentIdx >= 0 ? targetIdx - currentIdx : 0;

  // Calculated end date from weeks
  const endDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + totalWeeks * 7);
    return d.toISOString().split("T")[0];
  }, [totalWeeks]);

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
    const nextDiscipline = fields.discipline ?? discipline;
    const nextGoalType = nextDiscipline === "lead"
      ? "lead_grade"
      : nextDiscipline === "boulder"
        ? "boulder_grade"
        : "all_round";
    update("goal", {
      ...goal,
      ...fields,
      goal_type: nextGoalType,
    });
  };

  // Sync current_grade whenever it changes
  const syncAndSetGoal = (fields: Partial<typeof goal>) => {
    const nextDiscipline = fields.discipline ?? discipline;
    const nextStyle = fields.target_style ?? targetStyle;

    let nextCurrent: string;
    if (nextDiscipline === "boulder") {
      nextCurrent = grades.boulder_max_rp ?? "";
    } else {
      nextCurrent = nextStyle === "onsight" ? grades.lead_max_os : grades.lead_max_rp;
    }

    setGoal({
      ...fields,
      current_grade: nextCurrent,
      // Reset targets when discipline changes
      ...(fields.discipline !== undefined
        ? { target_grade: "", target_boulder_grade: undefined }
        : {}),
      // Reset target when style changes
      ...(fields.target_style !== undefined && !fields.discipline
        ? { target_grade: "" }
        : {}),
    });
  };

  // Validation
  const hasLeadTarget = !showLeadTarget || goal.target_grade !== "";
  const hasBoulderTarget = !showBoulderTarget || !!goal.target_boulder_grade;
  const isValid =
    hasLeadTarget &&
    hasBoulderTarget &&
    !isTooLow;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Your goal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Target style — hidden for boulder-only */}
          {showTargetStyle && (
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
              <p className="text-xs text-muted-foreground">
                Redpoint = your max grade after working the route. Onsight = climbing it clean on the first try. This changes how we prioritize your weaknesses.
              </p>
            </div>
          )}

          {/* Current grade display */}
          {currentGrade && (
            <div className="rounded-md bg-muted px-3 py-2 text-sm">
              Your current grade ({discipline === "both" ? "lead" : discipline}{" "}
              {showTargetStyle ? targetStyle : "redpoint"}):{" "}
              <strong>{currentGrade}</strong>
              {discipline === "both" && currentBoulderGrade && (
                <span className="ml-2">
                  · boulder: <strong>{currentBoulderGrade}</strong>
                </span>
              )}
            </div>
          )}

          {/* Lead target grade */}
          {showLeadTarget && (
            <div className="space-y-2">
              <Label>{discipline === "both" ? "Lead target grade *" : "Target grade *"}</Label>
              <Select
                value={goal.target_grade}
                onValueChange={(v) => setGoal({ target_grade: v, current_grade: currentLeadGrade })}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select grade" />
                </SelectTrigger>
                <SelectContent>
                  {leadTargetGrades.map((g) => (
                    <SelectItem key={g} value={g}>
                      {g}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Boulder target grade */}
          {showBoulderTarget && (
            <div className="space-y-2">
              <Label>{discipline === "both" ? "Boulder target grade *" : "Target grade *"}</Label>
              <Select
                value={goal.target_boulder_grade ?? ""}
                onValueChange={(v) => {
                  if (discipline === "both") {
                    setGoal({ target_boulder_grade: v });
                  } else {
                    // Boulder-only: store in target_boulder_grade (backend maps to lead equivalent)
                    setGoal({ target_boulder_grade: v, target_grade: "", current_grade: currentBoulderGrade });
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select grade" />
                </SelectTrigger>
                <SelectContent>
                  {boulderTargetGrades.map((g) => (
                    <SelectItem key={g} value={g}>
                      {g}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Plan duration (weeks) */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Plan duration (weeks) *</Label>
              <span className="text-sm font-medium tabular-nums">
                {totalWeeks} weeks
              </span>
            </div>
            <Slider
              min={8}
              max={24}
              step={1}
              value={[totalWeeks]}
              onValueChange={([v]) => setGoal({ total_weeks: v, deadline: (() => {
                const d = new Date();
                d.setDate(d.getDate() + v * 7);
                return d.toISOString().split("T")[0];
              })() })}
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>8 wk</span>
              <span className="font-medium text-primary">12 wk recommended</span>
              <span>24 wk</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Your plan ends: <strong>{endDate}</strong>
            </p>
            <p className="text-xs text-muted-foreground">
              A well-structured periodization cycle needs at least 12 weeks to go through all training phases (base, strength, power endurance, peak, recovery). Shorter plans compress phases and reduce effectiveness.
            </p>
            {totalWeeks < 12 && (
              <div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-200">
                Short plan — some training phases will be compressed
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
