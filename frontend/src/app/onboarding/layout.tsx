"use client";

import { OnboardingProvider } from "@/components/onboarding/onboarding-context";
import { StepIndicator } from "@/components/onboarding/step-indicator";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OnboardingProvider>
      <div className="min-h-screen flex flex-col">
        <StepIndicator />
        <main className="flex-1 px-4 pb-8">{children}</main>
      </div>
    </OnboardingProvider>
  );
}
