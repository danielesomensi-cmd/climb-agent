"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Check, X, Undo2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExerciseCard } from "@/components/training/exercise-card";
import type { SessionSlot } from "@/lib/types";

interface Gym {
  name: string;
  equipment: string[];
}

interface SessionCardProps {
  session: SessionSlot;
  gyms?: Gym[];
  onMarkDone?: () => void;
  onMarkSkipped?: () => void;
  onUndo?: () => void;
}

/** Format session_id into a readable string: replace _ with spaces, capitalize */
function formatSessionName(sessionId: string): string {
  return sessionId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

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

export function SessionCard({
  session,
  gyms,
  onMarkDone,
  onMarkSkipped,
  onUndo,
}: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);

  const isHard = session.tags?.hard === true;
  const isFinger = session.tags?.finger === true;
  const isDone = session.status === "done";
  const isSkipped = session.status === "skipped";
  const isFinalized = isDone || isSkipped;
  const locationLabel = getLocationLabel(session, gyms);

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
                    return (
                      <ExerciseCard
                        key={`${ex.exercise_id}-${i}`}
                        exercise={{
                          exercise_id: (ex.exercise_id as string) ?? "",
                          name: (ex.name as string) ?? (ex.exercise_id as string) ?? "",
                          sets: prescription.sets as number | undefined,
                          reps: prescription.reps != null ? String(prescription.reps) : undefined,
                          load_kg: prescription.load_kg as number | undefined,
                          rest_s: prescription.rest_s as number | undefined,
                          tempo: prescription.tempo as string | undefined,
                          notes: prescription.notes as string | undefined,
                        }}
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
            <div className="flex items-center gap-2">
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
                  <Check className="size-4 mr-1" />
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
                  <X className="size-4 mr-1" />
                  Skipped
                </Button>
              )}
            </div>
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
