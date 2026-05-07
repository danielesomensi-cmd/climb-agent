import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { WelcomeContent } from "./welcome-content";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function WelcomePage() {
  const { userId, getToken } = await auth();

  if (!userId) {
    return <WelcomeContent />;
  }

  let hasMacrocycle = false;
  try {
    const token = await getToken();
    const res = await fetch(`${API_BASE}/api/state`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (res.ok) {
      const state = (await res.json()) as { macrocycle?: unknown };
      hasMacrocycle = !!state.macrocycle;
    }
  } catch {
    // Network/backend hiccup — treat as onboarding incomplete and continue the wizard
  }

  if (hasMacrocycle) redirect("/today");
  redirect("/onboarding/install");
}
