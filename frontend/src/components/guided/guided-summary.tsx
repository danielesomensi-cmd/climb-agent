"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, SkipForward, AlertTriangle, Send } from "lucide-react";
import { SessionTimer } from "@/components/guided/session-timer";
import type { GuidedExercise } from "@/lib/types";

interface GuidedSummaryProps {
  exercises: GuidedExercise[];
  sessionName: string;
  startedAt: string;
  onMarkRemainingOk: () => void;
  onSkipRemaining: () => void;
  onSubmit: () => void;
  submitting: boolean;
}

const FEEDBACK_STYLE: Record<string, string> = {
  very_easy: "text-green-400",
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
}: GuidedSummaryProps) {
  const pendingExercises = exercises.filter((ex) => ex.status === "pending");
  const nonWarmupPending = pendingExercises.filter(
    (ex) => !WARMUP_CATEGORIES.includes(ex.category)
  );
  const doneCount = exercises.filter((ex) => ex.status === "done").length;
  const skippedCount = exercises.filter((ex) => ex.status === "skipped").length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card className="gap-0 py-0">
        <CardHeader className="py-4">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-lg">Session complete!</CardTitle>
            <SessionTimer startedAt={startedAt} />
          </div>
          <p className="text-sm text-muted-foreground">{sessionName}</p>
        </CardHeader>

        <CardContent className="pb-4">
          {/* Summary stats */}
          <div className="flex items-center gap-3 text-sm mb-4">
            <span className="text-green-400">{doneCount} done</span>
            {skippedCount > 0 && (
              <span className="text-red-400">{skippedCount} skipped</span>
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
                    <Check className="size-4 text-green-500 shrink-0" />
                  )}
                  {ex.status === "skipped" && (
                    <SkipForward className="size-4 text-red-400 shrink-0" />
                  )}
                  {ex.status === "pending" && (
                    <div className="size-4 rounded-full border border-muted-foreground/30 shrink-0" />
                  )}
                  <span className="text-sm truncate">
                    {ex.name || ex.exerciseId.replace(/_/g, " ")}
                  </span>
                </div>
                {ex.status !== "pending" && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] shrink-0 ${FEEDBACK_STYLE[ex.feedbackLabel] ?? ""}`}
                  >
                    {ex.feedbackLabel.replace(/_/g, " ")}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pending exercises action */}
      {nonWarmupPending.length > 0 && (
        <Card className="gap-0 py-0 border-yellow-500/30">
          <CardContent className="py-4 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="size-4 text-yellow-500 mt-0.5 shrink-0" />
              <p className="text-sm">
                {nonWarmupPending.length} exercise{nonWarmupPending.length > 1 ? "s" : ""} not completed.
                Mark remaining as:
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={onMarkRemainingOk}
              >
                <Check className="size-4 mr-1" />
                OK (done)
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-muted-foreground"
                onClick={onSkipRemaining}
              >
                <SkipForward className="size-4 mr-1" />
                Skip all
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Submit button */}
      <Button
        className="w-full bg-green-600 hover:bg-green-700 text-white"
        size="lg"
        onClick={onSubmit}
        disabled={submitting}
      >
        {submitting ? (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
        ) : (
          <Send className="size-4 mr-2" />
        )}
        {submitting ? "Submitting..." : "Submit & finish"}
      </Button>
    </div>
  );
}
