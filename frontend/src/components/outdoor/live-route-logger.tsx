"use client";

import { useEffect, useRef, useState } from "react";
import type { OutdoorRoute } from "@/lib/types";
import { deriveTryTimings, lastTryMs, routeHasTimestamps } from "@/lib/try-timings";
import { TryBreakdown } from "./try-breakdown";

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
 *
 * B279 — project mode:
 * - After a Fell the route stays "active": the main panel (climb timer + big
 *   Sent/Fell buttons) targets the SAME route for the next burn instead of
 *   creating a new one. "New route" exits project mode; a Sent closes it.
 * - Each attempt stores its own rest_seconds/climb_seconds so timing stays
 *   coherent across burns; route-level fields keep the first burn (A227 legacy).
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

/** Total rest for a row: sum of per-attempt values (B279) when present, else
 *  the A227 route-level value, else the at_min delta to the previous route
 *  (legacy live routes have no rest_seconds at all). */
function restForRow(routes: LiveRoute[], i: number): number | null {
  const r = routes[i];
  const perAttempt = r.attempts.filter((a) => typeof a.rest_seconds === "number");
  if (perAttempt.length) return perAttempt.reduce((s, a) => s + (a.rest_seconds ?? 0), 0);
  if (typeof r.rest_seconds === "number") return r.rest_seconds;
  if (i > 0) {
    const delta = r.atMin - routes[i - 1].atMin;
    if (delta > 0) return delta * 60;
  }
  return null;
}

/** Total on-the-wall time for a row: sum of per-attempt values (B279) when
 *  present, else the A227 route-level value. */
function climbForRow(r: LiveRoute): number | null {
  const perAttempt = r.attempts.filter((a) => typeof a.climb_seconds === "number");
  if (perAttempt.length) return perAttempt.reduce((s, a) => s + (a.climb_seconds ?? 0), 0);
  return typeof r.climb_seconds === "number" ? r.climb_seconds : null;
}

