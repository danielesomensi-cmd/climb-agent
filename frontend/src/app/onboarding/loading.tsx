/**
 * A245 Phase D (F48) — the onboarding segment had no loading.tsx, so a server
 * component awaiting the backend (welcome) rendered nothing at all while it
 * waited. On the first screen after sign-up that reads as a broken app.
 */
export default function OnboardingLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="animate-pulse text-sm text-muted-foreground">
        Setting things up...
      </div>
    </div>
  );
}
