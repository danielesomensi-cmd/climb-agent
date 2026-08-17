"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { TopBar } from "@/components/layout/top-bar";
import { SessionTimer } from "@/components/guided/session-timer";
import { ConditionBadge } from "@/components/outdoor/condition-badge";
import { StrategyView } from "@/components/outdoor/strategy-view";
import { LiveRouteLogger, type LiveRoute } from "@/components/outdoor/live-route-logger";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";
import {
  getOutdoorStrategy,
  getOutdoorSpots,
  startOutdoorSession,
  finishOutdoorSession,
  cancelOutdoorSession,
  getActiveOutdoorSession,
  replaceOutdoorRoutes,
} from "@/lib/api";
import type {
  OutdoorDayType,
  OutdoorRouteProfile,
  OutdoorStrategyResponse,
  OutdoorSpot,
  OutdoorSessionFinishResponse,
} from "@/lib/types";
import { useUserState } from "@/lib/hooks/use-state";
import { enqueue } from "@/lib/outbox";
import {
  clearLiveSession,
  isLocalSessionId,
  isOfflineError,
  loadLiveSession,
  newLocalSessionId,
  pickRestoredSession,
  saveLiveSession,
  type LiveOutdoorSession,
} from "@/lib/outdoor-live-session";

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

/** Map backend active-session routes (snake_case at_min) → LiveRoute[]. */
function mapLiveRoutes(routes: unknown): LiveRoute[] {
  if (!Array.isArray(routes)) return [];
  return routes.map((r) => {
    const o = r as Record<string, unknown>;
    return {
      name: String(o.name ?? ""),
      grade: String(o.grade ?? ""),
      attempts: (o.attempts as LiveRoute["attempts"]) ?? [],
      style: o.style as LiveRoute["style"],
      discipline: o.discipline as LiveRoute["discipline"],
      atMin: typeof o.at_min === "number" ? o.at_min : 0,
      ...(typeof o.rest_seconds === "number" ? { rest_seconds: o.rest_seconds } : {}),
      ...(typeof o.climb_seconds === "number" ? { climb_seconds: o.climb_seconds } : {}),
    };
  });
}

