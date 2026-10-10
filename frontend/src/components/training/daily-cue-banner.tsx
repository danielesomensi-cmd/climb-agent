import { Lightbulb } from "lucide-react";
import type { SessionSlot } from "@/lib/types";

/** Tiny deterministic string hash (FNV-1a-ish) — stable per date, no flicker. */
function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * A220: ONE process cue for the day (cues are per-session, so when the day has
 * multiple sessions we pick one deterministically — seeded on the date,
 * preferring not-yet-finalized sessions). Null when no session carries a cue
 * (rest day, cues absent). The /guided banner is unaffected.
 *
 * A308: the cue no longer has its own amber card above the day — it is one
 * line under the header of the session it belongs to (see SessionCard).
 */
export function pickDailyCue(
  sessions: SessionSlot[],
  date: string,
): { session: SessionSlot; text: string } | null {
  // Only planned (non-finalized) sessions — the cue is a pre-session briefing,
  // so once everything for the day is done/skipped the line disappears.
  const candidates = sessions.filter(
    (s) =>
      s.status !== "done" &&
      s.status !== "skipped" &&
      s.process_cue?.text &&
      s.process_cue.text.trim().length > 0,
  );
  if (candidates.length === 0) return null;

  // Cues are per-session; with multiple sessions pick one deterministically
  // (seeded on the date so it's stable per render but varies day to day).
  const picked = candidates[hashString(date) % candidates.length];
  return { session: picked, text: picked.process_cue!.text };
}

/** A308 — the day's focus as a single line inside the session card. */
export function DailyCueLine({ text }: { text: string }) {
  return (
    <p className="flex items-start gap-1.5 text-sm text-fg">
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
      <span>
        <span className="font-medium text-warning">Focus:</span> {text}
      </span>
    </p>
  );
}
