"use client";

import { Suspense, useState, useCallback, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import {
  Layers, Target, Repeat, Eye, ArrowLeft,
  Smartphone, Moon, Box, Route, Flame, Mountain, ChevronDown,
} from "lucide-react";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import { ClimbLogger, type LoggedClimb } from "@/components/free-session/climb-logger";
import { SessionSummary } from "@/components/free-session/session-summary";
import {
  getFreeSessionPresets,
  startFreeSession,
  finishFreeSession,
} from "@/lib/api";
import { useFreeSessionSurfaces } from "@/lib/hooks/queries/use-free-session";
import { invalidateFreeSessionHistory } from "@/lib/invalidation";
import { CircuitSetup, type CircuitConfig } from "@/components/circuit/CircuitSetup";
import { CircuitTimer, type CircuitResult } from "@/components/circuit/CircuitTimer";
import { CircuitCompletion } from "@/components/circuit/CircuitCompletion";
import { useUserState } from "@/lib/hooks/use-state";
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";
import { findPendingDraft, clearDraft, type FreeSessionDraft } from "@/lib/free-session-utils";

// ── Types ──────────────────────────────────────────────────────────────

interface Surface {
  id: string;
  name: string;
}

interface Gym {
  gym_id: string;
  name: string;
}

interface Preset {
  id: string;
  name: string;
  description: string;
  icon: string;
  target_grade: string | null;
  rest_seconds: number;
  target_climbs: string;
  duration: string;
  phase_compatibility: string;
  phase_tip: string;
}

interface ActiveSession {
  sessionId: string;
  surface: string;
  mode: "template" | "free";
  presetName?: string;
  gymName?: string;
  targetGrade?: string;
  restSeconds?: number;
  tip?: string;
  targetClimbs?: string;
}

interface FinishedData {
  summary: {
    total_climbs: number;
    flashed: number;
    sent: number;
    attempted: number;
    max_grade_sent: string | null;
    max_grade_attempted: string | null;
    send_rate: number;
  };
  durationMinutes: number | null;
  loadScore: number | null;
}

type Step = "surface" | "gym" | "mode" | "preset" | "active" | "summary"
  | "circuit_setup" | "circuit_running" | "circuit_complete";

// ── All surfaces (always shown) ────────────────────────────────────────

const ALL_SURFACES: Surface[] = [
  { id: "gym_boulder", name: "Gym Boulder" },
  { id: "board_kilter", name: "Kilter Board" },
  { id: "board_moonboard", name: "MoonBoard" },
  { id: "board_other", name: "Other Board" },
  { id: "gym_routes", name: "Lead / Top-rope" },
];

const SURFACE_ICONS: Record<string, React.ReactNode> = {
  gym_boulder: <Box className="size-6" />,
  board_kilter: <Smartphone className="size-6" />,
  board_moonboard: <Moon className="size-6" />,
  board_other: <Layers className="size-6" />,
  gym_routes: <Route className="size-6" />,
};

const SURFACE_COLORS: Record<string, string> = {
  gym_boulder: "from-orange-500/20 to-orange-600/5 border-orange-500/30",
  board_kilter: "from-purple-500/20 to-purple-600/5 border-purple-500/30",
  board_moonboard: "from-blue-500/20 to-blue-600/5 border-blue-500/30",
  board_other: "from-teal-500/20 to-teal-600/5 border-teal-500/30",
  gym_routes: "from-rose-500/20 to-rose-600/5 border-rose-500/30",
};

const SURFACE_ICON_COLORS: Record<string, string> = {
  gym_boulder: "text-orange-400",
  board_kilter: "text-purple-400",
  board_moonboard: "text-blue-400",
  board_other: "text-teal-400",
  gym_routes: "text-rose-400",
};

const PRESET_ICONS: Record<string, React.ReactNode> = {
  layers: <Layers className="size-5" />,
  target: <Target className="size-5" />,
  repeat: <Repeat className="size-5" />,
  eye: <Eye className="size-5" />,
};

const PHASE_BADGE: Record<string, { label: string; color: string }> = {
  recommended: { label: "\u2705", color: "text-emerald-400 bg-emerald-500/15 border-emerald-500/30" },
  caution: { label: "\u26a0\ufe0f", color: "text-amber-400 bg-amber-500/15 border-amber-500/30" },
  not_recommended: { label: "\u274c", color: "text-red-400 bg-red-500/15 border-red-500/30" },
};

// ── Page component ─────────────────────────────────────────────────────

function FreeSessionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded: authReady } = useAuth();
  const { state: userState } = useUserState(authReady);
  const qc = useQueryClient();
  const gradeSystem: BoulderGradeSystem = ((userState as Record<string, unknown>)?.preferences as Record<string, unknown>)?.grade_system_boulder as BoulderGradeSystem || "font";
  const paramContext = searchParams.get("context") || "standalone";
  const paramDate = searchParams.get("date") || new Date().toISOString().split("T")[0];
  const [step, setStep] = useState<Step>("surface");
  const surfacesQuery = useFreeSessionSurfaces(authReady);
  const gyms: Gym[] = useMemo(
    () => (surfacesQuery.data?.gyms ?? []) as Gym[],
    [surfacesQuery.data],
  );

  // A202: derive climbing surfaces actually available to the user from their
  // equipment (union of all gyms + home). Fallback to ALL_SURFACES if we cannot
  // determine equipment yet, so the picker is never empty during initial load.
  const availableClimbingSurfaces: Surface[] = useMemo(() => {
    const eq = (userState as Record<string, unknown> | null)?.equipment as
      | { gyms?: Array<{ equipment?: string[] }>; home?: string[] }
      | undefined;
    if (!eq) return ALL_SURFACES;
    const owned = new Set<string>();
    for (const g of eq.gyms ?? []) {
      for (const id of g.equipment ?? []) owned.add(id);
    }
    for (const id of eq.home ?? []) owned.add(id);
    const filtered = ALL_SURFACES.filter((s) => owned.has(s.id));
    return filtered.length > 0 ? filtered : ALL_SURFACES;
  }, [userState]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selections
  // B201: selectedGymId holds the gym_id of a SAVED gym (from user's list).
  // customGym holds a free-text custom gym name not in the saved list.
  // They are mutually exclusive; "" means "no saved gym selected".
  const [selectedSurface, setSelectedSurface] = useState<string>("");
  const [selectedGymId, setSelectedGymId] = useState<string>("");
  const [customGym, setCustomGym] = useState("");
  // A202: collapsible climbing card — auto-expanded when >1 available surface.
  const [climbingExpanded, setClimbingExpanded] = useState<boolean>(false);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [freeModeTip, setFreeModeTip] = useState("");
  const [phaseId, setPhaseId] = useState("");

  // Active session
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  const [finishedData, setFinishedData] = useState<FinishedData | null>(null);
  const [sessionClimbs, setSessionClimbs] = useState<LoggedClimb[]>([]);
  const [sessionStartedAt, setSessionStartedAt] = useState<number>(Date.now());

  // Pending draft (resume banner)
  const [pendingDraft, setPendingDraft] = useState<FreeSessionDraft | null>(null);

  // Circuit state
  const [circuitConfig, setCircuitConfig] = useState<CircuitConfig | null>(null);
  const [circuitResult, setCircuitResult] = useState<CircuitResult | null>(null);
  const [circuitSessionId, setCircuitSessionId] = useState<string | null>(null);

  // Check for pending draft on mount — offer resume if found
  useEffect(() => {
    const draft = findPendingDraft();
    if (draft) setPendingDraft(draft);
  }, []);

  // Resume a pending draft: skip selection steps and go straight to active
  const handleResumeDraft = useCallback((draft: FreeSessionDraft) => {
    setActiveSession({
      sessionId: draft.sessionId,
      surface: draft.surface,
      mode: draft.sessionMode,
      presetName: draft.presetName,
      gymName: draft.gymName,
      targetGrade: draft.targetGrade,
      restSeconds: draft.restSeconds,
      tip: draft.tip,
      targetClimbs: draft.targetClimbs,
    });
    setSessionStartedAt(draft.startedAt);
    setPendingDraft(null);
    setStep("active");
  }, []);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleSurfaceSelect = useCallback(async (surfaceId: string) => {
    // Circuit surfaces route to circuit flow
    if (surfaceId.startsWith("circuit_")) {
      setSelectedSurface(surfaceId);
      setError(null);
      setStep("circuit_setup");
      return;
    }

    setSelectedSurface(surfaceId);
    setError(null);

    // Pre-select gym if only one
    if (gyms.length === 1) {
      setSelectedGymId(gyms[0].gym_id);
      setCustomGym("");
    } else {
      setSelectedGymId("");
    }

    // Load presets
    setLoading(true);
    try {
      const data = await getFreeSessionPresets(surfaceId);
      setPresets(data.presets);
      setFreeModeTip(data.free_mode_tip);
      setPhaseId(data.phase_id);

      // Skip gym step if 0 or 1 gym
      if (gyms.length <= 1) {
        if (gyms.length === 1) {
          setSelectedGymId(gyms[0].gym_id);
          setCustomGym("");
        }
        setStep("mode");
      } else {
        setStep("gym");
      }
    } catch {
      setError("Failed to load presets");
    } finally {
      setLoading(false);
    }
  }, [gyms]);

  const handleGymSelect = useCallback((gymId: string) => {
    setSelectedGymId(gymId);
    setCustomGym("");
    setStep("mode");
  }, []);

  const handleCustomGymSelect = useCallback((name: string) => {
    setSelectedGymId("");
    setCustomGym(name);
    setStep("mode");
  }, []);

  const handleModeSelect = useCallback(async (mode: "template" | "free") => {
    if (mode === "template") {
      setStep("preset");
      return;
    }

    // Start free mode session
    setLoading(true);
    setError(null);
    try {
      const savedGym = selectedGymId ? gyms.find((g) => g.gym_id === selectedGymId) : undefined;
      const gymIdPayload = savedGym ? savedGym.gym_id : undefined;
      const gymNamePayload = savedGym ? undefined : (customGym || undefined);
      const displayName = savedGym?.name ?? customGym ?? undefined;
      const result = await startFreeSession({
        date: paramDate,
        surface: selectedSurface,
        gym_id: gymIdPayload,
        gym_name: gymNamePayload,
        session_mode: "free",
        context: paramContext,
      });

      setActiveSession({
        sessionId: result.session_id,
        surface: selectedSurface,
        mode: "free",
        gymName: displayName,
        tip: result.tip || freeModeTip,
      });
      setSessionStartedAt(Date.now());
      setStep("active");
    } catch {
      setError("Failed to start session");
    } finally {
      setLoading(false);
    }
  }, [selectedSurface, selectedGymId, customGym, gyms, freeModeTip, paramDate, paramContext]);

  const handlePresetSelect = useCallback(async (preset: Preset) => {
    setLoading(true);
    setError(null);
    try {
      const savedGym = selectedGymId ? gyms.find((g) => g.gym_id === selectedGymId) : undefined;
      const gymIdPayload = savedGym ? savedGym.gym_id : undefined;
      const gymNamePayload = savedGym ? undefined : (customGym || undefined);
      const displayName = savedGym?.name ?? customGym ?? undefined;
      const result = await startFreeSession({
        date: paramDate,
        surface: selectedSurface,
        gym_id: gymIdPayload,
        gym_name: gymNamePayload,
        session_mode: "template",
        preset_id: preset.id,
        context: paramContext,
      });

      setActiveSession({
        sessionId: result.session_id,
        surface: selectedSurface,
        mode: "template",
        presetName: preset.name,
        gymName: displayName,
        targetGrade: result.target_grade || undefined,
        restSeconds: result.rest_seconds || undefined,
        tip: result.tip || preset.phase_tip,
        targetClimbs: preset.target_climbs,
      });
      setSessionStartedAt(Date.now());
      setStep("active");
    } catch {
      setError("Failed to start session");
    } finally {
      setLoading(false);
    }
  }, [selectedSurface, selectedGymId, customGym, gyms, paramDate, paramContext]);

  const handleCancel = useCallback(async () => {
    if (!activeSession) return;
    // Remove the unfinished session from state
    try {
      const { getState, putState } = await import("@/lib/api");
      const state = await getState();
      const sessions = (state as Record<string, unknown>).free_sessions as Array<Record<string, unknown>> || [];
      const filtered = sessions.filter((s) => s.id !== activeSession.sessionId);
      await putState({ free_sessions: filtered });
    } catch {
      // Non-critical — session will remain as unfinished
    }
    // Reset state and go back to surface selection
    setActiveSession(null);
    setSessionClimbs([]);
    setStep("surface");
    setError(null);
  }, [activeSession]);

  const handleFinish = useCallback(() => {
    // Don't call finish API yet — go to summary first so user can add feel + notes
    setStep("summary");
  }, []);

  const handleSaveSummary = useCallback(async (feel?: string, notes?: string) => {
    if (!activeSession) return;
    try {
      const result = await finishFreeSession(activeSession.sessionId, {
        overall_feel: feel,
        notes: notes,
      });
      setFinishedData({
        summary: result.summary,
        durationMinutes: result.duration_minutes,
        loadScore: result.load_score,
      });
      invalidateFreeSessionHistory(qc);
    } catch {
      // Session might already be finished — non-critical
    }
    router.push("/today");
  }, [activeSession, router, qc]);

  // ── Circuit handlers ──────────────────────────────────────────────

  const handleCircuitStart = useCallback(async (config: CircuitConfig) => {
    setCircuitConfig(config);
    setLoading(true);
    setError(null);
    try {
      const result = await startFreeSession({
        date: paramDate,
        surface: "circuit_core",
        session_mode: "circuit",
        context: paramContext,
      });
      setCircuitSessionId(result.session_id);
      setStep("circuit_running");
    } catch {
      setError("Failed to start circuit session");
    } finally {
      setLoading(false);
    }
  }, [paramDate, paramContext]);

  const handleCircuitComplete = useCallback((result: CircuitResult) => {
    setCircuitResult(result);
    setStep("circuit_complete");
  }, []);

  const handleCircuitStop = useCallback((result: CircuitResult) => {
    setCircuitResult(result);
    setStep("circuit_complete");
  }, []);

  const handleCircuitSave = useCallback(async (feel?: string, notes?: string) => {
    if (!circuitSessionId || !circuitResult) return;
    try {
      await finishFreeSession(circuitSessionId, {
        overall_feel: feel,
        notes,
        circuit: {
          work_seconds: circuitResult.workSeconds,
          rest_seconds: circuitResult.restSeconds,
          target_exercises: circuitResult.targetExercises,
          completed_exercises: circuitResult.completedExercises,
          exercises_performed: circuitResult.exercisesPerformed,
        },
      });
      invalidateFreeSessionHistory(qc);
    } catch {
      // Non-critical
    }
    router.push("/today");
  }, [circuitSessionId, circuitResult, router, qc]);

  const handleCircuitRestart = useCallback(() => {
    // Keep same config, go back to running with new session
    if (circuitConfig) {
      handleCircuitStart(circuitConfig);
    }
  }, [circuitConfig, handleCircuitStart]);

  const goBack = useCallback(() => {
    if (step === "gym") setStep("surface");
    else if (step === "mode") setStep(gyms.length > 1 ? "gym" : "surface");
    else if (step === "preset") setStep("mode");
    else if (step === "circuit_setup") setStep("surface");
  }, [step, gyms.length]);

  // ── Render ─────────────────────────────────────────────────────────

  const showBack = step !== "surface" && step !== "active" && step !== "summary"
    && step !== "circuit_running" && step !== "circuit_complete";
  const title = step === "active" ? "Free Session" :
    step === "summary" ? "Summary" :
    step === "circuit_setup" ? "Core Circuit" :
    step === "circuit_complete" ? "Circuit Complete" : "Free Session";

  return (
    <>
      <TopBar
        title={title}
        backHref={showBack ? undefined : undefined}
      />

      <main className="mx-auto max-w-2xl pt-4 pb-24">
        {/* Back button for sub-steps */}
        {showBack && (
          <button
            onClick={goBack}
            className="mb-4 flex items-center gap-1 px-4 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </button>
        )}

        {error && (
          <div className="mx-4 mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading && step !== "active" && (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* STEP: Surface selection */}
        {step === "surface" && !loading && (
          <div className="flex flex-col gap-3 px-4">
            {/* Resume pending draft banner */}
            {pendingDraft && (
              <div className="flex items-center justify-between rounded-xl border border-primary/30 bg-primary/10 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-primary">Resume previous session?</p>
                  <p className="text-xs text-muted-foreground">
                    {pendingDraft.loggedClimbs.length} {pendingDraft.surface === "gym_routes" ? "routes" : "boulders"} logged
                    {pendingDraft.gymName ? ` · ${pendingDraft.gymName}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => { clearDraft(pendingDraft.sessionId); setPendingDraft(null); }}
                    className="text-xs"
                  >
                    Discard
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleResumeDraft(pendingDraft)}
                    className="text-xs"
                  >
                    Resume
                  </Button>
                </div>
              </div>
            )}
            <h2 className="mb-2 text-center text-lg font-semibold">Choose your activity</h2>

            {/* A202: grouped climbing card — collapsible. Single-surface shortcut
                goes directly to handleSurfaceSelect without expanding. */}
            {availableClimbingSurfaces.length === 1 ? (
              <button
                onClick={() => handleSurfaceSelect(availableClimbingSurfaces[0].id)}
                className={`flex items-center gap-4 rounded-xl border bg-gradient-to-r p-4 text-left transition-all hover:scale-[1.01] active:scale-[0.99] ${SURFACE_COLORS[availableClimbingSurfaces[0].id]}`}
              >
                <div className={`flex h-12 w-12 items-center justify-center rounded-lg bg-black/20 ${SURFACE_ICON_COLORS[availableClimbingSurfaces[0].id]}`}>
                  {SURFACE_ICONS[availableClimbingSurfaces[0].id]}
                </div>
                <div className="font-semibold">{availableClimbingSurfaces[0].name}</div>
              </button>
            ) : (
              <div className="rounded-xl border bg-gradient-to-r from-sky-500/20 to-sky-600/5 border-sky-500/30 overflow-hidden">
                <button
                  onClick={() => setClimbingExpanded((v) => !v)}
                  className="flex w-full items-center gap-4 p-4 text-left transition-all active:scale-[0.99]"
                  aria-expanded={climbingExpanded}
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/20 text-sky-400">
                    <Mountain className="size-6" />
                  </div>
                  <div className="flex-1 font-semibold">Climbing</div>
                  <ChevronDown
                    className={`size-5 text-muted-foreground transition-transform ${climbingExpanded ? "rotate-180" : ""}`}
                  />
                </button>
                {climbingExpanded && (
                  <div className="flex flex-col gap-2 border-t border-sky-500/20 bg-black/10 p-3">
                    {availableClimbingSurfaces.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => handleSurfaceSelect(s.id)}
                        className={`flex items-center gap-3 rounded-lg border bg-gradient-to-r p-3 text-left transition-all hover:scale-[1.01] active:scale-[0.99] ${SURFACE_COLORS[s.id]}`}
                      >
                        <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-black/20 ${SURFACE_ICON_COLORS[s.id]}`}>
                          {SURFACE_ICONS[s.id]}
                        </div>
                        <div className="font-medium text-sm">{s.name}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Add-ons divider */}
            <div className="flex items-center gap-3 pt-2">
              <div className="h-px flex-1 bg-border" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Add-ons</span>
              <div className="h-px flex-1 bg-border" />
            </div>

            {/* Core Circuit */}
            <button
              onClick={() => handleSurfaceSelect("circuit_core")}
              className="flex items-center gap-4 rounded-xl border bg-gradient-to-r from-emerald-500/20 to-emerald-600/5 border-emerald-500/30 p-4 text-left transition-all hover:scale-[1.01] active:scale-[0.99]"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-black/20 text-emerald-400">
                <Flame className="size-6" />
              </div>
              <div>
                <div className="font-semibold">Core Circuit</div>
                <div className="text-xs text-muted-foreground">Guided bodyweight core workout with timer</div>
              </div>
            </button>
          </div>
        )}

        {/* STEP: Gym selection */}
        {step === "gym" && !loading && (
          <div className="flex flex-col gap-3 px-4">
            <h2 className="mb-2 text-center text-lg font-semibold">Which gym?</h2>
            {gyms.map((g) => (
              <button
                key={g.gym_id}
                onClick={() => handleGymSelect(g.gym_id)}
                className="rounded-xl border bg-card p-4 text-left font-medium transition-all hover:border-primary/30"
              >
                {g.name}
              </button>
            ))}
            <div className="mt-2">
              <input
                type="text"
                value={customGym}
                onChange={(e) => setCustomGym(e.target.value)}
                placeholder="Other gym..."
                className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/50"
              />
              {customGym && (
                <Button
                  variant="outline"
                  onClick={() => handleCustomGymSelect(customGym)}
                  className="mt-2 w-full"
                >
                  Continue with &quot;{customGym}&quot;
                </Button>
              )}
            </div>
            <Button variant="ghost" onClick={() => { setSelectedGymId(""); setCustomGym(""); setStep("mode"); }} className="text-sm">
              Skip — no gym
            </Button>
          </div>
        )}

        {/* STEP: Mode selection */}
        {step === "mode" && !loading && (
          <div className="flex flex-col gap-4 px-4">
            <h2 className="mb-2 text-center text-lg font-semibold">How do you want to climb?</h2>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleModeSelect("template")}
                className="flex flex-col items-center gap-3 rounded-xl border bg-gradient-to-b from-primary/10 to-transparent p-6 transition-all hover:border-primary/40 active:scale-[0.98]"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/20 text-primary">
                  <Layers className="size-7" />
                </div>
                <div className="text-center">
                  <div className="font-semibold">Template</div>
                  <div className="mt-1 text-xs text-muted-foreground">Get a structure</div>
                </div>
              </button>
              <button
                onClick={() => handleModeSelect("free")}
                className="flex flex-col items-center gap-3 rounded-xl border bg-gradient-to-b from-muted/50 to-transparent p-6 transition-all hover:border-foreground/20 active:scale-[0.98]"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <Route className="size-7" />
                </div>
                <div className="text-center">
                  <div className="font-semibold">Free</div>
                  <div className="mt-1 text-xs text-muted-foreground">Climb your way</div>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* STEP: Preset selection */}
        {step === "preset" && !loading && (
          <div className="flex flex-col gap-3 px-4">
            <h2 className="mb-2 text-center text-lg font-semibold">Choose your session</h2>
            {phaseId && (
              <p className="mb-1 text-center text-xs text-muted-foreground capitalize">
                Current phase: {phaseId.replace("_", " ")}
              </p>
            )}
            {presets.map((p) => {
              const badge = PHASE_BADGE[p.phase_compatibility] || PHASE_BADGE.caution;
              return (
                <button
                  key={p.id}
                  onClick={() => handlePresetSelect(p)}
                  className="flex flex-col gap-2 rounded-xl border bg-card p-4 text-left transition-all hover:border-primary/30 active:scale-[0.99]"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-primary">{PRESET_ICONS[p.icon] || PRESET_ICONS.layers}</span>
                      <span className="font-semibold">{p.name}</span>
                    </div>
                    <span className={`rounded-full border px-2 py-0.5 text-xs ${badge.color}`}>
                      {badge.label} {phaseId.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{p.description}</p>
                  <div className="flex gap-3 text-xs text-muted-foreground">
                    {p.target_grade && <span>~{displayBoulderGrade(p.target_grade, gradeSystem)}</span>}
                    <span>{Math.floor(p.rest_seconds / 60)} min rest</span>
                    <span>{p.target_climbs} climbs</span>
                    <span>{p.duration}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* STEP: Active session (ClimbLogger) */}
        {step === "active" && activeSession && (
          <ClimbLogger
            sessionId={activeSession.sessionId}
            surface={activeSession.surface}
            sessionMode={activeSession.mode}
            presetName={activeSession.presetName}
            gymName={activeSession.gymName}
            targetGrade={activeSession.targetGrade}
            restSeconds={activeSession.restSeconds}
            tip={activeSession.tip}
            targetClimbs={activeSession.targetClimbs}
            onFinish={handleFinish}
            onCancel={handleCancel}
            onClimbLogged={(climb) => setSessionClimbs((prev) => [...prev, climb])}
            gradeSystem={gradeSystem}
          />
        )}

        {/* STEP: Summary */}
        {step === "summary" && activeSession && (
          <SessionSummary
            surface={activeSession.surface}
            gymName={activeSession.gymName}
            presetName={activeSession.presetName}
            durationMinutes={finishedData?.durationMinutes}
            loadScore={finishedData?.loadScore}
            summary={finishedData?.summary}
            climbs={sessionClimbs}
            startedAt={sessionStartedAt}
            onSave={handleSaveSummary}
            gradeSystem={gradeSystem}
          />
        )}

        {/* STEP: Circuit setup */}
        {step === "circuit_setup" && !loading && (
          <CircuitSetup
            onStart={handleCircuitStart}
            onCancel={() => setStep("surface")}
          />
        )}

        {/* STEP: Circuit complete */}
        {step === "circuit_complete" && circuitResult && (
          <CircuitCompletion
            completedExercises={circuitResult.completedExercises}
            targetExercises={circuitResult.targetExercises}
            workSeconds={circuitResult.workSeconds}
            restSeconds={circuitResult.restSeconds}
            durationSeconds={circuitResult.durationSeconds}
            onSave={handleCircuitSave}
            onRestart={handleCircuitRestart}
            onBack={() => setStep("surface")}
          />
        )}
      </main>

      {/* Circuit timer — rendered outside main as fullscreen overlay */}
      {step === "circuit_running" && circuitConfig && (
        <CircuitTimer
          workSeconds={circuitConfig.workSeconds}
          restSeconds={circuitConfig.restSeconds}
          totalExercises={circuitConfig.totalExercises}
          onComplete={handleCircuitComplete}
          onStop={handleCircuitStop}
          onExit={() => setStep("surface")}
        />
      )}
    </>
  );
}

export default function FreeSessionPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>}>
      <FreeSessionContent />
    </Suspense>
  );
}