export default function OutdoorDayPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const date = String(params.date);
  const spotName = search.get("spot") || "";
  const disciplineParam = (search.get("discipline") as "lead" | "boulder" | "both" | null) || "lead";
  // v1: the strategy/nutrition catalog (C241) is lead-only. On a boulder spot we
  // skip the lead strategy (it would be misleading) and offer a timer + log only.
  const isBoulder = disciplineParam === "boulder";

  const { state: userState } = useUserState();
  const [spots, setSpots] = useState<OutdoorSpot[]>([]);

  const [dayType, setDayType] = useState<OutdoorDayType | null>(null);
  const [profile, setProfile] = useState<OutdoorRouteProfile>({});
  const [strategy, setStrategy] = useState<OutdoorStrategyResponse | null>(null);
  const [loadingStrat, setLoadingStrat] = useState(false);
  const [refineOpen, setRefineOpen] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);

  const [phase, setPhase] = useState<Phase>("setup");
  const [liveRoutes, setLiveRoutes] = useState<LiveRoute[]>([]);
  const [climbBusy, setClimbBusy] = useState(false);
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

  // B336 — true once the session exists only on this device (started offline).
  const [isLocal, setIsLocal] = useState(false);
  // B336 — set when the last server sync failed; drives the "saved on this
  // device" reassurance instead of a red error the athlete cannot act on.
  const [pendingSync, setPendingSync] = useState(false);

  /** B336 — mirror the whole live session to the device. */
  const persist = useCallback(
    (patch: Partial<LiveOutdoorSession> & { sessionId: string; startedAt: string }) => {
      saveLiveSession({
        isLocal,
        date,
        spotName,
        discipline: disciplineParam,
        dayType,
        routes: [],
        ...patch,
      });
    },
    [date, spotName, disciplineParam, dayType, isLocal],
  );

  // Restore an in-progress session after a refresh / app close.
  //
  // B336: the device copy is consulted FIRST and wins (see pickRestoredSession).
  // Before this the restore read only the server, so a phone that died offline
  // came back to an empty day with every logged route gone.
  useEffect(() => {
    let cancelled = false;
    const local = loadLiveSession(date);

    const applyRestore = (s: LiveOutdoorSession | null) => {
      if (cancelled || !s) return;
      setSessionId(s.sessionId);
      setStartedAt(s.startedAt);
      setIsLocal(s.isLocal);
      if (s.dayType) setDayType(s.dayType);
      setLiveRoutes(s.routes as LiveRoute[]);
      setPhase("active");
    };

    getActiveOutdoorSession(date)
      .then((r) => {
        const s = r.session;
        applyRestore(
          pickRestoredSession(local, {
            sessionId: String(s.session_id),
            isLocal: false,
            date,
            spotName: String(s.spot_name ?? spotName ?? ""),
            discipline: disciplineParam,
            dayType: (s.day_type as OutdoorDayType) ?? null,
            startedAt: String(s.started_at),
            routes: mapLiveRoutes(s.routes),
            updatedAt: 0,
          }),
        );
      })
      // 404 = no active session; offline = no answer at all. Either way the
      // device copy is what we have, and it is the one that matters.
      .catch(() => applyRestore(local));

    return () => {
      cancelled = true;
    };
    // Restoring is a per-date, mount-time concern: re-running it when the spot
    // label or day type changes would clobber the live session with itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  // Client owns the route list (multiple attempts, removals); each change is
  // written to the device FIRST (B336) and then synced to the active session as
  // a whole, so it survives a refresh, a crash and a dead battery.
  const syncRoutes = useCallback(
    async (next: LiveRoute[]) => {
      setLiveRoutes(next); // optimistic
      if (!sessionId || !startedAt) return;
      persist({ sessionId, startedAt, routes: next, isLocal });
      if (isLocal) return; // no server session to sync to — the device copy is it
      setClimbBusy(true);
      try {
        await replaceOutdoorRoutes(
          sessionId,
          next.map((r) => ({
            name: r.name,
            grade: r.grade,
            attempts: r.attempts,
            at_min: r.atMin,
            ...(r.style ? { style: r.style } : {}),
            ...(r.discipline ? { discipline: r.discipline } : {}),
            ...(typeof r.rest_seconds === "number" ? { rest_seconds: r.rest_seconds } : {}),
            ...(typeof r.climb_seconds === "number" ? { climb_seconds: r.climb_seconds } : {}),
          })),
        );
        setPendingSync(false);
        setError(null);
      } catch (e) {
        // B336: the route is already on the device, so a dead network is not an
        // error the athlete needs to act on — say so instead of alarming them.
        if (isOfflineError(e)) {
          setPendingSync(true);
        } else {
          setError(e instanceof Error ? e.message : "Failed to sync routes");
        }
      } finally {
        setClimbBusy(false);
      }
    },
    [sessionId, startedAt, isLocal, persist],
  );

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

  // B264: a restored in-progress session never ran setup, so `strategy` is null
  // → the weather widget + rest-guidance disappear after a close/reopen. Re-resolve
  // once we know the day_type and we're past setup; re-runs only when the
  // (day_type, coords) pair changes — so weather fills in once coordinates arrive,
  // without looping when the provider legitimately returns no conditions.
  const autoResolveKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (phase === "setup" || isBoulder || !dayType) return;
    const key = `${dayType}|${coords ? `${coords.lat},${coords.lon}` : "nocoords"}`;
    if (autoResolveKeyRef.current === key) return;
    autoResolveKeyRef.current = key;
    resolve(dayType, profile);
  }, [phase, dayType, isBoulder, coords, resolve, profile]);

  const pickDayType = (dt: OutdoorDayType) => {
    setDayType(dt);
    setReadyOk(null);
    if (!isBoulder) resolve(dt, profile); // boulder: no lead-strategy resolve (v1)
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
      setIsLocal(false);
      setPendingSync(false);
      persist({ sessionId: r.session_id, startedAt: r.started_at, isLocal: false, routes: [] });
      setPhase("active");
    } catch (e) {
      // B336: with no signal the session used to be un-startable, so the whole
      // day went unlogged. Start it on the device instead — the finish then goes
      // through the outbox as a plain (append-only, self-contained) outdoor log.
      if (!isOfflineError(e)) {
        setError(e instanceof Error ? e.message : "Failed to start session");
        return;
      }
      const localId = newLocalSessionId();
      const now = new Date().toISOString();
      setSessionId(localId);
      setStartedAt(now);
      setIsLocal(true);
      setPendingSync(true);
      const stored = saveLiveSession({
        sessionId: localId, isLocal: true, date, spotName,
        discipline: disciplineParam, dayType, startedAt: now, routes: [],
      });
      setPhase("active");
      toast(
        stored
          ? "Started offline — this session is saved on this device and will sync when you're back online."
          : "Started offline, but this device refused to save it. Keep a paper note as a backup.",
        { duration: 8000 },
      );
    }
  };

  const handleFinish = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!sessionId || !startedAt) throw new Error("No active session");
      try {
        const res = await finishOutdoorSession(sessionId, payload as never);
        setFinishMeta(res);
        clearLiveSession();
      } catch (e) {
        // B336: the finish used to bypass the outbox precisely when a session
        // had been STARTED — i.e. the recommended path was the unsafe one. The
        // session id came from the server, so replaying the finish later is
        // valid and also clears the dangling active session.
        if (!isOfflineError(e)) throw e;
        const queued = enqueue("outdoor_finish", { session_id: sessionId, ...payload });
        if (!queued) throw e;
        clearLiveSession();
        toast("Session saved on this device — it will sync when you're back online.", {
          duration: 6000,
        });
      }
    },
    [sessionId, startedAt],
  );

  const cancelActive = async () => {
    if (sessionId && !isLocalSessionId(sessionId)) {
      try { await cancelOutdoorSession(sessionId); } catch { /* already gone */ }
    }
    clearLiveSession();
    router.push("/week");
  };

  // Client-side elapsed for prefilling the log duration.
  const elapsedMin = startedAt ? Math.max(1, Math.round((Date.now() - new Date(startedAt).getTime()) / 60000)) : undefined;

  const isProject = dayType === "project";
  const gatePassed = isBoulder || !isProject || readyOk === true;

  return (
    <>
      <TopBar title="Outdoor day" />
      <main className="mx-auto max-w-xl px-4 pb-24 pt-4 space-y-5">
        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">{spotName || "Outdoor session"}</h1>
          <p className="text-xs text-zinc-500">{date}</p>
        </div>

        {/* Weather widget (A227) — full-width, expandable; hidden when no conditions */}
        <ConditionBadge conditions={strategy?.conditions} coords={coords} />

        {error && <p className="rounded-md border border-red-900/40 bg-red-950/20 p-3 text-sm text-red-400">{error}</p>}

        {/* B336 — offline reassurance. Amber, not red: nothing is lost and there
            is nothing for the athlete to do about it at the crag. */}
        {pendingSync && (
          <p className="rounded-md border border-amber-900/40 bg-amber-950/20 p-3 text-sm text-amber-200/90">
            Offline — this session is saved on this device and will sync when you&apos;re back
            online. Keep logging.
          </p>
        )}

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

            {dayType && isBoulder && (
              <div className="rounded-lg border border-white/10 bg-zinc-900/30 p-4 text-sm text-zinc-400">
                <p className="font-medium text-zinc-200">Boulder strategy coming soon</p>
                <p className="mt-1">Use the timer and log your sends — full boulder strategy lands in a later update.</p>
              </div>
            )}

            {dayType && !isBoulder && (
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
              </>
            )}

            {/* Actions (shared — boulder or lead) */}
            {dayType && (
              <div className="space-y-2">
                {/* B336: the strategy is ADVICE, not a precondition. Gating Start
                    on a network fetch meant no signal → no session → the whole
                    day unlogged, which is the opposite of the trade we want. */}
                {!isBoulder && !strategy && !loadingStrat && (
                  <p className="text-xs text-zinc-500">
                    Strategy unavailable offline — you can still start and log the session.
                  </p>
                )}
                <button
                  onClick={start}
                  disabled={!gatePassed}
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

            {/* Live route logging — capture each climb as you go */}
            {startedAt && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-zinc-300">Log as you climb</h3>
                <LiveRouteLogger
                  discipline={disciplineParam}
                  startedAt={startedAt}
                  routes={liveRoutes}
                  onChange={syncRoutes}
                  suggestedRest={strategy?.strategy.base.rest_between_attempts_min}
                  busy={climbBusy}
                />
              </div>
            )}

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
            initialRoutes={liveRoutes.map((r) => ({
              name: r.name,
              grade: r.grade,
              attempts: r.attempts,
              ...(r.style ? { style: r.style } : {}),
              ...(r.discipline ? { discipline: r.discipline } : {}),
              ...(typeof r.rest_seconds === "number" ? { rest_seconds: r.rest_seconds } : {}),
              ...(typeof r.climb_seconds === "number" ? { climb_seconds: r.climb_seconds } : {}),
            }))}
            conditions={strategy?.conditions}
            durationCappedNote={
              elapsedMin && elapsedMin > 600 ? { cap: 600, raw: elapsedMin } : null
            }
            // B336: a LOCAL session has no server id to finish, so it falls
            // through to the form's own postOutdoorLog path — which is already
            // outbox-backed (A245 F5) and is exactly the right shape for it:
            // append-only and self-contained.
            onSubmit={sessionId && !isLocal ? handleFinish : undefined}
            submitLabel={sessionId ? "Finish & save" : undefined}
            onSuccess={() => {
              clearLiveSession();
              router.push("/outdoor");
            }}
          />
        )}

        {finishMeta?.duration_capped && (
          <p className="text-xs text-amber-500">Saved with capped duration ({finishMeta.duration_minutes} min).</p>
        )}
      </main>
    </>
  );
}
