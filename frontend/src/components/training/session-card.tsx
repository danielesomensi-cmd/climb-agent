"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { hasSavedProgress } from "@/lib/guided-session-utils";
import { ChevronDown, Check, X, Undo2, Play, ArrowRightLeft, Trash2, Pencil, Plus, Search, RefreshCw, Mountain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
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
import { ExerciseCard } from "@/components/training/exercise-card";
import { getExercises, addExerciseToSession, removeExerciseFromSession, resolveSession } from "@/lib/api";
import type { SessionSlot, GuidedSessionState, GuidedExercise, Exercise, WeekPlan } from "@/lib/types";
import { expandEquipment, isExerciseCompatible } from "@/lib/equipment-filter";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface SessionCardProps {
  session: SessionSlot;
  date: string;
  gyms?: Gym[];
  homeEquipment?: string[];
  weekPlan?: WeekPlan | null;
  sessionIndex?: number;
  onMarkDone?: () => void;
  onMarkSkipped?: () => void;
  onUndo?: () => void;
  onMove?: () => void;
  onRemove?: () => void;
  onReplan?: () => void;
  onSessionUpdated?: (updatedWeekPlan?: WeekPlan) => void;
}

/** Format session_id into a readable string: replace _ with spaces, capitalize */
function formatSessionName(sessionId: string): string {
  return sessionId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const FEEDBACK_BADGE_STYLE: Record<string, string> = {
  very_easy: "bg-emerald-400/20 text-emerald-300 border-emerald-400/30",
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

/** Resolve location display name */
function getLocationLabel(session: SessionSlot, gyms?: Gym[]): string {
  if (session.location !== "gym") return "Home";
  if (session.gym_id && gyms) {
    const gym = gyms.find((g) => (g.gym_id || g.name) === session.gym_id);
    if (gym) return gym.name;
  }
  if (gyms && gyms.length > 0 && gyms[0].name) return gyms[0].name;
  return "Gym";
}

/** Build a GuidedExercise from a resolver exercise instance */
function buildGuidedExercise(inst: Record<string, unknown>): GuidedExercise {
  const prescription = (inst.prescription ?? {}) as Record<string, unknown>;
  const suggested = (inst.suggested ?? {}) as Record<string, unknown>;
  const boulderTarget = (suggested.suggested_boulder_target ?? {}) as Record<string, unknown>;
  const rightHand = suggested.right_hand as Record<string, unknown> | undefined;
  const leftHand = suggested.left_hand as Record<string, unknown> | undefined;

  return {
    exerciseId: (inst.exercise_id as string) ?? "",
    name: (inst.name as string) ?? ((inst.exercise_id as string) ?? "").replace(/_/g, " "),
    category: (inst.category as string) ?? "",
    blockUid: (inst.block_uid as string) ?? "",
    loadModel: (inst.load_model as string) ?? "",
    unilateral: !!(inst.unilateral ?? rightHand),
    altSides: !!(inst.alt_sides),
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
      gradeLow: boulderTarget.target_grade_low as string | undefined,
      repScheme: suggested.suggested_rep_scheme as string | undefined,
      surface: boulderTarget.surface_selected as string | undefined,
      attemptGuidance: boulderTarget.attempt_guidance as string | undefined,
      restGuidance: boulderTarget.rest_guidance as string | undefined,
      loadSource: suggested.load_source as string | undefined,
      loadWarning: suggested.load_warning as string | undefined,
      rightHand: rightHand ? { externalLoadKg: rightHand.suggested_external_load_kg as number | undefined } : undefined,
      leftHand: leftHand ? { externalLoadKg: leftHand.suggested_external_load_kg as number | undefined } : undefined,
    },
    videoUrl: (inst.video_url as string | undefined) ?? undefined,
    cues: (inst.cues as string[] | undefined) ?? undefined,
    status: "pending",
    feedbackLabel: "ok",
    testField: (inst.attributes as Record<string, unknown> | undefined)?.test_field as string | undefined,
    testUnit: (inst.attributes as Record<string, unknown> | undefined)?.test_unit as string | undefined,
    limitationWarning: inst.limitation_warning as GuidedExercise["limitationWarning"],
    limitationZone: inst.limitation_zone as string | undefined,
    limitationLoadModifier: inst.limitation_load_modifier as number | undefined,
    limitationPrehabFor: inst.limitation_prehab_for as string | undefined,
  };
}

/** Build a GuidedExercise from an instruction_only block */
function buildInstructionStep(block: Record<string, unknown>): GuidedExercise {
  const instructions = (block.instructions ?? {}) as Record<string, unknown>;
  const notes = (instructions.notes ?? []) as string[];
  const options = (instructions.options ?? []) as string[];
  const focus = (instructions.focus ?? []) as string[];
  const duration = instructions.duration_min_range as [number, number] | undefined;
  const blockId = (block.block_id as string) ?? "";
  const blockType = (block.type as string) ?? "";

  return {
    exerciseId: `instruction_${blockId}`,
    name: blockId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    category: blockType,
    blockUid: (block.block_uid as string) ?? blockId,
    loadModel: "",
    isInstructionOnly: true,
    instructionNotes: notes.length > 0 ? notes : undefined,
    instructionOptions: options.length > 0 ? options : undefined,
    instructionFocus: focus.length > 0 ? focus : undefined,
    instructionDuration: duration,
    prescription: {},
    suggested: {},
    status: "pending",
    feedbackLabel: "ok",
  };
}

/** Build GuidedSessionState from a resolved session slot */
function buildGuidedState(
  session: SessionSlot,
  date: string,
): GuidedSessionState | null {
  const resolved = session.resolved as Record<string, unknown> | undefined;
  const resolvedSession = resolved?.resolved_session as Record<string, unknown> | undefined;
  const instances = (resolvedSession?.exercise_instances ?? []) as Array<Record<string, unknown>>;
  const blocks = (resolvedSession?.blocks ?? []) as Array<Record<string, unknown>>;
  if (instances.length === 0 && blocks.length === 0) return null;

  const exercises: GuidedExercise[] = [];
  const usedInstances = new Set<number>();

  for (const block of blocks) {
    const blockUid = (block.block_uid as string) ?? "";
    const selExercises = (block.selected_exercises ?? []) as unknown[];

    if (selExercises.length === 0 && block.instructions) {
      exercises.push(buildInstructionStep(block));
    } else {
      for (let i = 0; i < instances.length; i++) {
        if (!usedInstances.has(i) && (instances[i].block_uid as string) === blockUid) {
          exercises.push(buildGuidedExercise(instances[i]));
          usedInstances.add(i);
        }
      }
    }
  }

  for (let i = 0; i < instances.length; i++) {
    if (!usedInstances.has(i)) {
      exercises.push(buildGuidedExercise(instances[i]));
    }
  }

  if (exercises.length === 0) return null;

  let bodyweightKg: number | undefined;
  for (const inst of instances) {
    const sug = (inst.suggested ?? {}) as Record<string, unknown>;
    const basedOn = sug.based_on as Record<string, number> | undefined;
    if (basedOn?.bodyweight_kg) {
      bodyweightKg = basedOn.bodyweight_kg;
      break;
    }
    const total = sug.suggested_total_load_kg as number | undefined;
    const external = sug.suggested_external_load_kg as number | undefined;
    if (total != null && external != null) {
      bodyweightKg = total - external;
      break;
    }
  }

  const sessionMeta = resolved?.session as Record<string, unknown> | undefined;
  const sessionName = (sessionMeta?.session_name as string) ||
    session.session_id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  // A141: process cue from API response
  const processCue = session.process_cue ?? undefined;

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
    processCue,
  };
}

// B197 Bug 1: shared "Start session" handler. Guards against re-starting an
// already-done session and preserves any pre-existing `startedAt` in localStorage
// so the wall-clock duration survives a /today render race / accidental restart.
function handleStartGuided(
  session: SessionSlot,
  date: string,
  router: ReturnType<typeof useRouter>,
): void {
  // Don't allow restarting a server-side completed session — the duration
  // would otherwise be reset and clobber the real value via the resubmit path.
  if (session.status === "done" || session.status === "skipped") {
    return;
  }

  // A207: custom sessions have no guided runtime — route to the read-only view.
  if (session.is_custom && session.custom_session_id) {
    router.push(`/session-builder/${session.custom_session_id}/view`);
    return;
  }

  // B181: don't overwrite saved progress — resume instead.
  if (hasSavedProgress(date, session.session_id)) {
    router.push(`/guided/${date}/${session.session_id}`);
    return;
  }

  const guidedState = buildGuidedState(session, date);
  if (!guidedState) return;

  const userId = window.Clerk?.session ? "clerk" : "";
  const key = `guided_session_${userId}_${date}_${session.session_id}`;

  // B197: if any prior state exists for this slot (even one without
  // visible progress that hasSavedProgress would skip), preserve its
  // startedAt so the duration measured at submit time isn't reset.
  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      const prior = JSON.parse(raw) as GuidedSessionState;
      if (prior?.startedAt) {
        guidedState.startedAt = prior.startedAt;
      }
    }
  } catch {
    /* ignore — fall through to fresh startedAt */
  }

  localStorage.setItem(key, JSON.stringify(guidedState));
  router.push(`/guided/${date}/${session.session_id}`);
}

