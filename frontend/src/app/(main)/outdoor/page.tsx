"use client";

import { useEffect, useState } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { getOutdoorSessions, getOutdoorStats } from "@/lib/api";
import type { OutdoorSession, OutdoorStats } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function OutdoorPage() {
  const [sessions, setSessions] = useState<(OutdoorSession & { load_score?: number })[]>([]);
  const [stats, setStats] = useState<OutdoorStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getOutdoorSessions(), getOutdoorStats()])
      .then(([sessData, statsData]) => {
        setSessions(sessData.sessions as (OutdoorSession & { load_score?: number })[]);
        setStats(statsData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

        {!loading && sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No outdoor sessions logged yet.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Log your first outdoor session from the week view.
            </p>
          </div>
        )}

        {!loading && stats && sessions.length > 0 && (
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
                value={stats.top_grade_sent || "—"}
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
                              {topGrade}
                            </Badge>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
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
                            {topGrade && <span>top: {topGrade}</span>}
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
                          ...Object.values(stats.grade_histogram),
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
