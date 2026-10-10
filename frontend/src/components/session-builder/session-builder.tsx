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
import { toast } from "sonner";
import { BuilderExerciseCard } from "./builder-exercise-card";
import { BuilderSkeleton } from "./builder-skeleton";
import {
  canMoveWithinGroup,
  computeDuration,
  groupEntries,
  insertMainEntry,
  moveWithinGroup,
  restoreEntryAt,
  type GroupedEntry,
} from "./builder-groups";
import { ExercisePicker } from "./exercise-picker";
import { ExerciseParamsEditor } from "./exercise-params-editor";
import { WarmupCooldownPicker } from "./warmup-cooldown-picker";
import { useCustomSession, useBuilderExercises } from "@/lib/hooks/queries";
import {
  useCreateCustomSession,
  useUpdateCustomSession,
  useDeleteCustomSession,
} from "@/lib/hooks/mutations";
import type { CustomSessionExercise } from "@/lib/types";
import { Plus, Save, Trash2, Flame, Snowflake, type LucideIcon } from "lucide-react";

/** Tracks exercise + its display name (catalog name at add time). */
interface BuilderEntry {
  exercise: CustomSessionExercise;
  name: string;
  tag?: "warmup" | "cooldown";
}

// ── Load / duration computation (mirrors backend) ─────────────────────

export function computeLoadScore(entries: BuilderEntry[], catalog: Map<string, number>): number {
  const raw = entries.reduce((sum, e) => sum + (catalog.get(e.exercise.exercise_id) ?? 0), 0);
  return Math.min(85, Math.round(raw * 1.5));
}

/**
 * B356 — {exercise_id: fatigue_cost} dal catalogo del builder.
 * Speculare a `build_fatigue_map` in backend/engine/load_score.py. Estratta e
 * testata perché il bug non era la formula ma la mappa: restava vuota, quindi
 * `computeLoadScore` sommava zeri e il builder scriveva "Load: 0" per sempre.
 */
export function buildFatigueMap(
  exercises: Array<{ id: string; fatigue_cost?: number }> | undefined,
): Map<string, number> {
  const map = new Map<string, number>();
  for (const ex of exercises ?? []) map.set(ex.id, ex.fatigue_cost ?? 0);
  return map;
}

// computeDuration lives in ./builder-groups (A309: also used per group).

/** A309: Warmup / Main / Cooldown section header with the group's total. */
function GroupHeader({
  label,
  icon: Icon,
  iconClassName,
  items,
}: {
  label: string;
  icon?: LucideIcon;
  iconClassName?: string;
  items: GroupedEntry<BuilderEntry>[];
}) {
  return (
    <div className="flex items-center justify-between gap-2 pt-1">
      <h2 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {Icon && <Icon className={`h-3.5 w-3.5 ${iconClassName ?? ""}`} aria-hidden="true" />}
        {label}
      </h2>
      {items.length > 0 && (
        <span className="text-xs tabular-nums text-muted-foreground">
          {items.length} · ~{computeDuration(items.map((g) => g.entry))} min
        </span>
      )}
    </div>
  );
}

const DASHED_ROW =
  "flex w-full items-center gap-2 rounded-lg border border-dashed px-3 text-sm font-medium transition-colors active:scale-[0.99]";

// ── Component ─────────────────────────────────────────────────────────

interface SessionBuilderProps {
  /** Session ID for edit mode. null = create mode. */
  sessionId: string | null;
  /**
   * B356 — notifica alla pagina che ci sono modifiche non salvate. Il pulsante
   * "indietro" sta nella TopBar della pagina, non qui, quindi è la pagina a
   * dover chiedere conferma prima di uscire.
   */
  onDirtyChange?: (dirty: boolean) => void;
}

