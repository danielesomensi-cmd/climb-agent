"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
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
 *
 * A286 — era usato da 4 step su 12; gli altri 8 avevano footer copiati a mano
 * (CTA da 36px, bottoni grigi senza spiegazione). Ora lo usano tutti e 12, e
 * le due varianti che servivano davvero sono props: `secondary` (lo "Skip" di
 * tests/limitations) e `actions` (la review, che invia invece di navigare).
 */
export function StepNav({
  backHref,
  nextHref,
  blockers = [],
  nextLabel = "Next",
  onNext,
  secondary,
  actions,
  backDisabled,
}: {
  backHref: string;
  /** Not needed when `actions` replaces the primary CTA. */
  nextHref?: string;
  /** Human-readable list of what is still missing. Empty = free to continue. */
  blockers?: string[];
  nextLabel?: string;
  /** Runs before navigating, only when there are no blockers. */
  onNext?: () => void;
  /** Optional ghost action shown to the left of the primary CTA ("Skip"). */
  secondary?: ReactNode;
  /** Replaces the primary CTA entirely — for the step that submits. */
  actions?: ReactNode;
  backDisabled?: boolean;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [attempted, setAttempted] = useState(false);
  const blocked = blockers.length > 0;

  // A245 Phase D (F47) — when the user came here from the summary to fix one
  // field, Next should take them back there, not deeper into the wizard.
  const fromReview = params.get("from") === "review";
  const target = fromReview ? "/onboarding/review" : (nextHref ?? "");
  const label = fromReview ? "Done — back to summary" : nextLabel;

  return (
    <div className="space-y-3">
      {attempted && blocked && (
        <div
          id="step-blockers"
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

      <div className="flex items-center justify-between gap-3">
        <Button
          variant="outline"
          className="min-h-[44px]"
          disabled={backDisabled}
          onClick={() => router.push(backHref)}
        >
          Back
        </Button>
        <div className="flex items-center gap-2">
          {secondary}
          {actions ?? (
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
                if (target) router.push(target);
              }}
            >
              {label}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
