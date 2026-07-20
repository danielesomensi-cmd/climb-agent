"use client";

import { OnboardingProvider } from "@/components/onboarding/onboarding-context";
import { StepIndicator } from "@/components/onboarding/step-indicator";
import { ReturnToReviewBar } from "@/components/onboarding/return-to-review-bar";
import { Suspense } from "react";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OnboardingProvider>
      <div className="min-h-screen flex flex-col">
        {/* A245 Phase D (F47) — one-tap return when arriving from the summary */}
        <Suspense fallback={null}>
          <ReturnToReviewBar />
        </Suspense>
        <StepIndicator />
        <main className="flex-1 px-4 pb-8">{children}</main>
      </div>
    </OnboardingProvider>
  );
}
