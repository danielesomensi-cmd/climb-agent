"use client";

import { useState, useEffect, useLayoutEffect, useMemo, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { queryKeys } from "@/lib/query-keys";
import { sessionResolutionState } from "@/lib/session-resolution";
import { anchoredLoadNotes } from "@/lib/anchored-load";
import { asMeasure } from "@/lib/measured-feedback";
import { asLadder } from "@/lib/bw-ladder";
import { buildGuidedStateFromExercises, guidedStorageKey, hasSavedProgress } from "@/lib/guided-session-utils";
import {
  GUIDED_PROGRESS_EVENT,
  discardSavedSession,
  readSavedProgress,
  resumeLabel,
  type SavedProgress,
} from "@/lib/guided-resume";
import { localToday } from "@/lib/key-sessions";
import { scheduleIdle } from "@/lib/hooks/queries/use-week-plan";
import { useOnline } from "@/lib/hooks/use-auth-wait";
import { confirmServerDenied, hasCachedServerNo } from "@/lib/hooks/use-subscription";
import { ChunkErrorBoundary } from "@/components/chunk-error-boundary";
import { notifyChunkLoadFailure } from "@/lib/chunk-load";
import { ChevronDown, Check, X, Undo2, Play, ArrowRightLeft, Trash2, Pencil, Plus, RefreshCw, Mountain, Star, AlertTriangle, Loader2, RotateCcw, CloudOff } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
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
import { FEEDBACK_CHIP } from "@/components/training/feedback-colors";
import { removeExerciseFromSession, setSessionSurface, apiErrorDetail } from "@/lib/api";
import type { SessionSlot, GuidedSessionState, GuidedExercise, WeekPlan, KeySessionRole } from "@/lib/types";
import { formatSessionId, keyLabel } from "@/lib/key-sessions";
import { focusLabel, type SessionAlert } from "@/lib/week-alerts";
import { expandEquipment } from "@/lib/equipment-filter";
import { walkResolvedBlocks } from "@/lib/session-blocks";
import { formatSessionName } from "@/lib/format";
import { formatLoad, pickLoadUnit } from "@/lib/load-units";
import { DailyCueLine } from "@/components/training/daily-cue-banner";

// B396 — its own chunk, fetched on the first "Add exercise" (it was inlined
// here and shipped with every /today and /week first load).
const loadAddExerciseDialog = () => import("@/components/training/add-exercise-dialog");
const AddExerciseDialog = dynamic(
  () => loadAddExerciseDialog().then((m) => m.AddExerciseDialog),
  { ssr: false },
);

/**
 * B396 review — offline, a chunk the service worker has never seen cannot be
 * fetched: the lazy dialog threw and took the whole page into the route error
 * boundary. It is now behind a ChunkErrorBoundary, and fetched once per page
 * while idle and online so it is in the SW cache before the gym.
 */
let addExercisePreloaded = false;

/** B396 — the guided player's route for a session (also what gets prefetched). */
function guidedHref(date: string, sessionId: string): string {
  return `/guided/${date}/${sessionId}`;
}

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
  // F6 — i callback della page sono async: il tipo deve permettere di attenderli
  // per poter disabilitare il bottone finché la mutation è in volo.
  onMarkDone?: () => void | Promise<void>;
  onMarkSkipped?: () => void | Promise<void>;
  onUndo?: () => void | Promise<void>;
  onMove?: () => void;
  onRemove?: () => void;
  onReplan?: () => void;
  onSessionUpdated?: (updatedWeekPlan?: WeekPlan) => void;
  /** A294 — the session's role in the week's key stimuli (from key_status). */
  keyRole?: KeySessionRole | null;
  /**
   * A300 / A301 — the alerts that involve this session (recovery guards and
   * lunch-rotation rules). Shown as a badge + one line each: a heads-up, the
   * session stays exactly as planned.
   */
  alerts?: SessionAlert[];
  /** A308 — the day's process cue, when this is the session it belongs to (/today). */
  focusCue?: string;
}


