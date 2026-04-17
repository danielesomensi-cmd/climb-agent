"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { BuilderExerciseCard } from "./builder-exercise-card";
import { ExercisePicker } from "./exercise-picker";
import { ExerciseParamsEditor } from "./exercise-params-editor";
import { WarmupCooldownPicker } from "./warmup-cooldown-picker";
import { useCustomSession } from "@/lib/hooks/queries";
import {
  useCreateCustomSession,
  useUpdateCustomSession,
  useDeleteCustomSession,
} from "@/lib/hooks/mutations";
import type { CustomSessionExercise, BuilderExercise } from "@/lib/types";
import { Plus, Save, Trash2, Flame, Snowflake } from "lucide-react";

/** Tracks exercise + its display name (catalog name at add time). */
interface BuilderEntry {
  exercise: CustomSessionExercise;
  name: string;
  tag?: "warmup" | "cooldown";
}

// ── Load / duration computation (mirrors backend) ─────────────────────

function computeLoadScore(entries: BuilderEntry[], catalog: Map<string, number>): number {
  const raw = entries.reduce((sum, e) => sum + (catalog.get(e.exercise.exercise_id) ?? 0), 0);
  return Math.min(85, Math.round(raw * 1.5));
}

function computeDuration(entries: BuilderEntry[]): number {
  let totalSeconds = 0;
  for (const { exercise: ex } of entries) {
    const sets = ex.sets || 1;
    const workPerSet = ex.work_seconds ?? (ex.reps ? ex.reps * 4 : 30);
    const rest = ex.rest_between_sets_seconds ?? 60;
    totalSeconds += sets * workPerSet + (sets - 1) * rest;
  }
  return Math.max(1, Math.round(totalSeconds / 60));
}

// ── Component ─────────────────────────────────────────────────────────

interface SessionBuilderProps {
  /** Session ID for edit mode. null = create mode. */
  sessionId: string | null;
}

