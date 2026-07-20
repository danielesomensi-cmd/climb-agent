"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

/**
 * A245 Phase D (F18) — shared Back/Next footer for the wizard.
 *
 * The steps used to render `<Button disabled={!isValid}>Next</Button>`, with
 * nothing anywhere saying what "valid" meant. Weaknesses, grades and
 * availability were all classic grey-button dead ends: the user taps, nothing
 * happens, no explanation, and they leave.
 *
 * Next is never disabled here. Tapping it with unmet requirements reveals
 * exactly what is missing, which turns a dead end into an instruction.
 */
export function StepNav({
  backHref,
  nextHref,
  blockers,
  nextLabel = "Next",
  onNext,
}: {
  backHref: string;
  nextHref: string;
  /** Human-readable list of what is still missing. Empty = free to continue. */
  blockers: string[];
  nextLabel?: string;
  /** Runs before navigating, only when there are no blockers. */
  onNext?: () => void;
}) {
  const router = useRouter();
  const [attempted, setAttempted] = useState(false);
  const blocked = blockers.length > 0;

  return (
    <div className="space-y-3">
      {attempted && blocked && (
        <div
          role="alert"
          className="rounded-md border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning"
        >
          <p className="font-medium">Before you continue:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-between">
        <Button
          variant="outline"
          className="min-h-[44px]"
          onClick={() => router.push(backHref)}
        >
          Back
        </Button>
        <Button
          className="min-h-[44px]"
          // Deliberately NOT disabled — see the note above.
          aria-describedby={attempted && blocked ? "step-blockers" : undefined}
          onClick={() => {
            if (blocked) {
              setAttempted(true);
              return;
            }
            onNext?.();
            router.push(nextHref);
          }}
        >
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}
