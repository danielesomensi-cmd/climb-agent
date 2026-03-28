"use client";

import type { WeekPlan } from "@/lib/types";

const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

interface WeekProgressBarProps {
  weekPlan: WeekPlan;
  /** Free sessions for the week — each should have load_score */
  freeSessions?: Array<Record<string, unknown>>;
}

export function WeekProgressBar({ weekPlan, freeSessions }: WeekProgressBarProps) {
  const days = weekPlan.weeks?.[0]?.days ?? [];
  const allSessions = days.flatMap((d) => d.sessions ?? []).filter((s) => s.session_id);
  const totalSessions = allSessions.length;
  if (totalSessions === 0) return null;

  const doneSessions = allSessions.filter((s) => s.status === "done").length;
  const totalLoad = allSessions.reduce((sum, s) => sum + (s.estimated_load_score || 0), 0);

  // Actual load: prefer session_load_score (post-resolve actual), fall back to estimated
  const doneSessionLoad = allSessions
    .filter((s) => s.status === "done")
    .reduce((sum, s) => {
      const raw = s as unknown as Record<string, unknown>;
      const actual = (raw.session_load_score as number | undefined) ?? s.estimated_load_score ?? 0;
      return sum + actual;
    }, 0);

  // Add free session load (matches report_engine.py logic)
  const freeLoad = (freeSessions ?? []).reduce(
    (sum, fs) => sum + ((fs.load_score as number) || 0), 0
  );
  const doneLoad = Math.round(doneSessionLoad + freeLoad);

  const phaseId = (weekPlan.profile_snapshot?.phase_id as string) ?? "";
  const phaseLabel = PHASE_LABELS[phaseId] ?? phaseId;
  const weekNum = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.week_number as number | undefined;
  const totalWeeks = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.total_weeks as number | undefined;

  const pct = Math.round((doneSessions / totalSessions) * 100);
  const isDeload = phaseId === "deload";
  const allDone = doneSessions === totalSessions;

  const weekLabel = weekNum != null && totalWeeks != null
    ? `Week ${weekNum}/${totalWeeks}`
    : null;

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-sm text-slate-300">
        <span>
          {weekLabel && <>{weekLabel} &middot; </>}
          {phaseLabel}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isDeload ? "bg-blue-400" : "bg-emerald-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-xs text-slate-400">
        {doneSessions}/{totalSessions} sessions{allDone ? " \u2713" : ""}
        {totalLoad > 0 && (
          <>
            {" \u00B7 Load "}
            <span className={
              doneLoad > totalLoad ? "text-emerald-400"
              : doneLoad < totalLoad * 0.8 && doneSessions > 0 ? "text-amber-400"
              : ""
            }>
              {doneLoad}
            </span>
            {" / "}{totalLoad}
          </>
        )}
      </div>
    </div>
  );
}