export function LiveRouteLogger({ discipline, startedAt, routes, onChange, suggestedRest, busy }: Props) {
  const grades = discipline === "boulder" ? FONT_BOULDER_GRADES : FRENCH_SPORT_GRADES;
  const [grade, setGrade] = useState(grades.includes("6a") ? "6a" : grades[0]);
  const [name, setName] = useState("");
  const routeLabel = discipline === "boulder" ? "problem" : "route";

  // B279 — project mode: index of the route the main panel targets. Set on a
  // Fell (quick-add or row +✗), cleared on a Sent / "New route". Guarded against
  // an out-of-range index after an external routes change (e.g. restore).
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const projectIdx = activeIdx != null && activeIdx < routes.length ? activeIdx : null;
  const projectRoute = projectIdx != null ? routes[projectIdx] : null;

  const startMs = new Date(startedAt).getTime();

  // React 19 lint bans Date.now()/ref reads in render. Keep "now" and the last
  // action time in refs (written from handlers/effects only); the 1s ticker reads
  // them and derives the rest counter. Fallback to the latest route's minute mark
  // covers a restore where we have no live action ref yet.
  const nowMsRef = useRef<number>(startMs);
  const liveActionMsRef = useRef<number | null>(null);
  const [restSec, setRestSec] = useState(0);
  // A241 — render-safe "now" for the per-route "since last try" ticker.
  const [nowMs, setNowMs] = useState<number>(startMs);
  // A241 — per-card expand/collapse (indices into `routes`).
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  // A4 — optional climb timer (counts on-the-wall time for the current burn).
  const climbStartMsRef = useRef<number | null>(null);
  const [climbSec, setClimbSec] = useState(0);
  const [climbing, setClimbing] = useState(false);

  useEffect(() => {
    const tick = () => {
      nowMsRef.current = Date.now();
      setNowMs(nowMsRef.current);
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

  /** Close out the burn that just ended: stop the climb timer, restart the
   *  rest counter, and return the timing for the new try. A241: the try stores
   *  its end-of-burn timestamp (rest is derived at render, never stored);
   *  route-level rest/climb keep the A227 first-burn contract. */
  const takeBurnTiming = () => {
    const pressMs = nowMsRef.current;
    const climb = consumeClimb();
    const rest = Math.round(restSec); // A227 route-level field only
    liveActionMsRef.current = pressMs;
    setRestSec(0);
    const atMin = Math.max(0, Math.round((pressMs - startMs) / 60000));
    return { climb, rest, atMin, loggedAt: new Date(pressMs).toISOString() };
  };

  const addRoute = (result: "sent" | "fell") => {
    const { climb, rest, atMin, loggedAt } = takeBurnTiming();
    const idx = routes.length;
    onChange([
      ...routes,
      {
        name: name.trim() || `${routeLabel} ${idx + 1}`,
        grade,
        attempts: [{ result, logged_at: loggedAt, ...(climb ? { climb_seconds: climb } : {}) }],
        atMin,
        rest_seconds: rest,
        ...(climb ? { climb_seconds: climb } : {}),
      },
    ]);
    setName("");
    // B279 — a fall opens project mode on the new route; a send closes it.
    setActiveIdx(result === "fell" ? idx : null);
  };

  const addAttempt = (idx: number, result: "sent" | "fell") => {
    const { climb, atMin, loggedAt } = takeBurnTiming();
    onChange(
      routes.map((r, i) => {
        if (i !== idx) return r;
        const attempts = [
          ...r.attempts,
          { result, logged_at: loggedAt, ...(climb ? { climb_seconds: climb } : {}) },
        ];
        // Validity rule: >1 attempt invalidates onsight/flash. A send on a
        // multi-attempt route is a redpoint going forward.
        let style = r.style;
        if (style === "onsight" || style === "flash") style = undefined;
        if (attempts.some((a) => a.result === "sent") && !style) style = "redpoint";
        return { ...r, attempts, atMin, style };
      }),
    );
    // B279 — keep projecting the route after a fall; a send releases it.
    setActiveIdx((cur) => (result === "fell" ? idx : cur === idx ? null : cur));
  };

  // A2 — tag a first-attempt send as onsight/flash (toggle off to clear).
  const tagStyle = (idx: number, s: "onsight" | "flash") =>
    onChange(routes.map((r, i) => (i === idx ? { ...r, style: r.style === s ? undefined : s } : r)));

  const remove = (idx: number) => {
    onChange(routes.filter((_, i) => i !== idx));
    setActiveIdx((cur) => (cur == null || cur === idx ? null : cur > idx ? cur - 1 : cur));
    setExpanded(new Set()); // indices shifted — collapse all (cheap & safe)
  };

  const toggleExpanded = (idx: number) =>
    setExpanded((cur) => {
      const next = new Set(cur);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });

  // A241 — derived per-try timings (session-wide chronological rest).
  const timings = deriveTryTimings(routes);

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

      {/* Quick-add / project mode (B279) — after a fall the panel keeps
          targeting the same route until it's sent or the user switches. */}
      <div className={`rounded-lg border p-3 ${projectRoute ? "border-indigo-700/40 bg-indigo-950/10" : "border-white/10"}`}>
        {projectRoute ? (
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] uppercase tracking-wide text-indigo-400">Projecting</p>
              <p className="truncate text-sm text-zinc-200">
                <span className="font-mono font-medium">{projectRoute.grade}</span> {projectRoute.name}
                <span className="text-zinc-500"> · try {projectRoute.attempts.length + 1}</span>
              </p>
            </div>
            <button
              onClick={() => setActiveIdx(null)}
              className="shrink-0 rounded-md border border-white/10 px-2.5 py-1.5 text-xs text-zinc-400"
            >
              New {routeLabel}
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <select value={grade} onChange={(e) => setGrade(e.target.value)} aria-label="Grade"
              className="w-[78px] shrink-0 rounded-md border bg-background px-2 py-2 text-sm">
              {grades.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={`new ${routeLabel} name (optional)`}
              className="min-w-0 flex-1 rounded-md border bg-background px-2 py-2 text-sm" />
          </div>
        )}
        {/* A4 — optional climb timer */}
        <button
          onClick={startClimb}
          disabled={busy || climbing}
          className="mt-2 w-full rounded-md border border-amber-700/40 py-1.5 text-xs text-amber-300/90 disabled:opacity-40"
        >
          {climbing ? `▶ Climbing… ${fmt(climbSec)}` : "▶ Start climb timer (optional)"}
        </button>
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => (projectIdx == null ? addRoute("sent") : addAttempt(projectIdx, "sent"))}
            disabled={busy}
            className="flex-1 rounded-md bg-green-600 py-2 text-sm font-medium text-white disabled:opacity-50"
          >✓ Sent</button>
          <button
            onClick={() => (projectIdx == null ? addRoute("fell") : addAttempt(projectIdx, "fell"))}
            disabled={busy}
            className="flex-1 rounded-md bg-red-600/90 py-2 text-sm font-medium text-white disabled:opacity-50"
          >✗ Fell / try</button>
        </div>
      </div>

      {/* Logged routes — append attempts with one tap. B265: newest on top
          (render in reverse) while keeping the original chronological index `i`
          for handlers and the rest-delta computation. */}
      {routes.length > 0 && (
        <ul className="space-y-1.5">
          {routes.map((r, i) => ({ r, i })).reverse().map(({ r, i }) => {
            const sent = r.attempts.some((a) => a.result === "sent" || a.result === "topped_out");
            const firstTrySend = sent && r.attempts.length === 1;
            // A241 — timestamped routes: ticking "since last try" + expandable
            // per-try breakdown. Legacy routes (no logged_at): old totals.
            const hasTs = routeHasTimestamps(r);
            const isOpen = hasTs && expanded.has(i);
            const last = hasTs ? lastTryMs(r) : null;
            const sinceLast = last != null ? Math.max(0, Math.floor((nowMs - last) / 1000)) : null;
            const restSecRow = hasTs ? null : restForRow(routes, i);
            const climbSecRow = hasTs ? null : climbForRow(r);
            const multi = r.attempts.length > 1;
            return (
              <li key={i} className={`rounded-lg border px-3 py-2 ${i === projectIdx ? "border-indigo-600/50 bg-indigo-950/20" : "border-white/5 bg-zinc-900/40"}`}>
                <button
                  type="button"
                  onClick={() => hasTs && toggleExpanded(i)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center gap-2 text-left text-sm"
                >
                  <span className="w-10 shrink-0 font-mono font-medium text-zinc-200">{r.grade}</span>
                  <span className="min-w-0 flex-1 truncate text-zinc-400">{r.name}</span>
                  {/* attempt dots */}
                  <span className="flex shrink-0 items-center gap-1">
                    {r.attempts.map((a, ai) => (
                      <span key={ai}
                        title={[
                          a.result,
                          typeof a.climb_seconds === "number" ? `climb ${fmt(a.climb_seconds)}` : null,
                          typeof a.rest_seconds === "number" ? `rest ${fmt(a.rest_seconds)}` : null,
                        ].filter(Boolean).join(" · ")}
                        className={`inline-block size-2 rounded-full ${a.result === "sent" || a.result === "topped_out" ? "bg-green-500" : "bg-red-500"}`} />
                    ))}
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 text-[11px] text-zinc-500">
                    {/* A241 — ticking time since the last try on THIS route */}
                    {sinceLast != null && (
                      <span className="tabular-nums" title="Time since the last try on this route">
                        last try {fmt(sinceLast)} ago
                      </span>
                    )}
                    {/* A3 / B264 / B265 / B279 — legacy totals (no timestamps) */}
                    {climbSecRow != null && (
                      <span title={multi ? `Total time on the wall (${r.attempts.length} tries)` : "Time on the wall"} className="text-amber-300/80">climb {fmt(climbSecRow)}</span>
                    )}
                    {climbSecRow != null && restSecRow != null && (
                      <span className="text-zinc-600" aria-hidden="true">·</span>
                    )}
                    {restSecRow != null && (
                      <span title={multi ? `Total rest (${r.attempts.length} tries)` : "Rest taken before this burn"}>rest {fmt(restSecRow)}</span>
                    )}
                    {hasTs && (
                      <svg
                        className={`h-3 w-3 text-zinc-600 transition-transform ${isOpen ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    )}
                  </span>
                </button>
                {/* A241 — per-try rest/climb progression (chronological) */}
                {isOpen && (
                  <div className="mt-1.5 border-t border-white/5 pt-1.5">
                    <TryBreakdown attempts={r.attempts} timings={timings[i]} />
                  </div>
                )}
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <span className={`text-[11px] ${i === projectIdx ? "text-indigo-400" : "text-zinc-600"}`}>{sent ? "Sent" : i === projectIdx ? "Projecting" : "Open"} · {r.attempts.length} {r.attempts.length === 1 ? "try" : "tries"}</span>
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
