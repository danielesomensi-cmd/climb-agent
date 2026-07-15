"use client";

import type { WeekPlan } from "@/lib/types";
import { getPhaseName } from "@/lib/phase-labels";
import { normalizeOtherActivities } from "@/lib/other-activity";

interface WeekProgressBarProps {
  weekPlan: WeekPlan;
  /** Free sessions for the week — each should have load_score */
  freeSessions?: Array<Record<string, unknown>>;
  /** When true, free session data has finished loading */
  freeSessionsLoaded?: boolean;
}

export function WeekProgressBar({ weekPlan, freeSessions, freeSessionsLoaded = true }: WeekProgressBarProps) {
  const days = weekPlan.weeks?.[0]?.days ?? [];
  const allSessions = days.flatMap((d) => d.sessions ?? []).filter((s) => s.session_id);
  const totalSessions = allSessions.length;
  if (totalSessions === 0) return null;

  const doneSessions = allSessions.filter((s) => s.status === "done").length;
  // B164 follow-up: align with week header + report — use planned_load from summary
  const wls = weekPlan.weekly_load_summary;
  const totalLoad = wls?.planned_load ?? wls?.total_load ??
    allSessions.reduce((sum, s) => sum + (s.estimated_load_score || 0), 0);

  // Actual load: prefer session_load_score (post-resolve actual), fall back to estimated
  const doneSessionLoad = allSessions
    .filter((s) => s.status === "done")
    .reduce((sum, s) => {
      const raw = s as unknown as Record<string, unknown>;
      const actual = (raw.session_load_score as number | undefined) ?? s.estimated_load_score ?? 0;
      return sum + actual;
    }, 0);

  // Add other activity load (Yoga, running, etc.) from completed days (B276: sum per-slot list)
  const otherActivityLoad = days.reduce(
    (sum, d) => sum + normalizeOtherActivities(d).reduce((s, oa) => s + (oa.load ?? 0), 0), 0
  );

  // Add free session load (matches report_engine.py logic)
  const freeLoad = (freeSessions ?? []).reduce(
    (sum, fs) => sum + ((fs.load_score as number) || 0), 0
  );

  const doneLoad = Math.round(doneSessionLoad + otherActivityLoad + freeLoad);

  const phaseId = (weekPlan.profile_snapshot?.phase_id as string) ?? "";
  const wpDiscipline = (weekPlan.profile_snapshot?.discipline as string) ?? "lead";
  const phaseLabel = getPhaseName(phaseId, wpDiscipline as "lead" | "boulder" | "all_round");
  const weekNum = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.week_number as number | undefined;
  const totalWeeks = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.total_weeks as number | undefined;

  const pct = Math.round((doneSessions / totalSessions) * 100);
  const isDeload = phaseId === "deload";
  const allDone = doneSessions === totalSessions;

  const weekLabel = weekNum != null && totalWeeks != null
    ? `Week ${weekNum}/${totalWeeks}`
    : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm text-fg-secondary">
        <span>
          {weekLabel && <>{weekLabel} &middot; </>}
          {phaseLabel}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-surface-inset overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isDeload ? "bg-info" : "bg-brand"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-xs text-fg-muted">
        <span className="font-medium text-fg">{doneSessions}/{totalSessions}</span> sessions{allDone ? " \u2713" : ""}
        {totalLoad > 0 && (
          <>
            {" \u00B7 Load "}
            <span className={
              doneLoad > totalLoad ? "text-success font-medium"
              : doneLoad < totalLoad * 0.8 && doneSessions > 0 ? "text-warning font-medium"
              : "font-medium text-fg"
            }>
              {freeSessionsLoaded ? doneLoad : "—"}
            </span>
            {" / "}{totalLoad}
          </>
        )}
      </div>
    </div>
  );
}
