"use client";

import { useState } from "react";
import { Check, Moon, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import type { WeekPlan, DayPlan } from "@/lib/types";

interface WeekGridProps {
  weekPlan: WeekPlan;
  currentDate?: string;
  onDayClick?: (date: string) => void;
  /** A294 — days carrying a key session ("lost" = skipped / downgraded). */
  keyDays?: Record<string, "key" | "lost">;
}

/** Map English weekday name to abbreviated label */
const WEEKDAY_EN: Record<string, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

/** Format date in compact form: "15/02" */
function formatDateCompact(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  return `${parts[2]}/${parts[1]}`;
}

/**
 * A308 — one bar per session, in the colour of the week's phase (same
 * --phase-* tokens as the macrocycle timeline).
 */
const PHASE_BAR: Record<string, string> = {
  base: "bg-phase-aerobic",
  strength_power: "bg-phase-anaerobic-alactic",
  power_endurance: "bg-phase-anaerobic-lactic",
  performance: "bg-phase-specific",
  deload: "bg-phase-recovery",
};

export function WeekGrid({ weekPlan, currentDate, onDayClick, keyDays }: WeekGridProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Flatten: take the first week (or all if needed)
  const days: DayPlan[] =
    weekPlan.weeks.length > 0 ? weekPlan.weeks[0].days : [];
  const phaseId = (weekPlan.profile_snapshot?.phase_id as string | undefined) ?? "";
  const barColor = PHASE_BAR[phaseId] ?? "bg-muted-foreground/50";

  // A286 — 7 colonne vere anche a 375px: prima a max-sm diventava 4+3 e la
  // settimana smetteva di leggersi come una settimana.
  return (
    <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
      {days.map((day) => {
        const isToday = currentDate === day.date;
        const isSelected = selectedDate === day.date;
        const weekdayLabel =
          WEEKDAY_EN[day.weekday.toLowerCase()] ?? day.weekday;
        const status = day.status ?? "planned";
        const sessionCount = day.sessions.length;

        return (
          <Card
            key={day.date}
            className={cn(
              "relative min-h-16 gap-0.5 py-2 px-0.5 sm:px-2 cursor-pointer transition-colors text-center select-none",
              // Il giorno corrente si distingue per anello + bordo, non solo colore.
              isToday && "ring-2 ring-primary border-primary",
              isSelected && "bg-accent",
              !isToday && !isSelected && "hover:bg-muted/50"
            )}
            onClick={() => {
              setSelectedDate(day.date);
              onDayClick?.(day.date);
            }}
          >
            {/* Day name — iniziale sotto sm, per stare in 7 colonne a 375px */}
            <p
              className={cn(
                "text-[11px] sm:text-xs font-medium leading-tight",
                isToday && "text-primary"
              )}
            >
              <span className="sm:hidden">{weekdayLabel.slice(0, 2)}</span>
              <span className="max-sm:hidden">{weekdayLabel}</span>
            </p>

            {/* Compact date */}
            <p className="text-[10px] tabular-nums leading-tight text-muted-foreground">
              <span className="sm:hidden">{day.date.split("-")[2]}</span>
              <span className="max-sm:hidden">{formatDateCompact(day.date)}</span>
            </p>

            {/* A308 — what the day holds: a bar per session (up to 2), dimmed
                when skipped, ticked when done; a moon on a rest day. Was a
                grey/green/red dot + count, the same grey for planned and rest. */}
            <div
              className="mt-1 flex flex-col items-center gap-1 px-1"
              title={`${sessionCount} session${sessionCount !== 1 ? "s" : ""} · ${status}`}
            >
              {sessionCount === 0 ? (
                <>
                  <Moon className="size-3 text-muted-foreground/60" aria-hidden="true" />
                  <span className="sr-only">Rest</span>
                </>
              ) : (
                <>
                  {day.sessions.slice(0, 2).map((s, i) => (
                    <span
                      key={`${s.session_id}-${i}`}
                      className={cn(
                        "relative flex h-1.5 w-full max-w-8 items-center justify-center rounded-full",
                        barColor,
                        s.status === "skipped" && "opacity-40",
                      )}
                    >
                      {s.status === "done" && (
                        <Check className="absolute size-3 rounded-full bg-success p-px text-surface-base" strokeWidth={3} aria-hidden="true" />
                      )}
                    </span>
                  ))}
                  {sessionCount > 2 && (
                    <span className="text-[10px] leading-none text-muted-foreground" aria-hidden="true">
                      +{sessionCount - 2}
                    </span>
                  )}
                  <span className="sr-only">
                    {sessionCount} session{sessionCount !== 1 ? "s" : ""}, {status}
                  </span>
                </>
              )}
            </div>
            {/* A294 — key session marker (red when the key was lost); A308: in
                the corner, so every cell keeps the same height. */}
            {keyDays?.[day.date] && (
              <div className="absolute right-0.5 top-0.5" title={keyDays[day.date] === "lost" ? "Key session lost" : "Key session"}>
                <Star
                  className={cn(
                    "size-3",
                    keyDays[day.date] === "lost" ? "text-danger" : "text-primary fill-primary/40",
                  )}
                  aria-label={keyDays[day.date] === "lost" ? "Key session lost" : "Key session"}
                />
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
