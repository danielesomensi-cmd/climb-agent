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
  // A286 — l'indice viene SEMPRE da ONBOARDING_STEPS. Le schermate che stanno
  // fuori dal wizard (install, start-week) cadevano su stepIndexOf() = -1 e
  // l'ultima schermata del flusso annunciava "0 / 12" con la barra a zero:
  // fuori dalla lista significa "wizard concluso", non "step zero".
  const idx = stepIndexOf(pathname);
  const isDone = idx < 0;
  const currentStep = isDone ? STEPS.length - 1 : idx;
  const progress = isDone ? 100 : ((idx + 1) / STEPS.length) * 100;

  return (
    <div className="px-4 pt-4 pb-2">
      <Progress value={progress} className="h-1.5" />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {isDone ? "Done" : `${idx + 1} / ${STEPS.length}`}
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
