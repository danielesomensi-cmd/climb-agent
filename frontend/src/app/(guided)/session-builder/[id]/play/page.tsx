"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trophy } from "lucide-react";
import { SoundToggle } from "@/components/guided/sound-toggle";
import { Button } from "@/components/ui/button";
import { useCustomSession, useBuilderExercises } from "@/lib/hooks/queries";
import { useWakeLock } from "@/lib/hooks/use-wake-lock";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { queryKeys } from "@/lib/query-keys";
import { applyEvents, postFeedback } from "@/lib/api";
import type { WeekPlan, CustomSessionExercise } from "@/lib/types";
import { CustomExerciseStep } from "@/components/session-play/custom-exercise-step";
import { CustomRestTimer } from "@/components/session-play/custom-rest-timer";
import { displaySetNumber, sideForSet, totalSetsWithSides } from "@/lib/alt-sides";
import { unlockAudio } from "@/lib/audio-unlock";
import { FeedbackPills } from "@/components/guided/feedback-pills";
import { measureFields, withFeedbackContract, type MeasureValues } from "@/lib/measured-feedback";
import type { LimitProblemDraft, SessionPain } from "@/lib/types";
import { MeasureInput, PainPicker } from "@/components/training/measured-feedback-inputs";
import { LadderBadge } from "@/components/training/ladder-badge";
import { LimitProblemLogger } from "@/components/training/limit-problem-logger";
import { limitFeedbackFields, limitTargetFor } from "@/lib/limit-problems";

type Stage = "idle" | "exercise_active" | "resting" | "completed";

type CachedWeek = { week_num: number; phase_id?: string | null; week_plan: WeekPlan };

// A240: perceived-effort options mirror the guided player's feedback labels
// (guided-exercise-step.tsx) — reused verbatim so custom logging feeds the same
// exercise_feedback_v1 shape the engine's apply_feedback already consumes.

/**
 * A240: per-exercise capture on the completion screen. Collects perceived
 * effort (feedback_label) and an optional used load (kg). Sets completed are
 * tracked by the parent during playback. This is off-plan support work — the
 * data feeds working_loads but never the macrocycle closed-loop.
 */
function ExerciseFeedbackCard({
  name,
  prescriptionSummary,
  setsCompleted,
  totalSets,
  altSides,
  feedbackLabel,
  loadKg,
  showLoadInput,
  onFeedbackChange,
  onLoadChange,
  exercise,
  measures,
  onMeasuresChange,
  problems,
  onProblemsChange,
  surface,
  onSurfaceChange,
  customSessionId,
  date,
}: {
  name: string;
  prescriptionSummary: string;
  setsCompleted: number;
  totalSets: number;
  altSides?: boolean;
  /** A295: undefined = not rated (nothing pre-selected). */
  feedbackLabel: string | undefined;
  loadKg: string;
  showLoadInput: boolean;
  onFeedbackChange: (label: string | undefined) => void;
  onLoadChange: (kg: string) => void;
  exercise: CustomSessionExercise;
  measures: MeasureValues;
  onMeasuresChange: (patch: MeasureValues) => void;
  /** A296: limit problem log (limit-boulder family read with ?date=). */
  problems: LimitProblemDraft[];
  onProblemsChange: (problems: LimitProblemDraft[]) => void;
  /** A296 (review): the wall the athlete says he is on (null = server default). */
  surface: string | null;
  onSurfaceChange: (surface: string) => void;
  /** A298: the session the promotion tap rewrites, and the day played. */
  customSessionId?: string;
  date?: string;
}) {
  const limit = limitTargetFor(exercise, surface);
  return (
    <div className="rounded-lg border bg-muted/20 p-3 space-y-3 text-left">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium truncate">{name}</p>
        <span className="text-[11px] text-muted-foreground tabular-nums shrink-0">
          {setsCompleted}/{totalSets} sets{altSides ? " (R+L)" : ""}
        </span>
      </div>
      {prescriptionSummary && (
        <p className="text-[11px] text-muted-foreground -mt-1">{prescriptionSummary}</p>
      )}
      {/* A298: ladder level + promotion proposal (custom 'ladder' rows) */}
      <LadderBadge ladder={exercise.ladder} customSessionId={customSessionId} date={date} compact />
      {/* A307: same 44px pills as the guided player */}
      <FeedbackPills value={feedbackLabel} onChange={(v) => onFeedbackChange(v ?? undefined)} />
      {/* A295: optional measure (last-set reps / hang margin) */}
      {exercise.measure && (
        <MeasureInput
          id={`${exercise.exercise_id}-measure`}
          measure={exercise.measure}
          prescribedReps={exercise.reps ?? undefined}
          targetReps={exercise.target_reps}
          lastSetReps={measures.lastSetReps}
          hangMargin={measures.hangMargin}
          onLastSetReps={(v) => onMeasuresChange({ lastSetReps: v })}
          onHangMargin={(v) => onMeasuresChange({ hangMargin: v })}
        />
      )}
      {exercise.log_problems && (
        <LimitProblemLogger
          idPrefix={exercise.exercise_id}
          target={limit.target}
          targetLow={limit.targetLow}
          problems={problems}
          onChange={onProblemsChange}
          surfaceOptions={exercise.surface_options}
          surface={limit.surface}
          onSurfaceChange={onSurfaceChange}
        />
      )}
      {showLoadInput && !exercise.log_problems && (
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="shrink-0">Used load</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step={0.5}
            value={loadKg}
            onChange={(e) => onLoadChange(e.target.value)}
            placeholder="optional"
            className="h-11 w-full max-w-[10rem] rounded-md border bg-background px-3 text-lg text-foreground tabular-nums"
          />
          <span className="shrink-0">kg</span>
        </label>
      )}
    </div>
  );
}

