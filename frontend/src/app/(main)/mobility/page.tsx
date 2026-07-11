"use client";

// A231 — Stretching & Mobility guided flow (Core Circuit UX).
// Setup: pick regions + total time + pace + rest — the system picks the
// stretches. Flow: auto-advancing fullscreen timer with sounds and L/R
// sequencing. GATE-1 by placement: reachable only from the free-session area.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import {
  deleteFreeSession,
  finishFreeSession,
  getMobilityPool,
  startFreeSession,
  type MobilityRegion,
} from "@/lib/api";
import { MobilitySetup, type MobilityConfig } from "@/components/mobility/MobilitySetup";
import {
  MobilityFlowTimer,
  type MobilityFlowResult,
} from "@/components/mobility/MobilityFlowTimer";

type Step = "setup" | "flow" | "summary";

export default function MobilityPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("setup");
  const [regions, setRegions] = useState<MobilityRegion[]>([]);
  const [config, setConfig] = useState<MobilityConfig | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [result, setResult] = useState<MobilityFlowResult | null>(null);
  const [durationMinutes, setDurationMinutes] = useState<number | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    getMobilityPool()
      .then((data) => setRegions(data.regions))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const handleStart = useCallback(
    async (cfg: MobilityConfig) => {
      setError(null);
      try {
        const r = await startFreeSession({
          date: today,
          surface: "mobility_stretching",
          session_mode: "mobility",
          context: "standalone",
        });
        setSessionId(r.session_id);
        setConfig(cfg);
        setStep("flow");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start session");
      }
    },
    [today]
  );

  const finalize = useCallback(
    async (res: MobilityFlowResult) => {
      setResult(res);
      if (!sessionId) {
        setStep("summary");
        return;
      }
      if (res.completedSteps === 0) {
        // Nothing done — drop the session record instead of logging an empty one
        try {
          await deleteFreeSession(sessionId);
        } catch {
          /* best-effort */
        }
        setSessionId(null);
        setStep("setup");
        return;
      }
      try {
        const r = await finishFreeSession(sessionId, {
          mobility: {
            completed_entries: res.entriesPerformed,
            completed_count: res.entriesPerformed.length,
          },
        });
        setDurationMinutes(r.duration_minutes);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to save session");
      }
      setStep("summary");
    },
    [sessionId]
  );

  const handleExitFlow = useCallback(() => {
    // Exit without result — treat as stop with nothing recorded
    if (sessionId) {
      deleteFreeSession(sessionId).catch(() => {});
      setSessionId(null);
    }
    setStep("setup");
  }, [sessionId]);

  return (
    <>
      {step !== "flow" && <TopBar title="Stretching & Mobility" backHref="/free-session" />}
      <main className="mx-auto max-w-lg pb-8">
        {error && (
          <div className="mx-4 mb-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {step === "setup" &&
          (loading ? (
            <p className="py-12 text-center text-sm text-muted-foreground">Loading…</p>
          ) : (
            <MobilitySetup
              regions={regions}
              today={today}
              onStart={handleStart}
              onCancel={() => router.push("/free-session")}
            />
          ))}

        {step === "flow" && config && (
          <MobilityFlowTimer
            steps={config.plan.steps}
            restSeconds={config.restSeconds}
            onComplete={finalize}
            onStop={finalize}
            onExit={handleExitFlow}
          />
        )}

        {step === "summary" && result && (
          <div className="flex flex-col items-center gap-4 px-4 py-10 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-violet-500/20 text-4xl">
              🧘
            </div>
            <h2 className="text-xl font-bold">Nice work!</h2>
            <p className="text-sm text-muted-foreground">
              {result.entriesPerformed.length}{" "}
              {result.entriesPerformed.length === 1 ? "stretch" : "stretches"} ·{" "}
              {result.completedSteps}/{result.totalSteps} steps
              {durationMinutes != null && ` · ${durationMinutes} min`}
            </p>
            <div className="flex w-full max-w-xs flex-col gap-2 text-left">
              {result.entriesPerformed.map((e) => (
                <div key={e.id} className="rounded-lg border bg-card p-3 text-sm">
                  <span className="text-violet-400">✓</span> {e.name}
                </div>
              ))}
            </div>
            <div className="flex w-full max-w-xs flex-col gap-2">
              <Button
                onClick={() => {
                  setResult(null);
                  setSessionId(null);
                  setConfig(null);
                  setDurationMinutes(null);
                  setStep("setup");
                }}
                variant="outline"
                className="w-full"
              >
                Stretch again
              </Button>
              <Button onClick={() => router.push("/free-session")} className="w-full">
                Done
              </Button>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
