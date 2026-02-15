"use client";

import { useRouter } from "next/navigation";
import { useOnboarding } from "@/components/onboarding/onboarding-context";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function ExperiencePage() {
  const router = useRouter();
  const { data, update } = useOnboarding();
  const exp = data.experience;

  const set = (
    field: keyof typeof exp,
    value: number,
  ) => {
    update("experience", { ...exp, [field]: value });
  };

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Your experience</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          {/* Climbing years */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>How many years have you been climbing?</Label>
              <span className="text-sm font-medium tabular-nums">
                {exp.climbing_years}
              </span>
            </div>
            <Slider
              min={0}
              max={30}
              step={1}
              value={[exp.climbing_years]}
              onValueChange={([v]) => set("climbing_years", v)}
            />
          </div>

          {/* Structured training years */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>How many years of structured training?</Label>
              <span className="text-sm font-medium tabular-nums">
                {exp.structured_training_years}
              </span>
            </div>
            <Slider
              min={0}
              max={20}
              step={1}
              value={[exp.structured_training_years]}
              onValueChange={([v]) => set("structured_training_years", v)}
            />
            <p className="text-xs text-muted-foreground">
              If you've never followed a training plan, enter 0
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => router.push("/onboarding/profile")}
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