function formatExerciseName(id: string, catalogMap: Map<string, string>): string {
  return (
    catalogMap.get(id) ??
    id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function exercisePrescriptionSummary(ex: CustomSessionExercise): string {
  const parts: string[] = [];
  const sets = ex.sets ?? 1;
  // B324: make the laterality visible in the summary \u2014 "3\u00d720s per side".
  const perSide = ex.alt_sides ? " per side" : "";
  if (ex.reps != null && ex.reps > 0) parts.push(`${sets}\u00d7${ex.reps}${perSide}`);
  else if (ex.work_seconds != null && ex.work_seconds > 0) parts.push(`${sets}\u00d7${ex.work_seconds}s${perSide}`);
  else parts.push(`${sets} sets${perSide}`);
  if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null && ex.rest_between_sets_seconds > 0) {
    parts.push(`rest ${ex.rest_between_sets_seconds}s`);
  }
  return parts.join(" \u00b7 ");
}

/**
 * Scan cached weeks for the one containing this custom session on the given
 * date. We don't thread `weekNum` through session-card — the cache already has
 * whatever week the user was looking at when they tapped Start.
 */
function findWeekForCustomSession(
  qc: ReturnType<typeof useQueryClient>,
  customSessionId: string,
  date: string,
): { weekNum: number; weekPlan: WeekPlan } | null {
  const sessionRef = `custom_${customSessionId}`;
  for (let w = 0; w < 14; w++) {
    const cached = qc.getQueryData<CachedWeek>(queryKeys.week(w));
    const weekPlan = cached?.week_plan;
    if (!weekPlan) continue;
    for (const weekObj of weekPlan.weeks ?? []) {
      for (const day of weekObj.days ?? []) {
        if (day.date !== date) continue;
        for (const s of day.sessions ?? []) {
          if (s.session_id === sessionRef || s.custom_session_id === customSessionId) {
            return { weekNum: w, weekPlan };
          }
        }
      }
    }
  }
  return null;
}

export default function SessionPlayPage() {
  const params = useParams();
  const router = useRouter();
  const search = useSearchParams();
  const qc = useQueryClient();
  const id = params.id as string;
  const date = search.get("date") ?? "";

  const { canInteract, loading: subLoading } = useSubscription();
  useEffect(() => {
    if (!subLoading && !canInteract) router.replace("/subscribe");
  }, [canInteract, subLoading, router]);

  // B364: the loads of the day being played (anchored exercises follow the
  // official max + working load on that date, like the planned sessions).
  const { data: session, isLoading, error: fetchError } = useCustomSession(id, date);
  const { data: catalogData } = useBuilderExercises("", "");

  const catalogNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const ex of catalogData?.exercises ?? []) {
      map.set(ex.id, ex.name);
    }
    return map;
  }, [catalogData]);

  const [stage, setStage] = useState<Stage>("idle");
  const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);
  const [currentSet, setCurrentSet] = useState(1);
  const startedAtRef = useRef<number>(0);
  const [durationSec, setDurationSec] = useState(0);
  const [setsCompleted, setSetsCompleted] = useState(0);
  // A240: per-exercise capture (keyed by exercise index).
  const [setsByIndex, setSetsByIndex] = useState<Record<number, number>>({});
  const [feedbackByIndex, setFeedbackByIndex] = useState<Record<number, string>>({});
  const [kgByIndex, setKgByIndex] = useState<Record<number, string>>({});
  // A295: optional measures per exercise + session pain (nothing pre-selected).
  const [measuresByIndex, setMeasuresByIndex] = useState<Record<number, MeasureValues>>({});
  // A296: limit problem log per exercise (limit-boulder family).
  const [problemsByIndex, setProblemsByIndex] = useState<Record<number, LimitProblemDraft[]>>({});
  // A296 (review): a custom session has no gym — the athlete picks the wall.
  const [surfaceByIndex, setSurfaceByIndex] = useState<Record<number, string>>({});
  const [pain, setPain] = useState<SessionPain | null>(null);
  useEffect(() => {
    if (startedAtRef.current === 0) startedAtRef.current = Date.now();
  }, []);

  const completeSession = useCallback(() => {
    if (startedAtRef.current > 0) {
      setDurationSec(Math.floor((Date.now() - startedAtRef.current) / 1000));
    }
    setStage("completed");
  }, []);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmBack, setConfirmBack] = useState(false);

  // Keep screen awake during active playback (not idle, not completed).
  useWakeLock(stage === "exercise_active" || stage === "resting");

  // Audio unlock on first touch anywhere on page (iOS gesture gate).
  useEffect(() => {
    const onTouch = () => {
      unlockAudio();
      window.removeEventListener("touchstart", onTouch);
    };
    window.addEventListener("touchstart", onTouch, { once: true });
    return () => window.removeEventListener("touchstart", onTouch);
  }, []);

  const exercises = useMemo(() => session?.exercises ?? [], [session]);
  const currentExercise: CustomSessionExercise | undefined = exercises[currentExerciseIndex];
  const nextExercise: CustomSessionExercise | undefined = exercises[currentExerciseIndex + 1];

  const backDestination = date ? `/today?date=${date}` : "/today";

  const handleBack = useCallback(() => {
    if (stage === "idle" || stage === "completed") {
      router.push(backDestination);
      return;
    }
    if (confirmBack) {
      router.push(backDestination);
    } else {
      setConfirmBack(true);
      setTimeout(() => setConfirmBack(false), 3000);
    }
  }, [router, stage, confirmBack, backDestination]);

  const handleBeginSession = useCallback(async () => {
    await unlockAudio();
    setStage("exercise_active");
  }, []);

  /** Called when the current set finishes (timer hit zero OR user tapped Done for reps). */
  const handleSetDone = useCallback(() => {
    if (!currentExercise) return;
    setSetsCompleted((n) => n + 1);
    // A240: track sets completed per exercise for the completion-screen log.
    setSetsByIndex((prev) => ({
      ...prev,
      [currentExerciseIndex]: (prev[currentExerciseIndex] ?? 0) + 1,
    }));

    // B324: alt_sides → one internal set per side, so 3 prescribed sets run as 6.
    const totalSets = totalSetsWithSides(currentExercise.sets, currentExercise.alt_sides === true);
    const restSec = currentExercise.rest_between_sets_seconds ?? 0;
    const hasMoreSetsInExercise = currentSet < totalSets;
    const hasNextExercise = currentExerciseIndex < exercises.length - 1;

    if (hasMoreSetsInExercise) {
      if (restSec > 0) {
        setStage("resting");
      } else {
        setCurrentSet((s) => s + 1);
        // Stay in exercise_active — next set starts fresh via key prop
      }
      return;
    }

    // End of exercise
    if (hasNextExercise) {
      if (restSec > 0) {
        setStage("resting");
      } else {
        setCurrentExerciseIndex((i) => i + 1);
        setCurrentSet(1);
      }
      return;
    }

    // End of session
    completeSession();
  }, [currentExercise, currentSet, currentExerciseIndex, exercises.length, completeSession]);

  /** B281: skip the CURRENT exercise entirely (all remaining sets). Never trap
   * the user — long timed drills made sessions feel broken without this. */
  const handleSkipExercise = useCallback(() => {
    if (currentExerciseIndex < exercises.length - 1) {
      setCurrentExerciseIndex((i) => i + 1);
      setCurrentSet(1);
      setStage("exercise_active");
      return;
    }
    completeSession();
  }, [currentExerciseIndex, exercises.length, completeSession]);

  /** Called when rest timer reaches target + user taps Start next, or skips early. */
  const handleRestDone = useCallback(() => {
    if (!currentExercise) return;
    const totalSets = totalSetsWithSides(currentExercise.sets, currentExercise.alt_sides === true);
    if (currentSet < totalSets) {
      setCurrentSet((s) => s + 1);
      setStage("exercise_active");
      return;
    }
    if (currentExerciseIndex < exercises.length - 1) {
      setCurrentExerciseIndex((i) => i + 1);
      setCurrentSet(1);
      setStage("exercise_active");
      return;
    }
    completeSession();
  }, [currentExercise, currentSet, currentExerciseIndex, exercises.length, completeSession]);

  const handleFinish = useCallback(async () => {
    if (!session) return;
    if (!date) {
      setError("Session date is missing — return to Today and retry.");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const found = findWeekForCustomSession(qc, id, date);
      if (!found) {
        setError("Could not locate this session in the cached week plan. Return to Today and try again.");
        setSubmitting(false);
        return;
      }

      const result = await applyEvents({
        events: [
          {
            event_type: "mark_done",
            date,
            session_ref: `custom_${id}`,
          },
        ],
        week_plan: found.weekPlan,
      });

      qc.setQueryData<CachedWeek>(queryKeys.week(found.weekNum), (old) =>
        old ? { ...old, week_plan: result.week_plan } : { week_num: found.weekNum, week_plan: result.week_plan },
      );

      // A240: log per-exercise feedback so custom sessions build working_loads
      // memory. resolved_day is intentionally OMITTED — the backend closed-loop
      // gate skips on absent resolved_day, and the _is_custom_session guard is a
      // second server-side barrier. This is off-plan support work: it must
      // never feed macrocycle progression (stimulus_recency / fatigue_proxy).
      const durationSeconds =
        durationSec > 0
          ? durationSec
          : startedAtRef.current > 0
            ? Math.max(0, Math.floor((Date.now() - startedAtRef.current) / 1000))
            : 0;
      const exerciseFeedback = exercises.map((ex, i) => {
        // A295: the label only when picked — untouched = not rated.
        const item: Record<string, unknown> = {
          exercise_id: ex.exercise_id,
          completed: true,
        };
        if (feedbackByIndex[i]) item.feedback_label = feedbackByIndex[i];
        Object.assign(
          item,
          measureFields(ex.measure, { targetReps: ex.target_reps, ...(measuresByIndex[i] ?? {}) }),
        );
        const rawKg = kgByIndex[i] ?? (ex.load_kg > 0 ? String(ex.load_kg) : "");
        const kg = parseFloat(rawKg);
        if (!Number.isNaN(kg) && kg > 0) item.used_external_load_kg = kg;
        const sets = setsByIndex[i];
        if (sets != null) item.completed_sets = sets;
        if (ex.log_problems) {
          // A296: the limit is logged problem by problem; without problems the
          // day's target travels as the grade used (same as the guided player).
          const limit = limitTargetFor(ex, surfaceByIndex[i]);
          Object.assign(item, limitFeedbackFields(problemsByIndex[i], limit.target));
          if (limit.surface) item.surface_selected = limit.surface;
          delete item.used_external_load_kg;
        }
        return item;
      });
      await postFeedback({
        log_entry: withFeedbackContract({
          date,
          session_id: `custom_${id}`,
          // Real wall-clock start (ms ref → ISO) for the health-vault export.
          ...(startedAtRef.current > 0
            ? { started_at: new Date(startedAtRef.current).toISOString() }
            : {}),
          session_duration_seconds: durationSeconds,
          actual: { exercise_feedback_v1: exerciseFeedback },
        }, pain),
        status: "done",
      });

      // Refresh working_loads (state) and the week cache (actual_exercises).
      qc.invalidateQueries({ queryKey: queryKeys.state });
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });

      router.push(backDestination);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the session.");
      setSubmitting(false);
    }
  }, [
    session,
    date,
    id,
    qc,
    router,
    backDestination,
    exercises,
    durationSec,
    feedbackByIndex,
    kgByIndex,
    setsByIndex,
    measuresByIndex,
    problemsByIndex,
    surfaceByIndex,
    pain,
  ]);

  // --- Render ---

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!session || fetchError) {
    return (
      <div className="mx-auto max-w-2xl p-4 space-y-3">
        <p className="text-sm text-muted-foreground">Session not found.</p>
        <Button variant="outline" onClick={() => router.push(backDestination)}>
          Back to Today
        </Button>
      </div>
    );
  }

  if (exercises.length === 0) {
    return (
      <div className="mx-auto max-w-2xl p-4 space-y-3">
        <p className="text-sm text-muted-foreground">This session has no exercises.</p>
        <Button variant="outline" onClick={() => router.push(backDestination)}>
          Back to Today
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleBack}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            {confirmBack ? "Tap again to leave" : "Back"}
          </button>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-medium px-2 py-0.5 rounded border border-primary/40 bg-primary/10 text-primary uppercase tracking-wider">
              Custom
            </span>
            <SoundToggle />
          </div>
        </div>
        <p className="text-base font-semibold truncate">{session.name}</p>
        {stage !== "completed" && currentExercise && (
          <p className="text-xs text-muted-foreground">
            Exercise {currentExerciseIndex + 1} of {exercises.length}
            {stage === "exercise_active" && (
              <>
                {" "}
                · Set {displaySetNumber(currentSet, currentExercise.alt_sides === true)} of{" "}
                {currentExercise.sets ?? 1}
                {sideForSet(currentSet, currentExercise.alt_sides === true) && (
                  <> · {sideForSet(currentSet, currentExercise.alt_sides === true)}</>
                )}
              </>
            )}
            {stage === "resting" && <> · Resting</>}
          </p>
        )}
      </header>

      <main className="flex-1 px-4 pb-8">
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-center text-sm text-destructive mt-3">
            {error}
          </div>
        )}

        {stage === "idle" && currentExercise && (
          <div className="py-12 text-center space-y-6">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                First exercise
              </p>
              <h2 className="text-2xl font-semibold">
                {formatExerciseName(currentExercise.exercise_id, catalogNameMap)}
              </h2>
              <p className="text-sm text-muted-foreground">
                {exercisePrescriptionSummary(currentExercise)}
              </p>
              {currentExercise.notes && (
                <p className="text-xs text-muted-foreground italic max-w-md mx-auto pt-1">
                  {currentExercise.notes}
                </p>
              )}
            </div>
            <Button size="lg" onClick={handleBeginSession} className="min-w-[200px]">
              Start first exercise
            </Button>
            <p className="text-[11px] text-muted-foreground">
              {exercises.length} exercises · ~{session.estimated_duration_minutes} min
            </p>
          </div>
        )}

        {stage === "exercise_active" && currentExercise && (
          <>
            <CustomExerciseStep
              key={`${currentExerciseIndex}-${currentSet}`}
              exercise={currentExercise}
              exerciseName={formatExerciseName(currentExercise.exercise_id, catalogNameMap)}
              currentSet={currentSet}
              onSetDone={handleSetDone}
            />
            {/* B281: always reachable exit from the current exercise. */}
            <div className="pt-2 text-center">
              <button
                type="button"
                onClick={handleSkipExercise}
                className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
              >
                Skip exercise →
              </button>
            </div>
          </>
        )}

        {stage === "resting" &&
          currentExercise &&
          (() => {
            const altSides = currentExercise.alt_sides === true;
            const totalSets = totalSetsWithSides(currentExercise.sets, altSides);
            const hasMoreSetsInExercise = currentSet < totalSets;
            // B324: the next bout may be the other side of the same set.
            const nextSide = sideForSet(currentSet + 1, altSides);
            const nextLabel = hasMoreSetsInExercise
              ? `Set ${displaySetNumber(currentSet + 1, altSides)} of ${currentExercise.sets ?? 1}${
                  nextSide ? ` · ${nextSide}` : ""
                } · ${formatExerciseName(currentExercise.exercise_id, catalogNameMap)}`
              : nextExercise
                ? formatExerciseName(nextExercise.exercise_id, catalogNameMap)
                : "Finish";
            // B350: what comes after this rest — another set of the same
            // exercise, or the next one. Timed work restarts on its own.
            const nextBout = hasMoreSetsInExercise ? currentExercise : nextExercise;
            const nextIsTimed = (nextBout?.work_seconds ?? 0) > 0;
            return (
              <CustomRestTimer
                targetSeconds={currentExercise.rest_between_sets_seconds ?? 0}
                nextLabel={nextLabel}
                onComplete={handleRestDone}
                onSkip={handleRestDone}
                autoAdvance={nextIsTimed}
              />
            );
          })()}

        {stage === "completed" && (
          <div className="py-12 text-center space-y-6">
            <div className="flex items-center justify-center">
              <div className="flex items-center justify-center w-20 h-20 rounded-full bg-green-500/15 border border-green-500/30">
                <Trophy className="size-10 text-green-500" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-wider text-emerald-500">Session complete</p>
              <h2 className="text-2xl font-semibold">{session.name}</h2>
            </div>
            <div className="rounded-lg border bg-muted/30 p-4 space-y-2 max-w-sm mx-auto text-left">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Duration</span>
                <span className="font-medium tabular-nums">
                  {Math.floor(durationSec / 60)}m {durationSec % 60}s
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Sets completed</span>
                <span className="font-medium tabular-nums">{setsCompleted}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Load score</span>
                <span className="font-medium tabular-nums">{session.estimated_load_score}</span>
              </div>
            </div>

            {/* A240: per-exercise log — perceived effort + optional used load. */}
            <div className="max-w-sm mx-auto space-y-3">
              <p className="text-xs uppercase tracking-wider text-muted-foreground text-left">
                How did each exercise feel?
              </p>
              {exercises.map((ex, i) => (
                <ExerciseFeedbackCard
                  key={`${ex.exercise_id}-${i}`}
                  name={formatExerciseName(ex.exercise_id, catalogNameMap)}
                  prescriptionSummary={exercisePrescriptionSummary(ex)}
                  setsCompleted={setsByIndex[i] ?? 0}
                  totalSets={totalSetsWithSides(ex.sets, ex.alt_sides === true)}
                  altSides={ex.alt_sides === true}
                  feedbackLabel={feedbackByIndex[i]}
                  loadKg={kgByIndex[i] ?? (ex.load_kg > 0 ? String(ex.load_kg) : "")}
                  showLoadInput
                  onFeedbackChange={(label) =>
                    setFeedbackByIndex((prev) => {
                      const next = { ...prev };
                      if (label) next[i] = label;
                      else delete next[i];
                      return next;
                    })
                  }
                  onLoadChange={(kg) => setKgByIndex((prev) => ({ ...prev, [i]: kg }))}
                  exercise={ex}
                  customSessionId={id}
                  date={date || undefined}
                  measures={measuresByIndex[i] ?? {}}
                  onMeasuresChange={(patch) =>
                    setMeasuresByIndex((prev) => ({ ...prev, [i]: { ...(prev[i] ?? {}), ...patch } }))
                  }
                  problems={problemsByIndex[i] ?? []}
                  onProblemsChange={(rows) => setProblemsByIndex((prev) => ({ ...prev, [i]: rows }))}
                  surface={surfaceByIndex[i] ?? null}
                  onSurfaceChange={(sf) => setSurfaceByIndex((prev) => ({ ...prev, [i]: sf }))}
                />
              ))}
              <p className="text-[11px] text-muted-foreground text-left">
                Untouched exercises are saved as not rated and don&apos;t change your loads.
              </p>
              <div className="rounded-lg border bg-muted/20 p-3 text-left">
                <PainPicker value={pain} onChange={setPain} />
              </div>
            </div>

            <div className="flex gap-3 justify-center pt-2">
              <Button variant="outline" onClick={handleBack} disabled={submitting}>
                Back
              </Button>
              <Button
                onClick={handleFinish}
                disabled={submitting}
                className="bg-success hover:bg-success/90 text-black min-h-[52px] text-base min-w-[140px]"
              >
                {submitting ? "Saving\u2026" : "Done"}
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
