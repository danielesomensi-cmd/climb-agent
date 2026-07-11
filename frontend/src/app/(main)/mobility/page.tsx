"use client";

// A230 — Stretching & Mobility free-session surface.
// GATE-1 by placement: reachable only from the free-session area (post-session
// or rest-day context) — never from warm-up flows or planned climbing sessions.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import {
  finishFreeSession,
  getMobilityPool,
  startFreeSession,
  type MobilityEntry,
  type MobilityRegion,
} from "@/lib/api";
import { MobilityRunner, type MobilityResult } from "@/components/mobility/MobilityRunner";

type Step = "regions" | "entries" | "runner" | "summary";

const REGION_ICONS: Record<string, string> = {
  forearms_wrists: "🖐️",
  hips_glutes: "🍑",
  chest_anterior_shoulder: "🫁",
  thoracic_spine: "🦴",
  hip_flexors_quads: "🦵",
  adductors_groin: "🧘",
  lats: "🔝",
  shoulders_scapula: "🏋️",
  hamstrings: "🏃",
  calves_ankles: "🦶",
  spine_rotation_obliques: "🌀",
};

const EQUIPMENT_LABELS: Record<string, string> = {
  foam_roller: "Foam roller",
  ball_or_roller: "Ball / roller",
  strap: "Strap / towel",
  wall: "Wall",
  pullup_bar: "Bar",
  block: "Step / block",
};

