"use client";

import { useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { putState } from "@/lib/api";
import {
  celebrationKey,
  computeCurrentWeek,
  getPhaseAtWeek,
  isCycleEnded,
} from "@/lib/phase-progress";
import { getPhaseName } from "@/lib/phase-labels";
import { getDiscipline } from "@/lib/gradeUtils";
import { PHASE_RATIONALES } from "@/lib/phase-rationales";
import type { Macrocycle, UserState } from "@/lib/types";
import { parseISODateLocal } from "@/lib/dates";

interface PhaseCelebrationProps {
  state: UserState | undefined;
}

/**
 * A235 (A-GAMIFY-01): one-time celebration modal when the user enters a new
 * macrocycle phase — celebrates the phase they just COMPLETED and frames what
 * comes next (SDT competence, "train better not more"; see
 * docs/design_gamification.md §P1).
 *
 * Seen-tracking lives in preferences.phase_celebrations_seen (keys scoped to
 * the cycle via start_date, so a new cycle celebrates again). Backlog rule:
 * only the CURRENT phase entry is ever celebrated — earlier unseen phases are
 * marked silently (no modal queue for users returning after weeks away).
 * Never shown for the first phase, while paused, or after cycle end.
 */
export function PhaseCelebration({ state }: PhaseCelebrationProps) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState<{
    prevLabel: string;
    prevWeeks: number;
    newLabel: string;
    expect?: string;
  } | null>(null);
  const checkedRef = useRef(false);

  useEffect(() => {
    if (checkedRef.current) return;
    const macrocycle = state?.macrocycle as Macrocycle | undefined;
    if (!macrocycle?.phases?.length || !macrocycle.start_date) return;
    checkedRef.current = true;

    if (macrocycle.pause?.active_since) return; // paused → not a celebration moment
    if (parseISODateLocal(macrocycle.start_date).getTime() > Date.now()) return;
    if (isCycleEnded(macrocycle)) return;

    const week = computeCurrentWeek(macrocycle);
    const current = getPhaseAtWeek(macrocycle, week);
    if (!current) return;

    const prefs = (state?.preferences ?? {}) as Record<string, unknown>;
    const seen: string[] = Array.isArray(prefs.phase_celebrations_seen)
      ? (prefs.phase_celebrations_seen as string[])
      : [];

    // Keys for every phase up to and including the current one.
    const dueKeys = macrocycle.phases
      .slice(0, current.index + 1)
      .map((p) => celebrationKey(macrocycle, p.phase_id));
    const unseen = dueKeys.filter((k) => !seen.includes(k));
    if (unseen.length === 0) return;

    const currentKey = celebrationKey(macrocycle, current.phase.phase_id);
    const celebrate = current.index > 0 && unseen.includes(currentKey);

    // Persist ALL due keys in one write — earlier phases are silently
    // backfilled so a long absence never queues multiple modals.
    const nextSeen = [...seen, ...unseen];
    putState({ preferences: { phase_celebrations_seen: nextSeen } }).catch(
      () => {}, // best-effort — worst case the modal shows once more
    );

    if (!celebrate) return;
    const prev = macrocycle.phases[current.index - 1];
    const discipline = getDiscipline(
      (state?.goal as { goal_type?: string } | undefined)?.goal_type,
    );
    setContent({
      prevLabel: getPhaseName(prev.phase_id, discipline),
      prevWeeks: prev.duration_weeks,
      newLabel: getPhaseName(current.phase.phase_id, discipline),
      expect: PHASE_RATIONALES[current.phase.phase_id]?.what_to_expect,
    });
    setOpen(true);
  }, [state]);

  if (!content) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-center text-2xl">🎉</DialogTitle>
          <DialogTitle className="text-center">
            {content.prevLabel} complete!
          </DialogTitle>
          <DialogDescription className="text-center">
            {content.prevWeeks}{" "}
            {content.prevWeeks === 1 ? "week" : "weeks"} of focused work in the
            bank. Your body has adapted — time for the next stimulus.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-md border bg-background/50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Now: {content.newLabel}
          </p>
          {content.expect && (
            <p className="mt-1 text-sm text-muted-foreground">{content.expect}</p>
          )}
        </div>
        <Button onClick={() => setOpen(false)} className="w-full">
          Let&apos;s go
        </Button>
      </DialogContent>
    </Dialog>
  );
}
