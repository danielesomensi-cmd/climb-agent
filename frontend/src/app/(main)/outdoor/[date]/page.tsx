"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { SessionTimer } from "@/components/guided/session-timer";
import { ConditionBadge } from "@/components/outdoor/condition-badge";
import { StrategyView } from "@/components/outdoor/strategy-view";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";
import {
  getOutdoorStrategy,
  getOutdoorSpots,
  startOutdoorSession,
  finishOutdoorSession,
  cancelOutdoorSession,
} from "@/lib/api";
import type {
  OutdoorDayType,
  OutdoorRouteProfile,
  OutdoorStrategyResponse,
  OutdoorSpot,
  OutdoorSessionFinishResponse,
} from "@/lib/types";
import { useUserState } from "@/lib/hooks/use-state";

// ---------------------------------------------------------------------------
// Static option metadata
// ---------------------------------------------------------------------------

const DAY_TYPES: { id: OutdoorDayType; label: string; sub: string; icon: string }[] = [
  { id: "project", label: "Project", sub: "Max redpoint burns", icon: "🎯" },
  { id: "onsight_flash", label: "Onsight / Flash", sub: "First-go attempts", icon: "👁️" },
  { id: "volume", label: "Volume", sub: "Sub-max mileage", icon: "🔁" },
  { id: "scout_easy", label: "Scout / Easy", sub: "Explore & recover", icon: "🧭" },
];

// KB leverage order for progressive refine.
const REFINE: { key: keyof OutdoorRouteProfile; label: string; options: { v: string; l: string }[] }[] = [
  { key: "route_length", label: "Length", options: [
    { v: "short_power", l: "Short / power" }, { v: "medium", l: "Medium" }, { v: "long_endurance", l: "Long / endurance" } ] },
  { key: "wall_angle", label: "Angle", options: [
    { v: "slab", l: "Slab" }, { v: "vertical", l: "Vertical" }, { v: "overhang", l: "Overhang" }, { v: "roof", l: "Roof" } ] },
  { key: "hold_style", label: "Holds", options: [
    { v: "crimp", l: "Crimp" }, { v: "sloper_pinch", l: "Sloper / pinch" }, { v: "mixed", l: "Mixed" } ] },
  { key: "target_grade_relative", label: "Grade", options: [
    { v: "within_limit", l: "Within limit" }, { v: "at_or_above_limit", l: "At / above limit" } ] },
];

type Phase = "setup" | "active" | "logging";

