"use client";

import { useState, type ReactNode } from "react";
import { ChunkErrorBoundary } from "@/components/chunk-error-boundary";
import { notifyChunkLoadFailure } from "@/lib/chunk-load";

/**
 * B398 review (round 2) — a dialog or sheet loaded with next/dynamic, mounted
 * only from its first open and kept mounted afterwards (so its close
 * animation still plays).
 *
 * Always mounted, the lazy component fetched its chunk as soon as the page
 * rendered: offline, right after a deploy, a chunk the service worker had
 * never seen threw during render and the route error boundary replaced the
 * whole page (/plan, /settings). Now nothing is fetched until the athlete
 * opens it, and a chunk that cannot load closes it (`onFail`) with a toast
 * that says why — instead of taking the page down.
 */
export function LazyWhenOpen({
  open,
  onFail,
  children,
}: {
  open: boolean;
  onFail: () => void;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(open);
  // Derived from the previous render (React's documented pattern): becomes
  // true on the first open and never goes back.
  if (open && !mounted) setMounted(true);
  if (!mounted) return null;
  return (
    <ChunkErrorBoundary
      onError={() => {
        // Review round 3 — unmount the failed boundary too: kept mounted it
        // rendered nothing on the next open and said nothing, and `open`
        // stayed true. Remounted on the next open, it surfaces the (still
        // rejected) import again: closed again, toast again.
        setMounted(false);
        onFail();
        notifyChunkLoadFailure();
      }}
    >
      {children}
    </ChunkErrorBoundary>
  );
}
