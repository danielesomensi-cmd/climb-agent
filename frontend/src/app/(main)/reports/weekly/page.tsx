"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Info,
  Mountain,
  Dumbbell,
  Calendar,
} from "lucide-react";
import { getWeeklyReport } from "@/lib/api";
import type {
  WeeklyReport,
  WeeklyReportHighlight,
  WeeklyReportDay,
} from "@/lib/types";

const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  very_easy: "bg-green-400",
  easy: "bg-green-500",
  ok: "bg-yellow-500",
  hard: "bg-orange-500",
  very_hard: "bg-red-500",
};

const DIFFICULTY_LABELS: Record<string, string> = {
  very_easy: "Very Easy",
  easy: "Easy",
  ok: "OK",
  hard: "Hard",
  very_hard: "Very Hard",
};

const STATUS_COLORS: Record<string, string> = {
  done: "bg-green-500",
  skipped: "bg-zinc-500",
  planned: "bg-blue-500",
};

const HIGHLIGHT_ICON: Record<string, typeof CheckCircle2> = {
  positive: CheckCircle2,
  progress: TrendingUp,
  warning: AlertTriangle,
  info: Info,
};

const HIGHLIGHT_STYLE: Record<string, string> = {
  positive: "text-green-400",
  progress: "text-blue-400",
  warning: "text-amber-400",
  info: "text-zinc-400",
};

const CATEGORY_LABELS: Record<string, string> = {
  finger_strength: "Finger Strength",
  boulder_power: "Boulder Power",
  endurance: "Endurance",
  complementaries: "Complementaries",
};

function shiftWeek(dateStr: string, delta: number): string {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + delta * 7);
  return d.toISOString().slice(0, 10);
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function WeeklyReportPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    }>
      <WeeklyReportContent />
    </Suspense>
  );
}

