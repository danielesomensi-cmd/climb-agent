"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { purgePersistedCache } from "@/lib/query-persist";
import { purgeLegacyGuidedKeys } from "@/lib/guided-session-utils";

/**
 * A245 B-2 — purge every device-local trace of the previous user when the
 * signed-in identity changes.
 *
 * Sign-out happens inside Clerk's <UserButton />, so there is no app-level
 * callback to hang this on. Watching `userId` instead is strictly better: it
 * fires on sign-out AND on account switch, and the switch is the dangerous
 * case — signing in as B with A's plan still in the persisted cache would
 * render A's training data for B.
 *
 * Mounted once in the root layout, inside <Providers> so the QueryClient is
 * in scope.
 */
export function SessionScopeGuard() {
  const { isLoaded, userId } = useAuth();
  const qc = useQueryClient();
  const previous = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    if (!isLoaded) return;
    const current = userId ?? null;

    // First observation after mount: nothing to compare against. The persister
    // already refuses to restore a payload whose user id does not match, so
    // the cold-start case is covered there.
    if (previous.current === undefined) {
      previous.current = current;
      purgeLegacyGuidedKeys();
      return;
    }

    if (previous.current !== current) {
      purgePersistedCache();
      qc.clear();
      previous.current = current;
    }
  }, [isLoaded, userId, qc]);

  return null;
}
