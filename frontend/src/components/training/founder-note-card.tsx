"use client";

import { useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { putState } from "@/lib/api";
import {
  founderNoteCta,
  shouldShowFounderNote,
  type FounderNoteData,
} from "@/lib/founder-note";

/**
 * A264: a note from the founder, addressed to one specific athlete.
 *
 * Unlike {@link DailyTipCard} there is no catalog and no engine behind this —
 * the note is written by hand into ``user_state.founder_note`` for a single
 * user, and nobody else's ``/today`` renders anything. That is deliberate:
 * these go out when there is something worth saying to *that* person (a bug
 * we fixed on their account, a read of their assessment), and a templated
 * broadcast would defeat the point.
 *
 * Dismissal is a deep-merge PUT of ``dismissed_at`` — no new endpoint, and it
 * survives reloads and device switches because it lives in the user state.
 */
export type FounderNote = FounderNoteData;

export function FounderNoteCard({
  note,
  isViewingToday,
}: {
  note?: FounderNote | null;
  isViewingToday: boolean;
}) {
  const [hidden, setHidden] = useState(false);

  if (!shouldShowFounderNote(note, { isViewingToday, locallyDismissed: hidden })) {
    return null;
  }
  const shown = note as FounderNote;
  const cta = founderNoteCta(shown);

  const handleDismiss = () => {
    setHidden(true); // optimistic — never block the card on the network
    putState({ founder_note: { dismissed_at: new Date().toISOString() } }).catch(
      () => {},
    );
  };

  return (
    <section
      aria-label="A note from the founder"
      className="relative rounded-xl border border-primary/30 bg-gradient-to-br from-primary/10 to-transparent p-4"
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss note"
        className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>

      <div className="pr-8">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">
          A note from the founder
        </p>
        <p className="mt-1 font-semibold">{shown.title}</p>
        <div className="mt-2 space-y-2">
          {shown.body.map((paragraph, i) => (
            <p key={i} className="text-sm leading-relaxed text-muted-foreground">
              {paragraph}
            </p>
          ))}
        </div>

        {cta && (
          <Link
            href={cta.href}
            className="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {cta.label} →
          </Link>
        )}

        {shown.signature && (
          <p className="mt-3 text-xs text-muted-foreground">— {shown.signature}</p>
        )}
      </div>
    </section>
  );
}
