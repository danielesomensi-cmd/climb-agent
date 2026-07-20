"use client";

import { useEffect } from "react";

/**
 * A245 C-4 (F10) — the app had zero error boundaries, so a single render
 * TypeError on an unexpected payload took down the whole screen with Next's
 * generic error page, unrecoverable without a reload. On an offline PWA the
 * reload itself can fail, so "just reload" was not a real escape hatch.
 *
 * Shared body for every error.tsx so the recovery affordances stay identical:
 * reset first (re-renders the segment without a network round trip), then a
 * link out to a route that is in the precache.
 */
export function ErrorFallback({
  error,
  reset,
  scope,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  scope: string;
}) {
  useEffect(() => {
    console.error(`[error-boundary:${scope}]`, error);
  }, [error, scope]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <span className="text-4xl" aria-hidden="true">
        ⚠️
      </span>
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This screen failed to load. Your training data is safe — nothing was
        lost.
      </p>
      <div className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={reset}
          className="flex min-h-[44px] items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground"
        >
          Try again
        </button>
        <a
          href="/today"
          className="flex min-h-[44px] items-center justify-center rounded-md border px-6 text-sm font-medium"
        >
          Back to Today
        </a>
      </div>
      {error.digest && (
        <p className="pt-2 font-mono text-[11px] text-muted-foreground/70">
          ref: {error.digest}
        </p>
      )}
    </div>
  );
}
