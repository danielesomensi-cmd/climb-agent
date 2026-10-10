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

/**
 * A311 — the segment the athlete is in: stronger tint plus an inset ring in
 * the phase colour (ring-current), so "where am I" reads without the marker.
 * Literal classes — Tailwind cannot see interpolated ones.
 */
const PHASE_STYLE_CURRENT: Record<string, string> = {
  base: "bg-phase-aerobic/35 text-phase-aerobic",
  strength_power: "bg-phase-anaerobic-alactic/35 text-phase-anaerobic-alactic",
  power_endurance: "bg-phase-anaerobic-lactic/35 text-phase-anaerobic-lactic",
  performance: "bg-phase-specific/35 text-phase-specific",
  deload: "bg-phase-recovery/35 text-phase-recovery",
};

const PHASE_STYLE_CURRENT_FALLBACK = "bg-muted text-foreground";

/**
 * B355 — offset di inizio di ogni fase (prefix-sum delle durate precedenti).
 * Era un accumulatore mutato dentro `.map()`: riassegnare una variabile di
 * render viola react-hooks/immutability. Il risultato è identico — la prima
 * fase parte da 0, ciascuna dalla somma delle durate che la precedono — ma
 * senza mutazione. Esportata per poterla bloccare con un test: un off-by-one
 * qui sposterebbe tutte le fasi del macrociclo.
 */
export function phaseStartWeeks(durations: number[]): number[] {
  return durations.map((_, i) =>
    durations.slice(0, i).reduce((sum, d) => sum + d, 0),
  );
}

export function MacrocycleTimeline({
  macrocycle,
  currentWeek,
  discipline = "lead",
  showProgress = false,
}: MacrocycleTimelineProps) {
  const totalWeeks = macrocycle.total_weeks;

  // Calculate the cumulative start offset of each phase
  const startWeeks = phaseStartWeeks(
    macrocycle.phases.map((p) => p.duration_weeks),
  );
  const phasesWithOffset = macrocycle.phases.map((phase, i) => ({
    ...phase,
    startWeek: startWeeks[i],
  }));

  // Current-week marker position as a percentage
  const currentWeekPct =
    currentWeek != null ? ((currentWeek - 0.5) / totalWeeks) * 100 : null;

  // currentWeek is 1-based; phase.startWeek is the 0-based offset.
  const isCurrentPhase = (phase: { startWeek: number; duration_weeks: number }) =>
    currentWeek != null &&
    currentWeek > phase.startWeek &&
    currentWeek <= phase.startWeek + phase.duration_weeks;

  return (
    <div className={cn("w-full space-y-2", currentWeekPct != null && "pt-5")}>
      {/* Horizontal phase bar */}
      <div className="relative">
        <div className="flex h-10 w-full overflow-hidden rounded-lg">
          {phasesWithOffset.map((phase) => {
            const widthPct = (phase.duration_weeks / totalWeeks) * 100;
            const isCurrent = isCurrentPhase(phase);
            const phaseStyle = isCurrent
              ? PHASE_STYLE_CURRENT[phase.phase_id] ?? PHASE_STYLE_CURRENT_FALLBACK
              : PHASE_STYLE[phase.phase_id] ?? PHASE_STYLE_FALLBACK;
            const label =
              getPhaseNameShort(phase.phase_id, discipline);

            return (
              <div
                key={phase.phase_id}
                className={cn(
                  "flex items-center justify-center text-[10px] sm:text-xs font-medium px-0.5 sm:px-1 leading-tight text-center",
                  // Sottile separatore fra fasi adiacenti, che ora hanno fondi tenui.
                  "border-r border-surface-base/40 last:border-r-0",
                  isCurrent && "font-semibold ring-1 ring-inset ring-current",
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

        {/* A311: current week — full-height line + "Now" label (was a 5px triangle). */}
        {currentWeekPct != null && (
          <>
            <div
              className="pointer-events-none absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full bg-primary"
              style={{ left: `${currentWeekPct}%` }}
              aria-hidden="true"
            />
            <span
              className="pointer-events-none absolute -top-5 -translate-x-1/2 text-[11px] font-semibold leading-none text-primary"
              // Clamped so the label never spills past the card edge in week 1 / last week.
              style={{ left: `clamp(0.875rem, ${currentWeekPct}%, calc(100% - 0.875rem))` }}
            >
              Now
            </span>
          </>
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
          const isCurrent = isCurrentPhase(phase);

          return (
            <div
              key={phase.phase_id}
              className="text-center"
              style={{ width: `${widthPct}%` }}
            >
              <p
                className={cn(
                  "text-[10px] sm:text-xs leading-tight break-words",
                  isCurrent ? "font-semibold text-foreground" : "font-medium text-muted-foreground",
                )}
              >
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
            // A311: "Week N of M" now leads the /plan card as its hero line.
            <>
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
