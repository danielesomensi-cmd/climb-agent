"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertTriangle, Check, SkipForward, Lightbulb, Film, Info, Timer, Play, Square, MessageSquare } from "lucide-react";
import type { GuidedExercise } from "@/lib/types";
import { ExerciseTimer } from "@/components/guided/exercise-timer";
import { FEEDBACK_OPTIONS } from "@/lib/format";
import { tapFeedback } from "@/lib/haptics";
import { displayPrescribedGrade } from "@/lib/gradeUtils";

interface GuidedExerciseStepProps {
  exercise: GuidedExercise;
  isTestSession?: boolean;
  bodyweightKg?: number;
  onDone: (feedbackLabel: string, usedLoad?: number, usedGrade?: string, usedTotalLoad?: number, testMeasurement?: number, perHand?: { right?: number; left?: number; right_reps?: number; left_reps?: number }) => void;
  onSkip: () => void;
  onSetChange?: (completedSets: number) => void;
  onNotesChange?: (notes: string) => void;
}


function formatRest(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? (s > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${m}:00`) : `${s}s`;
}

function formatPrescription(ex: GuidedExercise): string[] {
  const lines: string[] = [];
  const p = ex.prescription;

  // Main scheme
  if (p.sets && p.reps && p.workSeconds) {
    // Timed reps: "3 × 3 × 30s"
    const work = p.workSeconds >= 60 ? `${Math.round(p.workSeconds / 60)} min` : `${p.workSeconds}s`;
    lines.push(`${p.sets} \u00d7 ${p.reps} \u00d7 ${work}`);
  } else if (p.sets && p.reps) {
    lines.push(`${p.sets} \u00d7 ${p.reps}`);
  } else if (p.sets && p.workSeconds) {
    if (p.workSeconds >= 60) {
      lines.push(`${p.sets} \u00d7 ${Math.round(p.workSeconds / 60)} min`);
    } else {
      lines.push(`${p.sets} \u00d7 ${p.workSeconds}s`);
    }
  } else if (p.workSeconds) {
    if (p.workSeconds >= 60) {
      lines.push(`${Math.round(p.workSeconds / 60)} min`);
    } else {
      lines.push(`${p.workSeconds}s`);
    }
  } else if (p.sets && !p.reps && !p.workSeconds) {
    lines.push(`${p.sets} × max`);
  }

  // Rest info
  if (p.restBetweenRepsSeconds) {
    lines.push(`Rest between reps: ${formatRest(p.restBetweenRepsSeconds)}`);
  }
  if (p.restSeconds) {
    const label = p.restBetweenRepsSeconds ? "Set rest" : "Rest";
    lines.push(`${label}: ${formatRest(p.restSeconds)}`);
  }

  if (p.loadKg) {
    lines.push(`Load: ${p.loadKg} kg`);
  }

  if (p.tempo) {
    lines.push(`Tempo: ${p.tempo}`);
  }

  return lines;
}

export function GuidedExerciseStep({
  exercise,
  isTestSession,
  bodyweightKg,
  onDone,
  onSkip,
  onSetChange,
  onNotesChange,
}: GuidedExerciseStepProps) {
  const [feedback, setFeedback] = useState(exercise.feedbackLabel || "ok");
  const [loadInput, setLoadInput] = useState("");
  const [loadInputRight, setLoadInputRight] = useState("");
  const [loadInputLeft, setLoadInputLeft] = useState("");
  const [gradeInput, setGradeInput] = useState("");
  const [measurementInput, setMeasurementInput] = useState("");
  const [setsInput, setSetsInput] = useState("");
  const [repsInputRight, setRepsInputRight] = useState("");
  const [repsInputLeft, setRepsInputLeft] = useState("");
  const [notesInput, setNotesInput] = useState(exercise.notes ?? "");
  const [notesExpanded, setNotesExpanded] = useState(false);

  // B156: countup stopwatch for timed test_measurement exercises (e.g. L-sit hold)
  const [stopwatchRunning, setStopwatchRunning] = useState(false);
  const [stopwatchElapsed, setStopwatchElapsed] = useState(0);
  const stopwatchStartRef = useRef<number>(0);
  const stopwatchIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const STOPWATCH_CAP = 300; // 5 minutes max

  const startStopwatch = useCallback(() => {
    stopwatchStartRef.current = Date.now();
    setStopwatchElapsed(0);
    setStopwatchRunning(true);
  }, []);

  const stopStopwatch = useCallback(() => {
    setStopwatchRunning(false);
    if (stopwatchIntervalRef.current) {
      clearInterval(stopwatchIntervalRef.current);
      stopwatchIntervalRef.current = null;
    }
    const elapsed = Math.floor((Date.now() - stopwatchStartRef.current) / 1000);
    const capped = Math.min(elapsed, STOPWATCH_CAP);
    setStopwatchElapsed(capped);
    setMeasurementInput(String(capped));
  }, []);

  // Wall-clock tick for stopwatch (iOS Safari safe)
  useEffect(() => {
    if (!stopwatchRunning) return;
    stopwatchIntervalRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - stopwatchStartRef.current) / 1000);
      if (elapsed >= STOPWATCH_CAP) {
        stopStopwatch();
        return;
      }
      setStopwatchElapsed(elapsed);
    }, 250);
    return () => {
      if (stopwatchIntervalRef.current) clearInterval(stopwatchIntervalRef.current);
    };
  }, [stopwatchRunning, stopStopwatch]);

  // Recover from iOS background suspension
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible" || !stopwatchRunning) return;
      const elapsed = Math.floor((Date.now() - stopwatchStartRef.current) / 1000);
      if (elapsed >= STOPWATCH_CAP) {
        stopStopwatch();
      } else {
        setStopwatchElapsed(elapsed);
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [stopwatchRunning, stopStopwatch]);

  // Test measurement exercises: just a number input, no feedback
  const isTestMeasurement = exercise.category === "test_measurement" && !!exercise.testField;
  const isUnilateral = exercise.unilateral === true;

  // C-LOADMODEL-MISTAG: per-hand LOAD logging (independent L/R max, e.g. finger
  // loading-pin) is signalled by per-hand suggested loads — NOT by raw
  // unilaterality. Unilateral LEG accessories (bulgarian/cossack/split squat)
  // are external_load but load a single dumbbell → single field + single
  // progression, so they must NOT render the L/R hand inputs. Mirrors the
  // backend is_loading_pin gate (which routes only loading-pin work per-hand).
  const isPerHandLoad = isUnilateral && (
    exercise.suggested.rightHand?.externalLoadKg != null ||
    exercise.suggested.leftHand?.externalLoadKg != null
  );

  // B128: unilateral test measurement (e.g. lp_duration_test — seconds per hand)
  const isUnilateralTestMeasurement = isTestSession && isUnilateral && !!exercise.testField && !!exercise.testUnit;

  // B133: Repeater test (HB bilateral) — reps to failure
  const isRepeaterTest = isTestSession && (
    exercise.exerciseId === "repeater_hang_7_3" ||
    exercise.exerciseId === "test_repeater_7_3_to_failure"
  );

  // B133: LP repeater test (unilateral) — reps per hand to failure
  const isLpRepeaterTest = isTestSession && exercise.exerciseId === "lp_repeater_test";

  // B120: unilateral test exercises (LP max test) — dual R/L test result input
  const isUnilateralTest = !isTestMeasurement && !isRepeaterTest && !isLpRepeaterTest && !isUnilateralTestMeasurement && isTestSession && isUnilateral;

  // Test session total_load exercises get two mandatory fields
  const isTestLoadExercise = !isTestMeasurement && !isRepeaterTest && !isLpRepeaterTest && !isUnilateralTest && isTestSession && exercise.loadModel === "total_load";

  // Determine which kind of editable field to show.
  //
  // B298: a kg-loadable exercise (external_load / total_load) ALWAYS gets the
  // field, even with no suggested load — a loadable exercise the user has never
  // logged has no suggestion yet, and gating on one hid the field entirely
  // (adhoc Back Squat rendered with no way to log a weight at all). The field
  // just starts empty in that case. Loadability comes from load_model, never
  // from a non-zero resolved value.
  const isKgLoadable =
    exercise.loadModel === "external_load" || exercise.loadModel === "total_load";
  const hasLoadField =
    !isTestLoadExercise &&
    !isTestMeasurement &&
    (isKgLoadable ||
      // A228: catalog opt-in (e.g. Pallof Press) — record-only optional weight,
      // no suggested load and no engine consumption (D249).
      !!exercise.allowLoadLogging);
  const hasGradeField = !isTestMeasurement && exercise.suggested.grade != null;

  // Pre-populate from suggested values or previous user input.
  //
  // B288: this effect depends on the whole `exercise` object, so it re-ran on
  // EVERY update to the current exercise — changing sets or typing a note
  // rewrote the load field back to the suggested value, wiping what the user
  // had just typed (report: "metto 5 e poco dopo mi ripropone i 2kg"). The
  // pre-fill is a cold start, not a sync: run it once per exercise and never
  // clobber user input afterwards.
  const prefilledForRef = useRef<string | null>(null);
  useEffect(() => {
    if (prefilledForRef.current === exercise.exerciseId) return;
    prefilledForRef.current = exercise.exerciseId;
    if (exercise.usedLoadKg != null) {
      setLoadInput(String(exercise.usedLoadKg));
    } else if (exercise.suggested.externalLoadKg != null) {
      setLoadInput(String(exercise.suggested.externalLoadKg));
    }
    // Per-hand loads (unilateral LP exercises)
    if (exercise.usedLoadKgRight != null) {
      setLoadInputRight(String(exercise.usedLoadKgRight));
    } else if (exercise.suggested.rightHand?.externalLoadKg != null) {
      setLoadInputRight(String(exercise.suggested.rightHand.externalLoadKg));
    }
    if (exercise.usedLoadKgLeft != null) {
      setLoadInputLeft(String(exercise.usedLoadKgLeft));
    } else if (exercise.suggested.leftHand?.externalLoadKg != null) {
      setLoadInputLeft(String(exercise.suggested.leftHand.externalLoadKg));
    }
    if (exercise.usedGrade != null) {
      setGradeInput(exercise.usedGrade);
    } else if (exercise.suggested.grade) {
      // B344: prefill in the same scale the target is shown in. Safe to send
      // back lowercase — the engine's normalize_font_grade uppercases first.
      setGradeInput(displayPrescribedGrade(exercise.suggested.grade, exercise.suggested.gradeScale));
    }
    if (exercise.testMeasurement != null) {
      setMeasurementInput(String(exercise.testMeasurement));
    }
    if (exercise.completedSets != null) {
      setSetsInput(String(exercise.completedSets));
    }
    setNotesInput(exercise.notes ?? "");
    setNotesExpanded(!!(exercise.notes));
    setFeedback(exercise.feedbackLabel || "ok");
  }, [exercise]);

  const prescriptionLines = formatPrescription(exercise);
  const isAlreadyDone = exercise.status === "done";
  const isAlreadySkipped = exercise.status === "skipped";

  // Instruction-only block (warmup, mobility) — simplified UI
  if (exercise.isInstructionOnly) {
    return (
      <Card className="gap-0 py-0 border-primary/30">
        <CardHeader className="py-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Info className="size-4 text-primary shrink-0" />
              <CardTitle className="text-base">{exercise.name}</CardTitle>
            </div>
            {isAlreadyDone && (
              <Badge className="bg-green-600 text-white text-[10px]">Done</Badge>
            )}
          </div>
          {exercise.category && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {exercise.category.replace(/_/g, " ")}
            </p>
          )}
        </CardHeader>
        <CardContent className="pb-4 space-y-3">
          {exercise.instructionDuration && (
            <div className="flex items-center gap-1.5 text-sm">
              <Timer className="size-3.5 text-muted-foreground" />
              <span>{exercise.instructionDuration[0]}–{exercise.instructionDuration[1]} min</span>
            </div>
          )}
          {exercise.instructionNotes && exercise.instructionNotes.length > 0 && (
            <div className="space-y-1">
              {exercise.instructionNotes.map((note, i) => (
                <p key={i} className="text-sm text-muted-foreground">{note}</p>
              ))}
            </div>
          )}
          {exercise.instructionOptions && exercise.instructionOptions.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Options:</p>
              <div className="flex flex-wrap gap-1.5">
                {exercise.instructionOptions.map((opt) => (
                  <Badge key={opt} variant="outline" className="text-[10px]">
                    {opt.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {exercise.instructionFocus && exercise.instructionFocus.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Focus:</p>
              <div className="flex flex-wrap gap-1.5">
                {exercise.instructionFocus.map((f) => (
                  <Badge key={f} variant="outline" className="text-[10px]">
                    {f.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 pt-2">
            <Button
              size="sm"
              className="bg-green-600 hover:bg-green-700 text-white flex-1"
              onClick={() => onDone("ok")}
            >
              <Check className="size-4 mr-1" />
              {isAlreadyDone ? "Done" : "Done"}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  function handleDone() {
    if (isTestMeasurement) {
      const val = measurementInput ? parseFloat(measurementInput) : undefined;
      onDone("ok", undefined, undefined, undefined, val);
      return;
    }
    // B128: unilateral test measurement (e.g. lp_duration_test — seconds per hand)
    if (isUnilateralTestMeasurement) {
      const right = loadInputRight ? parseFloat(loadInputRight) : undefined;
      const left = loadInputLeft ? parseFloat(loadInputLeft) : undefined;
      onDone("ok", undefined, undefined, undefined, undefined, { right, left });
      return;
    }
    if (isRepeaterTest) {
      // B133-fix: ensure completedSets (= reps to failure) is set before Done
      const repsVal = setsInput ? parseInt(setsInput, 10) : undefined;
      if (repsVal != null && !isNaN(repsVal) && onSetChange) {
        onSetChange(repsVal);
      }
      const usedExternal = loadInput ? parseFloat(loadInput) : undefined;
      const usedTotal = usedExternal != null && bodyweightKg != null
        ? bodyweightKg + usedExternal
        : undefined;
      onDone(feedback, usedExternal, undefined, usedTotal);
      return;
    }
    // B133: LP repeater test — reps per hand + load per hand
    if (isLpRepeaterTest) {
      const right = loadInputRight ? parseFloat(loadInputRight) : undefined;
      const left = loadInputLeft ? parseFloat(loadInputLeft) : undefined;
      onDone(feedback, undefined, undefined, undefined, undefined, {
        right, left,
        right_reps: repsInputRight ? parseInt(repsInputRight, 10) : undefined,
        left_reps: repsInputLeft ? parseInt(repsInputLeft, 10) : undefined,
      });
      return;
    }
    // B120: unilateral test (LP max test) — pass per-hand loads
    if (isUnilateralTest) {
      const right = loadInputRight ? parseFloat(loadInputRight) : undefined;
      const left = loadInputLeft ? parseFloat(loadInputLeft) : undefined;
      onDone(feedback, undefined, undefined, undefined, undefined, { right, left });
      return;
    }
    if (isTestLoadExercise) {
      const usedExternal = loadInput ? parseFloat(loadInput) : undefined;
      const usedTotal = usedExternal != null && bodyweightKg != null
        ? bodyweightKg + usedExternal
        : undefined;
      onDone(feedback, usedExternal, undefined, usedTotal);
      return;
    }
    // Loading-pin (finger, independent L/R): pass per-hand loads. Unilateral
    // leg accessories fall through to the single-load path below (C-LOADMODEL-MISTAG).
    if (isPerHandLoad) {
      const right = loadInputRight ? parseFloat(loadInputRight) : undefined;
      const left = loadInputLeft ? parseFloat(loadInputLeft) : undefined;
      onDone(feedback, undefined, undefined, undefined, undefined, { right, left });
      return;
    }
    const usedLoad = hasLoadField && loadInput ? parseFloat(loadInput) : undefined;
    const usedGrade = hasGradeField && gradeInput ? gradeInput : undefined;
    onDone(feedback, usedLoad, usedGrade);
  }

  return (
    <Card className="gap-0 py-0">
      <CardHeader className="py-4">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{exercise.name || exercise.exerciseId.replace(/_/g, " ")}</CardTitle>
          {isAlreadyDone && (
            <Badge className="bg-green-600 text-white text-[10px]">Done</Badge>
          )}
          {isAlreadySkipped && (
            <Badge className="bg-red-400 text-white text-[10px]">Skipped</Badge>
          )}
        </div>
        {exercise.category && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {exercise.category.replace(/_/g, " ")}
          </p>
        )}
      </CardHeader>

      <CardContent className="pb-4 space-y-4">
        {/* Limitation warning banner (B38) */}
        {exercise.limitationWarning && (
          <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-xs ${
            exercise.limitationWarning === "severe"
              ? "bg-red-500/15 text-red-400 border border-red-500/30"
              : exercise.limitationWarning === "active"
                ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                : "bg-yellow-500/15 text-yellow-400 border border-yellow-500/30"
          }`}>
            <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
            <span>
              {exercise.limitationWarning === "severe" && (
                <>Caution: {exercise.limitationZone} injury — exercise replaced with prehab</>
              )}
              {exercise.limitationWarning === "active" && (
                <>Caution: {exercise.limitationZone} limitation — {exercise.limitationLoadModifier ? "load reduced by 20%" : "modified variant selected"}</>
              )}
              {exercise.limitationWarning === "monitor" && (
                <>Note: mild {exercise.limitationZone} sensitivity — proceed with awareness</>
              )}
            </span>
          </div>
        )}
        {exercise.limitationPrehabFor && !exercise.limitationWarning && (
          <div className="flex items-start gap-2 rounded-md px-3 py-2 text-xs bg-blue-500/15 text-blue-400 border border-blue-500/30">
            <Info className="size-3.5 shrink-0 mt-0.5" />
            <span>Auto-added prehab for {exercise.limitationPrehabFor} limitation</span>
          </div>
        )}

        {/* Prescription */}
        {prescriptionLines.length > 0 && (
          <div className="space-y-1">
            {prescriptionLines.map((line, i) => (
              <p key={i} className="text-sm">{line}</p>
            ))}
          </div>
        )}

        {exercise.prescription.notes && (
          <p className="text-xs text-muted-foreground italic">
            {exercise.prescription.notes}
          </p>
        )}

        {/* Cues */}
        {exercise.cues && exercise.cues.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Cues:</p>
            <ul className="space-y-0.5">
              {exercise.cues.map((cue, i) => (
                <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                  <span className="mt-1.5 block h-1 w-1 shrink-0 rounded-full bg-muted-foreground/50" />
                  {cue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Video link */}
        {exercise.videoUrl && (
          <a
            href={exercise.videoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
          >
            <Film className="size-3.5" />
            Watch video
          </a>
        )}

        {/* Test measurement: single value input, no feedback/timer */}
        {isTestMeasurement ? (
          <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
            <p className="text-xs font-medium text-primary">Record your result</p>

            {/* B156: Countup stopwatch for seconds-based tests (L-sit, max hang duration) */}
            {exercise.testUnit === "seconds" && (
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="text-4xl font-bold tabular-nums text-primary">
                  {Math.floor(stopwatchElapsed / 60)}:{String(stopwatchElapsed % 60).padStart(2, "0")}
                </div>
                {!stopwatchRunning && stopwatchElapsed === 0 && (
                  <Button
                    size="lg"
                    className="bg-green-600 hover:bg-green-700 text-white gap-2 w-40"
                    onClick={startStopwatch}
                  >
                    <Play className="size-5" />
                    Start
                  </Button>
                )}
                {stopwatchRunning && (
                  <Button
                    size="lg"
                    variant="destructive"
                    className="gap-2 w-40"
                    onClick={stopStopwatch}
                  >
                    <Square className="size-5" />
                    Stop
                  </Button>
                )}
                {!stopwatchRunning && stopwatchElapsed > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {stopwatchElapsed >= STOPWATCH_CAP
                      ? "Impressive! 5 minutes is the maximum we track."
                      : "Result auto-filled below. Edit if needed."}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="measurement-input" className="text-xs text-muted-foreground">
                Result ({exercise.testUnit ?? "value"}) *
              </Label>
              <Input
                id="measurement-input"
                type="number"
                inputMode="decimal"
                step={exercise.testUnit === "cm" ? "1" : "0.5"}
                min="0"
                value={measurementInput}
                onChange={(e) => setMeasurementInput(e.target.value)}
                className="w-40 h-9"
                placeholder={exercise.testUnit === "seconds" ? "e.g. 65" : exercise.testUnit === "cm" ? "e.g. 120" : ""}
                required
              />
            </div>
          </div>
        ) : isUnilateralTestMeasurement ? (
          /* B128: unilateral test measurement (e.g. lp_duration_test — seconds per hand) */
          <div className="space-y-3">
            {/* Suggested load per hand (the load to use during test) */}
            {(exercise.suggested.rightHand?.externalLoadKg != null || exercise.suggested.leftHand?.externalLoadKg != null) && (
              <div className="flex items-start gap-2 rounded-md bg-primary/5 border border-primary/20 p-3">
                <Lightbulb className="size-4 text-primary mt-0.5 shrink-0" />
                <div className="text-sm space-y-0.5 w-full">
                  <div className="grid grid-cols-2 gap-3">
                    <p>
                      Left: <span className="font-semibold">+{exercise.suggested.leftHand?.externalLoadKg ?? 0} kg</span>
                    </p>
                    <p>
                      Right: <span className="font-semibold">+{exercise.suggested.rightHand?.externalLoadKg ?? 0} kg</span>
                    </p>
                  </div>
                  {exercise.suggested.loadSource === "estimated" && (
                    <p className="text-xs text-muted-foreground">(estimated from hangboard baseline)</p>
                  )}
                </div>
              </div>
            )}
            <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
              <p className="text-xs font-medium text-primary">Record your test result</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="test-left-meas" className="text-xs text-muted-foreground">
                    Left hand ({exercise.testUnit}) *
                  </Label>
                  <Input
                    id="test-left-meas"
                    type="number"
                    inputMode="numeric"
                    step="1"
                    min="0"
                    value={loadInputLeft}
                    onChange={(e) => setLoadInputLeft(e.target.value)}
                    className="h-9"
                    placeholder="e.g. 65"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="test-right-meas" className="text-xs text-muted-foreground">
                    Right hand ({exercise.testUnit}) *
                  </Label>
                  <Input
                    id="test-right-meas"
                    type="number"
                    inputMode="numeric"
                    step="1"
                    min="0"
                    value={loadInputRight}
                    onChange={(e) => setLoadInputRight(e.target.value)}
                    className="h-9"
                    placeholder="e.g. 65"
                    required
                  />
                </div>
              </div>
            </div>
            {/* Feedback selector */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">How did it feel?</Label>
              <div className="flex flex-wrap gap-1.5">
                {FEEDBACK_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setFeedback(opt.value)}
                    onPointerDown={tapFeedback}
                    className={`min-h-[44px] rounded-full px-4 text-sm font-medium transition-all active:scale-95 motion-reduce:active:scale-100 ${
                      feedback === opt.value
                        ? `${opt.color} text-white ring-2 ring-offset-1 ring-offset-background ${opt.ring}`
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Suggested load/grade — per-hand (finger loading-pin) */}
            {isPerHandLoad && (exercise.suggested.rightHand?.externalLoadKg != null || exercise.suggested.leftHand?.externalLoadKg != null) && (
              <div className="flex items-start gap-2 rounded-md bg-primary/5 border border-primary/20 p-3">
                <Lightbulb className="size-4 text-primary mt-0.5 shrink-0" />
                <div className="text-sm space-y-0.5 w-full">
                  <div className="grid grid-cols-2 gap-3">
                    <p>
                      Left: <span className="font-semibold">+{exercise.suggested.leftHand?.externalLoadKg ?? 0} kg</span>
                    </p>
                    <p>
                      Right: <span className="font-semibold">+{exercise.suggested.rightHand?.externalLoadKg ?? 0} kg</span>
                    </p>
                  </div>
                  {exercise.suggested.repScheme && (
                    <p className="text-xs text-muted-foreground">{exercise.suggested.repScheme}</p>
                  )}
                  {exercise.suggested.loadSource === "estimated" && (
                    <p className="text-xs text-muted-foreground">(estimated from hangboard baseline)</p>
                  )}
                </div>
              </div>
            )}

            {/* Suggested load/grade — single (bilateral + unilateral leg accessories) */}
            {!isPerHandLoad && (exercise.suggested.externalLoadKg != null ||
              exercise.suggested.totalLoadKg != null ||
              exercise.suggested.grade != null) && (
              <div className="flex items-start gap-2 rounded-md bg-primary/5 border border-primary/20 p-3">
                <Lightbulb className="size-4 text-primary mt-0.5 shrink-0" />
                <div className="text-sm space-y-0.5 w-full">
                  {exercise.suggested.externalLoadKg != null && (
                    <p>
                      Suggested: <span className="font-semibold">+{exercise.suggested.externalLoadKg} kg</span>
                      {exercise.suggested.totalLoadKg != null && (
                        <span className="text-muted-foreground"> (total: {exercise.suggested.totalLoadKg} kg)</span>
                      )}
                      {exercise.suggested.loadSource === "estimated" && (
                        <span className="text-xs text-muted-foreground ml-1">(estimated)</span>
                      )}
                    </p>
                  )}
                  {exercise.suggested.grade && (
                    <p>
                      Target: <span className="font-semibold">
                        {exercise.suggested.gradeLow && exercise.suggested.gradeLow !== exercise.suggested.grade
                          ? `${displayPrescribedGrade(exercise.suggested.gradeLow, exercise.suggested.gradeScale)} – ${displayPrescribedGrade(exercise.suggested.grade, exercise.suggested.gradeScale)}`
                          : displayPrescribedGrade(exercise.suggested.grade, exercise.suggested.gradeScale)}
                      </span>
                      {exercise.suggested.surface && (
                        <span className="text-muted-foreground"> on {exercise.suggested.surface}</span>
                      )}
                    </p>
                  )}
                  {(exercise.suggested.attemptGuidance || exercise.suggested.restGuidance) && (
                    <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                      {exercise.suggested.attemptGuidance && <p>{exercise.suggested.attemptGuidance}</p>}
                      {exercise.suggested.restGuidance && <p>Rest: {exercise.suggested.restGuidance}</p>}
                    </div>
                  )}
                  {exercise.suggested.loadWarning && (
                    <p className="text-xs text-orange-500 mt-1">
                      ⚠ Suggested load requires counterweight — consider re-testing your max hang.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Exercise timer — shown for timed exercises AND multi-set rep-based exercises */}
            {(((exercise.prescription.workSeconds ?? 0) > 0) ||
              ((exercise.prescription.sets ?? 1) > 1 && (exercise.prescription.restSeconds ?? 0) > 0)) && (
              <ExerciseTimer
                workSeconds={exercise.prescription.workSeconds ?? 0}
                restBetweenRepsSeconds={exercise.prescription.restBetweenRepsSeconds ?? 0}
                restBetweenSetsSeconds={exercise.prescription.restSeconds ?? 0}
                sets={exercise.prescription.sets ?? 1}
                reps={typeof exercise.prescription.reps === "number" ? exercise.prescription.reps : 1}
                altSides={exercise.altSides ?? false}
                initialSet={(() => {
                  const prescSets = exercise.prescription.sets ?? 1;
                  const totalSets = (exercise.altSides ?? false) ? prescSets * 2 : prescSets;
                  if (exercise.completedSets != null && exercise.completedSets < totalSets) {
                    return Math.min(exercise.completedSets + 1, totalSets);
                  }
                  return 1;
                })()}
                onSetChange={onSetChange}
              />
            )}

            {/* Repeater test: reps completed to failure + optional load */}
            {isRepeaterTest && (
              <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-medium text-primary">Record your test result</p>
                <div className="space-y-1.5">
                  <Label htmlFor="sets-input" className="text-xs text-muted-foreground">
                    Reps completed (full 7s hangs) *
                  </Label>
                  <Input
                    id="sets-input"
                    type="number"
                    inputMode="numeric"
                    step="1"
                    min="0"
                    value={setsInput}
                    onChange={(e) => {
                      setSetsInput(e.target.value);
                      const parsed = parseInt(e.target.value, 10);
                      if (!isNaN(parsed) && parsed >= 0 && onSetChange) {
                        onSetChange(parsed);
                      }
                    }}
                    className="w-40 h-9"
                    placeholder="e.g. 12"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="repeater-load-input" className="text-xs text-muted-foreground">
                    External load added (kg)
                  </Label>
                  <Input
                    id="repeater-load-input"
                    type="number"
                    inputMode="decimal"
                    step="0.5"
                    min="0"
                    value={loadInput}
                    onChange={(e) => setLoadInput(e.target.value)}
                    className="w-40 h-9"
                    placeholder="e.g. 0"
                  />
                </div>
                {bodyweightKg != null && loadInput && !isNaN(parseFloat(loadInput)) && (
                  <p className="text-sm text-muted-foreground">
                    Total load:{" "}
                    <span className="font-semibold text-foreground">
                      {(bodyweightKg + parseFloat(loadInput)).toFixed(1)} kg
                    </span>
                    <span className="text-xs ml-1">
                      (your weight {bodyweightKg} kg + {loadInput} kg added)
                    </span>
                  </p>
                )}
              </div>
            )}

            {/* B133: LP repeater test — reps per hand + load per hand */}
            {isLpRepeaterTest && (
              <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-medium text-primary">Record your test result</p>
                {/* Suggested load per hand */}
                {(exercise.suggested.rightHand?.externalLoadKg != null || exercise.suggested.leftHand?.externalLoadKg != null) && (
                  <div className="flex items-start gap-2 rounded-md bg-primary/10 border border-primary/20 p-2">
                    <Lightbulb className="size-3.5 text-primary mt-0.5 shrink-0" />
                    <p className="text-xs text-muted-foreground">
                      Suggested load: L {exercise.suggested.leftHand?.externalLoadKg ?? 0} kg / R {exercise.suggested.rightHand?.externalLoadKg ?? 0} kg (60% of max)
                    </p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="lp-rep-reps-right" className="text-xs text-muted-foreground">
                      Right hand reps *
                    </Label>
                    <Input
                      id="lp-rep-reps-right"
                      type="number"
                      inputMode="numeric"
                      step="1"
                      min="0"
                      value={repsInputRight}
                      onChange={(e) => setRepsInputRight(e.target.value)}
                      className="h-9"
                      placeholder="e.g. 14"
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="lp-rep-reps-left" className="text-xs text-muted-foreground">
                      Left hand reps *
                    </Label>
                    <Input
                      id="lp-rep-reps-left"
                      type="number"
                      inputMode="numeric"
                      step="1"
                      min="0"
                      value={repsInputLeft}
                      onChange={(e) => setRepsInputLeft(e.target.value)}
                      className="h-9"
                      placeholder="e.g. 12"
                      required
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="lp-rep-load-right" className="text-xs text-muted-foreground">
                      Right hand load (kg)
                    </Label>
                    <Input
                      id="lp-rep-load-right"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      min="0"
                      value={loadInputRight}
                      onChange={(e) => setLoadInputRight(e.target.value)}
                      className="h-9"
                      placeholder="kg"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="lp-rep-load-left" className="text-xs text-muted-foreground">
                      Left hand load (kg)
                    </Label>
                    <Input
                      id="lp-rep-load-left"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      min="0"
                      value={loadInputLeft}
                      onChange={(e) => setLoadInputLeft(e.target.value)}
                      className="h-9"
                      placeholder="kg"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* B120: unilateral test — dual R/L test result input */}
            {isUnilateralTest && (
              <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-medium text-primary">Record your test result</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="test-left" className="text-xs text-muted-foreground">
                      Left hand (kg) *
                    </Label>
                    <Input
                      id="test-left"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      min="0"
                      value={loadInputLeft}
                      onChange={(e) => setLoadInputLeft(e.target.value)}
                      className="h-9"
                      placeholder="e.g. 42"
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="test-right" className="text-xs text-muted-foreground">
                      Right hand (kg) *
                    </Label>
                    <Input
                      id="test-right"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      min="0"
                      value={loadInputRight}
                      onChange={(e) => setLoadInputRight(e.target.value)}
                      className="h-9"
                      placeholder="e.g. 47"
                      required
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Feedback selector */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">How did it feel?</Label>
              <div className="flex flex-wrap gap-1.5">
                {FEEDBACK_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setFeedback(opt.value)}
                    onPointerDown={tapFeedback}
                    className={`min-h-[44px] rounded-full px-4 text-sm font-medium transition-all active:scale-95 motion-reduce:active:scale-100 ${
                      feedback === opt.value
                        ? `${opt.color} text-white ring-2 ring-offset-1 ring-offset-background ${opt.ring}`
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Test session: external load input with auto-computed total */}
            {isTestLoadExercise && (
              <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-medium text-primary">Record your test result</p>
                <div className="space-y-1.5">
                  <Label htmlFor="external-load-input" className="text-xs text-muted-foreground">
                    External load added (kg) *
                  </Label>
                  <Input
                    id="external-load-input"
                    type="number"
                    inputMode="decimal"
                    step="0.5"
                    min="0"
                    value={loadInput}
                    onChange={(e) => setLoadInput(e.target.value)}
                    className="w-40 h-9"
                    placeholder="e.g. 15"
                    required
                  />
                </div>
                {bodyweightKg != null && loadInput && !isNaN(parseFloat(loadInput)) && (
                  <p className="text-sm text-muted-foreground">
                    Total load:{" "}
                    <span className="font-semibold text-foreground">
                      {(bodyweightKg + parseFloat(loadInput)).toFixed(1)} kg
                    </span>
                    <span className="text-xs ml-1">
                      (your weight {bodyweightKg} kg + {loadInput} kg added)
                    </span>
                  </p>
                )}
              </div>
            )}

            {/* Editable load fields — per-hand (finger loading-pin), not shown for unilateral tests or bodyweight exercises */}
            {isPerHandLoad && !isTestMeasurement && !isUnilateralTest && exercise.loadModel !== "bodyweight_only" && (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  Actual load used (kg)
                </Label>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="load-left" className="text-[11px] text-muted-foreground">Left hand</Label>
                    <Input
                      id="load-left"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      value={loadInputLeft}
                      onChange={(e) => setLoadInputLeft(e.target.value)}
                      className="h-9"
                      placeholder="kg"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="load-right" className="text-[11px] text-muted-foreground">Right hand</Label>
                    <Input
                      id="load-right"
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      value={loadInputRight}
                      onChange={(e) => setLoadInputRight(e.target.value)}
                      className="h-9"
                      placeholder="kg"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Editable load field — single (bilateral + unilateral leg accessories, non-test) */}
            {hasLoadField && !isPerHandLoad && (
              <div className="space-y-1.5">
                <Label htmlFor="load-input" className="text-xs text-muted-foreground">
                  {exercise.allowLoadLogging ? "Weight used (kg) — optional" : "Actual load used (kg)"}
                </Label>
                <Input
                  id="load-input"
                  type="number"
                  inputMode="decimal"
                  step="0.5"
                  min={0}
                  value={loadInput}
                  onChange={(e) => setLoadInput(e.target.value)}
                  className="w-32 h-9"
                  placeholder={exercise.allowLoadLogging ? "kg — leave empty if using a band" : "kg"}
                />
              </div>
            )}

            {/* Editable grade field */}
            {hasGradeField && (
              <div className="space-y-1.5">
                <Label htmlFor="grade-input" className="text-xs text-muted-foreground">
                  Actual grade used
                </Label>
                <Input
                  id="grade-input"
                  type="text"
                  value={gradeInput}
                  onChange={(e) => setGradeInput(e.target.value)}
                  className="w-32 h-9"
                  placeholder="e.g. 7A"
                />
              </div>
            )}
          </>
        )}

        {/* B156: Per-exercise notes */}
        <div className="pt-1">
          {!notesExpanded ? (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setNotesExpanded(true)}
            >
              <MessageSquare className="size-3.5" />
              Add note
            </button>
          ) : (
            <div className="space-y-1">
              <textarea
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
                rows={2}
                maxLength={500}
                placeholder="How did it feel? Any details to remember..."
                value={notesInput}
                onChange={(e) => {
                  setNotesInput(e.target.value);
                  onNotesChange?.(e.target.value);
                }}
              />
              {notesInput.length > 400 && (
                <p className="text-[10px] text-muted-foreground text-right">{notesInput.length}/500</p>
              )}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="outline"
            className="min-h-[44px] text-muted-foreground"
            onClick={onSkip}
          >
            <SkipForward className="size-4 mr-1" />
            Skip
          </Button>
          <Button
            className="min-h-[44px] bg-green-600 hover:bg-green-700 text-white flex-1"
            onClick={handleDone}
          >
            <Check className="size-4 mr-1" />
            {isAlreadyDone ? "Update" : "Done"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
