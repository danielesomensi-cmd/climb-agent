"use client";

import { ArrowRight, Check, Flag, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * B411 — Skip and Done pinned to the bottom of the screen.
 *
 * Done used to close a long card: timer, "How to" open on arrival, load
 * fields, rating, notes. Every exercise ended with a swipe down to reach it,
 * and on an iPhone a tap that lands while the page is still gliding (or
 * bouncing at the end) only stops the scroll — the button never hears it.
 * Daniele, 02/11: «devo premere spesso done due volte». Pinned, the buttons
 * sit under the thumb from the first second and no scroll stands between the
 * last set and the next exercise.
 *
 * Below the enlarged timer (z-60), which covers it on purpose, and below the
 * update banner (z-100). The page reserves GUIDED_ACTION_BAR_SPACE at the end
 * of its content, so "Finish session early" still scrolls clear of the bar.
 */
export const GUIDED_ACTION_BAR_SPACE = "pb-[calc(9rem+env(safe-area-inset-bottom))]";

interface GuidedActionBarProps {
  onDone: () => void;
  /** Absent for instruction-only blocks (warm-up, mobility): Done only. */
  onSkip?: () => void;
  doneLabel: string;
  /**
   * Where Done / Skip lead: the next exercise still to do, or null when the
   * summary comes next. Undefined hides the line.
   */
  upNext?: string | null;
}

export function GuidedActionBar({ onDone, onSkip, doneLabel, upNext }: GuidedActionBarProps) {
  return (
    <div
      data-testid="guided-action-bar"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-40"
    >
      <div className="pointer-events-auto relative mx-auto max-w-2xl">
        {/* Content fades under the bar instead of being cut by a hard edge. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-linear-to-t from-background/90 to-transparent"
        />
        <div className="border-t border-border/60 bg-background/90 px-4 pt-2.5 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-[0_-16px_32px_-20px_rgba(0,0,0,0.8)] backdrop-blur-xl">
          {upNext !== undefined && (
            <p
              data-testid="guided-up-next"
              className="mb-2 flex min-w-0 items-center gap-1.5 px-0.5 text-xs text-muted-foreground"
            >
              {upNext === null ? (
                <>
                  <Flag className="size-3.5 shrink-0" aria-hidden />
                  <span className="truncate">Last one · then the summary</span>
                </>
              ) : (
                <>
                  <ArrowRight className="size-3.5 shrink-0" aria-hidden />
                  <span className="shrink-0">Next</span>
                  <span aria-hidden>·</span>
                  <span className="truncate font-medium text-foreground/80">{upNext}</span>
                </>
              )}
            </p>
          )}
          <div className="flex items-stretch gap-2">
            {onSkip && (
              <Button
                variant="outline"
                className="h-14 rounded-xl px-5 text-base text-muted-foreground"
                onClick={onSkip}
              >
                <SkipForward className="size-5" />
                Skip
              </Button>
            )}
            <Button
              className="h-14 flex-1 rounded-xl bg-success text-base font-semibold text-black shadow-[0_8px_24px_-10px_hsl(var(--glow-success))] hover:bg-success/90"
              onClick={onDone}
            >
              <Check className="size-5" strokeWidth={2.5} />
              {doneLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
