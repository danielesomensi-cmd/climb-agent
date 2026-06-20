"use client";

import { useEffect, useRef, useState } from "react";
import type { OutdoorRoute } from "@/lib/types";

/**
 * A226 / A227 — log routes LIVE during an active outdoor session.
 *
 * - Quick-add creates a new route (grade + optional name) with its first attempt.
 * - Each route row has +✓ / +✗ to append MORE attempts to that same route with
 *   one tap (no need to retype the name).
 * - A parallel REST timer counts up since the last attempt, with the strategy's
 *   suggested rest shown beside it.
 *
 * A227 additions:
 * - A2: on a first-attempt send, tag the burn as Onsight or Flash. A send after
 *   the first attempt is a Redpoint automatically (and adding attempts to an
 *   onsight/flash route downgrades it) so `flash/onsight ⇒ attempts == 1` holds.
 * - A3: each row shows the labeled REST taken before the burn (and, if timed,
 *   the on-the-wall CLIMB time) instead of an ambiguous cumulative counter.
 * - A4: an optional "Start climb" timer; pressing Sent/Fell stops it and starts
 *   the mandatory rest. Stored additively as `climb_seconds` — fully optional.
 */

const FRENCH_SPORT_GRADES = [
  "4a","4b","4c","5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+","9a","9a+",
];
const FONT_BOULDER_GRADES = [
  "4","4+","5","5+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
];

export interface LiveRoute extends OutdoorRoute {
  /** minutes since session start when last touched (pacing display) */
  atMin: number;
}

