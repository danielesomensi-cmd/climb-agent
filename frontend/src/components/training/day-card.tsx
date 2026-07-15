"use client";

import { useState } from "react";
import Link from "next/link";
import { MapPin, Mountain, Pencil, Plus, RefreshCw, Check, Undo2, ClipboardList, X, ChevronDown, ChevronUp, Clock, Grip } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SessionCard } from "@/components/training/session-card";
import type { DayPlan, OtherActivity, OutdoorRoute, WeekPlan } from "@/lib/types";
import { normalizeOtherActivities, hasOtherActivity } from "@/lib/other-activity";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface DayCardProps {
  day: DayPlan;
  gyms?: Gym[];
  homeEquipment?: string[];
  onMarkDone?: (sessionId: string) => void;
  onMarkSkipped?: (sessionId: string) => void;
  onUndo?: (sessionId: string) => void;
  onReplan?: (date: string, sessionIndex?: number) => void;
  onQuickAdd?: (date: string) => void;
  onMoveSession?: (date: string, slot: string, sessionId: string) => void;
  onRemoveSession?: (sessionId: string) => void;
  onChangeGym?: (date: string) => void;
  onCompleteOtherActivity?: (date: string, slot: string | undefined, feedback: string, durationMinutes?: number) => void;
  onUndoOtherActivity?: (date: string, slot?: string) => void;
  onEditOtherActivity?: (date: string, slot: string | undefined, fields: { activity_name?: string; feedback?: string; duration_minutes?: number }) => void;
  onRemoveOtherActivity?: (date: string, slot?: string) => void;
  onLogOutdoor?: (date: string) => void;
  onEditOutdoor?: (date: string) => void;
  onUndoOutdoor?: (date: string) => void;
  onRemoveOutdoor?: (date: string) => void;
  outdoorRoutes?: OutdoorRoute[];
  outdoorDurationMinutes?: number;
  outdoorLoadScore?: number;
  freeSessions?: Array<{
    id: string;
    surface: string;
    gym_name?: string;
    preset_id?: string;
    session_mode?: string;
    duration_minutes?: number;
    summary?: { total_climbs: number; flashed?: number; sent?: number; attempted?: number; max_grade_sent?: string | null; max_grade_attempted?: string | null; send_rate?: number };
    overall_feel?: string;
    finished_at?: string;
    load_score?: number;
    circuit?: { work_seconds: number; rest_seconds: number; target_exercises: number; completed_exercises: number; exercises_performed: string[] };
  }>;
  onDeleteFreeSession?: (sessionId: string) => void;
  /** @deprecated No longer used — View day button removed (B166) */
  showActions?: boolean;
  weekPlan?: WeekPlan | null;
  onSessionUpdated?: (updatedWeekPlan?: WeekPlan) => void;
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

/** Human label for an activity slot. */
const SLOT_LABEL: Record<string, string> = {
  morning: "Morning",
  lunch: "Lunch",
  evening: "Evening",
};

/**
 * A single "other activity" card (B276). Holds its own complete/edit/duration
 * state so multiple activities on the same day act independently. Every action
 * carries the activity's slot so the backend targets the right item.
 */
function OtherActivityBlock({
  date,
  activity,
  onComplete,
  onUndo,
  onEdit,
  onRemove,
}: {
  date: string;
  activity: OtherActivity;
  onComplete?: (date: string, slot: string | undefined, feedback: string, durationMinutes?: number) => void;
  onUndo?: (date: string, slot?: string) => void;
  onEdit?: (date: string, slot: string | undefined, fields: { activity_name?: string; feedback?: string; duration_minutes?: number }) => void;
  onRemove?: (date: string, slot?: string) => void;
}) {
  const slot = activity.slot;
  const [feedbackPicking, setFeedbackPicking] = useState(false);
  const [otherDurationStr, setOtherDurationStr] = useState("60");
  const [editingOther, setEditingOther] = useState(false);
  const [editName, setEditName] = useState("");
  const [editFeedback, setEditFeedback] = useState("");
  const [editDuration, setEditDuration] = useState("");

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 rounded-lg border border-dashed border-amber-500/40 p-3 text-sm">
        <span className="text-amber-500">🏃</span>
        <span className="font-medium">
          {activity.name ?? "Other activity"}
        </span>
        {slot && SLOT_LABEL[slot] && (
          <Badge variant="outline" className="text-[10px] text-muted-foreground">
            {SLOT_LABEL[slot]}
          </Badge>
        )}
        {onRemove && (
          <Button
            size="icon"
            variant="ghost"
            className="ml-auto size-6 text-muted-foreground hover:text-red-400"
            onClick={() => onRemove(date, slot)}
          >
            <X className="size-3.5" />
          </Button>
        )}
      </div>
      {activity.status === "completed" ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge className="bg-green-600 text-[10px]">
            <span className="text-white">Completed</span>
            {activity.duration_minutes != null ? (
              <span className="text-white"> · {activity.duration_minutes} min</span>
            ) : (
              <span className="text-zinc-300"> · ~60 min</span>
            )}
          </Badge>
          {activity.feedback && (
            <Badge
              variant="outline"
              className={`text-[10px] ${
                activity.feedback === "easy"
                  ? "bg-green-500/20 text-green-400 border-green-500/30"
                  : activity.feedback === "ok"
                  ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                  : "bg-orange-500/20 text-orange-400 border-orange-500/30"
              }`}
            >
              {activity.feedback}
            </Badge>
          )}
          {activity.load != null && (
            <Badge variant="outline" className="text-[10px]">
              Load: {activity.load}
            </Badge>
          )}
          {onEdit && (
            <Button
              size="sm"
              variant="ghost"
              className="text-xs text-muted-foreground ml-auto"
              onClick={() => {
                setEditName(activity.name ?? "");
                setEditFeedback(activity.feedback ?? "ok");
                setEditDuration(String(activity.duration_minutes ?? "60"));
                setEditingOther(true);
              }}
            >
              <Pencil className="size-3.5 mr-1" />
              Edit
            </Button>
          )}
          {onUndo && (
            <Button
              size="sm"
              variant="ghost"
              className={`text-xs text-muted-foreground ${!onEdit ? "ml-auto" : ""}`}
              onClick={() => onUndo(date, slot)}
            >
              <Undo2 className="size-3.5 mr-1" />
              Undo completion
            </Button>
          )}
          {/* B127: Edit other activity inline form */}
          {editingOther && (
            <div className="w-full mt-2 space-y-2 rounded-lg border p-3">
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground">Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-md border bg-background px-2 py-1 text-sm"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground">Difficulty</label>
                <div className="flex gap-1.5">
                  {FEEDBACK_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`rounded-md border px-3 py-1 text-xs font-medium transition-colors ${
                        editFeedback === opt.value
                          ? opt.color + " ring-1 ring-offset-1"
                          : "border-muted text-muted-foreground"
                      } hover:opacity-80`}
                      onClick={() => setEditFeedback(opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground">Duration (min)</label>
                <input
                  type="number"
                  min={1}
                  max={600}
                  value={editDuration}
                  onChange={(e) => setEditDuration(e.target.value)}
                  className="w-20 rounded-md border bg-background px-2 py-1 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs"
                  onClick={() => setEditingOther(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="text-xs"
                  onClick={() => {
                    const dur = parseInt(editDuration, 10);
                    onEdit?.(date, slot, {
                      activity_name: editName || undefined,
                      feedback: editFeedback || undefined,
                      duration_minutes: !isNaN(dur) && dur > 0 ? dur : undefined,
                    });
                    setEditingOther(false);
                  }}
                >
                  Save
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : feedbackPicking ? (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground mr-1">How was it?</span>
            {FEEDBACK_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`rounded-md border px-3 py-1 text-xs font-medium transition-colors ${opt.color} hover:opacity-80`}
                onClick={() => {
                  const dur = parseInt(otherDurationStr, 10);
                  setFeedbackPicking(false);
                  onComplete?.(date, slot, opt.value, !isNaN(dur) && dur > 0 ? dur : undefined);
                  setOtherDurationStr("60");
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Clock className="size-3 text-muted-foreground" />
            <input
              type="number"
              min={1}
              max={600}
              value={otherDurationStr}
              onChange={(e) => setOtherDurationStr(e.target.value)}
              className="w-16 rounded-md border bg-background px-2 py-1 text-xs"
              placeholder="60"
            />
            <span className="text-[10px] text-muted-foreground">min</span>
          </div>
        </div>
      ) : onComplete ? (
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
  );
}

export function DayCard({
  day,
  gyms,
  homeEquipment,
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
  onEditOtherActivity,
  onRemoveOtherActivity,
  onLogOutdoor,
  onEditOutdoor,
  onUndoOutdoor,
  onRemoveOutdoor,
  outdoorRoutes,
  outdoorDurationMinutes,
  outdoorLoadScore,
  freeSessions,
  onDeleteFreeSession,
  showActions = false,
  weekPlan,
  onSessionUpdated,
}: DayCardProps) {
  const [confirmRemove, setConfirmRemove] = useState(false);
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
        {day.prev_other_activity_reduce && !hasOtherActivity(day) && (
          <div className="flex items-center gap-2 rounded-lg border border-dashed border-yellow-500/40 p-3 text-xs text-muted-foreground">
            <span className="text-yellow-500">⚡</span>
            Other activity yesterday — consider going easy today
          </div>
        )}

        {/* Other activity cards — one per slot (B276), shown alongside sessions */}
        {normalizeOtherActivities(day).map((activity, idx) => (
          <OtherActivityBlock
            key={activity.slot ?? `oa-${idx}`}
            date={day.date}
            activity={activity}
            onComplete={onCompleteOtherActivity}
            onUndo={onUndoOtherActivity}
            onEdit={onEditOtherActivity}
            onRemove={onRemoveOtherActivity}
          />
        ))}

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
                      <Badge className="bg-green-600 text-[10px]">
                        <span className="text-white">Completed</span>
                        {hasExpandableOutdoor && (
                          <span className="text-white"> · {outdoorRoutes!.length} {routeLabel}</span>
                        )}
                        {outdoorDurationMinutes != null && outdoorDurationMinutes > 0 ? (
                          <span className="text-white"> · {outdoorDurationMinutes} min</span>
                        ) : (
                          <span className="text-zinc-300"> · ~120 min</span>
                        )}
                      </Badge>
                      {outdoorLoadScore != null && outdoorLoadScore > 0 && (
                        <Badge variant="outline" className="text-[10px]">
                          Load: {outdoorLoadScore}
                        </Badge>
                      )}
                      {onEditOutdoor && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs text-muted-foreground ml-auto"
                          onClick={() => onEditOutdoor(day.date)}
                        >
                          <Pencil className="size-3.5 mr-1" />
                          Edit
                        </Button>
                      )}
                      {onUndoOutdoor && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className={cn("text-xs text-muted-foreground", !onEditOutdoor && "ml-auto")}
                          onClick={() => onUndoOutdoor(day.date)}
                        >
                          <Undo2 className="size-3.5 mr-1" />
                          Undo completion
                        </Button>
                      )}
                    </>
                  ) : (
                    <>
                      <Button
                        asChild
                        size="sm"
                        className="text-xs bg-green-600 hover:bg-green-700 text-white"
                      >
                        <Link href={`/outdoor/${day.date}?spot=${encodeURIComponent(day.outdoor_spot_name ?? "")}&discipline=${day.outdoor_discipline ?? "lead"}`}>
                          <Mountain className="size-3 mr-1" />
                          Open outdoor day
                        </Link>
                      </Button>
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
                      {onRemoveOutdoor && !confirmRemove && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs text-muted-foreground"
                          onClick={() => setConfirmRemove(true)}
                        >
                          <X className="size-3 mr-1" />
                          Remove
                        </Button>
                      )}
                      {onRemoveOutdoor && confirmRemove && (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Remove from plan?</span>
                          <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => setConfirmRemove(false)}>
                            Cancel
                          </Button>
                          <Button size="sm" variant="destructive" className="h-6 px-2 text-xs" onClick={() => { setConfirmRemove(false); onRemoveOutdoor(day.date); }}>
                            Remove
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                </div>
                {/* Expanded outdoor route details */}
                {outdoorExpanded && hasExpandableOutdoor && (
                  <div className="space-y-1.5 rounded-lg border border-green-500/20 bg-green-500/5 p-3">
                    {outdoorRoutes!.map((route, idx) => {
                      const hasNotes = route.attempts.some(a => a.notes);
                      return (
                        <div key={idx} className="flex items-center gap-1.5 text-xs">
                          <span className="font-mono font-medium w-10 shrink-0">{route.grade}</span>
                          <span className="truncate flex-1 text-muted-foreground">{route.name}</span>
                          <div className="flex flex-wrap items-center gap-1 justify-end">
                            {route.attempts.map((a, ai) => {
                              const isSend = a.result === "sent" || a.result === "topped_out";
                              return (
                                <span
                                  key={ai}
                                  title={isSend ? "Sent" : "Fell"}
                                  className={cn(
                                    "inline-block size-2 rounded-full",
                                    isSend ? "bg-green-500" : "bg-red-500"
                                  )}
                                />
                              );
                            })}
                          </div>
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
                  homeEquipment={homeEquipment}
                  weekPlan={weekPlan}
                  sessionIndex={idx}
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
                    onReplan && session.status !== "done" && session.status !== "skipped"
                      ? () => onReplan(day.date, idx)
                      : undefined
                  }
                  onSessionUpdated={onSessionUpdated}
                />
              ))}

            {/* Free sessions (A138) */}
            {freeSessions && freeSessions.length > 0 && freeSessions.map((fs) => {
              const surfaceName = fs.surface === "gym_boulder" ? "Gym Boulder" :
                fs.surface === "board_kilter" ? "Kilter" :
                fs.surface === "board_moonboard" ? "Moon" :
                fs.surface === "board_other" ? "Board" :
                fs.surface === "gym_routes" ? "Lead" :
                fs.surface === "circuit_core" ? "Core Circuit" : fs.surface;
              const isCircuit = typeof fs.surface === "string" && fs.surface.startsWith("circuit_");
              const presetLabel = isCircuit
                ? ""
                : fs.preset_id
                  ? fs.preset_id.replace("free_", "").replace("lead_", "").replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())
                  : "Free";
              const climbType = fs.surface === "gym_routes" ? "routes" : "boulders";
              const total = fs.summary?.total_climbs ?? 0;
              const sentCount = (fs.summary?.flashed ?? 0) + (fs.summary?.sent ?? 0);
              const triedCount = fs.summary?.attempted ?? 0;
              const maxSent = fs.summary?.max_grade_sent;
              const maxAttempted = fs.summary?.max_grade_attempted;
              const showTriedGrade = maxAttempted && maxAttempted !== maxSent;
              return (
                <div key={fs.id} className="flex items-center gap-2 rounded-lg border border-dashed border-purple-500/40 p-3 text-sm">
                  <Grip className="size-4 text-purple-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium truncate">Free: {surfaceName} {presetLabel}</span>
                      <Badge className="bg-green-600 text-[10px] shrink-0">
                        <span className="text-white">Done</span>
                      </Badge>
                      {onDeleteFreeSession && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="ml-auto size-6 text-muted-foreground hover:text-red-400 shrink-0"
                          onClick={() => {
                            if (confirm("Delete this free session?")) {
                              onDeleteFreeSession(fs.id);
                            }
                          }}
                        >
                          <X className="size-3.5" />
                        </Button>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                      <span className="text-xs text-muted-foreground">
                        {isCircuit ? (
                          <>
                            {fs.circuit?.completed_exercises ?? 0} exercises
                            {fs.duration_minutes != null && fs.duration_minutes > 0
                              ? ` · ${fs.duration_minutes} min`
                              : fs.duration_minutes === 0 ? " · < 1 min" : ""}
                            {fs.overall_feel && ` · ${fs.overall_feel.charAt(0).toUpperCase() + fs.overall_feel.slice(1)}`}
                          </>
                        ) : (
                          <>
                            {total} {climbType}
                            {sentCount > 0 && ` · ${sentCount} sent`}
                            {triedCount > 0 && ` · ${triedCount} tried`}
                            {maxSent && ` · max ${maxSent}`}
                            {showTriedGrade && ` · tried ${maxAttempted}`}
                            {fs.duration_minutes != null && fs.duration_minutes > 0
                              ? ` · ${fs.duration_minutes} min`
                              : fs.duration_minutes === 0 ? " · < 1 min" : ""}
                          </>
                        )}
                      </span>
                      {fs.load_score != null && fs.load_score > 0 && (
                        <Badge variant="outline" className="text-[10px]">
                          Load: {fs.load_score}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Add-on button: show after all sessions if any engine session is done */}
            {day.sessions.some((s) => s.status === "done") && (
              <Link
                href={`/free-session?context=add_on&date=${day.date}`}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
              >
                <Plus className="size-3" />
                Log Free Session
              </Link>
            )}

            {/* Rest — only when nothing else */}
            {!hasOtherActivity(day) && !day.outdoor_spot_name && !day.outdoor_slot && day.sessions.length === 0 && (!freeSessions || freeSessions.length === 0) && (
              <p className="text-xs text-muted-foreground italic">
                Rest
              </p>
            )}

        {/* Action buttons */}
        {(onReplan || onQuickAdd || onChangeGym) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
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