export default function MobilityPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("regions");
  const [regions, setRegions] = useState<MobilityRegion[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [activeEntry, setActiveEntry] = useState<MobilityEntry | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [completed, setCompleted] = useState<MobilityResult[]>([]);
  const [gateBannerDismissed, setGateBannerDismissed] = useState(false);

  const [loading, setLoading] = useState(true);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ duration_minutes: number | null } | null>(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    setLoading(true);
    getMobilityPool(today)
      .then((data) => setRegions(data.regions))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load pool"))
      .finally(() => setLoading(false));
  }, [today]);

  const selectedRegion = useMemo(
    () => regions.find((r) => r.id === selectedRegionId) ?? null,
    [regions, selectedRegionId]
  );

  const regionHasWarnings = useMemo(
    () => (selectedRegion?.entries ?? []).some((e) => e.warning),
    [selectedRegion]
  );

  const completedIds = useMemo(() => new Set(completed.map((c) => c.id)), [completed]);

  // Lazily create the free session on the first started stretch, so browsing
  // the pool never creates a session record.
  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;
    const r = await startFreeSession({
      date: today,
      surface: "mobility_stretching",
      session_mode: "mobility",
      context: "standalone",
    });
    setSessionId(r.session_id);
    return r.session_id;
  }, [sessionId, today]);

  const handleEntrySelect = useCallback(
    async (entry: MobilityEntry) => {
      setError(null);
      try {
        await ensureSession();
        setActiveEntry(entry);
        setStep("runner");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start session");
      }
    },
    [ensureSession]
  );

  const handleRunnerComplete = useCallback((result: MobilityResult) => {
    setCompleted((prev) =>
      prev.some((c) => c.id === result.id) ? prev : [...prev, result]
    );
    setActiveEntry(null);
    setStep("entries");
  }, []);

  const handleFinish = useCallback(async () => {
    if (!sessionId) return;
    setFinishing(true);
    setError(null);
    try {
      const r = await finishFreeSession(sessionId, {
        mobility: {
          completed_entries: completed,
          completed_count: completed.length,
        },
      });
      setSummary({ duration_minutes: r.duration_minutes });
      setStep("summary");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to finish session");
    } finally {
      setFinishing(false);
    }
  }, [sessionId, completed]);

  return (
    <>
      <TopBar
        title="Stretching & Mobility"
        backHref={step === "regions" ? "/free-session" : undefined}
      />
      <main className="mx-auto max-w-lg px-4 py-4">
        {error && (
          <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* STEP: Region picker */}
        {step === "regions" && (
          <div className="flex flex-col gap-3">
            <p className="text-center text-sm text-muted-foreground">
              Pick a body region. Releases first, then stretches — roll first, stretch second.
            </p>
            {loading ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
            ) : (
              regions.map((region) => (
                <button
                  key={region.id}
                  onClick={() => {
                    setSelectedRegionId(region.id);
                    setGateBannerDismissed(false);
                    setStep("entries");
                  }}
                  className="flex items-center gap-3 rounded-xl border bg-card p-4 text-left transition-all hover:border-primary/40 active:scale-[0.99]"
                >
                  <div className="text-2xl">{REGION_ICONS[region.id] ?? "🧘"}</div>
                  <div className="flex-1 font-medium">{region.label}</div>
                  <span className="rounded-full border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground">
                    {region.count}
                  </span>
                </button>
              ))
            )}
            {completed.length > 0 && (
              <FinishBar
                count={completed.length}
                finishing={finishing}
                onFinish={handleFinish}
              />
            )}
          </div>
        )}

        {/* STEP: Entry list */}
        {step === "entries" && selectedRegion && (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setStep("regions")}
              className="text-left text-sm text-muted-foreground hover:text-foreground"
            >
              ← All regions
            </button>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <span>{REGION_ICONS[selectedRegion.id] ?? "🧘"}</span>
              <span>{selectedRegion.label}</span>
            </h2>

            {/* GATE-2 banner — dismissible, non-blocking */}
            {regionHasWarnings && !gateBannerDismissed && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-400">
                <span>⚠️</span>
                <span className="flex-1">
                  Climbing session scheduled later today — skip forearm-flexor stretches,
                  they can reduce grip strength for up to 1h.
                </span>
                <button
                  onClick={() => setGateBannerDismissed(true)}
                  className="text-amber-400/70 hover:text-amber-400"
                  aria-label="Dismiss"
                >
                  ✕
                </button>
              </div>
            )}

            {selectedRegion.entries.map((entry) => (
              <button
                key={entry.id}
                onClick={() => handleEntrySelect(entry)}
                className={`flex flex-col gap-1.5 rounded-xl border p-4 text-left transition-all hover:border-primary/40 active:scale-[0.99] ${
                  completedIds.has(entry.id) ? "border-emerald-500/40 bg-emerald-500/5" : "bg-card"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{entry.name}</span>
                  {completedIds.has(entry.id) && <span className="text-emerald-400">✓</span>}
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {entry.mode === "untimed_release" ? (
                    <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-sky-400">
                      Release
                    </span>
                  ) : entry.ux_flow ? (
                    <span className="rounded-full border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-teal-400">
                      Slow flow · {entry.prescription_defaults.work_seconds}s
                    </span>
                  ) : (
                    <span className="rounded-full border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-teal-400">
                      {entry.prescription_defaults.work_seconds}s hold
                    </span>
                  )}
                  {entry.unilateral && <span className="rounded-full border px-2 py-0.5">Per side</span>}
                  {entry.prescription_defaults.sets > 1 && (
                    <span className="rounded-full border px-2 py-0.5">
                      {entry.prescription_defaults.sets} sets
                    </span>
                  )}
                  {entry.equipment_required.map((eq) => (
                    <span key={eq} className="rounded-full border px-2 py-0.5">
                      {EQUIPMENT_LABELS[eq] ?? eq}
                    </span>
                  ))}
                </div>
                {entry.warning && (
                  <div className="text-xs text-amber-400">⚠️ {entry.warning}</div>
                )}
              </button>
            ))}

            {completed.length > 0 && (
              <FinishBar
                count={completed.length}
                finishing={finishing}
                onFinish={handleFinish}
              />
            )}
          </div>
        )}

        {/* STEP: Runner */}
        {step === "runner" && activeEntry && (
          <MobilityRunner
            entry={activeEntry}
            onComplete={handleRunnerComplete}
            onExit={() => {
              setActiveEntry(null);
              setStep("entries");
            }}
          />
        )}

        {/* STEP: Summary */}
        {step === "summary" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="text-5xl">🧘</div>
            <h2 className="text-xl font-semibold">Session complete</h2>
            <p className="text-sm text-muted-foreground">
              {completed.length} {completed.length === 1 ? "stretch" : "stretches"} completed
              {summary?.duration_minutes != null && ` · ${summary.duration_minutes} min`}
            </p>
            <div className="flex w-full max-w-xs flex-col gap-2 text-left">
              {completed.map((c) => (
                <div key={c.id} className="rounded-lg border bg-card p-3 text-sm">
                  <span className="text-emerald-400">✓</span> {c.name}
                </div>
              ))}
            </div>
            <Button onClick={() => router.push("/free-session")} className="w-full max-w-xs">
              Done
            </Button>
          </div>
        )}
      </main>
    </>
  );
}

function FinishBar({
  count,
  finishing,
  onFinish,
}: {
  count: number;
  finishing: boolean;
  onFinish: () => void;
}) {
  return (
    <div className="sticky bottom-4 mt-2 rounded-xl border bg-background/95 p-3 shadow-lg backdrop-blur">
      <div className="mb-2 text-sm">
        <span className="font-semibold">{count}</span>{" "}
        <span className="text-muted-foreground">
          {count === 1 ? "stretch" : "stretches"} done
        </span>
      </div>
      <Button onClick={onFinish} disabled={finishing} className="w-full">
        {finishing ? "Saving…" : "Finish session"}
      </Button>
    </div>
  );
}
