"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { Check, SkipForward, AlertTriangle, Send, Timer } from "lucide-react";
import { formatDuration } from "@/components/guided/session-timer";
import type { GuidedExercise, SessionPain } from "@/lib/types";
import { PainPicker } from "@/components/training/measured-feedback-inputs";

interface GuidedSummaryProps {
  exercises: GuidedExercise[];
  sessionName: string;
  startedAt: string;
  onMarkRemainingOk: () => void;
  onSkipRemaining: () => void;
  onSubmit: () => void;
  submitting: boolean;
  /** A295: session pain (0-3, zone from 2). */
  pain?: SessionPain | null;
  onPainChange?: (pain: SessionPain | null) => void;
}

const FEEDBACK_STYLE: Record<string, string> = {
  very_easy: "text-emerald-300",
  easy: "text-green-400",
  ok: "text-yellow-400",
  hard: "text-orange-400",
  very_hard: "text-red-400",
};

const WARMUP_CATEGORIES = ["warmup_general", "warmup_specific"];

export function GuidedSummary({
  exercises,
  sessionName,
  startedAt,
  onMarkRemainingOk,
  onSkipRemaining,
  onSubmit,
  submitting,
  pain,
  onPainChange,
}: GuidedSummaryProps) {
  const pendingExercises = exercises.filter((ex) => ex.status === "pending");
  const nonWarmupPending = pendingExercises.filter(
    (ex) => !WARMUP_CATEGORIES.includes(ex.category)
  );
  const doneCount = exercises.filter((ex) => ex.status === "done").length;
  const skippedCount = exercises.filter((ex) => ex.status === "skipped").length;
  // A307: the session is over — show how long it took, frozen on arrival,
  // instead of a clock that keeps running while you fill the summary.
  const [duration] = useState(() =>
    formatDuration(Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000))),
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card className="gap-0 py-0">
        <CardHeader className="py-4">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-lg">
              {pendingExercises.length > 0 ? "Finish session?" : "Session complete"}
            </CardTitle>
            <span className="flex items-center gap-1 text-sm text-muted-foreground tabular-nums">
              <Timer className="size-3.5" />
              {duration}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{sessionName}</p>
        </CardHeader>

        <CardContent className="pb-4">
          {/* Summary stats */}
          <div className="flex items-center gap-3 text-sm mb-4">
            <span className="text-success">{doneCount} done</span>
            {skippedCount > 0 && (
              <span className="text-muted-foreground">{skippedCount} skipped</span>
            )}
            {pendingExercises.length > 0 && (
              <span className="text-muted-foreground">{pendingExercises.length} remaining</span>
            )}
          </div>

          {/* Exercise list */}
          <div className="space-y-1.5">
            {exercises.map((ex, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 py-1.5 border-b border-border/50 last:border-0"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {ex.status === "done" && (
                    <Check className="size-4 text-success shrink-0" />
                  )}
                  {ex.status === "skipped" && (
                    <SkipForward className="size-4 text-muted-foreground shrink-0" />
                  )}
                  {ex.status === "pending" && (
                    <div className="size-4 rounded-full border border-muted-foreground/30 shrink-0" />
                  )}
                  <span className="text-sm truncate">
                    {ex.name || ex.exerciseId.replace(/_/g, " ")}
                  </span>
                </div>
                {ex.status !== "pending" && !ex.isInstructionOnly && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] shrink-0 ${ex.feedbackLabel ? FEEDBACK_STYLE[ex.feedbackLabel] ?? "" : "text-muted-foreground"}`}
                    aria-label={ex.feedbackLabel ? undefined : "Not rated"}
                  >
                    {/* A295: not rated shows as "—", never as a fake "ok" */}
                    {ex.feedbackLabel ? ex.feedbackLabel.replace(/_/g, " ") : "—"}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pending exercises action */}
      {nonWarmupPending.length > 0 && (
        <Card className="gap-0 py-0 border-warning/30">
          <CardContent className="py-4 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="size-4 text-warning mt-0.5 shrink-0" />
              <p className="text-sm">
                {nonWarmupPending.length} exercise{nonWarmupPending.length > 1 ? "s" : ""} not completed.
                Mark remaining as done (not rated) or skip them:
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="min-h-[44px] flex-1"
                onClick={onMarkRemainingOk}
              >
                <Check className="size-4 mr-1" />
                Mark done
              </Button>
              <Button
                variant="outline"
                className="min-h-[44px] flex-1 text-muted-foreground"
                onClick={onSkipRemaining}
              >
                <SkipForward className="size-4 mr-1" />
                Skip remaining
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* A295: one "Any pain?" row for the whole session */}
      {onPainChange && (
        <Card className="gap-0 py-0">
          <CardContent className="py-4">
            <PainPicker value={pain} onChange={onPainChange} />
          </CardContent>
        </Card>
      )}

      {/* Submit button */}
      <Button
        className="w-full min-h-[52px] text-base bg-success hover:bg-success/90 text-black"
        size="lg"
        onClick={onSubmit}
        disabled={submitting}
      >
        {submitting ? (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent mr-2" />
        ) : (
          <Send className="size-4 mr-2" />
        )}
        {submitting ? "Submitting..." : "Submit & finish"}
      </Button>
    </div>
  );
}
