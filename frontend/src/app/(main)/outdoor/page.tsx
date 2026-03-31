"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { TopBar } from "@/components/layout/top-bar";
import { getOutdoorSessions, getOutdoorStats } from "@/lib/api";
import type { OutdoorSession, OutdoorStats } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, ArrowUpRight, ChevronDown } from "lucide-react";
import { useUserState } from "@/lib/hooks/use-state";
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";

// ---------------------------------------------------------------------------
// Route aggregation (A180)
// ---------------------------------------------------------------------------

interface RouteAggregate {
  name: string;
  spot: string;
  grade: string;
  discipline?: "lead" | "boulder";
  totalAttempts: number;
  totalSessions: number;
  bestStyle: string;
  isSent: boolean;
  lastDate: string;
}

const STYLE_RANK: Record<string, number> = {
  onsight: 5,
  flash: 4,
  redpoint: 3,
  repeat: 2,
  project: 1,
};

const STYLE_LABEL: Record<string, string> = {
  onsight: "onsight",
  flash: "flash",
  redpoint: "sent",
  repeat: "repeat",
  project: "projecting",
};

/** Infer effective style from explicit style + attempt outcomes (B181). */
function inferStyle(route: { style?: string; attempts?: { result: string }[] }): string {
  if (route.style && STYLE_RANK[route.style]) return route.style;
  const hasSend = route.attempts?.some((a) => a.result === "sent");
  if (!hasSend) return "project";
  const sendIdx = route.attempts!.findIndex((a) => a.result === "sent");
  return sendIdx === 0 ? "flash" : "redpoint";
}

function aggregateRoutes(sessions: OutdoorSession[]): RouteAggregate[] {
  const map = new Map<string, RouteAggregate>();
  for (const s of sessions) {
    for (const r of s.routes || []) {
      if (!r.name?.trim()) continue;
      const key = `${r.name.trim()}||${s.spot_name || ""}`;
      const existing = map.get(key);
      const attempts = r.attempts?.length || 0;
      if (attempts === 0) continue;
      const effectiveStyle = inferStyle(r);
      const styleRank = STYLE_RANK[effectiveStyle] || 0;
      if (existing) {
        existing.totalAttempts += attempts;
        existing.totalSessions += 1;
        if (styleRank > (STYLE_RANK[existing.bestStyle] || 0)) {
          existing.bestStyle = effectiveStyle;
        }
        existing.isSent = (STYLE_RANK[existing.bestStyle] || 0) >= STYLE_RANK.redpoint;
        if (s.date > existing.lastDate) existing.lastDate = s.date;
      } else {
        map.set(key, {
          name: r.name.trim(),
          spot: s.spot_name || "",
          grade: r.grade || "",
          discipline: r.discipline,
          totalAttempts: attempts,
          totalSessions: 1,
          bestStyle: effectiveStyle,
          isSent: styleRank >= STYLE_RANK.redpoint,
          lastDate: s.date,
        });
      }
    }
  }
  return Array.from(map.values()).sort((a, b) => b.lastDate.localeCompare(a.lastDate));
}

