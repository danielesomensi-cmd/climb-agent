"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, Check, X, Undo2, Play, ArrowRightLeft, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExerciseCard } from "@/components/training/exercise-card";
import type { SessionSlot, GuidedSessionState, GuidedExercise } from "@/lib/types";

interface Gym {
  name: string;
  equipment: string[];
}

interface SessionCardProps {
  session: SessionSlot;
  date: string;
  gyms?: Gym[];
  onMarkDone?: () => void;
  onMarkSkipped?: () => void;
  onUndo?: () => void;
  onMove?: () => void;
  onRemove?: () => void;
}

/** Format session_id into a readable string: replace _ with spaces, capitalize */
function formatSessionName(sessionId: string): string {
  return sessionId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const FEEDBACK_BADGE_STYLE: Record<string, string> = {
  very_easy: "bg-green-500/20 text-green-400 border-green-500/30",
  easy: "bg-green-500/20 text-green-400 border-green-500/30",
  ok: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  hard: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  very_hard: "bg-red-500/20 text-red-400 border-red-500/30",
};

/** Map slot key to display label */
function formatSlot(slot: string): string {
  const slotMap: Record<string, string> = {
    morning: "Morning",
    afternoon: "Afternoon",
    evening: "Evening",
  };
  return slotMap[slot] ?? slot;
}

/** Resolve location display name — gym_id is the gym name from availability */
function getLocationLabel(session: SessionSlot, gyms?: Gym[]): string {
  if (session.location !== "gym") return "Home";
  if (session.gym_id) return session.gym_id;
  if (gyms && gyms.length > 0 && gyms[0].name) return gyms[0].name;
  return "Gym";
}

/** Build GuidedSessionState from a resolved session slot */
function buildGuidedState(
  session: SessionSlot,
  date: string,
): GuidedSessionState | null {
  const resolved = session.resolved as Record<string, unknown> | undefined;
  const resolvedSession = resolved?.resolved_session as Record<string, unknown> | undefined;
  const instances = (resolvedSession?.exercise_instances ?? []) as Array<Record<string, unknown>>;
  if (instances.length === 0) return null;

  const exercises: GuidedExercise[] = instances.map((inst) => {
    const prescription = (inst.prescription ?? {}) as Record<string, unknown>;
    const suggested = (inst.suggested ?? {}) as Record<string, unknown>;
    const boulderTarget = (suggested.suggested_boulder_target ?? {}) as Record<string, unknown>;

    return {
      exerciseId: (inst.exercise_id as string) ?? "",
      name: (inst.name as string) ?? ((inst.exercise_id as string) ?? "").replace(/_/g, " "),
      category: (inst.category as string) ?? "",
      blockUid: (inst.block_uid as string) ?? "",
      loadModel: (inst.load_model as string) ?? "",
      prescription: {
        sets: prescription.sets as number | undefined,
        reps: prescription.reps != null ? (prescription.reps as string | number) : undefined,
        workSeconds: (prescription.work_seconds ?? prescription.hang_seconds ?? prescription.duration_seconds) as number | undefined,
        restBetweenRepsSeconds: prescription.rest_between_reps_seconds as number | undefined,
        restSeconds: (prescription.rest_between_sets_seconds ?? prescription.rest_s) as number | undefined,
        loadKg: prescription.load_kg as number | undefined,
        tempo: prescription.tempo as string | undefined,
        notes: prescription.notes as string | undefined,
        intensityPct: (inst.attributes as Record<string, unknown> | undefined)?.intensity_pct as number | undefined,
      },
      suggested: {
        externalLoadKg: suggested.suggested_external_load_kg as number | undefined,
        totalLoadKg: suggested.suggested_total_load_kg as number | undefined,
        grade: (suggested.suggested_grade as string | undefined) ?? (boulderTarget.target_grade as string | undefined),
        repScheme: suggested.suggested_rep_scheme as string | undefined,
        surface: boulderTarget.surface_selected as string | undefined,
        loadSource: suggested.load_source as string | undefined,
        loadWarning: suggested.load_warning as string | undefined,
      },
      videoUrl: (inst.video_url as string | undefined) ?? undefined,
      cues: (inst.cues as string[] | undefined) ?? undefined,
      status: "pending",
      feedbackLabel: "ok",
      testField: (inst.attributes as Record<string, unknown> | undefined)?.test_field as string | undefined,
      testUnit: (inst.attributes as Record<string, unknown> | undefined)?.test_unit as string | undefined,
    };
  });

  // Extract bodyweight from resolved exercise suggested data (avoid async fetch)
  let bodyweightKg: number | undefined;
  for (const inst of instances) {
    const sug = (inst.suggested ?? {}) as Record<string, unknown>;
    // Priority 1: based_on.bodyweight_kg (from suggest_max_hang_load)
    const basedOn = sug.based_on as Record<string, number> | undefined;
    if (basedOn?.bodyweight_kg) {
      bodyweightKg = basedOn.bodyweight_kg;
      break;
    }
    // Priority 2: compute from total - external
    const total = sug.suggested_total_load_kg as number | undefined;
    const external = sug.suggested_external_load_kg as number | undefined;
    if (total != null && external != null) {
      bodyweightKg = total - external;
      break;
    }
  }

  const sessionName = (resolvedSession?.session_name as string) ??
    session.session_id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return {
    version: 1,
    date,
    sessionId: session.session_id,
    sessionName,
    startedAt: new Date().toISOString(),
    currentIndex: 0,
    exercises,
    isTestSession: session.tags?.test === true,
    bodyweightKg,
  };
}

export function SessionCard({
  session,
  date,
  gyms,
  onMarkDone,
  onMarkSkipped,
  onUndo,
  onMove,
  onRemove,
}: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const router = useRouter();

  const isHard = session.tags?.hard === true;
  const isFinger = session.tags?.finger === true;
  const isDone = session.status === "done";
  const isSkipped = session.status === "skipped";
  const isFinalized = isDone || isSkipped;
  const locationLabel = getLocationLabel(session, gyms);
  const hasExercises = (() => {
    const r = session.resolved as Record<string, unknown> | undefined;
    const rs = r?.resolved_session as Record<string, unknown> | undefined;
    return ((rs?.exercise_instances ?? []) as unknown[]).length > 0;
  })();

  return (
    <Card className="gap-0 py-0 overflow-hidden">
      {/* Header — clickable to expand */}
      <CardHeader
        className="cursor-pointer select-none py-3"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm">
            {formatSessionName(session.session_id)}
          </CardTitle>
          {expanded ? (
            <ChevronUp className="size-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
          )}
        </div>

        {/* Badge row */}
        <div className="flex flex-wrap items-center gap-1.5 mt-1">
          <Badge variant="secondary" className="text-[10px]">
            {locationLabel}
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {formatSlot(session.slot)}
          </Badge>
          {isHard && (
            <Badge className="bg-red-500 text-white text-[10px]">
              Hard
            </Badge>
          )}
          {isFinger && (
            <Badge className="bg-orange-500 text-white text-[10px]">
              Finger
            </Badge>
          )}
          {session.estimated_load_score != null && (
            <Badge variant="outline" className="text-[10px]">
              Load: {session.estimated_load_score}
            </Badge>
          )}
          {isDone && (
            <Badge className="bg-green-600 text-white text-[10px]">
              Completed
            </Badge>
          )}
          {isSkipped && (
            <Badge className="bg-yellow-500 text-white text-[10px]">
              Skipped
            </Badge>
          )}
          {isDone && session.feedback_summary && (
            <Badge
              variant="outline"
              className={`text-[10px] ${FEEDBACK_BADGE_STYLE[session.feedback_summary] ?? ""}`}
            >
              {session.feedback_summary.replace(/_/g, " ")}
            </Badge>
          )}
        </div>
      </CardHeader>

      {/* Expanded content */}
      {expanded && (
        <CardContent className="pt-0 pb-3 space-y-3">
          {/* Exercise list from resolved session */}
          {(() => {
            const instances = (
              session.resolved as Record<string, unknown> | undefined
            )?.resolved_session as Record<string, unknown> | undefined;
            const exercises = (instances?.exercise_instances ?? []) as Array<Record<string, unknown>>;
            if (exercises.length > 0) {
              return (
                <div className="space-y-1.5">
                  {exercises.map((ex, i) => {
                    const prescription = (ex.prescription ?? {}) as Record<string, unknown>;
                    const suggested = (ex.suggested ?? {}) as Record<string, unknown>;
                    const exerciseId = (ex.exercise_id as string) ?? "";
                    return (
                      <ExerciseCard
                        key={`${exerciseId}-${i}`}
                        exercise={{
                          exercise_id: exerciseId,
                          name: (ex.name as string) ?? exerciseId.replace(/_/g, " ") ?? "",
                          sets: prescription.sets as number | undefined,
                          reps: prescription.reps != null ? String(prescription.reps) : undefined,
                          load_kg: prescription.load_kg as number | undefined,
                          rest_s: (prescription.rest_between_sets_seconds ?? prescription.rest_s) as number | undefined,
                          tempo: prescription.tempo as string | undefined,
                          notes: prescription.notes as string | undefined,
                          suggested_external_load_kg: suggested.suggested_external_load_kg as number | undefined,
                          suggested_total_load_kg: suggested.suggested_total_load_kg as number | undefined,
                          load_source: suggested.load_source as string | undefined,
                        }}
                        feedbackLevel={session.exercise_feedback?.[exerciseId]}
                      />
                    );
                  })}
                </div>
              );
            }
            return (
              <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                No exercises resolved
              </div>
            );
          })()}

          {/* Action buttons — hidden for finalized sessions */}
          {!isFinalized && (
            <div className="flex flex-wrap items-center gap-1.5">
              {/* Start guided session button */}
              {hasExercises && (
                <Button
                  size="sm"
                  className="bg-primary hover:bg-primary/90 text-primary-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    const guidedState = buildGuidedState(session, date);
                    if (!guidedState) return;
                    const userId = localStorage.getItem("climb_user_id") ?? "";
                    const key = `guided_session_${userId}_${date}_${session.session_id}`;
                    localStorage.setItem(key, JSON.stringify(guidedState));
                    router.push(`/guided/${date}/${session.session_id}`);
                  }}
                >
                  <Play className="size-3.5 mr-1" />
                  Start session
                </Button>
              )}
              {onMarkDone && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-950"
                  onClick={(e) => {
                    e.stopPropagation();
                    onMarkDone();
                  }}
                >
                  <Check className="size-3.5 mr-1" />
                  Done
                </Button>
              )}
              {onMarkSkipped && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-muted-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    onMarkSkipped();
                  }}
                >
                  <X className="size-3.5 mr-1" />
                  Skip
                </Button>
              )}
              {onMove && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-muted-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    onMove();
                  }}
                >
                  <ArrowRightLeft className="size-3.5 mr-1" />
                  Move
                </Button>
              )}
              {onRemove && !confirmRemove && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-red-500 border-red-300 hover:bg-red-50 dark:hover:bg-red-950"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmRemove(true);
                  }}
                >
                  <Trash2 className="size-3.5 mr-1" />
                  Remove
                </Button>
              )}
            </div>
          )}

          {/* Remove confirmation */}
          {confirmRemove && (
            <div className="flex items-center gap-2 rounded-md border border-red-300 bg-red-50 dark:bg-red-950/30 p-2">
              <span className="text-xs text-red-600 dark:text-red-400">Remove this session?</span>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs text-muted-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmRemove(false);
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="destructive"
                className="text-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmRemove(false);
                  onRemove?.();
                }}
              >
                Remove
              </Button>
            </div>
          )}

          {/* Hint text for planned sessions with exercises */}
          {!isFinalized && hasExercises && (
            <p className="text-[11px] text-muted-foreground/60">
              Tap Start session to begin your guided workout
            </p>
          )}

          {/* Undo button — shown for finalized sessions */}
          {isFinalized && onUndo && (
            <div className="flex items-center">
              <Button
                size="sm"
                variant="ghost"
                className="text-xs text-muted-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  onUndo();
                }}
              >
                <Undo2 className="size-3.5 mr-1" />
                Undo
              </Button>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
