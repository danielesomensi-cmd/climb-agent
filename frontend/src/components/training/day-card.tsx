"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SessionCard } from "@/components/training/session-card";
import type { DayPlan } from "@/lib/types";

interface DayCardProps {
  day: DayPlan;
  onMarkDone?: (sessionId: string) => void;
  onMarkSkipped?: (sessionId: string) => void;
}

/** Mappa nome giorno inglese a abbreviazione italiana */
const WEEKDAY_IT: Record<string, string> = {
  monday: "Lun",
  tuesday: "Mar",
  wednesday: "Mer",
  thursday: "Gio",
  friday: "Ven",
  saturday: "Sab",
  sunday: "Dom",
};

/** Mappa stato a badge italiano + variante */
const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  planned: { label: "Pianificato", variant: "secondary" },
  done: { label: "Completato", variant: "default" },
  skipped: { label: "Saltato", variant: "destructive" },
};

/** Controlla se una data (YYYY-MM-DD) corrisponde a oggi */
function isToday(dateStr: string): boolean {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return dateStr === `${y}-${m}-${d}`;
}

/** Formatta data in formato leggibile italiano: "15 feb" */
function formatDateShort(dateStr: string): string {
  const months = [
    "gen", "feb", "mar", "apr", "mag", "giu",
    "lug", "ago", "set", "ott", "nov", "dic",
  ];
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const day = parseInt(parts[2], 10);
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${day} ${months[monthIdx] ?? parts[1]}`;
}

export function DayCard({ day, onMarkDone, onMarkSkipped }: DayCardProps) {
  const today = isToday(day.date);
  const weekdayLabel =
    WEEKDAY_IT[day.weekday.toLowerCase()] ?? day.weekday;
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
            Riposo
          </p>
        ) : (
          day.sessions.map((session) => (
            <SessionCard
              key={session.session_id}
              session={session}
              onMarkDone={onMarkDone ? () => onMarkDone(session.session_id) : undefined}
              onMarkSkipped={
                onMarkSkipped ? () => onMarkSkipped(session.session_id) : undefined
              }
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
