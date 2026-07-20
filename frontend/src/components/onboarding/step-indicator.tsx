"use client";

import { usePathname } from "next/navigation";
import { Progress } from "@/components/ui/progress";
import { ONBOARDING_STEPS, stepIndexOf } from "@/lib/onboarding-steps";

// A245 Phase D (F45): `welcome` used to be in this list. It is hidden by the
// guard below but still counted, so the first screen the user actually fills in
// announced itself as "2 / 14".
const STEPS = ONBOARDING_STEPS;

export function StepIndicator() {
  const pathname = usePathname();
  // A216: hide on welcome — hero takes full visual focus
  if (pathname.endsWith("/welcome")) return null;
  const isStartWeek = pathname.includes("start-week");
  const currentStep = isStartWeek ? STEPS.length - 1 : stepIndexOf(pathname);
  const progress = isStartWeek ? 100 : (currentStep >= 0 ? ((currentStep + 1) / STEPS.length) * 100 : 0);

  return (
    <div className="px-4 pt-4 pb-2">
      <Progress value={progress} className="h-1.5" />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {isStartWeek ? "Done" : `${currentStep + 1} / ${STEPS.length}`}
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
