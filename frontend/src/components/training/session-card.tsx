"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, Check, X, Undo2, Play, ArrowRightLeft, Trash2, MoreHorizontal, Plus, Search } from "lucide-react";
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
import { ExerciseCard } from "@/components/training/exercise-card";
import { getExercises, addExerciseToSession } from "@/lib/api";
import type { SessionSlot, GuidedSessionState, GuidedExercise, Exercise, WeekPlan } from "@/lib/types";

interface Gym {
  gym_id?: string;
  name: string;
  equipment: string[];
}

interface SessionCardProps {
  session: SessionSlot;
  date: string;
  gyms?: Gym[];
  weekPlan?: WeekPlan | null;
  sessionIndex?: number;
  onMarkDone?: () => void;
  onMarkSkipped?: () => void;
  onUndo?: () => void;
  onMove?: () => void;
  onRemove?: () => void;
  onReplan?: () => void;
  onSessionUpdated?: () => void;
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

// ─── Add Exercise Dialog ─────────────────────────────────────────────

function AddExerciseDialog({
  open,
  onOpenChange,
  date,
  sessionIndex,
  weekPlan,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  date: string;
  sessionIndex: number;
  weekPlan: WeekPlan;
  onSuccess: () => void;
}) {
  const [catalog, setCatalog] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Exercise | null>(null);
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(10);
  const [loadKg, setLoadKg] = useState<number | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && catalog.length === 0) {
      setLoading(true);
      getExercises()
        .then((data) => setCatalog(data.exercises))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [open, catalog.length]);

  const filtered = useMemo(() => {
    if (!search.trim()) return catalog.slice(0, 30);
    const q = search.toLowerCase();
    return catalog.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.exercise_id.toLowerCase().includes(q) ||
        e.domain?.toLowerCase().includes(q)
    );
  }, [catalog, search]);

  const selectExercise = useCallback((ex: Exercise) => {
    setSelected(ex);
    const defaults = ex.prescription_defaults ?? {};
    setSets((defaults.sets as number) ?? 3);
    setReps((defaults.reps as number) ?? 10);
    setLoadKg(defaults.load_kg as number | undefined);
    setError(null);
  }, []);

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      const overrides: Record<string, unknown> = { sets, reps };
      if (loadKg != null) overrides.load_kg = loadKg;
      await addExerciseToSession({
        date,
        session_index: sessionIndex,
        exercise_id: selected.exercise_id,
        prescription_override: overrides,
        week_plan: weekPlan,
      });
      onOpenChange(false);
      setSelected(null);
      setSearch("");
      onSuccess();
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
            <div className="flex-1 overflow-y-auto space-y-1 min-h-0 max-h-[50vh]">
              {loading && <p className="text-xs text-muted-foreground p-2">Loading catalog...</p>}
              {!loading && filtered.length === 0 && (
                <p className="text-xs text-muted-foreground p-2">No exercises found</p>
              )}
              {filtered.map((ex) => (
                <button
                  key={ex.exercise_id}
                  className="w-full text-left px-3 py-2 rounded-md hover:bg-accent transition-colors"
                  onClick={() => selectExercise(ex)}
                >
                  <div className="text-sm font-medium">{ex.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {ex.domain} {ex.equipment_required?.length > 0 && `· ${ex.equipment_required.join(", ")}`}
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-md border p-3">
              <div className="text-sm font-medium">{selected.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{selected.domain}</div>
            </div>

            <div className="grid grid-cols-3 gap-3">
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
              <div>
                <Label className="text-xs">Load (kg)</Label>
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  value={loadKg ?? ""}
                  placeholder="BW"
                  onChange={(e) => setLoadKg(e.target.value ? Number(e.target.value) : undefined)}
                />
              </div>
            </div>

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

// ─── Session Card ────────────────────────────────────────────────────

export function SessionCard({
  session,
  date,
  gyms,
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
    <>
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
            <div className="flex items-center gap-1">
              {/* More actions button */}
              <button
                className="flex items-center justify-center size-8 min-w-[44px] min-h-[44px] rounded-md text-muted-foreground hover:bg-accent transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setDrawerOpen(true);
                }}
                aria-label="Session actions"
              >
                <MoreHorizontal className="size-4" />
              </button>
              {expanded ? (
                <ChevronUp className="size-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
              )}
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
            {/* Exercise list from resolved session (with instruction blocks) */}
            {(() => {
              const rs = (
                session.resolved as Record<string, unknown> | undefined
              )?.resolved_session as Record<string, unknown> | undefined;
              const allInstances = (rs?.exercise_instances ?? []) as Array<Record<string, unknown>>;
              const allBlocks = (rs?.blocks ?? []) as Array<Record<string, unknown>>;

              if (allInstances.length === 0 && allBlocks.length === 0) {
                return (
                  <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                    No exercises resolved
                  </div>
                );
              }

              const items: Array<{ type: "instruction"; block: Record<string, unknown> } | { type: "exercise"; inst: Record<string, unknown> }> = [];
              const usedIdx = new Set<number>();

              for (const block of allBlocks) {
                const blockUid = (block.block_uid as string) ?? "";
                const selEx = (block.selected_exercises ?? []) as unknown[];

                if (selEx.length === 0 && block.instructions) {
                  items.push({ type: "instruction", block });
                } else {
                  for (let i = 0; i < allInstances.length; i++) {
                    if (!usedIdx.has(i) && (allInstances[i].block_uid as string) === blockUid) {
                      items.push({ type: "exercise", inst: allInstances[i] });
                      usedIdx.add(i);
                    }
                  }
                }
              }
              for (let i = 0; i < allInstances.length; i++) {
                if (!usedIdx.has(i)) items.push({ type: "exercise", inst: allInstances[i] });
              }

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
                    const ex = item.inst;
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
          </CardContent>
        )}
      </Card>

      {/* ⋯ Bottom sheet drawer */}
      <Drawer open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>{formatSessionName(session.session_id)}</DrawerTitle>
            <DrawerDescription>
              {isDone ? "Completed" : isSkipped ? "Skipped" : "Planned"} · {locationLabel} · {formatSlot(session.slot)}
            </DrawerDescription>
          </DrawerHeader>
          <div className="px-4 pb-6 space-y-1">
            {/* Add Exercise — both planned and done */}
            {weekPlan && (
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
                    setConfirmRemove(true);
                    setExpanded(true);
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
                  <span className="text-sm">Undo</span>
                </button>
              </DrawerClose>
            )}
          </div>
        </DrawerContent>
      </Drawer>

      {/* Add Exercise Dialog */}
      {weekPlan && (
        <AddExerciseDialog
          open={addExerciseOpen}
          onOpenChange={setAddExerciseOpen}
          date={date}
          sessionIndex={sessionIndex}
          weekPlan={weekPlan}
          onSuccess={() => onSessionUpdated?.()}
        />
      )}
    </>
  );
}