export default function OutdoorDayPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const date = String(params.date);
  const spotName = search.get("spot") || "";
  const disciplineParam = (search.get("discipline") as "lead" | "boulder" | "both" | null) || "lead";

  const { state: userState } = useUserState();
  const [spots, setSpots] = useState<OutdoorSpot[]>([]);

  const [dayType, setDayType] = useState<OutdoorDayType | null>(null);
  const [profile, setProfile] = useState<OutdoorRouteProfile>({});
  const [strategy, setStrategy] = useState<OutdoorStrategyResponse | null>(null);
  const [loadingStrat, setLoadingStrat] = useState(false);
  const [refineOpen, setRefineOpen] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);

  const [phase, setPhase] = useState<Phase>("setup");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [finishMeta, setFinishMeta] = useState<OutdoorSessionFinishResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Readiness gate (project only) — null = unanswered, true = ok, false = red flag.
  const [readyOk, setReadyOk] = useState<boolean | null>(null);

  // Injury history (D68) → pre-warn on the readiness gate.
  const injuryAreas = useMemo(() => {
    const lims = (userState?.limitations || {}) as Record<string, unknown>;
    return Object.keys(lims);
  }, [userState]);

  useEffect(() => {
    getOutdoorSpots().then((r) => setSpots(r.spots)).catch(() => {});
  }, []);

  // Geolocation once (graceful — no weather → no conditions/badge).
  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => {},
      { timeout: 8000, maximumAge: 15 * 60 * 1000 },
    );
  }, []);

  const resolve = useCallback(
    async (dt: OutdoorDayType, prof: OutdoorRouteProfile) => {
      setLoadingStrat(true);
      setError(null);
      try {
        const data = await getOutdoorStrategy({
          day_type: dt,
          discipline: "lead", // v1: catalog is lead-only
          use_current_phase: true,
          ...prof,
          ...(coords ? { lat: coords.lat, lon: coords.lon, date } : {}),
        });
        setStrategy(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load strategy");
      } finally {
        setLoadingStrat(false);
      }
    },
    [coords, date],
  );

  const pickDayType = (dt: OutdoorDayType) => {
    setDayType(dt);
    setReadyOk(null);
    resolve(dt, profile);
  };

  const setRefine = (key: keyof OutdoorRouteProfile, v: string) => {
    const next = { ...profile };
    if (next[key] === v) delete next[key];
    else (next[key] as string) = v;
    setProfile(next);
    if (dayType) resolve(dayType, next);
  };

  const start = async () => {
    if (!dayType) return;
    setError(null);
    try {
      const r = await startOutdoorSession({ date, spot_name: spotName || undefined, discipline: disciplineParam, day_type: dayType });
      setSessionId(r.session_id);
      setStartedAt(r.started_at);
      setPhase("active");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    }
  };

  const handleFinish = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!sessionId) throw new Error("No active session");
      const res = await finishOutdoorSession(sessionId, payload as never);
      setFinishMeta(res);
    },
    [sessionId],
  );

  const cancelActive = async () => {
    if (sessionId) {
      try { await cancelOutdoorSession(sessionId); } catch { /* already gone */ }
    }
    router.push("/week");
  };

  // Client-side elapsed for prefilling the log duration.
  const elapsedMin = startedAt ? Math.max(1, Math.round((Date.now() - new Date(startedAt).getTime()) / 60000)) : undefined;

  const isProject = dayType === "project";
  const gatePassed = !isProject || readyOk === true;

  return (
    <>
      <TopBar title="Outdoor day" />
      <main className="mx-auto max-w-xl px-4 pb-24 pt-4 space-y-5">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">{spotName || "Outdoor session"}</h1>
            <p className="text-xs text-zinc-500">{date}</p>
          </div>
          <ConditionBadge conditions={strategy?.conditions} />
        </div>

        {error && <p className="rounded-md border border-red-900/40 bg-red-950/20 p-3 text-sm text-red-400">{error}</p>}

        {/* ── SETUP ─────────────────────────────────────────────── */}
        {phase === "setup" && (
          <>
            <div>
              <h2 className="mb-2 text-sm font-medium text-zinc-300">What kind of day?</h2>
              <div className="grid grid-cols-2 gap-2">
                {DAY_TYPES.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => pickDayType(d.id)}
                    className={`rounded-xl border p-3 text-left transition ${
                      dayType === d.id ? "border-indigo-500 bg-indigo-950/30" : "border-white/10 hover:border-white/20"
                    }`}
                  >
                    <div className="text-xl" aria-hidden="true">{d.icon}</div>
                    <div className="mt-1 text-sm font-medium text-zinc-100">{d.label}</div>
                    <div className="text-[11px] text-zinc-500">{d.sub}</div>
                  </button>
                ))}
              </div>
            </div>

            {dayType && (
              <>
                {/* Refine (progressive disclosure) */}
                <div className="rounded-lg border border-white/5">
                  <button
                    type="button"
                    onClick={() => setRefineOpen((v) => !v)}
                    aria-expanded={refineOpen}
                    className="flex w-full items-center justify-between p-3 text-left"
                  >
                    <span className="text-sm font-medium text-zinc-300">Refine (optional)</span>
                    <svg className={`h-4 w-4 text-zinc-500 transition-transform ${refineOpen ? "rotate-180" : ""}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {refineOpen && (
                    <div className="space-y-3 border-t border-white/5 p-3">
                      {REFINE.map((dim) => (
                        <div key={dim.key}>
                          <div className="mb-1 text-[11px] uppercase tracking-wide text-zinc-500">{dim.label}</div>
                          <div className="flex flex-wrap gap-1.5">
                            {dim.options.map((o) => (
                              <button
                                key={o.v}
                                onClick={() => setRefine(dim.key, o.v)}
                                className={`rounded-full border px-3 py-1 text-xs transition ${
                                  profile[dim.key] === o.v ? "border-indigo-500 bg-indigo-950/40 text-indigo-200" : "border-white/10 text-zinc-400"
                                }`}
                              >
                                {o.l}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Readiness gate (project only) */}
                {isProject && (
                  <div className="rounded-lg border border-white/10 p-3">
                    <p className="text-sm font-medium text-zinc-200">Fingers OK? Any pain or tweaks?</p>
                    {injuryAreas.length > 0 && (
                      <p className="mt-1 text-xs text-amber-500">History flagged: {injuryAreas.join(", ")}. Be honest with yourself.</p>
                    )}
                    <div className="mt-2 flex gap-2">
                      <button onClick={() => setReadyOk(true)} className={`flex-1 rounded-md border px-3 py-2 text-sm ${readyOk === true ? "border-emerald-600 bg-emerald-950/30 text-emerald-300" : "border-white/10"}`}>All good</button>
                      <button onClick={() => setReadyOk(false)} className={`flex-1 rounded-md border px-3 py-2 text-sm ${readyOk === false ? "border-red-600 bg-red-950/30 text-red-300" : "border-white/10"}`}>Pain / tweak</button>
                    </div>
                    {readyOk === false && (
                      <div className="mt-2 rounded-md border border-amber-900/40 bg-amber-950/20 p-2.5 text-xs text-amber-200/90">
                        <p className="font-medium">Red flag — consider downgrading.</p>
                        <p className="mt-1">{strategy?.strategy.base.downgrade_rule}</p>
                        <div className="mt-2 flex gap-2">
                          <button onClick={() => pickDayType("volume")} className="rounded border border-white/20 px-2 py-1">Switch to Volume</button>
                          <button onClick={() => pickDayType("scout_easy")} className="rounded border border-white/20 px-2 py-1">Switch to Scout</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Strategy */}
                {loadingStrat && <p className="text-sm text-zinc-500">Loading strategy…</p>}
                {strategy && !loadingStrat && <StrategyView data={strategy} />}

                {/* Actions */}
                <div className="space-y-2">
                  <button
                    onClick={start}
                    disabled={!gatePassed || !strategy}
                    className="w-full rounded-md bg-indigo-600 py-2.5 text-sm font-medium text-white disabled:opacity-40"
                  >
                    Start session
                  </button>
                  <button
                    onClick={() => setPhase("logging")}
                    className="w-full rounded-md border border-white/10 py-2 text-sm text-zinc-400"
                  >
                    Log without timer
                  </button>
                </div>
              </>
            )}
          </>
        )}

        {/* ── ACTIVE ────────────────────────────────────────────── */}
        {phase === "active" && (
          <>
            <div className="flex items-center justify-between rounded-xl border border-indigo-700/30 bg-indigo-950/20 p-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-indigo-400">Session in progress</p>
                <p className="text-sm text-zinc-300">{dayType?.replace(/_/g, " ")}</p>
              </div>
              {startedAt && <div className="text-xl font-semibold text-zinc-100"><SessionTimer startedAt={startedAt} /></div>}
            </div>

            {strategy && (
              <details className="rounded-lg border border-white/5">
                <summary className="cursor-pointer p-3 text-sm font-medium text-zinc-300">Strategy</summary>
                <div className="border-t border-white/5 p-3"><StrategyView data={strategy} /></div>
              </details>
            )}

            <div className="space-y-2">
              <button onClick={() => setPhase("logging")} className="w-full rounded-md bg-indigo-600 py-2.5 text-sm font-medium text-white">
                Close &amp; log
              </button>
              <button onClick={cancelActive} className="w-full rounded-md border border-white/10 py-2 text-sm text-zinc-500">
                Discard session
              </button>
            </div>
          </>
        )}

        {/* ── LOGGING ───────────────────────────────────────────── */}
        {phase === "logging" && (
          <OutdoorLogForm
            spots={spots}
            defaultDate={date}
            defaultSpotName={spotName}
            defaultDiscipline={disciplineParam}
            defaultDuration={elapsedMin}
            dayType={dayType || undefined}
            routeProfile={profile}
            conditions={strategy?.conditions}
            durationCappedNote={
              elapsedMin && elapsedMin > 600 ? { cap: 600, raw: elapsedMin } : null
            }
            onSubmit={sessionId ? handleFinish : undefined}
            submitLabel={sessionId ? "Finish & save" : undefined}
            onSuccess={() => router.push("/outdoor")}
          />
        )}

        {finishMeta?.duration_capped && (
          <p className="text-xs text-amber-500">Saved with capped duration ({finishMeta.duration_minutes} min).</p>
        )}
      </main>
    </>
  );
}