function WeeklyReportContent() {
  const searchParams = useSearchParams();
  const initialStart = searchParams.get("week_start") ?? "";
  const [weekStart, setWeekStart] = useState(initialStart);
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async (ws: string) => {
    if (!ws) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getWeeklyReport(ws);
      setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (weekStart) fetchReport(weekStart);
  }, [weekStart, fetchReport]);

  const handlePrev = () => {
    const ws = shiftWeek(weekStart, -1);
    setWeekStart(ws);
  };
  const handleNext = () => {
    const ws = shiftWeek(weekStart, 1);
    setWeekStart(ws);
  };

  const phaseLabel = report?.context.phase_id
    ? PHASE_LABELS[report.context.phase_id] ?? report.context.phase_id.replace(/_/g, " ")
    : null;

  return (
    <>
      <TopBar title="Weekly Report" />

      <main className="mx-auto max-w-2xl space-y-4 p-4 pb-24">
        {/* Header + navigation */}
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={handlePrev}>
            <ChevronLeft className="size-4 mr-1" /> Prev
          </Button>
          <div className="flex items-center gap-2 flex-wrap justify-center">
            <span className="text-sm font-medium">
              {weekStart && formatDate(weekStart)} — {report ? formatDate(report.week_end) : ""}
            </span>
            {phaseLabel && <Badge variant="secondary">{phaseLabel}</Badge>}
            {report?.context.macrocycle_week && (
              <Badge variant="outline">
                Week {report.context.macrocycle_week}
                {report.context.macrocycle_total_weeks
                  ? ` / ${report.context.macrocycle_total_weeks}`
                  : ""}
              </Badge>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={handleNext}>
            Next <ChevronRight className="size-4 ml-1" />
          </Button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {!loading && !error && report && (
          <>
            {/* Adherence ring */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Adherence</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <AdherenceRing pct={report.adherence.pct} />
                  <div className="space-y-1 text-sm">
                    <p>{report.adherence.completed} / {report.adherence.planned} sessions completed</p>
                    {report.adherence.skipped > 0 && (
                      <p className="text-muted-foreground">{report.adherence.skipped} skipped</p>
                    )}
                    {report.adherence.added > 0 && (
                      <p className="text-muted-foreground">{report.adherence.added} added</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Load bar */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Training Load</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <LoadBar
                  planned={report.load.planned_total}
                  actual={report.load.actual_total}
                />
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>{report.load.hard_days} hard day{report.load.hard_days !== 1 ? "s" : ""}</span>
                  <span>{report.load.recovery_days} rest day{report.load.recovery_days !== 1 ? "s" : ""}</span>
                  {report.load.indoor_minutes > 0 && (
                    <span>{report.load.indoor_minutes} min indoor</span>
                  )}
                  {report.load.outdoor_minutes > 0 && (
                    <span>{report.load.outdoor_minutes} min outdoor</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Difficulty distribution */}
            {Object.keys(report.difficulty.distribution).length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Difficulty</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <DifficultyBar distribution={report.difficulty.distribution} />
                  <p className="text-xs text-muted-foreground">
                    Average: {DIFFICULTY_LABELS[report.difficulty.avg_label] ?? report.difficulty.avg_label}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Highlights */}
            {report.highlights.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Highlights</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {report.highlights.map((h: WeeklyReportHighlight) => {
                      const Icon = HIGHLIGHT_ICON[h.type] ?? Info;
                      const style = HIGHLIGHT_STYLE[h.type] ?? "text-zinc-400";
                      return (
                        <li key={h.key} className="flex items-start gap-2 text-sm">
                          <Icon className={`size-4 mt-0.5 shrink-0 ${style}`} />
                          <span>{h.text}</span>
                        </li>
                      );
                    })}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Day-by-day timeline */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Calendar className="size-4" /> Day by Day
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {report.days.map((day: WeeklyReportDay) => (
                    <div
                      key={day.date}
                      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm ${
                        day.is_rest_day ? "opacity-50" : "bg-muted/30"
                      }`}
                    >
                      <span className="w-8 font-medium uppercase text-xs text-muted-foreground">
                        {day.weekday}
                      </span>
                      <span className="w-16 text-xs text-muted-foreground">
                        {formatDate(day.date)}
                      </span>
                      <div className="flex flex-wrap gap-1.5 flex-1">
                        {day.sessions.map((s, i) => (
                          <span
                            key={i}
                            className={`inline-block rounded-full px-2 py-0.5 text-xs text-white ${
                              STATUS_COLORS[s.status] ?? "bg-zinc-600"
                            }`}
                          >
                            {s.session_id.replace(/_/g, " ")}
                          </span>
                        ))}
                        {day.outdoor && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-xs text-white">
                            <Mountain className="size-3" />
                            {day.outdoor.spot_name ?? "Outdoor"}
                          </span>
                        )}
                        {day.is_rest_day && (
                          <span className="text-xs text-muted-foreground italic">Rest</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Progression table */}
            {report.progression.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="size-4" /> Progression
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {report.progression.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="font-medium">
                          {p.exercise_id.replace(/_/g, " ")}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{p.previous_load}</span>
                          <span className="text-muted-foreground">&rarr;</span>
                          <span className={
                            p.direction === "up"
                              ? "text-green-400 font-medium"
                              : p.direction === "down"
                              ? "text-red-400"
                              : ""
                          }>
                            {p.current_load}
                          </span>
                          {p.change_pct != null && (
                            <Badge variant={p.direction === "up" ? "default" : "secondary"} className="text-xs">
                              {p.change_pct > 0 ? "+" : ""}{p.change_pct}%
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Outdoor summary */}
            {report.outdoor.sessions > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Mountain className="size-4" /> Outdoor
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs">Sessions</p>
                      <p className="font-medium">{report.outdoor.sessions}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Routes</p>
                      <p className="font-medium">{report.outdoor.total_routes}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Send Rate</p>
                      <p className="font-medium">{report.outdoor.send_pct}%</p>
                    </div>
                    {report.outdoor.top_grade_sent && (
                      <div>
                        <p className="text-muted-foreground text-xs">Top Grade</p>
                        <p className="font-medium">{report.outdoor.top_grade_sent}</p>
                      </div>
                    )}
                    {report.outdoor.onsight_pct > 0 && (
                      <div>
                        <p className="text-muted-foreground text-xs">Onsight Rate</p>
                        <p className="font-medium">{report.outdoor.onsight_pct}%</p>
                      </div>
                    )}
                    {report.outdoor.spots.length > 0 && (
                      <div className="col-span-2">
                        <p className="text-muted-foreground text-xs">Spots</p>
                        <p className="font-medium">{report.outdoor.spots.join(", ")}</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Stimulus balance grid */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Dumbbell className="size-4" /> Stimulus Balance
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(report.stimulus_balance).map(([cat, data]) => (
                    <div key={cat} className="rounded-md bg-muted/30 p-3">
                      <p className="text-xs font-medium mb-1">
                        {CATEGORY_LABELS[cat] ?? cat.replace(/_/g, " ")}
                      </p>
                      <p className="text-lg font-bold">
                        {data.sessions_this_week}
                        <span className="text-xs font-normal text-muted-foreground ml-1">
                          session{data.sessions_this_week !== 1 ? "s" : ""}
                        </span>
                      </p>
                      {data.days_since_last != null && (
                        <p className={`text-xs ${data.days_since_last > 10 ? "text-amber-400" : "text-muted-foreground"}`}>
                          {data.days_since_last}d since last
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Back to week */}
            <div className="flex justify-center pt-2">
              <a href="/week">
                <Button variant="outline" size="sm">
                  <ChevronLeft className="size-4 mr-1" /> Back to Week
                </Button>
              </a>
            </div>
          </>
        )}

        {!loading && !error && !report && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">No report data available.</p>
          </div>
        )}
      </main>
    </>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/* Sub-components                                                        */
/* ────────────────────────────────────────────────────────────────────── */

function AdherenceRing({ pct }: { pct: number }) {
  const size = 72;
  const stroke = 6;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-muted/30"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          className={pct >= 80 ? "text-green-500" : pct >= 50 ? "text-yellow-500" : "text-red-500"}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
        {Math.round(pct)}%
      </span>
    </div>
  );
}

function LoadBar({ planned, actual }: { planned: number; actual: number }) {
  const max = Math.max(planned, actual, 1);
  const plannedPct = (planned / max) * 100;
  const actualPct = (actual / max) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs">
        <span className="w-16 text-muted-foreground">Planned</span>
        <div className="flex-1 h-3 rounded-full bg-muted/30 overflow-hidden">
          <div className="h-full rounded-full bg-blue-500/60" style={{ width: `${plannedPct}%` }} />
        </div>
        <span className="w-10 text-right font-medium">{planned}</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="w-16 text-muted-foreground">Actual</span>
        <div className="flex-1 h-3 rounded-full bg-muted/30 overflow-hidden">
          <div
            className={`h-full rounded-full ${
              actual > planned * 1.2
                ? "bg-amber-500"
                : actual >= planned * 0.8
                ? "bg-green-500"
                : "bg-red-400"
            }`}
            style={{ width: `${actualPct}%` }}
          />
        </div>
        <span className="w-10 text-right font-medium">{actual}</span>
      </div>
    </div>
  );
}

function DifficultyBar({ distribution }: { distribution: Record<string, number> }) {
  const order = ["very_easy", "easy", "ok", "hard", "very_hard"];
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div className="flex h-4 rounded-full overflow-hidden">
      {order.map((label) => {
        const count = distribution[label] ?? 0;
        if (count === 0) return null;
        const pct = (count / total) * 100;
        return (
          <div
            key={label}
            className={`${DIFFICULTY_COLORS[label]} relative group`}
            style={{ width: `${pct}%` }}
            title={`${DIFFICULTY_LABELS[label]}: ${count}`}
          />
        );
      })}
    </div>
  );
}
