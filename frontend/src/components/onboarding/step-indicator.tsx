"use client";

import { usePathname } from "next/navigation";
import { Progress } from "@/components/ui/progress";

const STEPS = [
  "welcome", "profile", "experience", "grades", "goals",
  "weaknesses", "tests", "limitations", "locations", "availability", "trips", "review",
];

export function StepIndicator() {
  const pathname = usePathname();
  const currentStep = STEPS.findIndex((s) => pathname.includes(s));
  const progress = currentStep >= 0 ? ((currentStep + 1) / STEPS.length) * 100 : 0;

  return (
    <div className="px-4 pt-4 pb-2">
      <Progress value={progress} className="h-1.5" />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {currentStep + 1} / {STEPS.length}
        </span>
        <div className="flex gap-1">
          {STEPS.map((step, i) => (
            <div
              key={step}
              className={`h-1.5 w-1.5 rounded-full transition-colors ${
                i <= currentStep ? "bg-primary" : "bg-muted"
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