export function SessionBuilder({ sessionId, onDirtyChange }: SessionBuilderProps) {
  const router = useRouter();
  const isEditMode = !!sessionId;

  // Queries
  const {
    data: existingSession,
    isLoading: loadingSession,
    refetch: refetchSession,
  } = useCustomSession(sessionId);
  const {
    data: catalogData,
    isLoading: loadingCatalog,
    isError: catalogError,
    refetch: refetchCatalog,
  } = useBuilderExercises("", "");

  // Mutations
  const createMutation = useCreateCustomSession();
  const updateMutation = useUpdateCustomSession();
  const deleteMutation = useDeleteCustomSession();

  // Builder state
  const [name, setName] = useState("");
  const [entries, setEntries] = useState<BuilderEntry[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // UI state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [warmupPickerOpen, setWarmupPickerOpen] = useState(false);
  const [cooldownPickerOpen, setCooldownPickerOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [nameError, setNameError] = useState("");
  const [saveError, setSaveError] = useState("");

  // Catalog name lookup: exercise_id → display name
  const catalogNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const ex of catalogData?.exercises ?? []) {
      map.set(ex.id, ex.name);
    }
    return map;
  }, [catalogData]);

  // A304: exercise_id → catalog load model ("Auto load" on weighted rows).
  const catalogLoadModelMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const ex of catalogData?.exercises ?? []) {
      map.set(ex.id, ex.load_model);
    }
    return map;
  }, [catalogData]);

  // Initialize from existing session in edit mode (wait for catalog to resolve names)
  // B355 — idratazione one-shot da dati asincroni (sessione + catalogo): finché
  // la query non risolve i nomi non c'è nulla da mostrare, e la guardia
  // `!initialized` la rende irripetibile. Non è uno stato derivabile in render.
  useEffect(() => {
    if (isEditMode && existingSession && catalogNameMap.size > 0 && !initialized) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setName(existingSession.name);
      setEntries(
        existingSession.exercises.map((ex) => ({
          exercise: ex,
          name: catalogNameMap.get(ex.exercise_id) ?? ex.exercise_id,
        }))
      );
      setInitialized(true);
    }
    if (!isEditMode && !initialized) {
      setInitialized(true);
    }
  }, [isEditMode, existingSession, initialized, catalogNameMap]);

  // Track dirty state
  // B355 — flag "appiccicoso": una volta sporco resta sporco finché il salvataggio
  // non lo azzera, quindi non è derivabile dal render corrente.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (initialized && (name || entries.length > 0)) setIsDirty(true);
  }, [name, entries, initialized]);

  // B356 — lo stato sporco risale alla pagina, che possiede il pulsante indietro.
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  /*
   * B356 — il builder mostrava "Load: 0" sempre, con qualunque esercizio dentro.
   * `fatigueCosts` era uno stato alimentato solo da un `updateFatigueCost` che
   * nessuno chiamava mai, quindi la mappa restava vuota e `computeLoadScore`
   * sommava zeri: `Math.min(85, Math.round(0 * 1.5))` = 0, per costruzione.
   * Il costo di fatica è già nel catalogo (`BuilderExercise.fatigue_cost`): la
   * mappa si costruisce da lì, esattamente come fa `catalogNameMap` sopra e come
   * fa `build_fatigue_map` in backend/engine/load_score.py.
   */
  const fatigueCosts = useMemo(
    () => buildFatigueMap(catalogData?.exercises),
    [catalogData],
  );

  // Computed values
  const loadScore = useMemo(() => computeLoadScore(entries, fatigueCosts), [entries, fatigueCosts]);
  const duration = useMemo(() => computeDuration(entries), [entries]);
  const addedIds = useMemo(() => new Set(entries.map((e) => e.exercise.exercise_id)), [entries]);
  const groups = useMemo(() => groupEntries(entries), [entries]);

  // ── Actions ────────────────────────────────────────────────────────

  // A309: before the cooldown block, so the list shows the order that is played.
  const addExercise = useCallback((exercise: CustomSessionExercise, exerciseName: string) => {
    setEntries((prev) => insertMainEntry(prev, { exercise, name: exerciseName }));
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

  // A309: no confirmation, but an Undo that puts the row back where it was.
  const removeExercise = useCallback((index: number) => {
    const removed = entries[index];
    if (!removed) return;
    setEntries((prev) => prev.filter((_, i) => i !== index));
    toast(`Removed ${removed.name}`, {
      action: {
        label: "Undo",
        onClick: () => setEntries((prev) => restoreEntryAt(prev, removed, index)),
      },
      duration: 6000,
    });
  }, [entries]);

  const moveExercise = useCallback((from: number, direction: -1 | 1) => {
    setEntries((prev) => moveWithinGroup(prev, from, direction));
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
      exercises: entries.map((e) => ({
        exercise_id: e.exercise.exercise_id,
        sets: e.exercise.sets,
        reps: e.exercise.reps ?? undefined,
        work_seconds: e.exercise.work_seconds ?? undefined,
        rest_between_sets_seconds: e.exercise.rest_between_sets_seconds ?? undefined,
        rest_between_reps_seconds: e.exercise.rest_between_reps_seconds ?? undefined,
        load_kg: e.exercise.load_kg || undefined,
        // B364: keep the user's load mode (missing = "anchored" on the server).
        load_mode: e.exercise.load_mode ?? undefined,
        // A298: ladder rows (missing = "fixed" on the server).
        progress_mode: e.exercise.progress_mode ?? undefined,
        notes: e.exercise.notes || undefined,
      })),
    };

    setSaveError("");
    try {
      if (isEditMode && sessionId) {
        await updateMutation.mutateAsync({ id: sessionId, data: payload as Parameters<typeof updateMutation.mutateAsync>[0]["data"] });
      } else {
        await createMutation.mutateAsync(payload as Parameters<typeof createMutation.mutateAsync>[0]);
      }
      setIsDirty(false);
      router.push("/free-session");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setSaveError(msg);
    }
  };

  const handleDelete = async () => {
    if (!sessionId) return;
    try {
      await deleteMutation.mutateAsync(sessionId);
      setIsDirty(false);
      router.push("/free-session");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      setSaveError(msg);
    }
  };

  // ── Editing state ──────────────────────────────────────────────────

  const editingEntry = editingIndex !== null ? entries[editingIndex] : null;

  // Determine field visibility from exercise defaults
  const editingHasReps = editingEntry ? editingEntry.exercise.reps !== null : false;
  const editingHasWork = editingEntry ? editingEntry.exercise.work_seconds !== null : false;
  const editingHasRestBetweenReps = editingEntry ? editingEntry.exercise.rest_between_reps_seconds !== null : false;

  // ── Loading ────────────────────────────────────────────────────────

  if (isEditMode && !initialized && (loadingSession || (loadingCatalog && !!existingSession))) {
    return <BuilderSkeleton />;
  }

  // A309: without the session or the catalog the hydration never runs, and the
  // editor used to sit on an empty form with no explanation.
  if (isEditMode && !initialized && (!existingSession || catalogError)) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-center space-y-3">
        <p className="text-sm text-muted-foreground">Couldn&apos;t load this session</p>
        <Button
          variant="outline"
          className="h-11"
          onClick={() => {
            void refetchSession();
            void refetchCatalog();
          }}
        >
          Retry
        </Button>
      </div>
    );
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const renderCards = (items: GroupedEntry<BuilderEntry>[]) =>
    items.map(({ entry, index: i }) => (
      <BuilderExerciseCard
        key={`${entry.exercise.exercise_id}-${i}`}
        exercise={entry.exercise}
        name={entry.name}
        position={i + 1}
        loadModel={catalogLoadModelMap.get(entry.exercise.exercise_id)}
        canMoveUp={canMoveWithinGroup(entries, i, -1)}
        canMoveDown={canMoveWithinGroup(entries, i, 1)}
        onMoveUp={() => moveExercise(i, -1)}
        onMoveDown={() => moveExercise(i, 1)}
        onEdit={() => setEditingIndex(i)}
      />
    ));

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

      {/* A309: the list in three sections read from entry.tag. The array stays
          in group order (see builder-groups.ts), so this is the played order. */}
      <section className="space-y-2" aria-label="Warmup">
        <GroupHeader label="Warmup" icon={Flame} iconClassName="text-warning" items={groups.warmup} />
        {groups.warmup.length > 0 ? (
          renderCards(groups.warmup)
        ) : (
          <button
            type="button"
            className={`${DASHED_ROW} min-h-11 border-warning/30 text-warning hover:bg-warning/10`}
            onClick={() => setWarmupPickerOpen(true)}
          >
            <Flame className="h-4 w-4" />
            Add warmup
          </button>
        )}
      </section>

      <section className="space-y-2" aria-label="Main">
        <GroupHeader label="Main" items={groups.main} />
        {renderCards(groups.main)}
        <button
          type="button"
          className={`${DASHED_ROW} h-14 border-border text-foreground hover:bg-accent`}
          onClick={() => setPickerOpen(true)}
        >
          <Plus className="h-4 w-4" />
          Add exercise
        </button>
      </section>

      <section className="space-y-2" aria-label="Cooldown">
        <GroupHeader label="Cooldown" icon={Snowflake} iconClassName="text-info" items={groups.cooldown} />
        {groups.cooldown.length > 0 ? (
          renderCards(groups.cooldown)
        ) : (
          <button
            type="button"
            className={`${DASHED_ROW} min-h-11 border-info/30 text-info hover:bg-info/10`}
            onClick={() => setCooldownPickerOpen(true)}
          >
            <Snowflake className="h-4 w-4" />
            Add cooldown
          </button>
        )}
      </section>

      {/* A309: sticky action bar — Load / duration stay in view while editing */}
      <div className="sticky bottom-[var(--nav-h)] z-10 -mx-4 border-t border-border bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        {saveError && <p className="mb-2 text-sm text-danger">{saveError}</p>}
        <div className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold tabular-nums">
              {entries.length > 0 ? `~${duration} min` : "—"}
            </p>
            <p className="text-xs text-muted-foreground tabular-nums">
              Load {loadScore} · {entries.length} exercise{entries.length !== 1 ? "s" : ""}
            </p>
          </div>
          <Button
            className="h-11 min-w-[140px]"
            disabled={!name.trim() || entries.length === 0 || isSaving}
            onClick={handleSave}
          >
            <Save className="h-4 w-4" />
            {isSaving ? "Saving..." : isEditMode ? "Update Session" : "Save Session"}
          </Button>
        </div>
      </div>

      {/* Delete button (edit mode) — kept away from Save */}
      {isEditMode && (
        <Button
          variant="ghost"
          className="mt-8 h-11 w-full text-destructive hover:text-destructive"
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
          onRemove={() => removeExercise(editingIndex)}
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

    </div>
  );
}
