"use client";

import { cn } from "@/lib/utils";
import { getPhaseNameShort } from "@/lib/phase-labels";
import type { Macrocycle } from "@/lib/types";

interface MacrocycleTimelineProps {
  macrocycle: Macrocycle;
  currentWeek?: number;
  discipline?: "lead" | "boulder" | "all_round";
  /** A235: mark completed phases (✓) and show cycle-progress summary. */
  showProgress?: boolean;
}

/** Background color keyed on phase_id */
const PHASE_COLORS: Record<string, string> = {
  base: "bg-blue-500",
  strength_power: "bg-red-500",
  power_endurance: "bg-orange-500",
  performance: "bg-green-500",
  deload: "bg-gray-400",
};

/** Text color for bar content */
const PHASE_TEXT: Record<string, string> = {
  base: "text-white",
  strength_power: "text-white",
  power_endurance: "text-white",
  performance: "text-white",
  deload: "text-gray-700",
};

export function MacrocycleTimeline({
  macrocycle,
  currentWeek,
  discipline = "lead",
  showProgress = false,
}: MacrocycleTimelineProps) {
  const totalWeeks = macrocycle.total_weeks;

  // Calculate the cumulative start offset of each phase
  let cumulativeWeeks = 0;
  const phasesWithOffset = macrocycle.phases.map((phase) => {
    const offset = cumulativeWeeks;
    cumulativeWeeks += phase.duration_weeks;
    return { ...phase, startWeek: offset };
  });

  // Current-week marker position as a percentage
  const currentWeekPct =
    currentWeek != null ? ((currentWeek - 0.5) / totalWeeks) * 100 : null;

  return (
    <div className="w-full space-y-2">
      {/* Horizontal phase bar */}
      <div className="relative">
        <div className="flex h-10 w-full overflow-hidden rounded-lg">
          {phasesWithOffset.map((phase) => {
            const widthPct = (phase.duration_weeks / totalWeeks) * 100;
            const bgColor = PHASE_COLORS[phase.phase_id] ?? "bg-gray-300";
            const txtColor = PHASE_TEXT[phase.phase_id] ?? "text-gray-800";
            const label =
              getPhaseNameShort(phase.phase_id, discipline);

            return (
              <div
                key={phase.phase_id}
                className={cn(
                  "flex items-center justify-center text-[10px] sm:text-xs font-medium px-0.5 sm:px-1 leading-tight text-center",
                  bgColor,
                  txtColor
                )}
                style={{ width: `${widthPct}%` }}
                title={`${phase.phase_name} — ${phase.duration_weeks} wk`}
              >
                {widthPct > 8 ? label : ""}
              </div>
            );
          })}
        </div>

        {/* Current week marker */}
        {currentWeekPct != null && (
          <div
            className="absolute -bottom-3 -translate-x-1/2"
            style={{ left: `${currentWeekPct}%` }}
          >
            <div className="w-0 h-0 border-l-[5px] border-r-[5px] border-b-[6px] border-l-transparent border-r-transparent border-b-primary" />
          </div>
        )}
      </div>

      {/* Labels below the bar */}
      <div className="flex pt-2">
        {phasesWithOffset.map((phase) => {
          const widthPct = (phase.duration_weeks / totalWeeks) * 100;
          const label =
            getPhaseNameShort(phase.phase_id, discipline);
          // A235: a phase is complete once its last week is behind the
          // current week (currentWeek is 1-based and clamped upstream).
          const isComplete =
            showProgress &&
            currentWeek != null &&
            phase.startWeek + phase.duration_weeks < currentWeek;

          return (
            <div
              key={phase.phase_id}
              className="text-center"
              style={{ width: `${widthPct}%` }}
            >
              <p className="text-[10px] font-medium text-muted-foreground leading-tight break-words">
                {label}
                {isComplete && (
                  <span className="ml-0.5 text-emerald-500" aria-label="Phase complete">
                    ✓
                  </span>
                )}
              </p>
              <p className="text-[10px] text-muted-foreground">
                {phase.duration_weeks} wk
              </p>
            </div>
          );
        })}
      </div>

      {/* Current week indicator (legend) */}
      {currentWeek != null && (
        <p className="text-xs text-muted-foreground text-center mt-1">
          {showProgress ? (
            <>
              Week {currentWeek} of {totalWeeks} ·{" "}
              {Math.round(((currentWeek - 1) / totalWeeks) * 100)}% of cycle
              complete
            </>
          ) : (
            <>
              Current week: {currentWeek} / {totalWeeks}
            </>
          )}
        </p>
      )}
    </div>
  );
}
