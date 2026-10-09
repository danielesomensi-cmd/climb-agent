"use client";

import { FEEDBACK_OPTIONS } from "@/lib/format";
import { tapFeedback } from "@/lib/haptics";

interface FeedbackPillsProps {
  /** Selected label, or null/undefined when not rated (A295). */
  value: string | null | undefined;
  /** Receives the new label, or null when the selected pill is tapped again. */
  onChange: (value: string | null) => void;
}

/**
 * A307 — the "How did it feel?" pill row, shared by the guided step and the
 * custom player's summary so both get the same 44px chalk-proof targets.
 * Wraps to two rows on a 375px screen.
 */
export function FeedbackPills({ value, onChange }: FeedbackPillsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {FEEDBACK_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(value === opt.value ? null : opt.value)}
          aria-pressed={value === opt.value}
          onPointerDown={tapFeedback}
          className={`min-h-[44px] rounded-full px-4 text-sm font-medium transition-all active:scale-95 motion-reduce:active:scale-100 ${
            value === opt.value
              ? `${opt.color} text-black ring-2 ring-offset-1 ring-offset-background ${opt.ring}`
              : "border border-border bg-muted text-foreground hover:bg-accent"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
