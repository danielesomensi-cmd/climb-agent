"use client";

import Link from "next/link";
import { formatPauseDate } from "@/lib/hooks/use-plan-pause";

/**
 * A223 — non-intrusive "plan paused" banner for the Week and Plan pages.
 * Read-only: the resume action lives in Settings (single source of truth),
 * so this just informs and links there.
 */
export function PausedBanner({ since }: { since: string | null | undefined }) {
  if (!since) return null;
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
      <span className="font-medium">Plan paused</span> since {formatPauseDate(since)}.{" "}
      <Link href="/settings" className="underline underline-offset-2">
        Resume in Settings
      </Link>{" "}
      to continue training.
    </div>
  );
}
