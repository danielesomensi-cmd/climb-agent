"use client";

import { useState } from "react";
import type { OutdoorSpot, OutdoorRoute, OutdoorAttempt } from "@/lib/types";
import { postOutdoorLog } from "@/lib/api";

interface Props {
  spots: OutdoorSpot[];
  defaultDate?: string;
  onSuccess?: () => void;
}

export default function OutdoorLogForm({ spots, defaultDate, onSuccess }: Props) {
  const [date, setDate] = useState(defaultDate || new Date().toISOString().slice(0, 10));
  const [spotName, setSpotName] = useState("");
  const [discipline, setDiscipline] = useState<"lead" | "boulder" | "both">("boulder");
  const [duration, setDuration] = useState(120);
  const [routes, setRoutes] = useState<OutdoorRoute[]>([]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addRoute = () => {
    setRoutes([...routes, { name: "", grade: "", attempts: [{ result: "sent" }] }]);
  };

  const updateRoute = (idx: number, field: keyof OutdoorRoute, value: string) => {
    const updated = [...routes];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    setRoutes(updated);
  };

  const updateAttemptResult = (rIdx: number, aIdx: number, result: OutdoorAttempt["result"]) => {
    const updated = [...routes];
    updated[rIdx].attempts[aIdx] = { ...updated[rIdx].attempts[aIdx], result };
    setRoutes(updated);
  };

  const addAttempt = (rIdx: number) => {
    const updated = [...routes];
    updated[rIdx].attempts.push({ result: "fell" });
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
      await postOutdoorLog({
        date,
        spot_name: spotName,
        discipline,
        duration_minutes: duration,
        routes: routes.filter(r => r.name && r.grade),
        notes: notes || undefined,
      });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to log session");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Log Outdoor Session</h3>

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

      {/* Routes */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium">Routes / Problems</label>
          <button
            onClick={addRoute}
            className="text-sm text-primary hover:underline"
          >
            + Add route
          </button>
        </div>
        {routes.map((route, rIdx) => (
          <div key={rIdx} className="mb-3 rounded-lg border p-3 space-y-2">
            <div className="flex gap-2">
              <input
                placeholder="Name"
                value={route.name}
                onChange={e => updateRoute(rIdx, "name", e.target.value)}
                className="flex-1 rounded-md border bg-background px-2 py-1 text-sm"
              />
              <input
                placeholder="Grade"
                value={route.grade}
                onChange={e => updateRoute(rIdx, "grade", e.target.value)}
                className="w-20 rounded-md border bg-background px-2 py-1 text-sm"
              />
              <button
                onClick={() => removeRoute(rIdx)}
                className="text-destructive text-sm"
              >
                x
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {route.attempts.map((a, aIdx) => (
                <button
                  key={aIdx}
                  onClick={() =>
                    updateAttemptResult(
                      rIdx,
                      aIdx,
                      a.result === "sent" ? "fell" : "sent"
                    )
                  }
                  className={`rounded px-2 py-0.5 text-xs ${
                    a.result === "sent"
                      ? "bg-green-600 text-white"
                      : "bg-red-600 text-white"
                  }`}
                >
                  {a.result === "sent" ? "Sent" : "Fell"}
                </button>
              ))}
              <button
                onClick={() => addAttempt(rIdx)}
                className="rounded px-2 py-0.5 text-xs border"
              >
                +
              </button>
            </div>
          </div>
        ))}
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
        {submitting ? "Saving..." : "Log Session"}
      </button>
    </div>
  );
}