export function SessionBuilder({ sessionId }: SessionBuilderProps) {
  const router = useRouter();
  const isEditMode = !!sessionId;

  // Queries
  const { data: existingSession, isLoading: loadingSession } = useCustomSession(sessionId);

  // Mutations
  const createMutation = useCreateCustomSession();
  const updateMutation = useUpdateCustomSession();
  const deleteMutation = useDeleteCustomSession();

  // Builder state
  const [name, setName] = useState("");
  const [entries, setEntries] = useState<BuilderEntry[]>([]);
  const [fatigueCosts, setFatigueCosts] = useState<Map<string, number>>(new Map());
  const [isDirty, setIsDirty] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // UI state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [warmupPickerOpen, setWarmupPickerOpen] = useState(false);
  const [cooldownPickerOpen, setCooldownPickerOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);
  const [nameError, setNameError] = useState("");

  // Initialize from existing session in edit mode
  useEffect(() => {
    if (isEditMode && existingSession && !initialized) {
      setName(existingSession.name);
      setEntries(
        existingSession.exercises.map((ex) => ({
          exercise: ex,
          name: ex.exercise_id, // will be resolved when catalog loads
        }))
      );
      setInitialized(true);
    }
    if (!isEditMode && !initialized) {
      setInitialized(true);
    }
  }, [isEditMode, existingSession, initialized]);

  // Track dirty state
  useEffect(() => {
    if (initialized && (name || entries.length > 0)) setIsDirty(true);
  }, [name, entries, initialized]);

  // Track fatigue costs from picker results
  const updateFatigueCost = useCallback((exerciseId: string, cost: number) => {
    setFatigueCosts((prev) => {
      const next = new Map(prev);
      next.set(exerciseId, cost);
      return next;
    });
  }, []);

  // Computed values
  const loadScore = useMemo(() => computeLoadScore(entries, fatigueCosts), [entries, fatigueCosts]);
  const duration = useMemo(() => computeDuration(entries), [entries]);
  const addedIds = useMemo(() => new Set(entries.map((e) => e.exercise.exercise_id)), [entries]);
  const hasWarmup = entries.some((e) => e.tag === "warmup");
  const hasCooldown = entries.some((e) => e.tag === "cooldown");

  // ── Actions ────────────────────────────────────────────────────────

  const addExercise = useCallback((exercise: CustomSessionExercise, exerciseName: string) => {
    setEntries((prev) => [...prev, { exercise, name: exerciseName }]);
  }, []);

  const addWarmupExercises = useCallback((exerciseList: Array<{ exercise: CustomSessionExercise; name: string }>) => {
    setEntries((prev) => [
      ...exerciseList.map((e) => ({ ...e, tag: "warmup" as const })),
      ...prev,
    ]);
  }, []);

  const addCooldownExercises = useCallback((exerciseList: Array<{ exercise: CustomSessionExercise; name: string }>) => {
    setEntries((prev) => [
      ...prev,
      ...exerciseList.map((e) => ({ ...e, tag: "cooldown" as const })),
    ]);
  }, []);

  const removeExercise = useCallback((index: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const moveExercise = useCallback((from: number, direction: -1 | 1) => {
    setEntries((prev) => {
      const next = [...prev];
      const to = from + direction;
      if (to < 0 || to >= next.length) return prev;
      [next[from], next[to]] = [next[to], next[from]];
      return next;
    });
  }, []);

  const updateExercise = useCallback((index: number, updated: CustomSessionExercise) => {
    setEntries((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, exercise: updated } : entry))
    );
  }, []);

  const handleSave = async () => {
    // Validations
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError("Name is required");
      return;
    }
    if (trimmedName.length > 100) {
      setNameError("Name must be under 100 characters");
      return;
    }
    setNameError("");

    if (entries.length === 0) return;

    const payload = {
      name: trimmedName,
      tags: [] as string[],
      exercises: entries.map((e) => e.exercise),
    };

    try {
      if (isEditMode && sessionId) {
        await updateMutation.mutateAsync({ id: sessionId, data: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      setIsDirty(false);
      router.push("/free-session");
    } catch {
      // Error is handled by TanStack Query
    }
  };

  const handleDelete = async () => {
    if (!sessionId) return;
    try {
      await deleteMutation.mutateAsync(sessionId);
      setIsDirty(false);
      router.push("/free-session");
    } catch {
      // Error handled by TanStack Query
    }
  };

  const handleBack = () => {
    if (isDirty) {
      setDiscardConfirmOpen(true);
    } else {
      router.push("/free-session");
    }
  };

  // ── Editing state ──────────────────────────────────────────────────

  const editingEntry = editingIndex !== null ? entries[editingIndex] : null;

  // Determine field visibility from exercise defaults
  const editingHasReps = editingEntry ? editingEntry.exercise.reps !== null : false;
  const editingHasWork = editingEntry ? editingEntry.exercise.work_seconds !== null : false;
  const editingHasRestBetweenReps = editingEntry ? editingEntry.exercise.rest_between_reps_seconds !== null : false;

  // ── Loading ────────────────────────────────────────────────────────

  if (isEditMode && loadingSession) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-4 pb-8">
      {/* Name input */}
      <div className="space-y-1.5">
        <Label htmlFor="session-name">Session name</Label>
        <Input
          id="session-name"
          placeholder="e.g. Finger Day, Power Session..."
          value={name}
          onChange={(e) => { setName(e.target.value); setNameError(""); }}
          maxLength={100}
        />
        {nameError && <p className="text-xs text-destructive">{nameError}</p>}
      </div>

      {/* Add Warmup shortcut */}
      {!hasWarmup && (
        <Button
          variant="outline"
          size="sm"
          className="w-full border-dashed text-orange-500 border-orange-500/30 hover:bg-orange-500/5"
          onClick={() => setWarmupPickerOpen(true)}
        >
          <Flame className="h-4 w-4 mr-2" />
          Add Warmup
        </Button>
      )}

      {/* Exercise list */}
      {entries.length > 0 ? (
        <div className="space-y-2">
          {entries.map((entry, i) => (
            <BuilderExerciseCard
              key={`${entry.exercise.exercise_id}-${i}`}
              exercise={entry.exercise}
              name={entry.name}
              index={i}
              total={entries.length}
              tag={entry.tag}
              onMoveUp={() => moveExercise(i, -1)}
              onMoveDown={() => moveExercise(i, 1)}
              onEdit={() => setEditingIndex(i)}
              onRemove={() => removeExercise(i)}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <p className="text-sm text-muted-foreground">No exercises yet. Tap below to start building.</p>
        </div>
      )}

      {/* Add Exercise button */}
      <Button
        variant="outline"
        className="w-full"
        onClick={() => setPickerOpen(true)}
      >
        <Plus className="h-4 w-4 mr-2" />
        Add Exercise
      </Button>

      {/* Add Cooldown shortcut */}
      {!hasCooldown && entries.length > 0 && (
        <Button
          variant="outline"
          size="sm"
          className="w-full border-dashed text-blue-500 border-blue-500/30 hover:bg-blue-500/5"
          onClick={() => setCooldownPickerOpen(true)}
        >
          <Snowflake className="h-4 w-4 mr-2" />
          Add Cooldown
        </Button>
      )}

      {/* Load / duration preview */}
      {entries.length > 0 && (
        <div className="flex items-center justify-center gap-4 text-sm text-muted-foreground py-2">
          <span>Load: <strong className="text-foreground">{loadScore}</strong></span>
          <span>\u00b7</span>
          <span>~<strong className="text-foreground">{duration}</strong> min</span>
        </div>
      )}

      {/* Save button */}
      <Button
        className="w-full"
        size="lg"
        disabled={!name.trim() || entries.length === 0 || isSaving}
        onClick={handleSave}
      >
        <Save className="h-4 w-4 mr-2" />
        {isSaving ? "Saving..." : isEditMode ? "Update Session" : "Save Session"}
      </Button>

      {/* Delete button (edit mode) */}
      {isEditMode && (
        <Button
          variant="ghost"
          className="w-full text-destructive hover:text-destructive"
          onClick={() => setDeleteConfirmOpen(true)}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Delete Session
        </Button>
      )}

      {/* ── Dialogs & drawers ── */}

      <ExercisePicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onAdd={(exercise, exerciseName) => {
          addExercise(exercise, exerciseName);
          // We don't close the picker — user can add multiple
        }}
        addedIds={addedIds}
      />

      {editingEntry && editingIndex !== null && (
        <ExerciseParamsEditor
          open={editingIndex !== null}
          onOpenChange={(open) => { if (!open) setEditingIndex(null); }}
          exercise={editingEntry.exercise}
          exerciseName={editingEntry.name}
          hasReps={editingHasReps}
          hasWork={editingHasWork}
          hasRestBetweenReps={editingHasRestBetweenReps}
          onConfirm={(updated) => updateExercise(editingIndex, updated)}
        />
      )}

      <WarmupCooldownPicker
        type="warmup"
        open={warmupPickerOpen}
        onOpenChange={setWarmupPickerOpen}
        onSelect={addWarmupExercises}
      />

      <WarmupCooldownPicker
        type="cooldown"
        open={cooldownPickerOpen}
        onOpenChange={setCooldownPickerOpen}
        onSelect={addCooldownExercises}
      />

      {/* Delete confirmation */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete session?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &ldquo;{name}&rdquo;. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Discard confirmation */}
      <AlertDialog open={discardConfirmOpen} onOpenChange={setDiscardConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard changes?</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Are you sure you want to go back?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction onClick={() => { setIsDirty(false); router.push("/free-session"); }}>
              Discard
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
