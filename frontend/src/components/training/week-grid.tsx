"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import type { WeekPlan, DayPlan } from "@/lib/types";

interface WeekGridProps {
  weekPlan: WeekPlan;
  currentDate?: string;
  onDayClick?: (date: string) => void;
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

/** Status indicator color (A286 — token, non più grigi da light-mode) */
function getStatusColor(status: DayPlan["status"]): string {
  switch (status) {
    case "done":
      return "bg-success";
    case "skipped":
      return "bg-danger";
    default:
      return "bg-muted-foreground/50";
  }
}

export function WeekGrid({ weekPlan, currentDate, onDayClick }: WeekGridProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Flatten: take the first week (or all if needed)
  const days: DayPlan[] =
    weekPlan.weeks.length > 0 ? weekPlan.weeks[0].days : [];

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
              "gap-0.5 py-2 px-0.5 sm:px-2 cursor-pointer transition-colors text-center select-none",
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

            {/* Status indicator (colored dot + session count) */}
            <div
              className="flex items-center justify-center gap-1 mt-0.5"
              title={`${sessionCount} session${sessionCount !== 1 ? "s" : ""} · ${status}`}
            >
              <span
                className={cn(
                  "inline-block size-2 rounded-full",
                  getStatusColor(status)
                )}
              />
              {sessionCount > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  {sessionCount}
                  <span className="sr-only"> sessions</span>
                </span>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
