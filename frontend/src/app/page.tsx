"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { getState } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Wait for Clerk to finish loading before making any decisions
    if (!isLoaded) return;

    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }

    getState()
      .then((state) => {
        if (state.macrocycle) {
          router.replace("/today");
        } else {
          router.replace("/onboarding/welcome");
        }
      })
      .catch(() => {
        router.replace("/onboarding/welcome");
      })
      .finally(() => setLoading(false));
  }, [isLoaded, isSignedIn, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }
  return null;
}