// A286 — la mappa vive in feedback-colors.ts: era duplicata (e divergente) qui,
// in exercise-card e in day-card.

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
    loadUnit: pickLoadUnit(suggested.load_unit, inst.load_unit),
    unilateral: !!(inst.unilateral ?? rightHand),
    altSides: !!(inst.alt_sides),
    allowLoadLogging: !!(inst.attributes as Record<string, unknown> | undefined)?.allow_load_logging,
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
      // B344: absent on the boulder-target path (that one really is Font) and
      // on older cached payloads — displayPrescribedGrade is a no-op then.
      gradeScale: suggested.grade_scale as string | undefined,
      repScheme: suggested.suggested_rep_scheme as string | undefined,
      surface: boulderTarget.surface_selected as string | undefined,
      attemptGuidance: boulderTarget.attempt_guidance as string | undefined,
      logProblems: boulderTarget.log_problems === true,
      restGuidance: boulderTarget.rest_guidance as string | undefined,
      loadSource: suggested.load_source as string | undefined,
      loadWarning: suggested.load_warning as string | undefined,
      loadNotes: anchoredLoadNotes(suggested),
      // A295: measured feedback — what the athlete may record on this exercise.
      measure: asMeasure(suggested.measure),
      // A298: the bodyweight ladder level the resolver prescribed (bw_ladder).
      ladder: asLadder((suggested.bw_ladder as Record<string, unknown> | undefined)?.ladder),
      ladderSource: prescription.source === "bw_ladder" ? "engine" : undefined,
      targetReps: typeof suggested.target_reps === "number" ? suggested.target_reps : undefined,
      painFlag: suggested.pain_flag === true,
      rightHand: rightHand ? { externalLoadKg: rightHand.suggested_external_load_kg as number | undefined } : undefined,
      leftHand: leftHand ? { externalLoadKg: leftHand.suggested_external_load_kg as number | undefined } : undefined,
    },
    videoUrl: (inst.video_url as string | undefined) ?? undefined,
    cues: (inst.cues as string[] | undefined) ?? undefined,
    hrTarget: (inst.hr_target as GuidedExercise["hrTarget"]) ?? undefined,  // A316
    status: "pending",
    feedbackLabel: null,  // A295: nothing pre-selected
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
    feedbackLabel: null,  // A295: nothing pre-selected
  };
}

/**
 * B218 Bug 3 / B283: build GuidedSessionState from an inline, flat-exercise
 * session (saved custom sessions AND Body Part Picker generated sessions —
 * both run through the real guided player; the A211 minimal page is retired).
 * Delegates to the shared lib helper.
 */
