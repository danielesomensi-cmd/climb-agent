"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface SummaryData {
  total_climbs: number;
  flashed: number;
  sent: number;
  attempted: number;
  max_grade_sent: string | null;
  max_grade_attempted: string | null;
  send_rate: number;
}

interface SessionSummaryProps {
  surface: string;
  gymName?: string;
  presetName?: string;
  durationMinutes?: number | null;
  loadScore?: number | null;
  summary?: SummaryData | null;
  climbs: Array<{ grade: string; status: string }>;
  startedAt?: number; // Date.now() when session started
  onSave: (feel?: string, notes?: string) => void;
}

export function SessionSummary({
  surface,
  gymName,
  presetName,
  durationMinutes: durationMinutesProp,
  loadScore,
  summary: summaryProp,
  climbs,
  startedAt,
  onSave,
}: SessionSummaryProps) {
  const [feel, setFeel] = useState<string | undefined>();
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Client-side summary from climbs
  const summary: SummaryData = summaryProp || (() => {
    const total = climbs.length;
    const flashed = climbs.filter((c) => c.status === "flash").length;
    const sent = climbs.filter((c) => c.status === "sent").length;
    const attempted = climbs.filter((c) => c.status === "attempted").length;
    const completed = flashed + sent;
    return {
      total_climbs: total,
      flashed,
      sent,
      attempted,
      max_grade_sent: null,
      max_grade_attempted: null,
      send_rate: total > 0 ? completed / total : 0,
    };
  })();

  const durationMinutes = durationMinutesProp ?? (startedAt ? Math.round((Date.now() - startedAt) / 60000) : null);

  // Compute grade distribution
  const gradeDist: Record<string, { sent: number; attempted: number }> = {};
  for (const c of climbs) {
    const g = c.grade.toUpperCase();
    if (!gradeDist[g]) gradeDist[g] = { sent: 0, attempted: 0 };
    if (c.status === "attempted") gradeDist[g].attempted++;
    else gradeDist[g].sent++;
  }

  const gradeEntries = Object.entries(gradeDist).sort((a, b) => {
    // Sort by grade order
    const grades = ["4A", "4B", "4C", "5A", "5A+", "5B", "5B+", "5C", "5C+", "6A", "6A+", "6B", "6B+", "6C", "6C+", "7A", "7A+", "7B", "7B+", "7C", "7C+", "8A", "8A+", "8B", "8B+", "8C", "8C+"];
    return grades.indexOf(a[0]) - grades.indexOf(b[0]);
  });

  const maxCount = Math.max(...gradeEntries.map(([, v]) => v.sent + v.attempted), 1);

  const surfaceName = surface === "gym_boulder" ? "Gym Boulder" :
    surface === "board_kilter" ? "Kilter" :
    surface === "board_moonboard" ? "Moon" :
    surface === "board_other" ? "Board" : "Lead";

  const formatDuration = (m: number | null) => {
    if (!m) return "—";
    if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}min`;
    return `${m} min`;
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(feel, notes || undefined);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 px-4 pb-8">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-xl font-bold">Session Complete!</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {surfaceName}
          {gymName && ` \u00b7 ${gymName}`}
          {presetName && ` \u00b7 ${presetName}`}
        </p>
        <p className="text-sm text-muted-foreground">
          Duration: {formatDuration(durationMinutes)}
          {loadScore != null && loadScore > 0 && ` \u00b7 Load: ${loadScore}`}
        </p>
      </div>

      {/* Stats card */}
      <div className="rounded-xl border bg-card p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="text-center">
            <div className="text-2xl font-bold">{summary.total_climbs}</div>
            <div className="text-xs text-muted-foreground">
              {surface === "gym_routes" ? "Routes" : "Boulders"}
            </div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{Math.round(summary.send_rate * 100)}%</div>
            <div className="text-xs text-muted-foreground">Send rate</div>
          </div>
        </div>

        <div className="mt-3 flex justify-center gap-4 text-sm">
          <span className="flex items-center gap-1 text-amber-400">
            <span className="font-semibold">{summary.flashed}</span> flash
          </span>
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="font-semibold">{summary.sent}</span> sent
          </span>
          <span className="flex items-center gap-1 text-red-400">
            <span className="font-semibold">{summary.attempted}</span> tried
          </span>
        </div>

        {summary.max_grade_sent && (
          <div className="mt-3 text-center text-sm">
            Max sent: <span className="font-bold text-emerald-400">{summary.max_grade_sent}</span>
            {summary.max_grade_attempted && summary.max_grade_attempted !== summary.max_grade_sent && (
              <> &middot; Max tried: <span className="font-bold text-red-400">{summary.max_grade_attempted}</span></>
            )}
          </div>
        )}
      </div>

      {/* Grade distribution */}
      {gradeEntries.length > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Grade Distribution</h3>
          <div className="flex flex-col gap-1.5">
            {gradeEntries.map(([grade, counts]) => {
              const total = counts.sent + counts.attempted;
              const sentPct = (counts.sent / maxCount) * 100;
              const attPct = (counts.attempted / maxCount) * 100;
              return (
                <div key={grade} className="flex items-center gap-2">
                  <span className="w-8 text-right text-xs font-medium">{grade}</span>
                  <div className="flex flex-1 gap-px">
                    {counts.sent > 0 && (
                      <div
                        className="h-5 rounded-l bg-emerald-500/70 transition-all duration-500"
                        style={{ width: `${sentPct}%` }}
                      />
                    )}
                    {counts.attempted > 0 && (
                      <div
                        className="h-5 rounded-r bg-red-500/50 transition-all duration-500"
                        style={{ width: `${attPct}%` }}
                      />
                    )}
                  </div>
                  <span className="w-4 text-xs text-muted-foreground">{total}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Feel selector */}
      <div>
        <h3 className="mb-2 text-center text-sm font-medium text-muted-foreground">How did it feel?</h3>
        <div className="flex gap-2">
          {([
            { key: "easy", label: "Easy", emoji: "\ud83d\ude34" },
            { key: "good", label: "Good", emoji: "\ud83d\udc4d" },
            { key: "hard", label: "Hard", emoji: "\ud83d\udcaa" },
          ] as const).map((f) => (
            <button
              key={f.key}
              onClick={() => setFeel(feel === f.key ? undefined : f.key)}
              className={`flex flex-1 flex-col items-center gap-1 rounded-xl border py-3 transition-all ${
                feel === f.key
                  ? "border-primary/50 bg-primary/10"
                  : "border-border hover:border-foreground/20"
              }`}
            >
              <span className="text-2xl">{f.emoji}</span>
              <span className="text-xs font-medium">{f.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Notes */}
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="How was the session? Any notes..."
        rows={2}
        className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/50"
      />

      {/* Save */}
      <Button onClick={handleSave} disabled={saving} size="lg" className="w-full text-base font-semibold">
        {saving ? "Saving..." : "Save"}
      </Button>
    </div>
  );
}
