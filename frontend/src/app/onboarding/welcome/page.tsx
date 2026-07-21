import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { ONBOARDING_STEPS } from "@/lib/onboarding-steps";
import { WelcomeContent } from "./welcome-content";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function WelcomePage() {
  const { userId, getToken } = await auth();

  if (!userId) {
    return <WelcomeContent />;
  }

  let hasMacrocycle = false;
  // B293: resume point from the server-side wizard draft — after a forced
  // re-auth the user lands back on the deepest step they reached, not on step 1.
  let resumeStep: string | null = null;
  try {
    const token = await getToken();
    // A245 Phase D (F48) — this fetch had no timeout, and being a server
    // component it blocks the whole page render: a slow or cold Railway meant
    // the very first screen after sign-up hung with nothing on screen at all.
    // 5s then continue the wizard; the redirect below is only an optimisation.
    const res = await fetch(`${API_BASE}/api/state`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const state = (await res.json()) as {
        macrocycle?: unknown;
        onboarding_draft?: { deepest_step?: number } | null;
      };
      hasMacrocycle = !!state.macrocycle;
      const idx = state.onboarding_draft?.deepest_step;
      if (typeof idx === "number" && idx > 0 && idx < ONBOARDING_STEPS.length) {
        resumeStep = ONBOARDING_STEPS[idx];
      }
    }
  } catch {
    // Network/backend hiccup — treat as onboarding incomplete and continue the wizard
  }

  if (hasMacrocycle) redirect("/today");
  redirect(resumeStep ? `/onboarding/${resumeStep}` : "/onboarding/profile");
}
