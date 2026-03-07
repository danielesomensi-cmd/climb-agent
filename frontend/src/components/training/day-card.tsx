"use client";

import { useState } from "react";
import Link from "next/link";
import { Eye, MapPin, Mountain, Plus, RefreshCw, Check, Undo2, ClipboardList, X, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SessionCard } from "@/components/training/session-card";
import type { DayPlan, OutdoorRoute } from "@/lib/types";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface DayCardProps {
  day: DayPlan;
  gyms?: Gym[];
  onMarkDone?: (sessionId: string) => void;
  onMarkSkipped?: (sessionId: string) => void;
  onUndo?: (sessionId: string) => void;
  onReplan?: (date: string, sessionIndex?: number) => void;
  onQuickAdd?: (date: string) => void;
  onMoveSession?: (date: string, slot: string, sessionId: string) => void;
  onRemoveSession?: (sessionId: string) => void;
  onChangeGym?: (date: string) => void;
  onCompleteOtherActivity?: (date: string, feedback: string) => void;
  onUndoOtherActivity?: (date: string) => void;
  onLogOutdoor?: (date: string) => void;
  onUndoOutdoor?: (date: string) => void;
  onRemoveOutdoor?: (date: string) => void;
  outdoorRoutes?: OutdoorRoute[];
  showActions?: boolean;
}

const FEEDBACK_OPTIONS = [
  { value: "easy", label: "Easy", color: "text-green-400 border-green-500/30 bg-green-500/20" },
  { value: "ok", label: "OK", color: "text-yellow-400 border-yellow-500/30 bg-yellow-500/20" },
  { value: "hard", label: "Hard", color: "text-orange-400 border-orange-500/30 bg-orange-500/20" },
];

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

/** Ordered grade list for determining max grade */
const GRADE_ORDER = [
  "4", "4+", "4a", "4b", "4c",
  "5", "5+", "5a", "5a+", "5b", "5b+", "5c", "5c+",
  "6a", "6a+", "6b", "6b+", "6c", "6c+",
  "7a", "7a+", "7b", "7b+", "7c", "7c+",
  "8a", "8a+", "8b", "8b+", "8c", "8c+",
  "9a", "9a+",
];

