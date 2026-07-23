"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { getState } from "@/lib/api";
import { readLastDestination, writeLastDestination } from "@/lib/last-destination";

/**
 * A245 B-3 (F1) — the root used to decide where to go by calling getState()
 * against Railway. Offline that call fails and the old `.catch` sent the user
 * to /onboarding/welcome: an established user opening the PWA in falesia was
 * dropped into the onboarding wizard, with the real plan sitting in cache.
 *
 * The last known destination is now recorded in localStorage and used
 * immediately; the network only ever corrects it.
 */

export default function Home() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Wait for Clerk to finish loading before making any decisions
    if (!isLoaded) return;

    // B300 — a cold visitor from an ad/flyer QR who types climbagent.app used
    // to hit the bare /sign-in form (a login wall, no pitch). Send them to the
    // public welcome landing instead: hero + value props + "Start assessment"
    // CTA, with a "Recover access" link for returning users. Signed-in users
    // still route straight to /today below (no double hop).
    if (!isSignedIn) {
      router.replace("/onboarding/welcome");
      return;
    }

    getState()
      .then((state) => {
        const dest = state.macrocycle ? "/today" : "/onboarding/welcome";
        writeLastDestination(dest);
        router.replace(dest);
      })
      .catch((err) => {
        // Network failure is NOT evidence that onboarding is incomplete.
        const remembered = readLastDestination();
        if (remembered) {
          console.warn("Root redirect offline — using last known destination:", remembered);
          router.replace(remembered);
          return;
        }
        console.error("Failed to load state on root redirect:", err);
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