function buildGuidedStateFromInline(
  session: SessionSlot,
  date: string,
): GuidedSessionState | null {
  return buildGuidedStateFromExercises(
    session.session_id,
    session.name || session.session_id,
    date,
    (session.exercises ?? []) as unknown as Array<Record<string, unknown>>,
  );
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

  // A245 G-7 (F20): shared walk — this loop existed verbatim ~800 lines below
  // for the card layout, so the guided order and the displayed order could
  // drift apart with any edit to either copy.
  const exercises: GuidedExercise[] = walkResolvedBlocks(blocks, instances).map((item) =>
    item.kind === "instruction"
      ? buildInstructionStep(item.block)
      : buildGuidedExercise(item.instance),
  );

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

/**
 * Does Start reopen what is saved on the device instead of starting anew?
 *
 * B396 review — a session whose feedback is queued (B397) only ever reopens
 * the player's "waiting to sync" view: that entry is the only copy of the
 * feedback, so it is never overwritten, even when nothing in it counts as
 * progress. B181 — a session under way is resumed, never overwritten.
 */
function resumesSavedSession(session: SessionSlot, date: string): boolean {
  try {
    if (readSavedProgress(window.localStorage, guidedStorageKey(date, session.session_id))?.pending) return true;
  } catch {
    /* storage blocked: nothing saved to protect */
  }
  return hasSavedProgress(date, session.session_id);
}

// B197 Bug 1: shared "Start session" handler. Guards against re-starting an
// already-done session and preserves any pre-existing `startedAt` in localStorage
// so the wall-clock duration survives a /today render race / accidental restart.
// B396 — returns whether it navigated, so the button can show it is working.
function handleStartGuided(
  session: SessionSlot,
  date: string,
  router: ReturnType<typeof useRouter>,
  serverDenied = false,
): boolean {
  // Don't allow restarting a server-side completed session — the duration
  // would otherwise be reset and clobber the real value via the resubmit path.
  if (session.status === "done" || session.status === "skipped") {
    return false;
  }

  // Queued feedback or a session under way: reopen it, never overwrite it.
  if (resumesSavedSession(session, date)) {
    router.push(guidedHref(date, session.session_id));
    return true;
  }

  // B397 review (rounds 2-3) — a NEW session is the paywall's entry point
  // (B202). Only the server's own "no" blocks it (`serverDenied`, confirmed
  // by the caller with a fresh answer): a missing answer — offline at the
  // crag, Clerk still booting — lets Start through, and the server still
  // refuses the feedback POST. Resume and the queued-feedback view above are
  // never blocked (A245 C-1).
  if (serverDenied) {
    router.push("/subscribe");
    return true;
  }

  // B218 Bug 3 / B283: is_custom sessions (saved custom, adhoc, Body Part
  // Picker) live in the week plan as a flat exercises[] list. Build a guided
  // state from that shape and reuse the real /guided/[date]/[sessionId] player
  // — the dedicated A211 playback page is retired (it lacked progress,
  // navigation, cues and load display).
  const guidedState = session.is_custom
    ? buildGuidedStateFromInline(session, date)
    : buildGuidedState(session, date);
  if (!guidedState) return false;

  // B290 (closes F54): was building the key inline with the literal "clerk".
  const key = guidedStorageKey(date, session.session_id);

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
  router.push(guidedHref(date, session.session_id));
  return true;
}

// Equipment expansion + compatibility logic extracted to @/lib/equipment-filter

// ─── Exercise Item Wrapper ───────────────────────────────────────────

function ExerciseItemWrapper({ children, canEdit, onRemove }: {
  children: React.ReactNode;
  canEdit: boolean;
  onRemove?: () => void;
}) {
  return (
    <div className="relative">
      {children}
      {/* A286 — era a opacità 30%: di fatto invisibile. Piena visibilità,
          44px di target; la conferma resta l'AlertDialog di A153. */}
      {canEdit && onRemove && (
        <button
          aria-label="Remove exercise"
          className="absolute top-0 right-0 flex items-center justify-center w-11 h-11 rounded-full text-muted-foreground hover:text-danger hover:bg-danger/10 transition-colors"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
        >
          <Trash2 className="size-4" />
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
  keyRole,
  alerts,
  focusCue,
}: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);
  // F6 — un secondo tap su Done/Skip prima che il primo abbia risposto partiva
  // dallo stesso snapshot e faceva perdere il mark precedente.
  const [marking, setMarking] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [addExerciseOpen, setAddExerciseOpen] = useState(false);
  // B396 — the dialog's chunk is fetched on the first open, then it stays
  // mounted (so closing still animates).
  const [addExerciseMounted, setAddExerciseMounted] = useState(false);
  const [exerciseToRemove, setExerciseToRemove] = useState<{ index: number; name: string } | null>(null);
  // A210 → B313: the "Boulder only" override lives on the slot now, not here.
  // Only the in-flight/error state is local.
  const [boulderOverrideLoading, setBoulderOverrideLoading] = useState(false);
  const [boulderOverrideError, setBoulderOverrideError] = useState<string | null>(null);
  const router = useRouter();

  /** F6 — esegue un mark tenendo il bottone disabilitato fino alla risposta. */
  const runMark = useCallback(
    async (fn: (() => void | Promise<void>) | undefined) => {
      if (!fn || marking) return;
      setMarking(true);
      try {
        await fn();
      } finally {
        setMarking(false);
      }
    },
    [marking],
  );

  // B313: one resolved session, period. When "Boulder only" is on, the server
  // has already swapped `session.resolved` for the adapted one — which is also
  // what handleStartGuided hands to the player and what the feedback is scored
  // against. Pre-B313 this line picked a React-state override the player could
  // not see, so the preview showed boulder and the session ran the rope plan.
  const effectiveResolved = session.resolved as Record<string, unknown> | undefined;
  const boulderOverrideActive = session.surface_override === "boulder";

  // B293 — never render a completable card with zero resolved exercises.
  const resolutionState = sessionResolutionState({
    is_custom: session.is_custom,
    resolve_error: session.resolve_error,
    resolved: effectiveResolved ?? null,
  });
  const completable = resolutionState === "ok";
  const qc = useQueryClient();
  const [retryingResolve, setRetryingResolve] = useState(false);
  const retryResolve = useCallback(async () => {
    // Resolved payloads of non-completed sessions are never persisted, so a
    // week refetch re-runs resolution server-side — that IS the retry.
    setRetryingResolve(true);
    try {
      await qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    } finally {
      setRetryingResolve(false);
    }
  }, [qc]);

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
  // A286 — micro-feedback sobrio: la card si illumina per un attimo quando la
  // sessione passa a "fatta". Il check di prefers-reduced-motion è esplicito
  // perché qui l'effetto è pilotato da JS, non solo da CSS.
  const [justCompleted, setJustCompleted] = useState(false);
  const wasDoneRef = useRef(isDone);
  useEffect(() => {
    const was = wasDoneRef.current;
    wasDoneRef.current = isDone;
    if (was || !isDone) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    setJustCompleted(true);
    const t = window.setTimeout(() => setJustCompleted(false), 1400);
    return () => window.clearTimeout(t);
  }, [isDone]);
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

  // A210: trigger detection — the button shows iff this session, as planned,
  // schedules a rope-dependent exercise. B313: which mechanism adapts it (swap
  // to the catalog's boulder_fallback, or re-resolve without the rope wall) is
  // the server's call now — the client only asks for "boulder".
  const hasRopeExercise = useMemo(() => {
    const rs = effectiveResolved?.resolved_session as Record<string, unknown> | undefined;
    const instances = (rs?.exercise_instances ?? []) as Array<Record<string, unknown>>;
    return instances.some((ex) => {
      const eq = (ex.equipment_required ?? []) as string[];
      return Array.isArray(eq) && eq.includes("gym_routes");
    });
  }, [effectiveResolved]);
  const canSwitchToBoulder =
    !boulderOverrideActive && !isFinalized && !session.is_custom && hasRopeExercise && !!weekPlan;

  const setSurface = useCallback(async (surface: "boulder" | null) => {
    if (!weekPlan) return;
    setBoulderOverrideLoading(true);
    setBoulderOverrideError(null);
    try {
      const result = await setSessionSurface({
        date,
        session_index: sessionIndex,
        surface,
        week_plan: weekPlan,
      });
      onSessionUpdated?.(result.week_plan);
    } catch (err) {
      console.error("[B313] surface override failed:", err);
      // B314: say what the server said. The previous copy blamed the gym's
      // equipment for every failure, including a 404 from a backend that had
      // not finished deploying.
      setBoulderOverrideError(apiErrorDetail(
        err,
        surface === null
          ? "Could not restore the planned session. Try again."
          : "Could not adapt this session. Try again.",
      ));
    } finally {
      setBoulderOverrideLoading(false);
    }
  }, [weekPlan, date, sessionIndex, onSessionUpdated]);

  const handleBoulderOnly = useCallback(() => setSurface("boulder"), [setSurface]);
  const handleUndoBoulderOverride = useCallback(() => setSurface(null), [setSurface]);

  // A210: copy variant — route_projecting → limit_boulder is an equivalent stimulus,
  // aerobic/endurance swaps trade aerobic capacity for volume bouldering.
  const boulderCopyVariant: "equivalent" | "volume_swap" =
    session.surface_override_from === "route_projecting_gym" ? "equivalent" : "volume_swap";

  // B396 — the guided progress saved for this session, if any. Start resumes
  // it (B181), so the button says so: "Resume · 3/8". Read before paint, again
  // once Clerk is up (the key carries the user id), and whenever progress is
  // discarded or restored.
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const [savedProgress, setSavedProgress] = useState<SavedProgress | null>(null);
  useLayoutEffect(() => {
    const read = () => {
      try {
        setSavedProgress(readSavedProgress(window.localStorage, guidedStorageKey(date, session.session_id)));
      } catch {
        setSavedProgress(null); // storage blocked
      }
    };
    read();
    window.addEventListener(GUIDED_PROGRESS_EVENT, read);
    return () => window.removeEventListener(GUIDED_PROGRESS_EVENT, read);
  }, [date, session.session_id, authLoaded]);

  /** B396 — Discard saved progress from the actions sheet, with Undo. */
  const discardProgress = useCallback(() => {
    let restore: (() => void) | null = null;
    try {
      restore = discardSavedSession(window.localStorage, guidedStorageKey(date, session.session_id));
    } catch {
      restore = null;
    }
    if (!restore) return;
    toast("Session progress discarded", {
      duration: 8000,
      action: { label: "Undo", onClick: restore },
    });
  }, [date, session.session_id]);

  // B396 — Start used to be a bare router.push: no feedback while the guided
  // route loaded (up to seconds on a bad connection). It now shows a spinner
  // and stays disabled until the page changes; if the navigation never
  // happens, the button comes back after a while.
  const [starting, setStarting] = useState(false);
  // B397 review (round 4) — the tap a pending subscription check belongs to.
  // Bumped when the button comes back and when the card goes away: a check
  // that answers after that (offline, the request waits for the network) must
  // not navigate — the athlete may be in another session by then.
  const startTapRef = useRef(0);
  useEffect(() => {
    const taps = startTapRef;
    return () => {
      taps.current++;
    };
  }, []);
  useEffect(() => {
    if (!starting) return;
    const t = window.setTimeout(() => {
      startTapRef.current++;
      setStarting(false);
    }, 8000);
    return () => window.clearTimeout(t);
  }, [starting]);

  // B396 — and the guided route is prefetched (full: shell + JS) once the page
  // is idle, for today's startable session only. Never before Clerk is up: a
  // request to a protected route without a fresh session cookie would only
  // come back as the sign-in redirect.
  const startable = !isFinalized && hasExercises;
  const isTodayCard = date === localToday();

  // B396 review — the "Add exercise" chunk, preloaded while idle and online.
  const online = useOnline();
  const canAddExercise = !!weekPlan && !session.is_custom;
  useEffect(() => {
    if (!canAddExercise || !online || addExercisePreloaded) return;
    return scheduleIdle(() => {
      if (addExercisePreloaded) return;
      addExercisePreloaded = true;
      loadAddExerciseDialog().catch(() => {
        // Not retried within this page: React.lazy and the bundler runtime
        // keep the rejection. The next page load tries again.
      });
    });
  }, [canAddExercise, online]);
  useEffect(() => {
    if (!startable || !isTodayCard || !authLoaded || !isSignedIn) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) return;
    return scheduleIdle(() => {
      router.prefetch(guidedHref(date, session.session_id), {
        kind: "full",
      } as unknown as Parameters<typeof router.prefetch>[1]);
    });
  }, [startable, isTodayCard, authLoaded, isSignedIn, router, date, session.session_id]);

  return (
    <>
      <div className="relative">
      {boulderOverrideActive && (
        <div className="mb-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-fg flex items-start gap-2">
          <Mountain className="size-4 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium">Boulder only — session adapted for today.</p>
            {boulderCopyVariant === "volume_swap" && (
              <p className="mt-0.5 text-fg-secondary">
                Volume climbing replaces aerobic endurance. Aerobic stimulus is not replicable without rope.
              </p>
            )}
          </div>
          <button
            className="text-warning hover:text-fg underline text-xs shrink-0 disabled:opacity-50"
            disabled={boulderOverrideLoading}
            onClick={handleUndoBoulderOverride}
          >
            Undo
          </button>
        </div>
      )}
      {boulderOverrideError && (
        <div className="mb-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {boulderOverrideError}
        </div>
      )}
      <Card
        className={`gap-0 py-0 overflow-hidden transition-shadow duration-500 ${
          justCompleted ? "ring-2 ring-success/60" : ""
        }`}
      >
        {/* Header — clickable to expand */}
        <CardHeader
          className="cursor-pointer select-none py-3"
          onClick={() => setExpanded((prev) => !prev)}
        >
          <div className="flex items-start justify-between gap-2">
            {/* A308 — the session name is the headline (was text-sm, the same
                size as the coach card subtitle). */}
            <CardTitle className="flex flex-wrap items-center gap-1.5 text-lg font-semibold leading-tight">
              <span>
                {session.is_custom
                  ? (session.name || formatSessionName(session.session_id))
                  : ((session.resolved as Record<string, Record<string, string>> | undefined)?.session?.session_name || formatSessionName(session.session_id))}
              </span>
              {session.is_custom && (
                <Badge className="bg-primary/20 text-primary border-primary/40 text-[11px]">
                  Custom
                </Badge>
              )}
              {boulderOverrideActive && (
                <Badge variant="outline" className="text-[11px] gap-1 px-1.5 py-0 border-warning/30 bg-warning/15 text-warning">
                  <Mountain className="size-2.5" />
                  Boulder
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-1.5">
              {/* Edit actions button */}
              <button
                className="flex items-center justify-center min-w-[44px] min-h-[44px] bg-surface-elevated rounded-lg p-1.5 text-fg-secondary hover:text-fg transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setDrawerOpen(true);
                }}
                aria-label="Session actions"
              >
                <Pencil className="size-[18px]" />
              </button>
              <ChevronDown
                className={`size-5 shrink-0 text-fg-secondary transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              />
            </div>
          </div>

          {/* A308 — one plain meta line instead of a row of same-weight chips. */}
          {(() => {
            // B298: custom/adhoc sessions carry their estimate at the top level
            // (`target_duration_min`), not under resolved.session — read that as
            // a fallback so the custom card shows the duration too.
            const targetMin = !isDone && !isSkipped
              ? ((effectiveResolved as Record<string, Record<string, unknown>> | undefined)?.session?.target_duration_min as number | undefined)
                ?? (session.is_custom ? session.target_duration_min : undefined)
              : undefined;
            const parts = [
              formatSlot(session.slot),
              // A300 — a complementary (lunch) session placed by the rotation
              session.slot_role === "complementary" ? focusLabel(session.focus) : null,
              locationLabel,
              targetMin ? `~${targetMin} min` : null,
            ].filter(Boolean);
            return (
              <p className="mt-1 text-xs text-fg-secondary">{parts.join(" \u00b7 ")}</p>
            );
          })()}

          {/* At most three chips: key role, one intensity, the status. */}
          {(keyRole || isHard || isFinger || isDone || isSkipped) && (
            <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
              {/* A294 — key-session role */}
              <KeyRoleBadge role={keyRole} />
              {/* A286 — testo colorato su fondo tenue dello stesso colore.
                  A308 — Finger implies hard: one intensity chip, not two. */}
              {isFinger ? (
                <Badge variant="outline" className="text-[11px] border-axis-finger/30 bg-axis-finger/15 text-axis-finger">
                  Finger
                </Badge>
              ) : isHard ? (
                <Badge variant="outline" className="text-[11px] border-danger/30 bg-danger/15 text-danger">
                  Hard
                </Badge>
              ) : null}
              {isDone && (() => {
                // B217: only show a duration when we have a measured one. No
                // slot-table fallback — "Completed" alone is the honest signal.
                const hasReal = session.session_duration_seconds != null && session.session_duration_seconds > 0;
                return (
                  <Badge
                    variant="outline"
                    className="text-[11px] border-success/30 bg-success/15 text-success"
                  >
                    <span>Completed</span>
                    {hasReal && (
                      <span>{` · ${Math.round(session.session_duration_seconds! / 60)} min`}</span>
                    )}
                  </Badge>
                );
              })()}
              {isSkipped && (
                <Badge
                  variant="outline"
                  className="text-[11px] border-warning/30 bg-warning/15 text-warning"
                >
                  Skipped
                </Badge>
              )}
            </div>
          )}

          {/* Post-session feedback — part of the status, said as text. */}
          {isDone && session.feedback_summary && (
            <p className="mt-1 text-xs text-fg-secondary">
              Felt{" "}
              <span className={`rounded px-1 font-medium ${FEEDBACK_CHIP[session.feedback_summary] ?? ""}`}>
                {session.feedback_summary.replace(/_/g, " ")}
              </span>
            </p>
          )}

          {/* A301 — what the recovery / lunch rules flag on this session.
              A308 — the only place /today says it (no badge, no repeat in the
              day's alerts card). */}
          {alerts && alerts.length > 0 && (
            <ul className="mt-1.5 space-y-0.5" aria-label="Alerts" data-testid="session-alerts">
              {alerts.map((a, i) => (
                <li key={`${a.source}-${a.code}-${i}`} className="flex items-start gap-1.5 text-xs leading-snug text-warning">
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                  <span>
                    <span className="font-medium">{a.title}:</span>{" "}
                    <span className="text-muted-foreground">{a.message}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}

          {/* A308 — the day's focus (was its own amber card above the day). */}
          {focusCue && (
            <div className="mt-2">
              <DailyCueLine text={focusCue} />
            </div>
          )}

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
                  <p key={r.label} className="text-[11px] text-brand-secondary font-medium">
                    {r.label}: {r.value}
                  </p>
                ))}
              </div>
            );
          })()}
        </CardHeader>

        {/* A286 — barra azioni sempre visibile, anche a card chiusa: segnare
            "fatta" costava 2 tap + lo scroll di tutta la lista esercizi,
            mentre Start ne costava 1. Stesse funzioni di prima, nessuna
            logica duplicata. */}
        {!isFinalized && (hasExercises || onMarkDone || onMarkSkipped) && (
          <div className="flex flex-wrap items-center gap-1.5 px-6 pb-3">
            {hasExercises && (
              <Button
                className="min-h-[44px] bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={starting}
                aria-busy={starting || undefined}
                onClick={(e) => {
                  e.stopPropagation();
                  if (starting) return;
                  // B397 review (round 3) — a cached "no" is confirmed with a
                  // fresh answer before a NEW session goes to /subscribe (the
                  // athlete may just have paid); resume and queued feedback
                  // never wait for the network.
                  if (!hasCachedServerNo(qc) || resumesSavedSession(session, date)) {
                    if (handleStartGuided(session, date, router)) setStarting(true);
                    return;
                  }
                  setStarting(true);
                  const tap = ++startTapRef.current;
                  void confirmServerDenied(qc).then((denied) => {
                    if (startTapRef.current !== tap) return; // superseded: no late navigation
                    if (!handleStartGuided(session, date, router, denied)) setStarting(false);
                  });
                }}
              >
                {starting ? (
                  <Loader2 className="size-3.5 mr-1 animate-spin" aria-hidden="true" />
                ) : savedProgress?.pending ? (
                  <CloudOff className="size-3.5 mr-1" aria-hidden="true" />
                ) : (
                  <Play className="size-3.5 mr-1" />
                )}
                {/* B396 review — "Waiting to sync" for a queued feedback (B397). */}
                {savedProgress ? resumeLabel(savedProgress) : "Start session"}
              </Button>
            )}
            {/* B293: a session with zero resolved exercises must never be
                completable — the buttons wait for a successful resolution. */}
            {onMarkDone && (
              <Button
                variant="outline"
                disabled={marking || !completable}
                className="min-h-[44px] text-success border-success/30 hover:bg-success/15 hover:text-success"
                onClick={(e) => {
                  e.stopPropagation();
                  void runMark(onMarkDone);
                }}
              >
                <Check className="size-4 mr-1" />
                Done
              </Button>
            )}
            {onMarkSkipped && (
              <Button
                variant="outline"
                disabled={marking || !completable}
                className="min-h-[44px] text-muted-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  void runMark(onMarkSkipped);
                }}
              >
                <X className="size-4 mr-1" />
                Skip
              </Button>
            )}
          </div>
        )}

        {/* Expanded content */}
        {expanded && (
          <CardContent className="pt-0 pb-3 space-y-3">
            {/* A308 — details that used to crowd the header chips. */}
            {(hasLoadingPin || session.estimated_load_score != null) && (
              <div className="flex flex-wrap items-center gap-1.5">
                {hasLoadingPin && (
                  <Badge variant="outline" className="text-[11px] border-axis-finger/30 bg-axis-finger/15 text-axis-finger">
                    Loading Pin
                  </Badge>
                )}
                {session.estimated_load_score != null && (
                  <Badge variant="outline" className="text-[11px] text-fg-muted">
                    Load: {session.estimated_load_score}
                  </Badge>
                )}
              </div>
            )}

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
                    if (ex.load_kg > 0) prescription.push(formatLoad(ex.load_kg, ex.load_unit));
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
                        {ex.cues && ex.cues.length > 0 && (
                          <ul className="mt-1.5 space-y-0.5">
                            {ex.cues.map((cue, ci) => (
                              <li key={ci} className="text-xs text-muted-foreground flex items-start gap-1.5">
                                <span className="mt-1.5 block h-1 w-1 shrink-0 rounded-full bg-muted-foreground/50" />
                                <span>{cue}</span>
                              </li>
                            ))}
                          </ul>
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
                // B293 — explanatory, never a bare completable card. `error`
                // means the backend marked a transient resolution failure
                // (resolve_error, A245 E-3/B17); `empty` means it resolved to
                // genuinely zero exercises. Both offer a retry: unresolved
                // sessions are re-resolved on every week refetch.
                return (
                  <div className="space-y-3 rounded-md border border-dashed p-4 text-center">
                    <p className="text-xs text-muted-foreground">
                      {resolutionState === "error"
                        ? "This session couldn't be prepared — it's usually temporary."
                        : "No exercises could be selected for this session right now."}
                    </p>
                    <Button
                      variant="outline"
                      className="min-h-[44px] text-sm"
                      disabled={retryingResolve}
                      onClick={(e) => {
                        e.stopPropagation();
                        void retryResolve();
                      }}
                    >
                      <RefreshCw className={`size-3.5 mr-1 ${retryingResolve ? "animate-spin" : ""}`} />
                      {retryingResolve ? "Retrying..." : "Retry"}
                    </Button>
                  </div>
                );
              }

              // Block-based grouping for display
              // A245 G-7 (F20): same walk as buildGuidedState — one copy now.
              const items = walkResolvedBlocks(allBlocks, allInstances).map((item) =>
                item.kind === "instruction"
                  ? { type: "instruction" as const, block: item.block, visualPos: undefined, moduleRole: undefined }
                  : {
                      type: "exercise" as const,
                      inst: item.instance,
                      visualPos: item.exerciseIndex,
                      moduleRole: item.moduleRole,
                    },
              );

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
                      load_unit: pickLoadUnit(suggested.load_unit, ex.load_unit),
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

            {/* A286 — Start/Done/Skip sono risaliti sotto la testata: erano in
                fondo alla card espansa, dopo tutta la lista esercizi.
                A308 — the "Tap Start session…" hint went too: it repeated the
                visible button. */}
          </CardContent>
        )}
      </Card>

      {/* A286 — il FAB "Start session" sporgeva di 16px nel gap e finiva sopra
          la card successiva. L'azione ora è nella barra in flusso sotto la
          testata, sempre visibile: niente sovrapposizioni. */}
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
                    setAddExerciseMounted(true);
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

            {/* B396 — start over: the saved guided progress goes (with Undo
                in the toast). It used to be the banner's one-tap Discard.
                B396 review — never for a session whose feedback is waiting to
                sync: that entry is the only copy of the feedback. */}
            {!isFinalized && savedProgress && !savedProgress.pending && (
              <DrawerClose asChild>
                <button
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left"
                  onClick={discardProgress}
                >
                  <RotateCcw className="size-5 text-muted-foreground" />
                  <span className="text-sm">Discard saved progress</span>
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
                  className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-accent transition-colors text-left text-destructive"
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

      {/* Add Exercise Dialog.
          B396 review — a chunk that cannot load (offline, never cached)
          closes the dialog with a toast instead of crashing the page. It stays
          unavailable for the life of the page, so the toast offers a reload
          when online. */}
      {weekPlan && addExerciseMounted && (
        <ChunkErrorBoundary
          onError={() => {
            setAddExerciseOpen(false);
            setAddExerciseMounted(false);
            notifyChunkLoadFailure();
          }}
        >
          <AddExerciseDialog
            open={addExerciseOpen}
            onOpenChange={setAddExerciseOpen}
            date={date}
            sessionIndex={sessionIndex}
            weekPlan={weekPlan}
            availableEquipment={availableEquipment}
            onSuccess={(updatedPlan) => onSessionUpdated?.(updatedPlan)}
          />
        </ChunkErrorBoundary>
      )}
    </>
  );
}


/** A294 — Key / Supporting / Optional / Skipped key / Downgraded badge. */
function KeyRoleBadge({ role }: { role?: KeySessionRole | null }) {
  if (!role) return null;
  if (role.role === "key") {
    const done = role.status === "done";
    const labels = role.keys.filter((k) => k !== "try_hard").map(keyLabel).join(" + ");
    return (
      <Badge
        variant="outline"
        className={`text-[11px] gap-1 ${done ? "border-success/40 bg-success/15 text-success" : "border-primary/40 bg-primary/15 text-primary"}`}
        title={role.keys.map(keyLabel).join(", ")}
      >
        <Star className="size-2.5" aria-hidden="true" />
        {done ? "Key ✓" : `Key · ${labels}`}
      </Badge>
    );
  }
  if (role.role === "skipped") {
    return (
      <Badge variant="outline" className="text-[11px] gap-1 border-danger/30 bg-danger/15 text-danger" title="Key stimulus lost this week">
        <Star className="size-2.5" aria-hidden="true" />
        Key lost · {role.keys.map(keyLabel).join(" + ")}
      </Badge>
    );
  }
  if (role.role === "downgraded") {
    return (
      <Badge variant="outline" className="text-[11px] border-warning/30 bg-warning/15 text-warning">
        Downgraded from {formatSessionId(role.downgraded_from)}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[11px] text-muted-foreground" title={role.supporting.map(keyLabel).join(", ")}>
      {role.role === "optional" ? "Optional" : "Supporting"}
    </Badge>
  );
}
