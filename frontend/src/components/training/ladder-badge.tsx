"use client";

/**
 * A298 — bodyweight ladder badge: where the athlete stands on the ladder of
 * this exercise, and the promotion proposal of a custom 'ladder' row.
 *
 * The proposal is only a proposal: nothing changes until the athlete taps
 * "Switch". "Stay" clears it (the next sessions at the top of the band propose
 * it again). Without `customSessionId` (engine sessions promote on their own)
 * the card only informs.
 */

import { useState } from "react";
import { TrendingUp } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/lib/query-keys";
import { tapFeedback } from "@/lib/haptics";
import type { LadderInfo } from "@/lib/types";
import { apiErrorDetail, resolveLadderPromotion } from "@/lib/api";
import { ladderSubtitle, ladderTitle, proposalText } from "@/lib/bw-ladder";
import { toast } from "sonner";

export function LadderBadge({
  ladder,
  customSessionId,
  date,
  compact = false,
  onResolved,
}: {
  ladder: LadderInfo | undefined;
  /** The custom session to rewrite on "Switch" (custom rows only). */
  customSessionId?: string;
  /** Day the session is played (YYYY-MM-DD). */
  date?: string;
  compact?: boolean;
  onResolved?: (accepted: boolean) => void;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<null | "accepted" | "declined">(null);
  if (!ladder) return null;
  const proposal = proposalText(ladder);
  const canAct = !!customSessionId && !!ladder.proposal && done === null;

  const resolve = async (accept: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      await resolveLadderPromotion(ladder.family, { accept, date, custom_session_id: customSessionId });
      setDone(accept ? "accepted" : "declined");
      toast(accept ? `Switched to ${ladder.proposal?.to_name}` : "Staying on this level");
      // The saved rows (and the week plan copies) changed: refetch them.
      qc.invalidateQueries({ queryKey: queryKeys.customSessionAll });
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
      qc.invalidateQueries({ queryKey: queryKeys.state });
      onResolved?.(accept);
    } catch (err) {
      toast.error(apiErrorDetail(err, "Could not update the level"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={cn(
        "rounded-md border border-primary/30 bg-primary/5 text-left",
        compact ? "px-2 py-1.5" : "p-2.5 space-y-1.5",
      )}
      data-testid="ladder-badge"
    >
      <div className="flex items-center gap-1.5">
        <TrendingUp className="size-3.5 shrink-0 text-primary" aria-hidden />
        <p className="text-xs font-medium">{ladderTitle(ladder)}</p>
        <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">{ladder.dose}</span>
      </div>
      {!compact && <p className="text-[11px] text-muted-foreground">{ladderSubtitle(ladder)}</p>}
      {proposal && done === null && (
        <div className="space-y-1.5 pt-1">
          <p className="text-xs font-medium">{proposal}</p>
          {canAct ? (
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => resolve(true)}
                onPointerDown={tapFeedback}
                className="min-h-[44px] rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-60"
              >
                Switch
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => resolve(false)}
                onPointerDown={tapFeedback}
                className="min-h-[44px] rounded-full border border-border bg-muted px-4 text-sm font-medium disabled:opacity-60"
              >
                Stay
              </button>
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">Confirm it from the session builder.</p>
          )}
        </div>
      )}
      {done === "accepted" && (
        <p className="text-[11px] text-muted-foreground">Saved — the session now uses {ladder.proposal?.to_name}.</p>
      )}
    </div>
  );
}
