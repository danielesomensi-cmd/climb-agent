"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMonthlyHeatmap } from "@/lib/hooks/queries";
import { cn } from "@/lib/utils";
import type { HeatmapDay } from "@/lib/types";

/**
 * A236 (A-GAMIFY-03): monthly activity heatmap, rest-positive by design
 * (docs/design_gamification.md §P2). Respected rest days get their own green
 * — we reward recovery, not just work. Skipped days stay NEUTRAL: no red, no
 * color shame. Tap a day to open it in the Today view.
 */

const MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function currentMonthISO(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return `${MONTH_LABELS[m - 1]} ${y}`;
}

/** Mon-first column index (0-6) of the month's first day. */
function firstWeekdayOffset(firstDateISO: string): number {
  const [y, m, d] = firstDateISO.split("-").map(Number);
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
}

function cellClasses(day: HeatmapDay): string {
  switch (day.status) {
    case "done":
      // Load tiers — light / medium / strong training day
      if (day.load >= 30) return "bg-emerald-400 text-emerald-950";
      if (day.load >= 15) return "bg-emerald-500/90 text-emerald-950";
      return "bg-emerald-700 text-emerald-100";
    case "rest":
      // The differentiator: respected rest gets its own positive green
      return "bg-emerald-900/40 border border-emerald-700/50 text-emerald-300";
    case "skipped":
      // Neutral — deliberately indistinguishable from "quiet", never red
      return "bg-zinc-700/40 text-zinc-400";
    case "planned":
      return "bg-zinc-700/40 border border-dashed border-zinc-500 text-zinc-300";
    case "rest_planned":
      return "bg-zinc-800/50 border border-dashed border-zinc-600/60 text-zinc-500";
    case "none":
    default:
      return "bg-zinc-800/40 text-zinc-600";
  }
}

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

export function MonthlyHeatmap() {
  const router = useRouter();
  const [month, setMonth] = useState(currentMonthISO());
  const { data } = useMonthlyHeatmap(month);
  const atCurrentMonth = month >= currentMonthISO();

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Month at a glance</CardTitle>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setMonth((m) => shiftMonth(m, -1))}
              className="flex h-8 w-8 items-center justify-center rounded-md text-zinc-400 hover:text-zinc-200"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="min-w-28 text-center text-sm text-zinc-300">
              {monthLabel(month)}
            </span>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => setMonth((m) => shiftMonth(m, 1))}
              disabled={atCurrentMonth}
              className="flex h-8 w-8 items-center justify-center rounded-md text-zinc-400 hover:text-zinc-200 disabled:opacity-30"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((w, i) => (
            <div
              key={`${w}-${i}`}
              className="text-center text-[10px] font-medium text-zinc-500"
            >
              {w}
            </div>
          ))}
          {data && (
            <>
              {Array.from({ length: firstWeekdayOffset(data.days[0].date) }).map(
                (_, i) => (
                  <div key={`pad-${i}`} />
                ),
              )}
              {data.days.map((day) => {
                const dayNum = Number(day.date.slice(-2));
                const isToday = day.date === data.today;
                return (
                  <button
                    key={day.date}
                    type="button"
                    onClick={() => router.push(`/today?date=${day.date}`)}
                    title={`${day.date} — ${day.status}${day.load ? ` · load ${day.load}` : ""}`}
                    className={cn(
                      "flex aspect-square items-center justify-center rounded-md text-[11px] transition-opacity hover:opacity-80",
                      cellClasses(day),
                      isToday && "ring-2 ring-sky-400",
                    )}
                  >
                    {dayNum}
                  </button>
                );
              })}
            </>
          )}
        </div>
        {/* Legend — rest respected is a first-class positive outcome */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500/90" /> Trained
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-sm border border-emerald-700/50 bg-emerald-900/40" />{" "}
            Rest respected
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-sm bg-zinc-700/40" /> Skipped
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-sm border border-dashed border-zinc-500 bg-zinc-700/40" />{" "}
            Planned
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
