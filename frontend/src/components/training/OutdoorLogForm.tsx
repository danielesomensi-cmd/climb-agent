"use client";

import { useState } from "react";
import { toast } from "sonner";
import type {
  OutdoorSpot,
  OutdoorRoute,
  OutdoorSession,
  OutdoorDayType,
  OutdoorRouteProfile,
  OutdoorConditions,
} from "@/lib/types";
import { postOutdoorLog, putOutdoorLog } from "@/lib/api";
import { deriveTryTimings, routeHasTimestamps } from "@/lib/try-timings";
import { TryBreakdown } from "@/components/outdoor/try-breakdown";

const FRENCH_SPORT_GRADES = [
  "4a","4b","4c","5a","5a+","5b","5b+","5c","5c+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
  "9a","9a+",
];

const FONT_BOULDER_GRADES = [
  "4","4+","5","5+",
  "6a","6a+","6b","6b+","6c","6c+",
  "7a","7a+","7b","7b+","7c","7c+",
  "8a","8a+","8b","8b+","8c","8c+",
];

/** mm:ss for a duration in seconds (B264 — rest/climb summary display). */
/** B279 — timing totals for a route: sum of per-attempt values when present,
 *  else the A227 route-level value (first burn only on legacy logs). */
function routeTiming(route: OutdoorRoute): { climb: number | null; rest: number | null } {
  const climbs = route.attempts.filter((a) => typeof a.climb_seconds === "number");
  const rests = route.attempts.filter((a) => typeof a.rest_seconds === "number");
  return {
    climb: climbs.length
      ? climbs.reduce((s, a) => s + (a.climb_seconds ?? 0), 0)
      : typeof route.climb_seconds === "number" ? route.climb_seconds : null,
    rest: rests.length
      ? rests.reduce((s, a) => s + (a.rest_seconds ?? 0), 0)
      : typeof route.rest_seconds === "number" ? route.rest_seconds : null,
  };
}