// Equipment expansion + compatibility logic extracted to @/lib/equipment-filter

// ─── Add Exercise Dialog ─────────────────────────────────────────────

function AddExerciseDialog({
  open,
  onOpenChange,
  date,
  sessionIndex,
  weekPlan,
  availableEquipment,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  date: string;
  sessionIndex: number;
  weekPlan: WeekPlan;
  availableEquipment: Set<string> | null;
  onSuccess: (updatedPlan?: WeekPlan) => void;
}) {
  const [catalog, setCatalog] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Exercise | null>(null);
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(10);
  const [workSeconds, setWorkSeconds] = useState<number | null>(null);
  const [loadKg, setLoadKg] = useState<number | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [isTestMeasurement, setIsTestMeasurement] = useState(false);
  const [isDurationBased, setIsDurationBased] = useState(false);

  useEffect(() => {
    if (open && catalog.length === 0) {
      setLoading(true);
      getExercises()
        .then((data) => setCatalog(data.exercises))
        .catch((err) => { console.error("Failed to load exercise catalog:", err); })
        .finally(() => setLoading(false));
    }
  }, [open, catalog.length]);

  // Reset showAll when dialog closes
  useEffect(() => {
    if (!open) setShowAll(false);
  }, [open]);

  const filtered = useMemo(() => {
    let result = catalog;

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.exercise_id.toLowerCase().includes(q) ||
          (Array.isArray(e.domain) ? e.domain.some(d => d.toLowerCase().includes(q)) : String(e.domain ?? "").toLowerCase().includes(q)) ||
          (e.category?.toLowerCase().includes(q)) ||
          (e.description?.toLowerCase().includes(q))
      );
    }

    // Equipment filter (skip if no equipment context or showAll)
    if (availableEquipment && !showAll) {
      result = result.filter((e) => isExerciseCompatible(e, availableEquipment));
    }

    return result;
  }, [catalog, search, availableEquipment, showAll]);

  // Count hidden exercises for the toggle label
  const hiddenCount = useMemo(() => {
    if (!availableEquipment || showAll) return 0;
    // Count how many in the text-filtered set are hidden by equipment
    let textFiltered = catalog;
    if (search.trim()) {
      const q = search.toLowerCase();
      textFiltered = textFiltered.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.exercise_id.toLowerCase().includes(q) ||
          (Array.isArray(e.domain) ? e.domain.some(d => d.toLowerCase().includes(q)) : String(e.domain ?? "").toLowerCase().includes(q)) ||
          (e.category?.toLowerCase().includes(q)) ||
          (e.description?.toLowerCase().includes(q))
      );
    }
    return textFiltered.length - filtered.length;
  }, [catalog, search, availableEquipment, showAll, filtered.length]);

  const selectExercise = useCallback((ex: Exercise) => {
    setSelected(ex);
    const defaults = ex.prescription_defaults ?? {};
    const testMeas = ex.category === "test_measurement";
    const ws = (defaults.work_seconds as number | null) ?? null;
    const durationBased = !testMeas && ws != null && ws > 0;
    setIsTestMeasurement(testMeas);
    setIsDurationBased(durationBased);
    setSets((defaults.sets as number) ?? (testMeas ? 1 : 3));
    setReps((defaults.reps as number) ?? (testMeas ? 0 : 10));
    setWorkSeconds(ws);
    setLoadKg((defaults.load_kg as number | undefined) ?? 0);
    setError(null);
  }, []);

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      const overrides: Record<string, unknown> = { sets };
      if (isTestMeasurement) {
        // test_measurement: no reps, no load, no work_seconds — user reports result in guided mode
        overrides.reps = null;
        overrides.work_seconds = null;
      } else if (isDurationBased) {
        overrides.work_seconds = workSeconds;
        if (reps) overrides.reps = reps;
      } else {
        overrides.reps = reps;
      }
      if (loadKg != null && !isTestMeasurement) overrides.load_kg = loadKg;
      const payload = {
        date,
        session_index: sessionIndex,
        exercise_id: selected.exercise_id,
        prescription_override: overrides,
        week_plan: weekPlan,
      };
      const result = await addExerciseToSession(payload);
      onOpenChange(false);
      setSelected(null);
      setSearch("");
      onSuccess(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add exercise");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Add Exercise</DialogTitle>
          <DialogDescription>Search the catalog and add an exercise to this session.</DialogDescription>
        </DialogHeader>

        {!selected ? (
          <div className="flex flex-col gap-3 flex-1 min-h-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                placeholder="Search exercises..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
                autoFocus
              />
            </div>
            {availableEquipment && (
              <div className="flex items-center justify-between">
                <button
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => setShowAll((v) => !v)}
                >
                  {showAll
                    ? "Show compatible only"
                    : `Show all exercises${hiddenCount > 0 ? ` (+${hiddenCount} hidden)` : ""}`}
                </button>
              </div>
            )}
            <div className="flex-1 overflow-y-auto space-y-1 min-h-0 max-h-[50vh]">
              {loading && <p className="text-xs text-muted-foreground p-2">Loading catalog...</p>}
              {!loading && filtered.length === 0 && (
                <p className="text-xs text-muted-foreground p-2">No exercises found</p>
              )}
              {filtered.map((ex) => {
                const incompatible = showAll && availableEquipment && !isExerciseCompatible(ex, availableEquipment);
                return (
                  <button
                    key={ex.exercise_id}
                    className={`w-full text-left px-3 py-2 rounded-md hover:bg-accent transition-colors ${incompatible ? "opacity-50" : ""}`}
                    onClick={() => selectExercise(ex)}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium">{ex.name}</span>
                      {incompatible && (
                        <Badge variant="outline" className="text-[10px] text-yellow-500 border-yellow-500/30">
                          Missing equipment
                        </Badge>
                      )}
                    </div>
                    {ex.description && (
                      <div className="text-xs text-muted-foreground/80 truncate">{ex.description}</div>
                    )}
                    <div className="text-xs text-muted-foreground">
                      {Array.isArray(ex.domain) ? ex.domain.join(", ") : ex.domain}
                      {ex.category && ` · ${ex.category}`}
                      {ex.equipment_required?.length > 0 && ` · ${ex.equipment_required.join(", ")}`}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-md border p-3">
              <div className="text-sm font-medium">{selected.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{Array.isArray(selected.domain) ? selected.domain.join(", ") : selected.domain}</div>
            </div>

            {isTestMeasurement ? (
              <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-sm font-medium">1 × max attempt</p>
                <p className="text-xs text-muted-foreground mt-1">
                  You&apos;ll record the result during the guided session.
                </p>
              </div>
            ) : (
              <div className={`grid ${isDurationBased ? "grid-cols-3" : "grid-cols-3"} gap-3`}>
                <div>
                  <Label className="text-xs">Sets</Label>
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={sets}
                    onChange={(e) => setSets(Number(e.target.value))}
                  />
                </div>
                {isDurationBased ? (
                  <div>
                    <Label className="text-xs">Duration (s)</Label>
                    <Input
                      type="number"
                      min={1}
                      max={600}
                      value={workSeconds ?? 0}
                      onChange={(e) => setWorkSeconds(Number(e.target.value))}
                    />
                  </div>
                ) : (
                  <div>
                    <Label className="text-xs">Reps</Label>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={reps}
                      onChange={(e) => setReps(Number(e.target.value))}
                    />
                  </div>
                )}
                <div>
                  <Label className="text-xs">Additional weight (kg)</Label>
                  <Input
                    type="number"
                    min={0}
                    step={0.5}
                    value={loadKg ?? 0}
                    onChange={(e) => setLoadKg(e.target.value ? Number(e.target.value) : 0)}
                  />
                  <p className="text-[10px] text-muted-foreground mt-1">Added to bodyweight. Enter 0 for BW only.</p>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-red-500">{error}</p>}

            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setSelected(null)}>
                Back
              </Button>
              <Button className="flex-1" onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Adding..." : "Add exercise"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Exercise Item Wrapper ───────────────────────────────────────────

function ExerciseItemWrapper({ children, canEdit, onRemove }: {
  children: React.ReactNode;
  canEdit: boolean;
  onRemove?: () => void;
}) {
  return (
    <div className="relative">
      {children}
      {canEdit && onRemove && (
        <button
          className="absolute top-1.5 right-1.5 flex items-center justify-center w-7 h-7 rounded-full text-muted-foreground/30 hover:text-red-500 hover:bg-red-500/10 transition-colors"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
        >
          <Trash2 className="size-3.5" />
        </button>
      )}
    </div>
  );
}

// ─── Session Card ────────────────────────────────────────────────────

export function SessionCard({
  session,
  date,
  gyms,
  homeEquipment,
  weekPlan,
  sessionIndex = 0,
  onMarkDone,
  onMarkSkipped,
  onUndo,
  onMove,
  onRemove,
  onReplan,
  onSessionUpdated,
}: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [addExerciseOpen, setAddExerciseOpen] = useState(false);
  const [exerciseToRemove, setExerciseToRemove] = useState<{ index: number; name: string } | null>(null);
  // A210: ephemeral "Boulder only" override (React state only, never persisted)
  const [boulderOverride, setBoulderOverride] = useState<Record<string, unknown> | null>(null);
  const [boulderOverrideLoading, setBoulderOverrideLoading] = useState(false);
  const [boulderOverrideError, setBoulderOverrideError] = useState<string | null>(null);
  const router = useRouter();

  // A210: effective resolved session — override takes precedence over the planned one
  const effectiveResolved = (boulderOverride ?? session.resolved) as Record<string, unknown> | undefined;

  // Exercise instances from effective resolved session
  const exerciseInstances = useMemo(() => {
    const rs = effectiveResolved?.resolved_session as Record<string, unknown> | undefined;
    return (rs?.exercise_instances ?? []) as Array<Record<string, unknown>>;
  }, [effectiveResolved]);

  const handleRemoveExercise = useCallback(async (exerciseIndex: number) => {
    if (!weekPlan) return;
    try {
      const result = await removeExerciseFromSession({
        date,
        session_index: sessionIndex,
        exercise_index: exerciseIndex,
        week_plan: weekPlan,
      });
      onSessionUpdated?.(result.week_plan);
    } catch (err) {
      console.error("[B155d] remove exercise FAILED:", err);
    }
  }, [weekPlan, date, sessionIndex, onSessionUpdated]);

  // Compute available equipment for this session (expanded with implicit items)
  const availableEquipment = useMemo<Set<string> | null>(() => {
    if (session.location === "home" && homeEquipment && homeEquipment.length > 0) {
      return expandEquipment(homeEquipment, "home");
    }
    if (session.location === "gym" && gyms) {
      const gym = session.gym_id
        ? gyms.find((g) => (g.gym_id || g.name) === session.gym_id)
        : gyms[0];
      if (gym) return expandEquipment(gym.equipment, "gym");
    }
    return null;
  }, [session.location, session.gym_id, gyms, homeEquipment]);

  const isHard = session.tags?.hard === true;
  const isFinger = session.tags?.finger === true;
  const isDone = session.status === "done";
  const isSkipped = session.status === "skipped";
  const isFinalized = isDone || isSkipped;
  const locationLabel = getLocationLabel(session, gyms);
  const hasExercises = (() => {
    if (session.is_custom) return (session.exercises ?? []).length > 0;
    const rs = effectiveResolved?.resolved_session as Record<string, unknown> | undefined;
    return ((rs?.exercise_instances ?? []) as unknown[]).length > 0;
  })();
  const hasLoadingPin = (() => {
    const rs = effectiveResolved?.resolved_session as Record<string, unknown> | undefined;
    const instances = (rs?.exercise_instances ?? []) as Array<Record<string, unknown>>;
    return instances.some((i) => String(i.exercise_id ?? "").startsWith("lp_"));
  })();

  // A210: trigger detection — based on the ORIGINAL resolved session, not the override.
  // Button shows iff a rope-dependent exercise was scheduled for this planned session.
  const originalResolved = session.resolved as Record<string, unknown> | undefined;
  const originalSessionMeta = originalResolved?.session as Record<string, unknown> | undefined;
  const boulderFallbackId = (originalSessionMeta?.boulder_fallback as string | null | undefined) ?? null;
  const originalSessionId = (originalSessionMeta?.session_id as string | undefined) ?? session.session_id;
  const hasRopeExercise = useMemo(() => {
    const rs = originalResolved?.resolved_session as Record<string, unknown> | undefined;
    const instances = (rs?.exercise_instances ?? []) as Array<Record<string, unknown>>;
    return instances.some((ex) => {
      const eq = (ex.equipment_required ?? []) as string[];
      return Array.isArray(eq) && eq.includes("gym_routes");
    });
  }, [originalResolved]);
  const canSwitchToBoulder =
    boulderOverride === null &&
    !isFinalized &&
    hasRopeExercise &&
    (boulderFallbackId !== null || !!availableEquipment);

  const handleBoulderOnly = useCallback(async () => {
    setBoulderOverrideLoading(true);
    setBoulderOverrideError(null);
    try {
      if (boulderFallbackId) {
        // Mechanism A: session_id swap to dedicated boulder session
        const result = await resolveSession(boulderFallbackId);
        setBoulderOverride(result.resolved as unknown as Record<string, unknown>);
      } else {
        // Mechanism B: equipment override — same session_id, strip gym_routes
        const override = availableEquipment
          ? Array.from(availableEquipment).filter((e) => e !== "gym_routes")
          : [];
        const result = await resolveSession(originalSessionId, undefined, override);
        setBoulderOverride(result.resolved as unknown as Record<string, unknown>);
      }
    } catch (err) {
      console.error("[A210] boulder override failed:", err);
      setBoulderOverrideError("Could not adapt this session. Try again.");
    } finally {
      setBoulderOverrideLoading(false);
    }
  }, [boulderFallbackId, availableEquipment, originalSessionId]);

  const handleUndoBoulderOverride = useCallback(() => {
    setBoulderOverride(null);
    setBoulderOverrideError(null);
  }, []);

  // A210: copy variant — route_projecting → limit_boulder is an equivalent stimulus,
  // aerobic/endurance swaps trade aerobic capacity for volume bouldering.
  const boulderCopyVariant: "equivalent" | "volume_swap" =
    originalSessionId === "route_projecting_gym" ? "equivalent" : "volume_swap";

  return (
    <>
      <div className="relative">
      {boulderOverride !== null && (
        <div className="mb-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 flex items-start gap-2">
          <Mountain className="size-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium">Boulder only — session adapted for today.</p>
            {boulderCopyVariant === "volume_swap" && (
              <p className="mt-0.5 text-amber-200/70">
                Volume climbing replaces aerobic endurance. Aerobic stimulus is not replicable without rope.
              </p>
            )}
          </div>
          <button
            className="text-amber-200 hover:text-white underline text-xs shrink-0"
            onClick={handleUndoBoulderOverride}
          >
            Undo
          </button>
        </div>
      )}
      {boulderOverrideError && (
        <div className="mb-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
          {boulderOverrideError}
        </div>
      )}
      <Card className="gap-0 py-0 overflow-hidden">
        {/* Header — clickable to expand */}
        <CardHeader
          className="cursor-pointer select-none py-3"
          onClick={() => setExpanded((prev) => !prev)}
        >
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm flex items-center gap-1.5">
              <span>
                {session.is_custom
                  ? (session.name || formatSessionName(session.session_id))
                  : ((session.resolved as Record<string, Record<string, string>> | undefined)?.session?.session_name || formatSessionName(session.session_id))}
              </span>
              {session.is_custom && (
                <Badge className="bg-primary/20 text-primary border-primary/40 text-[10px]">
                  Custom
                </Badge>
              )}
              {boulderOverride !== null && (
                <Badge className="bg-amber-600 hover:bg-amber-600 text-white text-[10px] gap-1 px-1.5 py-0">
                  <Mountain className="size-2.5" />
                  Boulder
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-1.5">
              {/* Edit actions button */}
              <button
                className="flex items-center justify-center min-w-[44px] min-h-[44px] bg-white/10 rounded-lg p-1.5 text-slate-300 hover:bg-white/20 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setDrawerOpen(true);
                }}
                aria-label="Session actions"
              >
                <Pencil className="size-[18px]" />
              </button>
              <ChevronDown
                className={`size-5 shrink-0 text-slate-300 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              />
            </div>
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
            {hasLoadingPin && (
              <Badge className="bg-purple-500 text-white text-[10px]">
                Loading Pin
              </Badge>
            )}
            {session.estimated_load_score != null && (
              <Badge variant="outline" className="text-[10px]">
                Load: {session.estimated_load_score}
              </Badge>
            )}
            {!isDone && !isSkipped && (() => {
              const targetMin = (effectiveResolved as Record<string, Record<string, unknown>> | undefined)?.session?.target_duration_min as number | undefined;
              if (!targetMin) return null;
              return (
                <Badge variant="outline" className="text-[10px] text-slate-400">
                  ~{targetMin} min
                </Badge>
              );
            })()}
            {isDone && (() => {
              // B217: only show a duration when we have a measured one. No
              // slot-table fallback — "Completed" alone is the honest signal.
              const hasReal = session.session_duration_seconds != null && session.session_duration_seconds > 0;
              return (
                <Badge className="bg-green-600 text-[10px]">
                  <span className="text-white">Completed</span>
                  {hasReal && (
                    <span className="text-white">{` · ${Math.round(session.session_duration_seconds! / 60)} min`}</span>
                  )}
                </Badge>
              );
            })()}
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

          {/* B136: Test results summary in header (visible without expanding) */}
          {isDone && session.actual_exercises && session.actual_exercises.length > 0 && (() => {
            const results: { label: string; value: string }[] = [];
            for (const ae of session.actual_exercises) {
              if (ae.used_total_load_kg != null && ae.exercise_id?.includes("max_hang")) {
                results.push({ label: "Max Hang", value: `${ae.used_total_load_kg} kg` });
              } else if (ae.completed_reps != null && ae.exercise_id?.includes("repeater")) {
                results.push({ label: "Repeater", value: `${ae.completed_reps} reps` });
              } else if ((ae as Record<string, unknown>).max_hang_duration_20mm_seconds != null) {
                results.push({ label: "Duration", value: `${(ae as Record<string, unknown>).max_hang_duration_20mm_seconds}s` });
              } else if ((ae as Record<string, unknown>).hip_flexibility_cm != null) {
                results.push({ label: "Hip Flex", value: `${(ae as Record<string, unknown>).hip_flexibility_cm} cm` });
              } else if ((ae as Record<string, unknown>).l_sit_hold_seconds != null) {
                results.push({ label: "L-sit", value: `${(ae as Record<string, unknown>).l_sit_hold_seconds}s` });
              }
            }
            if (results.length === 0) return null;
            return (
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5">
                {results.map((r) => (
                  <p key={r.label} className="text-[11px] text-amber-400 font-medium">
                    {r.label}: {r.value}
                  </p>
                ))}
              </div>
            );
          })()}
        </CardHeader>

        {/* Expanded content */}
        {expanded && (
          <CardContent className="pt-0 pb-3 space-y-3">
            {/* A207: custom sessions have exercises inline — no resolved blocks to render. */}
            {session.is_custom ? (
              (session.exercises ?? []).length === 0 ? (
                <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                  No exercises
                </div>
              ) : (
                <div className="space-y-1.5">
                  {(session.exercises ?? []).map((ex, i) => {
                    const prescription: string[] = [];
                    if (ex.reps != null) prescription.push(`${ex.sets}\u00d7${ex.reps}`);
                    else if (ex.work_seconds != null) prescription.push(`${ex.sets}\u00d7${ex.work_seconds}s`);
                    else prescription.push(`${ex.sets} sets`);
                    if (ex.load_kg > 0) prescription.push(`${ex.load_kg}kg`);
                    if (ex.rest_between_sets_seconds != null) prescription.push(`rest ${ex.rest_between_sets_seconds}s`);
                    return (
                      <div key={`${ex.exercise_id}-${i}`} className="rounded-md border px-3 py-2 text-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">
                            {ex.exercise_id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                          </span>
                          <span className="text-[11px] text-muted-foreground shrink-0">
                            {prescription.join(" \u00b7 ")}
                          </span>
                        </div>
                        {ex.notes && (
                          <p className="text-xs text-muted-foreground mt-0.5">{ex.notes}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )
            ) : (() => {
              const rs = effectiveResolved?.resolved_session as Record<string, unknown> | undefined;
              const allBlocks = (rs?.blocks ?? []) as Array<Record<string, unknown>>;

              const allInstances = exerciseInstances;

              if (allInstances.length === 0 && allBlocks.length === 0) {
                return (
                  <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                    No exercises resolved
                  </div>
                );
              }

              // Block-based grouping for display
              const items: Array<{ type: "instruction"; block: Record<string, unknown>; visualPos?: undefined; moduleRole?: undefined } | { type: "exercise"; inst: Record<string, unknown>; visualPos: number; moduleRole?: string }> = [];
              const usedIdx = new Set<number>();
              let exerciseCounter = 0;

              for (const block of allBlocks) {
                const blockUid = (block.block_uid as string) ?? "";
                const selEx = (block.selected_exercises ?? []) as unknown[];
                const blockModuleRole = (block.module_role ?? block.type) as string | undefined;

                if (selEx.length === 0 && block.instructions) {
                  items.push({ type: "instruction", block });
                } else {
                  for (let i = 0; i < allInstances.length; i++) {
                    if (!usedIdx.has(i) && (allInstances[i].block_uid as string) === blockUid) {
                      items.push({ type: "exercise", inst: allInstances[i], visualPos: exerciseCounter++, moduleRole: blockModuleRole });
                      usedIdx.add(i);
                    }
                  }
                }
              }
              for (let i = 0; i < allInstances.length; i++) {
                if (!usedIdx.has(i)) {
                  items.push({ type: "exercise", inst: allInstances[i], visualPos: exerciseCounter++ });
                }
              }

              const canEditExercises = !isFinalized && !!weekPlan;

              const renderExerciseCard = (ex: Record<string, unknown>, i: number, moduleRole?: string) => {
                const prescription = (ex.prescription ?? {}) as Record<string, unknown>;
                const suggested = (ex.suggested ?? {}) as Record<string, unknown>;
                const exerciseId = (ex.exercise_id as string) ?? "";
                const actualMatch = session.actual_exercises?.find(
                  (a) => a.exercise_id === exerciseId && !a.hand,
                );
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
                      category: (ex.category as string) ?? undefined,
                      testField: (ex.attributes as Record<string, unknown> | undefined)?.test_field as string | undefined,
                    }}
                    feedbackLevel={session.exercise_feedback?.[exerciseId]}
                    actual={actualMatch}
                    rawExercise={ex}
                    moduleRole={moduleRole}
                  />
                );
              };

              return (
                <div className="space-y-1.5">
                  {items.map((item, i) => {
                    if (item.type === "instruction") {
                      const instr = (item.block.instructions ?? {}) as Record<string, unknown>;
                      const notes = (instr.notes ?? []) as string[];
                      const dur = instr.duration_min_range as [number, number] | undefined;
                      const blockId = (item.block.block_id as string) ?? "";
                      return (
                        <div key={`instr-${i}`} className="flex items-start gap-2 rounded-md border border-primary/20 bg-primary/5 p-2.5">
                          <span className="text-primary mt-0.5 text-xs font-medium shrink-0">
                            {dur ? `${dur[0]}–${dur[1]} min` : ""}
                          </span>
                          <div className="text-xs text-muted-foreground">
                            <span className="font-medium text-foreground">
                              {blockId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                            </span>
                            {notes[0] && <span className="ml-1">— {notes[0]}</span>}
                          </div>
                        </div>
                      );
                    }
                    const exName = (item.inst.name as string) ?? (item.inst.exercise_id as string) ?? "";
                    return (
                      <ExerciseItemWrapper
                        key={`exercise-${item.visualPos}`}
                        canEdit={canEditExercises}
                        onRemove={canEditExercises && allInstances.length > 1 ? () => setExerciseToRemove({ index: item.visualPos, name: exName }) : undefined}
                      >
                        {renderExerciseCard(item.inst, i, item.moduleRole)}
                      </ExerciseItemWrapper>
                    );
                  })}
                </div>
              );
            })()}

            {/* Action buttons — planned sessions: Start / Done / Skip only */}
            {!isFinalized && (
              <div className="flex flex-wrap items-center gap-1.5">
                {hasExercises && (
                  <Button
                    size="sm"
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleStartGuided(session, date, router);
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
              </div>
            )}


            {/* Hint text for planned sessions with exercises */}
            {!isFinalized && hasExercises && (
              <p className="text-[11px] text-muted-foreground/60">
                Tap Start session to begin your guided workout
              </p>
            )}
          </CardContent>
        )}
      </Card>

      {/* FAB — Start session (visible without expanding the card) */}
      {!isFinalized && hasExercises && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleStartGuided(session, date, router);
          }}
          className="absolute bottom-[-16px] right-4 z-10 w-11 h-11 rounded-full bg-green-500 flex items-center justify-center shadow-lg active:scale-95 transition-transform"
          aria-label="Start session"
        >
          <Play className="w-5 h-5 text-white ml-0.5" />
        </button>
      )}
      </div>

      {/* ⋯ Bottom sheet drawer */}
      <Drawer open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>{session.is_custom ? (session.name || formatSessionName(session.session_id)) : ((session.resolved as Record<string, Record<string, string>> | undefined)?.session?.session_name || formatSessionName(session.session_id))}</DrawerTitle>
            <DrawerDescription>
              {(() => {
                // B217: drop slot-table fallback. Show duration only when measured.
                const hasReal = session.session_duration_seconds != null && session.session_duration_seconds > 0;
                const status = isDone ? "Completed" : isSkipped ? "Skipped" : "Planned";
                const durSegment = isDone && hasReal
                  ? ` · ${Math.round(session.session_duration_seconds! / 60)} min`
                  : "";
                return `${status}${durSegment} · ${locationLabel} · ${formatSlot(session.slot)}`;
              })()}
            </DrawerDescription>
          </DrawerHeader>
          <div className="px-4 pb-6 space-y-1">
            {/* Add Exercise — not supported for custom (user-owned, edit via builder) */}
            {weekPlan && !session.is_custom && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left"
                  onClick={() => {
                    setDrawerOpen(false);
                    setTimeout(() => setAddExerciseOpen(true), 150);
                  }}
                >
                  <Plus className="size-5 text-muted-foreground" />
                  <span className="text-sm">Add exercise</span>
                </button>
              </DrawerClose>
            )}

            {/* Modify session — indoor, planned only (bypassed for custom: no replanner) */}
            {!isFinalized && !session.is_custom && onReplan && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left"
                  onClick={() => onReplan()}
                >
                  <RefreshCw className="size-5 text-muted-foreground" />
                  <span className="text-sm">Modify session</span>
                </button>
              </DrawerClose>
            )}

            {/* A210: Boulder only — ephemeral override, planned only, rope-dependent session only */}
            {canSwitchToBoulder && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left disabled:opacity-50"
                  disabled={boulderOverrideLoading}
                  onClick={() => {
                    setDrawerOpen(false);
                    setTimeout(() => {
                      void handleBoulderOnly();
                    }, 150);
                  }}
                >
                  <Mountain className="size-5 text-muted-foreground" />
                  <span className="text-sm">Boulder only (today)</span>
                </button>
              </DrawerClose>
            )}

            {/* Move — planned only */}
            {!isFinalized && onMove && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left"
                  onClick={() => onMove()}
                >
                  <ArrowRightLeft className="size-5 text-muted-foreground" />
                  <span className="text-sm">Move session</span>
                </button>
              </DrawerClose>
            )}

            {/* Remove — planned only */}
            {!isFinalized && onRemove && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left text-red-500"
                  onClick={() => {
                    setDrawerOpen(false);
                    setTimeout(() => setConfirmRemove(true), 150);
                  }}
                >
                  <Trash2 className="size-5" />
                  <span className="text-sm">Remove session</span>
                </button>
              </DrawerClose>
            )}

            {/* Undo — finalized only */}
            {isFinalized && onUndo && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left"
                  onClick={() => onUndo()}
                >
                  <Undo2 className="size-5 text-muted-foreground" />
                  <span className="text-sm">{isDone ? "Undo completion" : "Undo skip"}</span>
                </button>
              </DrawerClose>
            )}
          </div>
        </DrawerContent>
      </Drawer>

      {/* Remove confirmation AlertDialog */}
      <AlertDialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {formatSessionName(session.session_id)}?</AlertDialogTitle>
            <AlertDialogDescription>
              This session will be removed from your plan. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => onRemove?.()}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Remove Exercise confirmation (A153) */}
      <AlertDialog open={!!exerciseToRemove} onOpenChange={(open) => { if (!open) setExerciseToRemove(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove exercise?</AlertDialogTitle>
            <AlertDialogDescription>
              Remove &ldquo;{exerciseToRemove?.name}&rdquo; from this session?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (exerciseToRemove) handleRemoveExercise(exerciseToRemove.index);
                setExerciseToRemove(null);
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Add Exercise Dialog */}
      {weekPlan && (
        <AddExerciseDialog
          open={addExerciseOpen}
          onOpenChange={setAddExerciseOpen}
          date={date}
          sessionIndex={sessionIndex}
          weekPlan={weekPlan}
          availableEquipment={availableEquipment}
          onSuccess={(updatedPlan) => onSessionUpdated?.(updatedPlan)}
        />
      )}
    </>
  );
}
