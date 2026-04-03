"use client";

import { useState } from "react";
import type { OutdoorSpot, OutdoorRoute, OutdoorAttempt, OutdoorSession } from "@/lib/types";
import { postOutdoorLog, putOutdoorLog } from "@/lib/api";

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

interface Props {
  spots: OutdoorSpot[];
  defaultDate?: string;
  defaultSpotName?: string;
  defaultDiscipline?: "lead" | "boulder" | "both";
  defaultGrade?: string;
  initialData?: OutdoorSession;
  onSuccess?: () => void;
}

export default function OutdoorLogForm({ spots, defaultDate, defaultSpotName, defaultDiscipline, defaultGrade, initialData, onSuccess }: Props) {
  const isEdit = !!initialData;
  const [date, setDate] = useState(initialData?.date || defaultDate || new Date().toISOString().slice(0, 10));
  const [spotName, setSpotName] = useState(initialData?.spot_name || defaultSpotName || "");
  const [discipline, setDiscipline] = useState<"lead" | "boulder" | "both">(initialData?.discipline || defaultDiscipline || "boulder");
  const [duration, setDuration] = useState(initialData?.duration_minutes || 120);
  const [routes, setRoutes] = useState<OutdoorRoute[]>(initialData?.routes || []);
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

  // Issue 4: cycle attempt through sent → fell → removed
  const cycleAttempt = (rIdx: number, aIdx: number) => {
    const updated = [...routes];
    const attempt = updated[rIdx].attempts[aIdx];
    if (attempt.result === "sent") {
      updated[rIdx].attempts[aIdx] = { ...attempt, result: "fell" };
      // Clear auto-filled style when un-sending
      const anySent = updated[rIdx].attempts.some((a, i) => i !== aIdx && a.result === "sent");
      if (!anySent) {
        delete (updated[rIdx] as unknown as Record<string, unknown>).style;
      }
    } else if (attempt.result === "fell") {
      // Remove this attempt entirely
      updated[rIdx].attempts = updated[rIdx].attempts.filter((_, i) => i !== aIdx);
    } else {
      // Any other state → sent
      updated[rIdx].attempts[aIdx] = { ...attempt, result: "sent" };
    }
    setRoutes(updated);
  };

  const addAttempt = (rIdx: number) => {
    const updated = [...routes];
    updated[rIdx].attempts.push({ result: "fell" });
    // B181: auto-fill style when user marks first send and style is empty
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
      const payload = {
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
      if (isEdit) {
        await putOutdoorLog(payload);
      } else {
        await postOutdoorLog(payload);
      }
      onSuccess?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to log session");
    } finally {
      setSubmitting(false);
    }
  };

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
          value={duration}
          onChange={e => setDuration(Number(e.target.value))}
          min={1}
          className="w-24 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>

      {/* Routes — Issue 2: 2-row layout per card */}
      <div>
        <label className="text-sm font-medium">Routes / Problems</label>

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

                {/* Issue 4: tap cycles sent→fell→removed */}
                {route.attempts.map((a, aIdx) => (
                  <button
                    key={aIdx}
                    onClick={() => cycleAttempt(rIdx, aIdx)}
                    className={`rounded px-2.5 py-1 text-xs font-medium ${
                      a.result === "sent"
                        ? "bg-green-600 text-white"
                        : "bg-red-600 text-white"
                    }`}
                    title="Tap: Sent → Fell → Remove"
                  >
                    {a.result === "sent" ? "Sent" : "Fell"}
                  </button>
                ))}

                <button
                  onClick={() => addAttempt(rIdx)}
                  className="rounded border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  +
                </button>
              </div>
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
        {submitting ? "Saving..." : isEdit ? "Save Changes" : "Log Session"}
      </button>
    </div>
  );
}
