"use client";

import Link from "next/link";
import { formatPauseDate } from "@/lib/hooks/use-plan-pause";

/**
 * A223 — "plan paused" banner. Read-only: the resume action lives in Settings
 * (single source of truth), so this just informs and links there.
 *
 * A286 — era duplicato: /week aveva questa riga, /today una card ambra scritta
 * a mano con copy e colori diversi per lo stesso stato. Una sola sorgente, due
 * densità:
 *  - "compact"   : riga informativa (Week, Plan)
 *  - "prominent" : card che sostituisce le sessioni del giorno (Today)
 */
export function PausedBanner({
  since,
  variant = "compact",
}: {
  since: string | null | undefined;
  variant?: "compact" | "prominent";
}) {
  if (!since) return null;

  if (variant === "prominent") {
    return (
      <div className="rounded-xl border border-warning/30 bg-warning/10 p-6 text-center space-y-3">
        <p className="text-lg font-semibold text-warning">Plan paused</p>
        <p className="text-sm text-muted-foreground">
          Paused since {formatPauseDate(since)}. Your training is frozen right
          where you left off — no sessions are scheduled while paused.
        </p>
        <Link
          href="/settings"
          className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Resume plan
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
      <span className="font-medium">Plan paused</span> since{" "}
      {formatPauseDate(since)}.{" "}
      <Link href="/settings" className="underline underline-offset-2">
        Resume in Settings
      </Link>{" "}
      to continue training.
    </div>
  );
}
