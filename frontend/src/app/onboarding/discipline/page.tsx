"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const DISCIPLINES = [
  {
    value: "lead",
    title: "Lead",
    description: "Sport climbing — routes on rope",
  },
  {
    value: "boulder",
    title: "Boulder",
    description: "Bouldering — short powerful problems",
  },
  {
    value: "both",
    title: "Both",
    description: "I train and climb both",
  },
] as const;

export default function DisciplinePage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const selected = data.goal.discipline || "lead";

  const setDiscipline = (value: string) => {
    const goalType =
      value === "lead"
        ? "lead_grade"
        : value === "boulder"
          ? "boulder_grade"
          : "all_round";
    update("goal", {
      ...data.goal,
      discipline: value,
      goal_type: goalType,
      // Reset targets when discipline changes
      target_grade: "",
      target_boulder_grade: undefined,
      target_style: value === "boulder" ? "" : data.goal.target_style || "redpoint",
    });
  };

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">What do you climb?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {DISCIPLINES.map((d) => (
            <Card
              key={d.value}
              className={`cursor-pointer transition-colors ${
                selected === d.value
                  ? "border-primary ring-2 ring-primary/30"
                  : "hover:border-primary/50"
              }`}
              onClick={() => setDiscipline(d.value)}
            >
              <CardContent className="py-4 px-5">
                <p className="text-base font-semibold">{d.title}</p>
                <p className="text-sm text-muted-foreground">
                  {d.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/experience")}
        >
          Back
        </Button>
        <Button onClick={() => router.push("/onboarding/grades")}>
          Next
        </Button>
      </div>
    </div>
  );
}