interface Props {
  discipline: "lead" | "boulder" | "both";
  startedAt: string;
  routes: LiveRoute[];
  onChange: (routes: LiveRoute[]) => void;
  suggestedRest?: string;
  busy?: boolean;
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Rest before this burn for a row: prefer the stored value, fall back to the
 *  at_min delta to the previous route (legacy live routes have no rest_seconds). */
function restForRow(routes: LiveRoute[], i: number): number | null {
  const r = routes[i];
  if (typeof r.rest_seconds === "number") return r.rest_seconds;
  if (i > 0) {
    const delta = r.atMin - routes[i - 1].atMin;
    if (delta > 0) return delta * 60;
  }
  return null;
}

export function LiveRouteLogger({ discipline, startedAt, routes, onChange, suggestedRest, busy }: Props) {
  const grades = discipline === "boulder" ? FONT_BOULDER_GRADES : FRENCH_SPORT_GRADES;
  const [grade, setGrade] = useState(grades.includes("6a") ? "6a" : grades[0]);
  const [name, setName] = useState("");
  const routeLabel = discipline === "boulder" ? "problem" : "route";

  const startMs = new Date(startedAt).getTime();

  // React 19 lint bans Date.now()/ref reads in render. Keep "now" and the last
  // action time in refs (written from handlers/effects only); the 1s ticker reads
  // them and derives the rest counter. Fallback to the latest route's minute mark
  // covers a restore where we have no live action ref yet.
  const nowMsRef = useRef<number>(startMs);
  const liveActionMsRef = useRef<number | null>(null);
  const [restSec, setRestSec] = useState(0);

  // A4 — optional climb timer (counts on-the-wall time for the current burn).
  const climbStartMsRef = useRef<number | null>(null);
  const [climbSec, setClimbSec] = useState(0);
  const [climbing, setClimbing] = useState(false);

  useEffect(() => {
    const tick = () => {
      nowMsRef.current = Date.now();
      const fallback = routes.length ? startMs + Math.max(...routes.map((r) => r.atMin)) * 60000 : null;
      const ref = liveActionMsRef.current ?? fallback;
      setRestSec(ref == null ? 0 : Math.max(0, Math.floor((nowMsRef.current - ref) / 1000)));
      setClimbSec(
        climbStartMsRef.current == null
          ? 0
          : Math.max(0, Math.floor((nowMsRef.current - climbStartMsRef.current) / 1000)),
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [routes, startMs]);

  const startClimb = () => {
    climbStartMsRef.current = nowMsRef.current;
    setClimbing(true);
    setClimbSec(0);
  };

  /** Stop the climb timer (if running) and return the elapsed seconds. */
  const consumeClimb = (): number | undefined => {
    if (climbStartMsRef.current == null) return undefined;
    const s = Math.max(1, Math.round((nowMsRef.current - climbStartMsRef.current) / 1000));
    climbStartMsRef.current = null;
    setClimbing(false);
    setClimbSec(0);
    return s;
  };

  const addRoute = (result: "sent" | "fell") => {
    const nowMs = nowMsRef.current;
    const climb = consumeClimb();
    const rest = Math.round(restSec); // rest taken before this burn
    liveActionMsRef.current = nowMs;
    setRestSec(0);
    const atMin = Math.max(0, Math.round((nowMs - startMs) / 60000));
    onChange([
      ...routes,
      {
        name: name.trim() || `${routeLabel} ${routes.length + 1}`,
        grade,
        attempts: [{ result }],
        atMin,
        rest_seconds: rest,
        ...(climb ? { climb_seconds: climb } : {}),
      },
    ]);
    setName("");
  };

  const addAttempt = (idx: number, result: "sent" | "fell") => {
    const nowMs = nowMsRef.current;
    const climb = consumeClimb();
    liveActionMsRef.current = nowMs;
    setRestSec(0);
    const atMin = Math.max(0, Math.round((nowMs - startMs) / 60000));
    onChange(
      routes.map((r, i) => {
        if (i !== idx) return r;
        const attempts = [...r.attempts, { result }];
        // Validity rule: >1 attempt invalidates onsight/flash. A send on a
        // multi-attempt route is a redpoint going forward.
        let style = r.style;
        if (style === "onsight" || style === "flash") style = undefined;
        if (attempts.some((a) => a.result === "sent") && !style) style = "redpoint";
        return {
          ...r,
          attempts,
          atMin,
          style,
          ...(climb ? { climb_seconds: climb } : {}),
        };
      }),
    );
  };

  // A2 — tag a first-attempt send as onsight/flash (toggle off to clear).
  const tagStyle = (idx: number, s: "onsight" | "flash") =>
    onChange(routes.map((r, i) => (i === idx ? { ...r, style: r.style === s ? undefined : s } : r)));

  const remove = (idx: number) => onChange(routes.filter((_, i) => i !== idx));

  return (
    <div className="space-y-3">
      {/* Rest / climb timer */}
      {routes.length > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-sky-800/30 bg-sky-950/15 px-3 py-2">
          <div className="flex items-center gap-2">
            {climbing ? (
              <>
                <span className="text-[11px] uppercase tracking-wide text-amber-400">Climbing</span>
                <span className="font-mono text-lg font-semibold text-amber-200 tabular-nums">{fmt(climbSec)}</span>
              </>
            ) : (
              <>
                <span className="text-[11px] uppercase tracking-wide text-sky-400">Rest</span>
                <span className="font-mono text-lg font-semibold text-zinc-100 tabular-nums">{fmt(restSec)}</span>
              </>
            )}
          </div>
          {climbing ? (
            <span className="text-right text-[11px] text-zinc-500">on the wall<br /><span className="text-zinc-400">tap Sent / Fell when done</span></span>
          ) : (
            suggestedRest && (
              <span className="text-right text-[11px] text-zinc-500">suggested<br /><span className="text-zinc-400">{suggestedRest}</span></span>
            )
          )}
        </div>
      )}

      {/* Quick-add (new route) */}
      <div className="rounded-lg border border-white/10 p-3">
        <div className="flex gap-2">
          <select value={grade} onChange={(e) => setGrade(e.target.value)} aria-label="Grade"
            className="w-[78px] shrink-0 rounded-md border bg-background px-2 py-2 text-sm">
            {grades.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={`new ${routeLabel} name (optional)`}
            className="min-w-0 flex-1 rounded-md border bg-background px-2 py-2 text-sm" />
        </div>
        {/* A4 — optional climb timer */}
        <button
          onClick={startClimb}
          disabled={busy || climbing}
          className="mt-2 w-full rounded-md border border-amber-700/40 py-1.5 text-xs text-amber-300/90 disabled:opacity-40"
        >
          {climbing ? `▶ Climbing… ${fmt(climbSec)}` : "▶ Start climb timer (optional)"}
        </button>
        <div className="mt-2 flex gap-2">
          <button onClick={() => addRoute("sent")} disabled={busy} className="flex-1 rounded-md bg-green-600 py-2 text-sm font-medium text-white disabled:opacity-50">✓ Sent</button>
          <button onClick={() => addRoute("fell")} disabled={busy} className="flex-1 rounded-md bg-red-600/90 py-2 text-sm font-medium text-white disabled:opacity-50">✗ Fell / try</button>
        </div>
      </div>

      {/* Logged routes — append attempts with one tap */}
      {routes.length > 0 && (
        <ul className="space-y-1.5">
          {routes.map((r, i) => {
            const sent = r.attempts.some((a) => a.result === "sent" || a.result === "topped_out");
            const firstTrySend = sent && r.attempts.length === 1;
            const restSecRow = restForRow(routes, i);
            return (
              <li key={i} className="rounded-lg border border-white/5 bg-zinc-900/40 px-3 py-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className="w-10 shrink-0 font-mono font-medium text-zinc-200">{r.grade}</span>
                  <span className="min-w-0 flex-1 truncate text-zinc-400">{r.name}</span>
                  {/* attempt dots */}
                  <span className="flex shrink-0 items-center gap-1">
                    {r.attempts.map((a, ai) => (
                      <span key={ai} title={a.result}
                        className={`inline-block size-2 rounded-full ${a.result === "sent" || a.result === "topped_out" ? "bg-green-500" : "bg-red-500"}`} />
                    ))}
                  </span>
                  {/* A3 — labeled rest / climb times */}
                  <span className="flex shrink-0 items-center gap-2 text-[11px] text-zinc-500">
                    {restSecRow != null && (
                      <span title="Rest taken before this burn">🛌 {fmt(restSecRow)}</span>
                    )}
                    {typeof r.climb_seconds === "number" && (
                      <span title="Time on the wall" className="text-amber-300/80">🧗 {fmt(r.climb_seconds)}</span>
                    )}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-zinc-600">{sent ? "Sent" : "Open"} · {r.attempts.length} {r.attempts.length === 1 ? "try" : "tries"}</span>
                  {/* A2 — onsight/flash only on a first-attempt send */}
                  {firstTrySend && (
                    <span className="flex items-center gap-1">
                      <button
                        onClick={() => tagStyle(i, "onsight")}
                        className={`rounded border px-1.5 py-0.5 text-[10px] ${r.style === "onsight" ? "border-emerald-500 bg-emerald-950/40 text-emerald-300" : "border-white/10 text-zinc-500"}`}
                        title="Onsight — sent first try, no beta"
                      >OS</button>
                      <button
                        onClick={() => tagStyle(i, "flash")}
                        className={`rounded border px-1.5 py-0.5 text-[10px] ${r.style === "flash" ? "border-amber-500 bg-amber-950/40 text-amber-300" : "border-white/10 text-zinc-500"}`}
                        title="Flash — sent first try, with beta"
                      >FL</button>
                    </span>
                  )}
                  <button onClick={() => addAttempt(i, "sent")} disabled={busy} className="ml-auto rounded border border-green-700/50 px-2 py-0.5 text-xs text-green-400 disabled:opacity-50">+✓</button>
                  <button onClick={() => addAttempt(i, "fell")} disabled={busy} className="rounded border border-red-700/50 px-2 py-0.5 text-xs text-red-400 disabled:opacity-50">+✗</button>
                  <button onClick={() => remove(i)} aria-label="Remove route" className="rounded border border-white/10 px-2 py-0.5 text-xs text-zinc-500">✕</button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {routes.length > 0 && (
        <p className="text-[11px] text-zinc-500">
          {routes.length} {routes.length === 1 ? routeLabel : `${routeLabel}s`} · {routes.filter((r) => r.attempts.some((a) => a.result === "sent")).length} sent
        </p>
      )}
    </div>
  );
}
