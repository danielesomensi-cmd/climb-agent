"use client";

import { useEffect, useRef, useState } from "react";
import type { OutdoorRoute } from "@/lib/types";

/**
 * A226 — log routes LIVE during an active outdoor session.
 *
 * - Quick-add creates a new route (grade + optional name) with its first attempt.
 * - Each route row has +✓ / +✗ to append MORE attempts to that same route with
 *   one tap (no need to retype the name).
 * - A parallel REST timer counts up since the last attempt, with the strategy's
 *   suggested rest shown beside it.
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

  useEffect(() => {
    const tick = () => {
      nowMsRef.current = Date.now();
      const fallback = routes.length ? startMs + Math.max(...routes.map((r) => r.atMin)) * 60000 : null;
      const ref = liveActionMsRef.current ?? fallback;
      setRestSec(ref == null ? 0 : Math.max(0, Math.floor((nowMsRef.current - ref) / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [routes, startMs]);

  const addRoute = (result: "sent" | "fell") => {
    const nowMs = nowMsRef.current;
    liveActionMsRef.current = nowMs;
    setRestSec(0);
    const atMin = Math.max(0, Math.round((nowMs - startMs) / 60000));
    onChange([...routes, { name: name.trim() || `${routeLabel} ${routes.length + 1}`, grade, attempts: [{ result }], atMin }]);
    setName("");
  };

  const addAttempt = (idx: number, result: "sent" | "fell") => {
    const nowMs = nowMsRef.current;
    liveActionMsRef.current = nowMs;
    setRestSec(0);
    const atMin = Math.max(0, Math.round((nowMs - startMs) / 60000));
    onChange(routes.map((r, i) => i === idx
      ? { ...r, attempts: [...r.attempts, { result }], atMin }
      : r));
  };

  const remove = (idx: number) => onChange(routes.filter((_, i) => i !== idx));

  return (
    <div className="space-y-3">
      {/* Rest timer */}
      {routes.length > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-sky-800/30 bg-sky-950/15 px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wide text-sky-400">Rest</span>
            <span className="font-mono text-lg font-semibold text-zinc-100 tabular-nums">{fmt(restSec)}</span>
          </div>
          {suggestedRest && (
            <span className="text-right text-[11px] text-zinc-500">suggested<br /><span className="text-zinc-400">{suggestedRest}</span></span>
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
            const prev = i > 0 ? routes[i - 1].atMin : 0;
            const rest = r.atMin - prev;
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
                  <span className="shrink-0 text-[11px] text-zinc-600" title="Minute into session (rest since previous route)">
                    {r.atMin}′{i > 0 && rest > 0 ? ` · +${rest}′` : ""}
                  </span>
                </div>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span className="text-[11px] text-zinc-600">{sent ? "Sent" : "Open"} · {r.attempts.length} {r.attempts.length === 1 ? "try" : "tries"}</span>
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