/** Style badge mapping for outdoor routes */
const STYLE_BADGE: Record<string, { emoji: string; label: string }> = {
  onsight: { emoji: "🟢", label: "Onsight" },
  flash: { emoji: "🟡", label: "Flash" },
  redpoint: { emoji: "🔴", label: "Redpoint" },
  project: { emoji: "⚪", label: "Project" },
  repeat: { emoji: "🔵", label: "Repeat" },
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
  onQuickAdd,
  onMoveSession,
  onRemoveSession,
  onChangeGym,
  onCompleteOtherActivity,
  onUndoOtherActivity,
  onLogOutdoor,
  onUndoOutdoor,
  onRemoveOutdoor,
  outdoorRoutes,
  showActions = false,
}: DayCardProps) {
  const [feedbackPicking, setFeedbackPicking] = useState(false);
  const [outdoorExpanded, setOutdoorExpanded] = useState(false);
  const today = isToday(day.date);
  const weekdayLabel =
    WEEKDAY_EN[day.weekday.toLowerCase()] ?? day.weekday;
  const status = day.status ?? "planned";
  const statusCfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.planned;
  const hasExpandableOutdoor = day.outdoor_session_status === "done" && (outdoorRoutes?.length ?? 0) > 0;
  const routeLabel = day.outdoor_discipline === "boulder" ? "problems" : "routes";

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
        {day.prev_other_activity_reduce && !day.other_activity && (
          <div className="flex items-center gap-2 rounded-lg border border-dashed border-yellow-500/40 p-3 text-xs text-muted-foreground">
            <span className="text-yellow-500">⚡</span>
            Other activity yesterday — consider going easy today
          </div>
        )}

        {/* Other activity card — shown alongside sessions, not exclusively */}
        {day.other_activity && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 rounded-lg border border-dashed border-amber-500/40 p-3 text-sm">
              <span className="text-amber-500">🏃</span>
              <span className="font-medium">
                {day.other_activity_name ?? "Other activity"}
              </span>
            </div>
            {day.other_activity_status === "completed" ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge className="bg-green-600 text-white text-[10px]">Completed</Badge>
                {day.other_activity_feedback && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      day.other_activity_feedback === "easy"
                        ? "bg-green-500/20 text-green-400 border-green-500/30"
                        : day.other_activity_feedback === "ok"
                        ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                        : "bg-orange-500/20 text-orange-400 border-orange-500/30"
                    }`}
                  >
                    {day.other_activity_feedback}
                  </Badge>
                )}
                {day.other_activity_load != null && (
                  <Badge variant="outline" className="text-[10px]">
                    Load: {day.other_activity_load}
                  </Badge>
                )}
                {onUndoOtherActivity && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs text-muted-foreground ml-auto"
                    onClick={() => onUndoOtherActivity(day.date)}
                  >
                    <Undo2 className="size-3.5 mr-1" />
                    Undo
                  </Button>
                )}
              </div>
            ) : feedbackPicking ? (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground mr-1">How was it?</span>
                {FEEDBACK_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`rounded-md border px-3 py-1 text-xs font-medium transition-colors ${opt.color} hover:opacity-80`}
                    onClick={() => {
                      setFeedbackPicking(false);
                      onCompleteOtherActivity?.(day.date, opt.value);
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : onCompleteOtherActivity ? (
              <Button
                size="sm"
                variant="outline"
                className="text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-950"
                onClick={() => setFeedbackPicking(true)}
              >
                <Check className="size-3.5 mr-1" />
                Complete
              </Button>
            ) : null}
          </div>
        )}

            {/* Outdoor session card — when spot is set */}
            {day.outdoor_spot_name && (
              <div className="space-y-2">
                <div
                  className={cn(
                    "flex items-center gap-2 rounded-lg border border-dashed border-green-500/40 p-3 text-sm",
                    hasExpandableOutdoor && "cursor-pointer"
                  )}
                  onClick={hasExpandableOutdoor ? () => setOutdoorExpanded(v => !v) : undefined}
                >
                  <Mountain className="size-4 text-green-500" />
                  <span className="font-medium">{day.outdoor_spot_name}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {day.outdoor_discipline ?? "outdoor"}
                  </Badge>
                  {hasExpandableOutdoor && (
                    outdoorExpanded
                      ? <ChevronUp className="size-4 text-muted-foreground ml-auto" />
                      : <ChevronDown className="size-4 text-muted-foreground ml-auto" />
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {day.outdoor_session_status === "done" ? (
                    <>
                      <Badge className="bg-green-600 text-white text-[10px]">Completed</Badge>
                      {hasExpandableOutdoor && (
                        <span className="text-[10px] text-muted-foreground">
                          {outdoorRoutes!.length} {routeLabel}
                        </span>
                      )}
                      {onUndoOutdoor && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs text-muted-foreground ml-auto"
                          onClick={() => onUndoOutdoor(day.date)}
                        >
                          <Undo2 className="size-3.5 mr-1" />
                          Undo
                        </Button>
                      )}
                    </>
                  ) : (
                    <>
                      {onLogOutdoor && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-950"
                          onClick={() => onLogOutdoor(day.date)}
                        >
                          <ClipboardList className="size-3 mr-1" />
                          Log routes
                        </Button>
                      )}
                      {onRemoveOutdoor && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs text-muted-foreground"
                          onClick={() => onRemoveOutdoor(day.date)}
                        >
                          <X className="size-3 mr-1" />
                          Remove
                        </Button>
                      )}
                    </>
                  )}
                </div>
                {/* Expanded outdoor route details */}
                {outdoorExpanded && hasExpandableOutdoor && (
                  <div className="space-y-1.5 rounded-lg border border-green-500/20 bg-green-500/5 p-3">
                    {outdoorRoutes!.map((route, idx) => {
                      const style = route.style || (route.attempts.some(a => a.result === "sent") ? "redpoint" : "project");
                      const badge = STYLE_BADGE[style];
                      const totalAttempts = route.attempts.length;
                      const hasNotes = route.attempts.some(a => a.notes);
                      return (
                        <div key={idx} className="flex items-center gap-1.5 text-xs">
                          <span className="font-mono font-medium w-10 shrink-0">{route.grade}</span>
                          <span className="truncate flex-1 text-muted-foreground">{route.name}</span>
                          {badge && <span title={badge.label}>{badge.emoji}</span>}
                          {totalAttempts > 1 && <span className="text-muted-foreground">×{totalAttempts}</span>}
                          {hasNotes && (
                            <span title={route.attempts.filter(a => a.notes).map(a => a.notes).join("; ")}>💬</span>
                          )}
                        </div>
                      );
                    })}
                    <div className="text-[10px] text-muted-foreground pt-1.5 mt-1 border-t border-green-500/20">
                      {outdoorRoutes!.length} {routeLabel}
                      {(() => {
                        const maxR = outdoorRoutes!.reduce((best, r) => {
                          const rank = GRADE_ORDER.indexOf(r.grade);
                          return rank > best.rank ? { grade: r.grade, rank } : best;
                        }, { grade: "", rank: -1 });
                        return maxR.grade ? ` · max ${maxR.grade}` : "";
                      })()}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Outdoor slot placeholder — planner-generated, no details yet */}
            {!day.outdoor_spot_name && day.outdoor_slot && (
              <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-sm">
                <Mountain className="size-4 text-green-500" />
                <span className="font-medium">Outdoor day</span>
                <span className="text-xs text-muted-foreground">
                  Tap &quot;Add session&quot; to set your spot
                </span>
              </div>
            )}

            {/* Regular sessions */}
            {day.sessions.length > 0 &&
              day.sessions.map((session, idx) => (
                <SessionCard
                  key={`${session.session_id}-${idx}`}
                  session={session}
                  date={day.date}
                  gyms={gyms}
                  onMarkDone={onMarkDone ? () => onMarkDone(session.session_id) : undefined}
                  onMarkSkipped={
                    onMarkSkipped ? () => onMarkSkipped(session.session_id) : undefined
                  }
                  onUndo={onUndo ? () => onUndo(session.session_id) : undefined}
                  onMove={
                    onMoveSession && session.status !== "done" && session.status !== "skipped"
                      ? () => onMoveSession(day.date, session.slot, session.session_id)
                      : undefined
                  }
                  onRemove={
                    onRemoveSession && session.status !== "done" && session.status !== "skipped"
                      ? () => onRemoveSession(session.session_id)
                      : undefined
                  }
                  onReplan={
                    onReplan && day.sessions.length > 1 && session.status !== "done" && session.status !== "skipped"
                      ? () => onReplan(day.date, idx)
                      : undefined
                  }
                />
              ))}

            {/* Rest — only when nothing else */}
            {!day.other_activity && !day.outdoor_spot_name && !day.outdoor_slot && day.sessions.length === 0 && (
              <p className="text-xs text-muted-foreground italic">
                Rest
              </p>
            )}

        {/* Action buttons */}
        {(showActions || onReplan || onQuickAdd || onChangeGym) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {showActions && (
              <Link href={`/today?date=${day.date}`}>
                <Button size="sm" variant="outline" className="text-xs px-2 py-1">
                  <Eye className="size-3 mr-1" />
                  View day
                </Button>
              </Link>
            )}
            {onReplan && day.sessions.length <= 1 && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs px-2 py-1"
                onClick={() => onReplan(day.date)}
              >
                <RefreshCw className="size-3 mr-1" />
                Change plan
              </Button>
            )}
            {onQuickAdd && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs px-2 py-1"
                onClick={() => onQuickAdd(day.date)}
              >
                <Plus className="size-3 mr-1" />
                Add session
              </Button>
            )}
            {onChangeGym && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs px-2 py-1"
                onClick={() => onChangeGym(day.date)}
              >
                <MapPin className="size-3 mr-1" />
                Change location
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