function fmtSec(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface Props {
  spots: OutdoorSpot[];
  defaultDate?: string;
  defaultSpotName?: string;
  defaultDiscipline?: "lead" | "boulder" | "both";
  defaultGrade?: string;
  defaultDuration?: number;
  initialData?: OutdoorSession;
  onSuccess?: () => void;
  // A226 — guided finish flow: carry day_type/route_profile/conditions and
  // submit through a custom handler (finishOutdoorSession) instead of post/put.
  dayType?: OutdoorDayType;
  routeProfile?: OutdoorRouteProfile;
  conditions?: OutdoorConditions | null;
  durationCappedNote?: { cap: number; raw: number } | null;
  onSubmit?: (payload: Record<string, unknown>) => Promise<void>;
  submitLabel?: string;
  // A226 — routes captured live during the active session (prefill, not edit mode).
  initialRoutes?: OutdoorRoute[];
}

export default function OutdoorLogForm({ spots, defaultDate, defaultSpotName, defaultDiscipline, defaultGrade, defaultDuration, initialData, onSuccess, dayType, routeProfile, conditions, durationCappedNote, onSubmit, submitLabel, initialRoutes }: Props) {
  const isEdit = !!initialData;
  const [date, setDate] = useState(initialData?.date || defaultDate || new Date().toISOString().slice(0, 10));
  const [spotName, setSpotName] = useState(initialData?.spot_name || defaultSpotName || "");
  const [discipline, setDiscipline] = useState<"lead" | "boulder" | "both">(initialData?.discipline || defaultDiscipline || "boulder");
  const [duration, setDuration] = useState(initialData?.duration_minutes || defaultDuration || 120);
  const [routes, setRoutes] = useState<OutdoorRoute[]>(initialData?.routes || initialRoutes || []);
  const [notes, setNotes] = useState(initialData?.notes || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gradeList = discipline === "lead" || discipline === "both"
    ? FRENCH_SPORT_GRADES
    : FONT_BOULDER_GRADES;
  const initialGrade = defaultGrade && gradeList.includes(defaultGrade) ? defaultGrade : "6a";

  // Issue 1: append at bottom
  const addRoute = () => {
    setRoutes([...routes, { name: "", grade: initialGrade, attempts: [{ result: "sent" }] }]);
  };

  const updateRoute = (idx: number, field: keyof OutdoorRoute, value: string) => {
    const updated = [...routes];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    setRoutes(updated);
  };

  /**
   * F39 (A245) — era un ciclo sent → fell → RIMOZIONE: un doppio tap
   * accidentale sul badge cancellava il tentativo. Ora è un toggle puro; la
   * rimozione ha il suo ✕ dedicato con undo.
   */
  const toggleAttempt = (rIdx: number, aIdx: number) => {
    const updated = [...routes];
    const attempt = updated[rIdx].attempts[aIdx];
    if (attempt.result === "sent") {
      updated[rIdx].attempts[aIdx] = { ...attempt, result: "fell" };
      // Clear auto-filled style when un-sending
      const anySent = updated[rIdx].attempts.some((a, i) => i !== aIdx && a.result === "sent");
      if (!anySent) {
        delete (updated[rIdx] as unknown as Record<string, unknown>).style;
      }
    } else {
      updated[rIdx].attempts[aIdx] = { ...attempt, result: "sent" };
    }
    setRoutes(updated);
  };

  /** F39 — rimozione esplicita di un tentativo, con undo di 10s. */
  const removeAttempt = (rIdx: number, aIdx: number) => {
    const removed = routes[rIdx].attempts[aIdx];
    setRoutes((cur) =>
      cur.map((r, i) =>
        i === rIdx ? { ...r, attempts: r.attempts.filter((_, j) => j !== aIdx) } : r,
      ),
    );
    toast("Attempt removed", {
      duration: 10_000,
      action: {
        label: "Undo",
        onClick: () =>
          setRoutes((cur) =>
            cur.map((r, i) => {
              if (i !== rIdx) return r;
              const attempts = [...r.attempts];
              attempts.splice(Math.min(aIdx, attempts.length), 0, removed);
              return { ...r, attempts };
            }),
          ),
      },
    });
  };

  const addAttempt = (rIdx: number) => {
    const updated = [...routes];
    updated[rIdx].attempts.push({ result: "sent" });
    setRoutes(updated);
  };

  const updateStyle = (rIdx: number, value: string) => {
    const updated = [...routes];
    if (value) {
      (updated[rIdx] as unknown as Record<string, unknown>).style = value;
    } else {
      delete (updated[rIdx] as unknown as Record<string, unknown>).style;
    }
    setRoutes(updated);
  };

  const removeRoute = (idx: number) => {
    setRoutes(routes.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    if (!spotName.trim()) {
      setError("Spot name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        date,
        spot_name: spotName,
        discipline,
        duration_minutes: duration,
        routes: routes.filter(r => r.name && r.grade).map(r => {
          const { style, ...rest } = r;
          return style ? { ...rest, style } : rest;
        }),
        notes: notes || undefined,
      };
      // A226 — carry outdoor.v2 fields when provided (guided flow).
      if (dayType) payload.day_type = dayType;
      if (routeProfile && Object.keys(routeProfile).length > 0) payload.route_profile = routeProfile;
      if (conditions) payload.conditions = conditions;

      if (onSubmit) {
        await onSubmit(payload);
      } else if (isEdit) {
        await putOutdoorLog(payload as unknown as Omit<OutdoorSession, "log_version">);
      } else {
        await postOutdoorLog(payload as unknown as Omit<OutdoorSession, "log_version">);
      }
      onSuccess?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to log session");
    } finally {
      setSubmitting(false);
    }
  };

  // A241 — derived per-try rest/climb (session-wide chronological rule).
  const tryTimings = deriveTryTimings(routes);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">{isEdit ? "Edit Outdoor Session" : "Log Outdoor Session"}</h3>

      {/* Date */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Date</label>
        <input
          type="date"
          value={date}
          onChange={e => setDate(e.target.value)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {/* Spot */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Spot</label>
        {spots.length > 0 ? (
          <select
            value={spotName}
            onChange={e => setSpotName(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">Select or type below...</option>
            {spots.map(s => (
              <option key={s.id} value={s.name}>{s.name}</option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          placeholder="Spot name"
          value={spotName}
          onChange={e => setSpotName(e.target.value)}
          className="w-full mt-1 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {/* Discipline */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Discipline</label>
        <div className="flex gap-2">
          {(["boulder", "lead", "both"] as const).map(d => (
            <button
              key={d}
              onClick={() => setDiscipline(d)}
              className={`rounded-md px-3 py-1.5 text-sm border ${
                discipline === d ? "bg-primary text-primary-foreground" : "bg-background"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Duration */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Duration (min)</label>
        <input
          type="number"
          inputMode="numeric"
          value={duration}
          onChange={e => setDuration(Number(e.target.value))}
          min={1}
          className="w-24 rounded-md border bg-background px-3 py-2 text-sm"
        />
        {durationCappedNote && (
          <p className="mt-1 text-xs text-amber-500">
            Timer ran long ({Math.round(durationCappedNote.raw / 60)}h) — capped to {durationCappedNote.cap} min. Adjust above if needed.
          </p>
        )}
      </div>

      {/* Routes — Issue 2: 2-row layout per card */}
      <div>
        <label className="text-sm font-medium">Routes / Problems</label>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Log your routes and attempts — tap + to add tries, tap a badge to cycle: Sent → Fell → remove. Climb Agent tracks your history and adapts your training based on what you climb outdoors.
        </p>

        <div className="mt-2 space-y-2">
          {routes.map((route, rIdx) => (
            <div key={rIdx} className="rounded-lg border p-3 space-y-2">
              {/* Row 1: Name + Grade + Delete */}
              <div className="flex gap-2">
                <input
                  placeholder="Name"
                  value={route.name}
                  onChange={e => updateRoute(rIdx, "name", e.target.value)}
                  className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-sm"
                />
                <select
                  value={route.grade}
                  onChange={e => updateRoute(rIdx, "grade", e.target.value)}
                  className="w-[72px] shrink-0 rounded-md border bg-background px-2 py-1.5 text-sm"
                >
                  {gradeList.map(g => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
                <button
                  onClick={() => removeRoute(rIdx)}
                  className="shrink-0 rounded-md border px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                  aria-label="Remove route"
                >
                  ✕
                </button>
              </div>

              {/* Row 2: Style + attempt badges + add attempt */}
              <div className="flex flex-wrap items-center gap-1.5">
                <select
                  value={route.style || ""}
                  onChange={e => updateStyle(rIdx, e.target.value)}
                  className="rounded-md border bg-background px-2 py-1 text-xs"
                >
                  <option value="">Style</option>
                  <option value="onsight">🟢 OS</option>
                  <option value="flash">🟡 FL</option>
                  <option value="redpoint">🔴 RP</option>
                  <option value="project">⚪ PRJ</option>
                </select>

                {/* F39: il badge fa solo toggle Sent⇄Fell; il ✕ rimuove (con undo) */}
                {route.attempts.map((a, aIdx) => (
                  <span key={aIdx} className="inline-flex overflow-hidden rounded">
                    <button
                      onClick={() => toggleAttempt(rIdx, aIdx)}
                      className={`min-h-[44px] px-3 text-sm font-medium ${
                        a.result === "sent"
                          ? "bg-green-600 text-white"
                          : "bg-red-600 text-white"
                      }`}
                      title="Tap to switch Sent ⇄ Fell"
                    >
                      {a.result === "sent" ? "Sent" : "Fell"}
                    </button>
                    <button
                      onClick={() => removeAttempt(rIdx, aIdx)}
                      aria-label={`Remove attempt ${aIdx + 1}`}
                      className="min-h-[44px] border-l border-black/20 bg-muted px-2.5 text-sm text-muted-foreground hover:text-foreground"
                    >
                      ✕
                    </button>
                  </span>
                ))}

                <button
                  onClick={() => addAttempt(rIdx)}
                  aria-label="Add attempt"
                  className="min-h-[44px] rounded border px-3 text-sm text-muted-foreground hover:text-foreground"
                >
                  +
                </button>
              </div>

              {/* A241 — per-try rest/climb breakdown when timestamps exist;
                  B264 / B265 / B279 totals as the legacy fallback */}
              {routeHasTimestamps(route) ? (
                <TryBreakdown attempts={route.attempts} timings={tryTimings[rIdx]} />
              ) : (() => {
                const t = routeTiming(route);
                const multi = route.attempts.length > 1;
                if (t.climb == null && t.rest == null) return null;
                return (
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    {t.climb != null && (
                      <span title={multi ? `Total time on the wall (${route.attempts.length} tries)` : "Time on the wall"} className="text-amber-500/80">climb {fmtSec(t.climb)}</span>
                    )}
                    {t.climb != null && t.rest != null && (
                      <span aria-hidden="true">·</span>
                    )}
                    {t.rest != null && (
                      <span title={multi ? `Total rest (${route.attempts.length} tries)` : "Rest taken before this burn"}>rest {fmtSec(t.rest)}</span>
                    )}
                  </div>
                );
              })()}
            </div>
          ))}
        </div>

        {/* Issue 3: "+ Add route" below last card, left-aligned */}
        <button
          onClick={addRoute}
          className="mt-2 text-sm text-primary hover:underline"
        >
          + Add route
        </button>
      </div>

      {/* Notes */}
      <div>
        <label className="block text-sm text-muted-foreground mb-1">Notes</label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {submitting ? "Saving..." : submitLabel || (isEdit ? "Save Changes" : "Log Session")}
      </button>
    </div>
  );
}
