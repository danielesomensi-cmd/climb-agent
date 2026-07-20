"use client";

import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";
import { makeQueryClient } from "@/lib/query-client";
import {
  createPersister,
  PERSISTED_QUERY_PREFIXES,
  PERSIST_MAX_AGE_MS,
} from "@/lib/query-persist";

/**
 * A187 — Client-side providers.
 *
 * Wraps the app in a QueryClientProvider. The QueryClient is held in
 * useState so React keeps the same instance across renders, but Next.js
 * mounts a fresh instance per browser session.
 *
 * A245 B-2 (F1) — PersistQueryClientProvider replaces the plain provider so
 * `state` and `week` survive iOS killing the PWA. The official provider (not a
 * hand-rolled hydration effect) is used because it holds rendering until the
 * restore resolves; doing it by hand races with the first queries and
 * intermittently serves an empty cache.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());
  const [persister] = useState(() => createPersister());

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: PERSIST_MAX_AGE_MS,
        dehydrateOptions: {
          shouldDehydrateQuery: (query) => {
            const root = query.queryKey[0];
            if (query.state.status !== "success") return false;
            if (typeof root !== "string" || !PERSISTED_QUERY_PREFIXES.includes(root)) {
              return false;
            }
            // B292 — never persist an EMPTY user state. It restores instantly
            // on the next load with `isLoading === false`, which made /today
            // tell an established user to "complete your onboarding" while the
            // real state was still being fetched. A user with no plan has
            // nothing worth showing offline anyway.
            if (root === "state") {
              const data = query.state.data as { macrocycle?: unknown } | undefined;
              return !!data?.macrocycle;
            }
            return true;
          },
        },
      }}
    >
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
      )}
    </PersistQueryClientProvider>
  );
}
