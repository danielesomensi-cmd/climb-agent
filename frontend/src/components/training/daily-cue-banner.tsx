import type { SessionSlot } from "@/lib/types";

interface DailyCueBannerProps {
  sessions: SessionSlot[];
  /** Date string (YYYY-MM-DD) of the viewed day — seeds the deterministic pick. */
  date: string;
  /** Whether the viewed day is today — switches the section label. */
  isToday?: boolean;
}

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
 * A220: standalone "Focus di oggi" section shown above the day's session cards
 * on /today. Surfaces ONE process cue for the day (cues are per-session, so when
 * the day has multiple sessions we pick one deterministically — seeded on the
 * date, preferring not-yet-finalized sessions). Renders nothing when no session
 * carries a cue (rest day, cues absent). The /guided banner is unaffected.
 */
export function DailyCueBanner({ sessions, date, isToday = true }: DailyCueBannerProps) {
  const withCue = sessions.filter(
    (s) => s.process_cue?.text && s.process_cue.text.trim().length > 0,
  );
  if (withCue.length === 0) return null;

  // Prefer planned (non-finalized) sessions — the cue is a pre-session briefing.
  const planned = withCue.filter(
    (s) => s.status !== "done" && s.status !== "skipped",
  );
  const candidates = planned.length > 0 ? planned : withCue;

  const picked = candidates[hashString(date) % candidates.length];
  const cueText = picked.process_cue!.text;

  return (
    <section
      aria-label="Focus of the day"
      className="rounded-xl bg-gradient-to-r from-amber-900/30 to-amber-800/20 border border-amber-700/30 p-4"
    >
      <div className="flex items-start gap-3">
        <svg
          className="h-5 w-5 text-amber-400 mt-0.5 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"
          />
        </svg>
        <div>
          <p className="text-xs font-medium text-amber-400 mb-1">
            {isToday ? "Focus di oggi" : "Focus della sessione"}
          </p>
          <p className="text-sm text-zinc-200 leading-relaxed">{cueText}</p>
        </div>
      </div>
    </section>
  );
}
