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

/**
 * A286 — la timeline aveva una palette Tailwind parallela (con grigi da
 * light-mode) e scriveva bianco su verde saturo: 2,28:1 su font 10-12px,
 * sotto AA anche per testo large. Ora usa i token --phase-*, che erano
 * definiti in globals.css e non usati da nessun componente: colore nel testo,
 * fondo tenue dello stesso colore.
 */
const PHASE_STYLE: Record<string, string> = {
  base: "bg-phase-aerobic/20 text-phase-aerobic",
  strength_power: "bg-phase-anaerobic-alactic/20 text-phase-anaerobic-alactic",
  power_endurance: "bg-phase-anaerobic-lactic/20 text-phase-anaerobic-lactic",
  performance: "bg-phase-specific/20 text-phase-specific",
  deload: "bg-phase-recovery/20 text-phase-recovery",
};

const PHASE_STYLE_FALLBACK = "bg-muted text-muted-foreground";

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
            const phaseStyle = PHASE_STYLE[phase.phase_id] ?? PHASE_STYLE_FALLBACK;
            const label =
              getPhaseNameShort(phase.phase_id, discipline);

            return (
              <div
                key={phase.phase_id}
                className={cn(
                  "flex items-center justify-center text-[10px] sm:text-xs font-medium px-0.5 sm:px-1 leading-tight text-center",
                  // Sottile separatore fra fasi adiacenti, che ora hanno fondi tenui.
                  "border-r border-surface-base/40 last:border-r-0",
                  phaseStyle
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
                  <span className="ml-0.5 text-success" aria-label="Phase complete">
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
