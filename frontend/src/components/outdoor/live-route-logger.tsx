"use client";

import { useState } from "react";
import type { OutdoorRoute } from "@/lib/types";

/**
 * A226 — log routes LIVE during an active outdoor session.
 *
 * Each route is captured the moment it's climbed (grade + optional name +
 * sent/fell), stamped with the minute mark since the session started so the
 * pacing / rest cadence is visible. Routes accumulate in the parent; at close
 * they prefill the log form for final correction.
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
  /** minutes since session start when logged (for pacing display) */
  atMin: number;
}

interface Props {
  discipline: "lead" | "boulder" | "both";
  startedAt: string;
  routes: LiveRoute[];
  onChange: (routes: LiveRoute[]) => void;
}

export function LiveRouteLogger({ discipline, startedAt, routes, onChange }: Props) {
  const grades = discipline === "boulder" ? FONT_BOULDER_GRADES : FRENCH_SPORT_GRADES;
  const [grade, setGrade] = useState(grades.includes("6a") ? "6a" : grades[0]);
  const [name, setName] = useState("");

  const routeLabel = discipline === "boulder" ? "problem" : "route";

  const add = (result: "sent" | "fell") => {
    const atMin = Math.max(0, Math.round((Date.now() - new Date(startedAt).getTime()) / 60000));
    onChange([...routes, { name: name.trim() || `${routeLabel} ${routes.length + 1}`, grade, attempts: [{ result }], atMin }]);
    setName("");
  };

  const remove = (idx: number) => onChange(routes.filter((_, i) => i !== idx));

  return (
    <div className="space-y-3">
      {/* Quick-add row */}
      <div className="rounded-lg border border-white/10 p-3">
        <div className="flex gap-2">
          <select
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            className="w-[78px] shrink-0 rounded-md border bg-background px-2 py-2 text-sm"
            aria-label="Grade"
          >
            {grades.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={`${routeLabel} name (optional)`}
            className="min-w-0 flex-1 rounded-md border bg-background px-2 py-2 text-sm"
          />
        </div>
        <div className="mt-2 flex gap-2">
          <button onClick={() => add("sent")} className="flex-1 rounded-md bg-green-600 py-2 text-sm font-medium text-white">
            ✓ Sent
          </button>
          <button onClick={() => add("fell")} className="flex-1 rounded-md bg-red-600/90 py-2 text-sm font-medium text-white">
            ✗ Fell / try
          </button>
        </div>
      </div>

      {/* Logged list (most recent first) */}
      {routes.length > 0 && (
        <ul className="space-y-1.5">
          {routes.map((r, i) => {
            const sent = r.attempts.some((a) => a.result === "sent" || a.result === "topped_out");
            const prev = i > 0 ? routes[i - 1].atMin : 0;
            const rest = r.atMin - prev;
            return (
              <li key={i} className="flex items-center gap-2 rounded-lg border border-white/5 bg-zinc-900/40 px-3 py-2 text-sm">
                <span className="w-10 shrink-0 font-mono font-medium text-zinc-200">{r.grade}</span>
                <span className="min-w-0 flex-1 truncate text-zinc-400">{r.name}</span>
                <span className={`shrink-0 text-xs font-medium ${sent ? "text-green-400" : "text-red-400"}`}>
                  {sent ? "Sent" : "Fell"}
                </span>
                <span className="shrink-0 text-[11px] text-zinc-600" title="Minutes into session (rest since previous)">
                  {r.atMin}′{i > 0 && rest > 0 ? ` · +${rest}′` : ""}
                </span>
                <button onClick={() => remove(i)} aria-label="Remove" className="shrink-0 text-zinc-600 hover:text-red-400">✕</button>
              </li>
            );
          })}
        </ul>
      )}
      {routes.length > 0 && (
        <p className="text-[11px] text-zinc-500">
          {routes.length} logged · {routes.filter((r) => r.attempts.some((a) => a.result === "sent")).length} sent
        </p>
      )}
    </div>
  );
}
