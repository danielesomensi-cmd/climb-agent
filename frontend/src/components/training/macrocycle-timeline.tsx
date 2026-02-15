"use client";

import { cn } from "@/lib/utils";
import type { Macrocycle } from "@/lib/types";

interface MacrocycleTimelineProps {
  macrocycle: Macrocycle;
  currentWeek?: number;
}

/** Background color based on the phase energy_system */
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

/** Labels for phase names */
const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength",
  power_endurance: "Power End.",
  performance: "Performance",
  deload: "Deload",
};

export function MacrocycleTimeline({
  macrocycle,
  currentWeek,
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
            const bgColor = PHASE_COLORS[phase.energy_system] ?? "bg-gray-300";
            const txtColor = PHASE_TEXT[phase.energy_system] ?? "text-gray-800";
            const label =
              PHASE_LABELS[phase.energy_system] ?? phase.phase_name;

            return (
              <div
                key={phase.phase_id}
                className={cn(
                  "flex items-center justify-center text-xs font-medium truncate px-1",
                  bgColor,
                  txtColor
                )}
                style={{ width: `${widthPct}%` }}
                title={`${phase.phase_name} — ${phase.duration_weeks} wk`}
              >
                {widthPct > 10 ? label : ""}
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
            PHASE_LABELS[phase.energy_system] ?? phase.phase_name;

          return (
            <div
              key={phase.phase_id}
              className="text-center"
              style={{ width: `${widthPct}%` }}
            >
              <p className="text-[10px] font-medium text-muted-foreground truncate">
                {label}
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
          Current week: {currentWeek} / {totalWeeks}
        </p>
      )}
    </div>
  );
}
