import type { OutdoorAttempt } from "@/lib/types";
import type { TryTiming } from "@/lib/try-timings";

/**
 * A241 — read-only per-try rest/climb rows for one route:
 *
 *   ✗ try 1 · rest —      · climb 2:41
 *   ✓ try 3 · rest 21:12
 *
 * Rendered wherever a route's tries are shown (live card expanded, log form,
 * history) so the athlete reads the rest/climb progression vertically.
 * Timings come from deriveTryTimings — this component only formats.
 */

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function TryBreakdown({ attempts, timings }: { attempts: OutdoorAttempt[]; timings: TryTiming[] }) {
  return (
    <ul className="space-y-0.5 font-mono text-[11px] text-muted-foreground">
      {attempts.map((a, i) => {
        const sent = a.result === "sent" || a.result === "topped_out";
        const t = timings[i];
        return (
          <li key={i} className="flex items-center gap-1.5">
            <span className={sent ? "text-success" : "text-danger"} aria-hidden="true">
              {sent ? "✓" : "✗"}
            </span>
            <span className="text-foreground/80">try {i + 1}</span>
            <span aria-hidden="true">·</span>
            <span title="Rest before this try (since the previous burn on any route)">
              rest {t?.rest_before_seconds != null ? fmt(t.rest_before_seconds) : "—"}
            </span>
            {t?.climb_seconds != null && (
              <>
                <span aria-hidden="true">·</span>
                <span className="text-warning" title="Time on the wall">climb {fmt(t.climb_seconds)}</span>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