export default function OutdoorPage() {
  const { isLoaded: authReady } = useAuth();
  const { state: userState } = useUserState(authReady);
  const gradeSystem: BoulderGradeSystem = ((userState as Record<string, unknown>)?.preferences as Record<string, unknown>)?.grade_system_boulder as BoulderGradeSystem || "font";
  const [sessions, setSessions] = useState<(OutdoorSession & { load_score?: number })[]>([]);
  const [stats, setStats] = useState<OutdoorStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // B155: gate on Clerk readiness
  useEffect(() => {
    if (!authReady) return;
    Promise.all([getOutdoorSessions(), getOutdoorStats()])
      .then(([sessData, statsData]) => {
        setSessions(sessData.sessions as (OutdoorSession & { load_score?: number })[]);
        setStats(statsData);
      })
      .catch((err) => {
        console.error("Failed to load outdoor data:", err);
        setError("Could not load outdoor history. Please try again.");
      })
      .finally(() => setLoading(false));
  }, [authReady]);

  const [routesExpanded, setRoutesExpanded] = useState(true);

  // Aggregate routes across all sessions (A180)
  const routes = aggregateRoutes(sessions);

  // Group sessions by spot
  const bySpot: Record<string, (OutdoorSession & { load_score?: number })[]> = {};
  for (const s of sessions) {
    const key = s.spot_name || "Unknown";
    if (!bySpot[key]) bySpot[key] = [];
    bySpot[key].push(s);
  }

  return (
    <>
      <TopBar title="Outdoor History" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {!loading && !error && sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No outdoor sessions logged yet.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Log your first outdoor session from the week view.
            </p>
          </div>
        )}

        {!loading && !error && stats && sessions.length > 0 && (
          <>
            {/* Stats cards */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Sessions" value={stats.total_sessions} />
              <StatCard label="Routes" value={stats.total_routes} />
              <StatCard
                label="Send %"
                value={`${stats.sent_pct}%`}
              />
              <StatCard
                label="Top grade"
                value={stats.top_grade_sent ? displayBoulderGrade(stats.top_grade_sent, gradeSystem) : "—"}
              />
            </div>

            {/* Per-spot breakdown */}
            {Object.keys(bySpot).length > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">By spot</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {Object.entries(bySpot).map(([spot, spotSessions]) => {
                    const totalRoutes = spotSessions.reduce(
                      (sum, s) => sum + (s.routes?.length || 0),
                      0,
                    );
                    const topGrade = spotSessions
                      .flatMap((s) => s.routes || [])
                      .filter((r) =>
                        r.attempts?.some((a) => a.result === "sent"),
                      )
                      .map((r) => r.grade)
                      .sort()
                      .pop();

                    return (
                      <div
                        key={spot}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="font-medium">{spot}</span>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>
                            {spotSessions.length} session
                            {spotSessions.length !== 1 ? "s" : ""}
                          </span>
                          <span>{totalRoutes} routes</span>
                          {topGrade && (
                            <Badge variant="outline" className="text-[10px]">
                              {displayBoulderGrade(topGrade, gradeSystem)}
                            </Badge>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            )}

            {/* Routes list (A180) */}
            {routes.length > 0 && (
              <Card>
                <CardHeader
                  className="cursor-pointer select-none"
                  onClick={() => setRoutesExpanded((v) => !v)}
                >
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">Routes ({routes.length})</CardTitle>
                    <ChevronDown
                      className={`h-4 w-4 text-muted-foreground transition-transform ${routesExpanded ? "" : "-rotate-90"}`}
                    />
                  </div>
                </CardHeader>
                {routesExpanded && (
                  <CardContent className="space-y-2">
                    {routes.map((r) => {
                      const displayGrade =
                        r.discipline === "boulder"
                          ? displayBoulderGrade(r.grade, gradeSystem)
                          : r.grade;
                      return (
                        <div
                          key={`${r.name}||${r.spot}`}
                          className="flex items-center justify-between rounded-md border px-3 py-2"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{r.name}</span>
                              <Badge
                                variant="outline"
                                className={`text-[10px] ${r.isSent ? "border-green-600 text-green-500" : "text-muted-foreground"}`}
                              >
                                {STYLE_LABEL[r.bestStyle] || r.bestStyle}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {r.spot && <>{r.spot} · </>}
                              {r.totalAttempts} attempt{r.totalAttempts !== 1 ? "s" : ""} · {r.totalSessions} session{r.totalSessions !== 1 ? "s" : ""}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {displayGrade && (
                              <span className="font-mono text-xs text-muted-foreground">
                                {displayGrade}
                              </span>
                            )}
                            {r.isSent ? (
                              <Check className="h-4 w-4 text-green-500" />
                            ) : (
                              <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                )}
              </Card>
            )}

            {/* Session list */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Sessions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {sessions
                  .slice()
                  .sort((a, b) => b.date.localeCompare(a.date))
                  .map((s, idx) => {
                    const topGrade = s.routes
                      ?.filter((r) =>
                        r.attempts?.some((a) => a.result === "sent"),
                      )
                      .map((r) => r.grade)
                      .sort()
                      .pop();

                    return (
                      <div
                        key={`${s.date}-${idx}`}
                        className="flex items-center justify-between rounded-md border px-3 py-2"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">
                              {new Date(s.date + "T00:00:00").toLocaleDateString(
                                "en-US",
                                {
                                  day: "numeric",
                                  month: "short",
                                },
                              )}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              {s.spot_name}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Badge variant="outline" className="text-[10px]">
                              {s.discipline}
                            </Badge>
                            <span>{s.routes?.length || 0} routes</span>
                            {topGrade && <span>top: {displayBoulderGrade(topGrade, gradeSystem)}</span>}
                          </div>
                        </div>
                        {s.load_score != null && (
                          <div className="text-right">
                            <p className="text-sm font-semibold">{s.load_score}</p>
                            <p className="text-[10px] text-muted-foreground">
                              load
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </CardContent>
            </Card>

            {/* Grade histogram */}
            {Object.keys(stats.grade_histogram).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Grade distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {Object.entries(stats.grade_histogram)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([grade, count]) => {
                        const maxCount = Math.max(
                          ...Object.values(stats.grade_histogram), 1,
                        );
                        const pct = (count / maxCount) * 100;

                        return (
                          <div
                            key={grade}
                            className="flex items-center gap-2 text-sm"
                          >
                            <span className="w-10 text-right font-mono text-xs">
                              {grade}
                            </span>
                            <div className="flex-1 h-4 rounded-sm bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-sm bg-primary"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="w-6 text-right text-xs text-muted-foreground">
                              {count}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <Card>
      <CardContent className="p-3 text-center">
        <p className="text-lg font-bold">{value}</p>
        <p className="text-[10px] text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
