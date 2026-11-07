"use client";

import { useLayoutEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Banner } from "@/components/training/banner";
import { GUIDED_PROGRESS_EVENT } from "@/lib/guided-resume";
import { listUndecidedGuidedFeedback, type UndecidedFeedback } from "@/lib/guided-pending-feedback";

/**
 * B414 (INBOX-2026-11-04-ORPHAN) — sessions played on this phone whose
 * feedback the server refused because they are no longer in the plan. They
 * wait on the device «to decide» (the replay passes over them); this banner
 * is the way back to the player's choice box. Not dismissable: the feedback
 * is the only copy, and the box's «Discard» is the deliberate way out.
 */
export function OrphanSessionsBanner({ authReady }: { authReady: boolean }) {
  const router = useRouter();
  const [entries, setEntries] = useState<UndecidedFeedback[]>([]);

  useLayoutEffect(() => {
    const scan = () => setEntries(listUndecidedGuidedFeedback());
    scan();
    window.addEventListener(GUIDED_PROGRESS_EVENT, scan);
    return () => window.removeEventListener(GUIDED_PROGRESS_EVENT, scan);
  }, [authReady]);

  if (entries.length === 0) return null;
  return (
    <Banner tone="warning" className="space-y-2">
      <p className="text-sm font-medium text-warning">
        {entries.length === 1
          ? "A session you played is no longer in your plan"
          : `${entries.length} sessions you played are no longer in your plan`}
      </p>
      <p className="text-xs text-warning/80">
        Nothing was saved yet. Log it in place of what is there now, as an extra, or discard it.
      </p>
      {entries.map((e) => (
        <button
          key={e.key}
          type="button"
          className="flex min-h-[44px] w-full items-center justify-between gap-2 rounded-md bg-warning px-4 text-sm font-medium text-surface-base transition-colors hover:bg-warning/90"
          onClick={() => router.push(`/guided/${e.date}/${e.sessionId}`)}
        >
          <span className="truncate">{e.sessionName}</span>
          <span className="shrink-0 tabular-nums">{e.date.slice(8, 10)}/{e.date.slice(5, 7)} · Choose</span>
        </button>
      ))}
    </Banner>
  );
}
