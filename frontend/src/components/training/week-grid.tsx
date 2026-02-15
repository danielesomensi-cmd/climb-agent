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

/** Status indicator color */
function getStatusColor(status: DayPlan["status"]): string {
  switch (status) {
    case "done":
      return "bg-green-500";
    case "skipped":
      return "bg-red-500";
    default:
      return "bg-gray-400";
  }
}

export function WeekGrid({ weekPlan, currentDate, onDayClick }: WeekGridProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Flatten: take the first week (or all if needed)
  const days: DayPlan[] =
    weekPlan.weeks.length > 0 ? weekPlan.weeks[0].days : [];

  return (
    <div className="grid grid-cols-7 gap-1.5 max-sm:grid-cols-4">
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
              "gap-1 py-2 px-2 cursor-pointer transition-colors text-center select-none",
              isToday && "ring-2 ring-primary",
              isSelected && "bg-accent",
              !isToday && !isSelected && "hover:bg-muted/50"
            )}
            onClick={() => {
              setSelectedDate(day.date);
              onDayClick?.(day.date);
            }}
          >
            {/* Day name */}
            <p
              className={cn(
                "text-xs font-medium",
                isToday && "text-primary"
              )}
            >
              {weekdayLabel}
            </p>

            {/* Compact date */}
            <p className="text-[10px] text-muted-foreground">
              {formatDateCompact(day.date)}
            </p>

            {/* Status indicator (colored dot) */}
            <div className="flex items-center justify-center gap-1 mt-1">
              <span
                className={cn(
                  "inline-block size-2 rounded-full",
                  getStatusColor(status)
                )}
              />
              {sessionCount > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  {sessionCount}
                </span>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
