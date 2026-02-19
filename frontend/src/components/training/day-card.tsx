"use client";

import Link from "next/link";
import { Eye, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SessionCard } from "@/components/training/session-card";
import type { DayPlan } from "@/lib/types";

interface Gym {
  name: string;
  equipment: string[];
}

interface DayCardProps {
  day: DayPlan;
  gyms?: Gym[];
  onMarkDone?: (sessionId: string) => void;
  onMarkSkipped?: (sessionId: string) => void;
  onUndo?: (sessionId: string) => void;
  onReplan?: (date: string) => void;
  showActions?: boolean;
}

/** Map English weekday name to short English abbreviation */
const WEEKDAY_EN: Record<string, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

/** Map status to badge label + variant */
const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  planned: { label: "Planned", variant: "secondary" },
  done: { label: "Completed", variant: "default" },
  skipped: { label: "Skipped", variant: "destructive" },
};

/** Check whether a date string (YYYY-MM-DD) corresponds to today */
function isToday(dateStr: string): boolean {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return dateStr === `${y}-${m}-${d}`;
}

/** Format a date string into a short readable form: "15 Feb" */
function formatDateShort(dateStr: string): string {
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const day = parseInt(parts[2], 10);
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${day} ${months[monthIdx] ?? parts[1]}`;
}

export function DayCard({
  day,
  gyms,
  onMarkDone,
  onMarkSkipped,
  onUndo,
  onReplan,
  showActions = false,
}: DayCardProps) {
  const today = isToday(day.date);
  const weekdayLabel =
    WEEKDAY_EN[day.weekday.toLowerCase()] ?? day.weekday;
  const status = day.status ?? "planned";
  const statusCfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.planned;

  return (
    <Card
      className={cn(
        "gap-3 py-4",
        today && "border-primary ring-1 ring-primary/30"
      )}
    >
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">
            {weekdayLabel}{" "}
            <span className="text-sm font-normal text-muted-foreground">
              {formatDateShort(day.date)}
            </span>
          </CardTitle>
          <Badge variant={statusCfg.variant} className="text-[10px]">
            {statusCfg.label}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-2">
        {day.sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            Rest
          </p>
        ) : (
          day.sessions.map((session) => (
            <SessionCard
              key={session.session_id}
              session={session}
              gyms={gyms}
              onMarkDone={onMarkDone ? () => onMarkDone(session.session_id) : undefined}
              onMarkSkipped={
                onMarkSkipped ? () => onMarkSkipped(session.session_id) : undefined
              }
              onUndo={onUndo ? () => onUndo(session.session_id) : undefined}
            />
          ))
        )}

        {/* Action buttons for week view */}
        {showActions && (
          <div className="flex items-center gap-2 pt-1">
            <Link href={`/today?date=${day.date}`}>
              <Button size="sm" variant="outline" className="text-xs">
                <Eye className="size-3.5 mr-1" />
                View day
              </Button>
            </Link>
            {onReplan && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => onReplan(day.date)}
              >
                <RefreshCw className="size-3.5 mr-1" />
                Change plan
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
