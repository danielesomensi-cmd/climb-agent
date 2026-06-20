"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { TopBar } from "@/components/layout/top-bar";
import { getOutdoorSpots, getOutdoorLogByDate, deleteOutdoorLog } from "@/lib/api";
import type { OutdoorSession, OutdoorSpot } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Check, ArrowUpRight, ChevronDown, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useUserState } from "@/lib/hooks/use-state";
import { useOutdoorSessions, useOutdoorStats } from "@/lib/hooks/queries/use-outdoor";
import { invalidateOutdoor } from "@/lib/invalidation";
import { displayBoulderGrade, hardestGrade, gradeRank, type BoulderGradeSystem } from "@/lib/gradeUtils";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";

// ---------------------------------------------------------------------------
// Route aggregation (A180)
// ---------------------------------------------------------------------------

interface RouteAggregate {
  name: string;
  spot: string;
  grade: string;
  discipline?: "lead" | "boulder";
  totalAttempts: number; // lifetime attempts across all sessions
  attemptsToSend: number | null; // attempts up to & incl. the first send (null = unsent)
  totalSessions: number;
  bestStyle: string;
  isSent: boolean;
  lastDate: string;
}

const STYLE_LABEL: Record<string, string> = {
  onsight: "onsight",
  flash: "flash",
  redpoint: "sent",
  repeat: "repeat",
  project: "projecting",
};

function isSendResult(result: string): boolean {
  return result === "sent" || result === "topped_out";
}

/**
 * B181/A227 — effective style of a single route WITHIN one session.
 *
 * Canonical validity rule: onsight/flash are valid only on a true first-try
 * send (exactly one attempt, sent). An explicit onsight/flash that doesn't hold
 * (e.g. tagged flash but multiple attempts) is downgraded to redpoint on display
 * — never rewritten in the log.
 */
function sessionRouteStyle(route: { style?: string; attempts?: { result: string }[] }): string {
  const attempts = route.attempts || [];
  const sendIdx = attempts.findIndex((a) => isSendResult(a.result));
  if (sendIdx === -1) return "project";
  const firstTry = sendIdx === 0 && attempts.length === 1;
  if (route.style === "onsight") return firstTry ? "onsight" : "redpoint";
  if (route.style === "flash") return firstTry ? "flash" : "redpoint";
  if (route.style === "redpoint" || route.style === "repeat") return route.style;
  return firstTry ? "flash" : "redpoint";
}

/**
 * Aggregate a route across sessions, chronologically, so the displayed style is
 * coherent with the attempt count (A227 / B3). `bestStyle` reflects the FIRST
 * ascent style; `attemptsToSend` counts attempts up to & including that first
 * send (so a flash/onsight always shows "1 try to send" — no more
 * "flash · 4 attempts" anomaly). `totalAttempts` stays the lifetime count.
 */
function aggregateRoutes(sessions: OutdoorSession[]): RouteAggregate[] {
  // Group occurrences by route key, preserving chronological order.
  const groups = new Map<string, { spot: string; grade: string; discipline?: "lead" | "boulder"; occ: { date: string; route: OutdoorSession["routes"][number] }[] }>();
  const ordered = sessions.slice().sort((a, b) => a.date.localeCompare(b.date));
  for (const s of ordered) {
    for (const r of s.routes || []) {
      if (!r.name?.trim()) continue;
      if (!(r.attempts?.length)) continue;
      const key = `${r.name.trim()}||${s.spot_name || ""}`;
      const g = groups.get(key);
      if (g) {
        g.occ.push({ date: s.date, route: r });
        if (!g.grade && r.grade) g.grade = r.grade;
      } else {
        groups.set(key, { spot: s.spot_name || "", grade: r.grade || "", discipline: r.discipline, occ: [{ date: s.date, route: r }] });
      }
    }
  }

  const out: RouteAggregate[] = [];
  for (const [key, g] of groups) {
    const name = key.split("||")[0];
    let totalAttempts = 0;
    let attemptsToSend: number | null = null;
    let firstSendOnsight = false;
    let lastDate = g.occ[0].date;
    let running = 0;
    for (const { date, route } of g.occ) {
      const atts = route.attempts || [];
      for (let i = 0; i < atts.length; i++) {
        running += 1;
        totalAttempts += 1;
        if (attemptsToSend === null && isSendResult(atts[i].result)) {
          attemptsToSend = running;
          firstSendOnsight = running === 1 && route.style === "onsight";
        }
      }
      if (date > lastDate) lastDate = date;
    }

    let bestStyle: string;
    if (attemptsToSend === null) bestStyle = "project";
    else if (attemptsToSend === 1) bestStyle = firstSendOnsight ? "onsight" : "flash";
    else bestStyle = "redpoint";

    out.push({
      name,
      spot: g.spot,
      grade: g.grade,
      discipline: g.discipline,
      totalAttempts,
      attemptsToSend,
      totalSessions: g.occ.length,
      bestStyle,
      isSent: attemptsToSend !== null,
      lastDate,
    });
  }
  return out;
}

export default function OutdoorPage() {
  const router = useRouter();
  const { isLoaded: authReady } = useAuth();
  const { state: userState } = useUserState(authReady);
  const gradeSystem: BoulderGradeSystem = ((userState as Record<string, unknown>)?.preferences as Record<string, unknown>)?.grade_system_boulder as BoulderGradeSystem || "font";
  const outdoorSpots = ((userState as Record<string, unknown>)?.outdoor_spots as Array<{ name: string; discipline: "lead" | "boulder" | "both" }>) || [];
  const hasSpots = outdoorSpots.length > 0;
  const today = new Date().toISOString().split("T")[0];
  const qc = useQueryClient();
  const sessionsQuery = useOutdoorSessions(undefined, authReady);
  const statsQuery = useOutdoorStats(undefined, authReady);
  const sessions = (sessionsQuery.data?.sessions ?? []) as (OutdoorSession & { load_score?: number })[];
  const stats = statsQuery.data ?? null;
  const loading = sessionsQuery.isLoading || statsQuery.isLoading;
  const queryError = sessionsQuery.error || statsQuery.error;
  const [error, setError] = useState<string | null>(null);

  // Log dialog state
  const [showLogDialog, setShowLogDialog] = useState(false);
  const [logSpots, setLogSpots] = useState<OutdoorSpot[]>([]);
  const [editData, setEditData] = useState<OutdoorSession | null>(null);
  const [ctaLoading, setCtaLoading] = useState(false);
  const [confirmDeleteDate, setConfirmDeleteDate] = useState<string | null>(null);
  const [deletingDate, setDeletingDate] = useState<string | null>(null);

  const reloadData = useCallback(() => {
    invalidateOutdoor(qc);
  }, [qc]);

  // Issue 1+3: open log dialog, check for existing session today
  const handleStartSession = useCallback(async () => {
    setCtaLoading(true);
    try {
      const spotsData = await getOutdoorSpots();
      setLogSpots(spotsData.spots);
      try {
        const existing = await getOutdoorLogByDate(today);
        setEditData(existing.session);
      } catch {
        // 404 = no session today
        setEditData(null);
      }
      setShowLogDialog(true);
    } catch {
      setError("Could not load spots. Please try again.");
    } finally {
      setCtaLoading(false);
    }
  }, [today]);

  const handleLogSuccess = useCallback(() => {
    setShowLogDialog(false);
    setEditData(null);
    reloadData();
  }, [reloadData]);

  // Issue 4: delete session
  const handleDeleteSession = useCallback(async (date: string) => {
    setDeletingDate(date);
    setConfirmDeleteDate(null);
    try {
      await deleteOutdoorLog(date);
      invalidateOutdoor(qc);
    } catch {
      setError("Could not delete session. Please try again.");
    } finally {
      setDeletingDate(null);
    }
  }, [qc]);

  const [routesExpanded, setRoutesExpanded] = useState(true);
  // B2 — routes list sort + collapse
  const [routeSort, setRouteSort] = useState<"grade" | "date">("grade");
  const [showAllRoutes, setShowAllRoutes] = useState(false);
  // B1 — expandable session rows
  const [openSessions, setOpenSessions] = useState<Set<string>>(new Set());
  const toggleSession = (date: string) =>
    setOpenSessions((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });

  // Aggregate routes across all sessions (A180)
  const routes = aggregateRoutes(sessions);

  // B2 — sort (default grade desc / hardest first, canonical Font/French) + collapse to 10
  const ROUTE_COLLAPSE = 10;
  const sortedRoutes = routes.slice().sort((a, b) =>
    routeSort === "grade"
      ? gradeRank(b.grade) - gradeRank(a.grade) || b.lastDate.localeCompare(a.lastDate)
      : b.lastDate.localeCompare(a.lastDate),
  );
  const visibleRoutes = showAllRoutes ? sortedRoutes : sortedRoutes.slice(0, ROUTE_COLLAPSE);

  // Group sessions by spot
  const bySpot: Record<string, (OutdoorSession & { load_score?: number })[]> = {};
  for (const s of sessions) {
    const key = s.spot_name || "Unknown";
    if (!bySpot[key]) bySpot[key] = [];
    bySpot[key].push(s);
  }

  // B4 — monthly aggregates (grade progression + volume) from existing data.
  const monthsMap = new Map<string, { sessions: number; routes: number; sentGrades: string[] }>();
  for (const s of sessions) {
    const mk = s.date.slice(0, 7); // YYYY-MM
    const m = monthsMap.get(mk) || { sessions: 0, routes: 0, sentGrades: [] };
    m.sessions += 1;
    for (const r of s.routes || []) {
      m.routes += 1;
      if (r.attempts?.some((a) => isSendResult(a.result))) m.sentGrades.push(r.grade);
    }
    monthsMap.set(mk, m);
  }
  const months = Array.from(monthsMap.entries()).sort(([a], [b]) => a.localeCompare(b));
  const progression = months
    .map(([mk, m]) => ({ mk, grade: hardestGrade(m.sentGrades) }))
    .filter((x): x is { mk: string; grade: string } => x.grade !== null);
  const maxRoutesMonth = Math.max(1, ...months.map(([, m]) => m.routes));
  const minProgRank = progression.length ? Math.min(...progression.map((p) => gradeRank(p.grade))) : 0;
  const maxProgRank = progression.length ? Math.max(...progression.map((p) => gradeRank(p.grade))) : 1;

  const monthLabel = (mk: string) =>
    new Date(mk + "-01T00:00:00").toLocaleDateString("en-US", { month: "short", year: "2-digit" });

  return (
    <>
      <TopBar title="Outdoor History" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Intro + CTA */}
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Every route you log becomes part of your training profile. Climb Agent tracks your projects, attempts, and sends — and uses that data to calibrate your indoor sessions. The more you log, the smarter your training gets.
          </p>
          {hasSpots ? (
            <div className="space-y-2">
              <button
                onClick={() => router.push(`/outdoor/${today}`)}
                className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 active:opacity-80"
              >
                Start Outdoor Session
              </button>
              <button
                onClick={handleStartSession}
                disabled={ctaLoading}
                className="w-full rounded-xl border py-2.5 text-sm text-muted-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {ctaLoading ? "Loading..." : "Quick log (no timer)"}
              </button>
            </div>
          ) : (
            <button
              onClick={() => router.push("/settings")}
              className="w-full rounded-xl bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 active:opacity-80"
            >
              Add your first spot
            </button>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {!loading && (error || queryError) && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error ?? (queryError instanceof Error ? queryError.message : "Could not load outdoor history. Please try again.")}</p>
          </div>
        )}

        {!loading && !error && !queryError && sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No outdoor sessions logged yet.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Log your first outdoor session from the week view.
            </p>
          </div>
        )}

        {!loading && !error && !queryError && stats && sessions.length > 0 && (
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
                    const topGrade = hardestGrade(
                      spotSessions
                        .flatMap((s) => s.routes || [])
                        .filter((r) => r.attempts?.some((a) => isSendResult(a.result)))
                        .map((r) => r.grade),
                    );

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
                    {/* B2 — sort control (default: hardest first, canonical Font/French) */}
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-muted-foreground">Sort:</span>
                      <button
                        onClick={() => setRouteSort("grade")}
                        className={`rounded-full border px-2.5 py-0.5 ${routeSort === "grade" ? "border-primary text-primary" : "text-muted-foreground"}`}
                      >
                        Hardest
                      </button>
                      <button
                        onClick={() => setRouteSort("date")}
                        className={`rounded-full border px-2.5 py-0.5 ${routeSort === "date" ? "border-primary text-primary" : "text-muted-foreground"}`}
                      >
                        Recent
                      </button>
                    </div>
                    {visibleRoutes.map((r) => {
                      const displayGrade =
                        r.discipline === "boulder"
                          ? displayBoulderGrade(r.grade, gradeSystem)
                          : r.grade;
                      const sub = r.isSent
                        ? `${r.attemptsToSend} ${r.attemptsToSend === 1 ? "try" : "tries"} to send · ${r.totalSessions} session${r.totalSessions !== 1 ? "s" : ""}${r.totalAttempts > (r.attemptsToSend ?? 0) ? ` · ${r.totalAttempts} total` : ""}`
                        : `${r.totalAttempts} attempt${r.totalAttempts !== 1 ? "s" : ""} · ${r.totalSessions} session${r.totalSessions !== 1 ? "s" : ""}`;
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
                              {sub}
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
                    {routes.length > ROUTE_COLLAPSE && (
                      <button
                        onClick={() => setShowAllRoutes((v) => !v)}
                        className="w-full pt-1 text-center text-xs text-primary hover:underline"
                      >
                        {showAllRoutes ? "Show less" : `Show all (${routes.length})`}
                      </button>
                    )}
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
                    const topGrade = hardestGrade(
                      (s.routes || [])
                        .filter((r) => r.attempts?.some((a) => isSendResult(a.result)))
                        .map((r) => r.grade),
                    );

                    const isConfirming = confirmDeleteDate === s.date;
                    const isDeleting = deletingDate === s.date;
                    const isOpen = openSessions.has(s.date);
                    const hasRoutes = (s.routes?.length || 0) > 0;

                    return (
                      <div
                        key={`${s.date}-${idx}`}
                        className="rounded-md border px-3 py-2 space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          {/* B1 — tap to expand the session's route list (read-only) */}
                          <button
                            type="button"
                            onClick={() => hasRoutes && toggleSession(s.date)}
                            aria-expanded={isOpen}
                            className="min-w-0 flex-1 space-y-0.5 text-left"
                          >
                            <div className="flex items-center gap-2">
                              {hasRoutes && (
                                <ChevronDown
                                  className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${isOpen ? "" : "-rotate-90"}`}
                                />
                              )}
                              <span className="text-sm font-medium">
                                {new Date(s.date + "T00:00:00").toLocaleDateString(
                                  "en-US",
                                  { day: "numeric", month: "short" },
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
                          </button>
                          <div className="flex items-center gap-3">
                            {s.load_score != null && (
                              <div className="text-right">
                                <p className="text-sm font-semibold">{s.load_score}</p>
                                <p className="text-[10px] text-muted-foreground">load</p>
                              </div>
                            )}
                            <button
                              onClick={() => setConfirmDeleteDate(isConfirming ? null : s.date)}
                              disabled={isDeleting}
                              className="text-muted-foreground/50 hover:text-destructive disabled:opacity-30"
                              aria-label="Delete session"
                            >
                              <Trash2 className="size-4" />
                            </button>
                          </div>
                        </div>
                        {isOpen && hasRoutes && (
                          <ul className="space-y-1 border-t pt-2">
                            {(s.routes || []).map((r, ri) => {
                              const style = sessionRouteStyle(r);
                              const sent = isSendResult(r.attempts?.[0]?.result ?? "") || (r.attempts || []).some((a) => isSendResult(a.result));
                              const dg = r.discipline === "boulder" ? displayBoulderGrade(r.grade, gradeSystem) : r.grade;
                              return (
                                <li key={ri} className="flex items-center gap-2 text-xs">
                                  <span className="w-10 shrink-0 font-mono text-muted-foreground">{dg}</span>
                                  <span className="min-w-0 flex-1 truncate">{r.name || "—"}</span>
                                  <Badge
                                    variant="outline"
                                    className={`text-[10px] ${sent ? "border-green-600/60 text-green-500" : "text-muted-foreground"}`}
                                  >
                                    {STYLE_LABEL[style] || style}
                                  </Badge>
                                  <span className="shrink-0 text-muted-foreground">
                                    {(r.attempts?.length || 0)} {(r.attempts?.length || 0) === 1 ? "try" : "tries"}
                                  </span>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                        {isConfirming && (
                          <div className="flex items-center gap-2 pt-1 border-t">
                            <span className="flex-1 text-xs text-muted-foreground">Delete this session?</span>
                            <button
                              onClick={() => setConfirmDeleteDate(null)}
                              className="rounded border px-2 py-1 text-xs"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleDeleteSession(s.date)}
                              className="rounded bg-destructive px-2 py-1 text-xs text-destructive-foreground"
                            >
                              Delete
                            </button>
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
                      .sort(([a], [b]) => gradeRank(a) - gradeRank(b))
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

            {/* B4 — grade progression over time (hardest send per month) */}
            {progression.length > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Grade progression</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {progression.map((p) => {
                      // Scale bar height by rank within the observed range (min..max).
                      const span = Math.max(1, maxProgRank - minProgRank);
                      const pct = 25 + (75 * (gradeRank(p.grade) - minProgRank)) / span;
                      const dg = displayBoulderGrade(p.grade, gradeSystem);
                      return (
                        <div key={p.mk} className="flex items-center gap-2 text-sm">
                          <span className="w-14 shrink-0 text-xs text-muted-foreground">{monthLabel(p.mk)}</span>
                          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-muted">
                            <div className="h-full rounded-sm bg-primary" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-10 shrink-0 text-right font-mono text-xs">{dg}</span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-[10px] text-muted-foreground">Hardest grade sent each month.</p>
                </CardContent>
              </Card>
            )}

            {/* B4 — monthly volume (routes climbed + sessions per month) */}
            {months.length > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Monthly volume</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {months.map(([mk, m]) => {
                      const pct = (m.routes / maxRoutesMonth) * 100;
                      return (
                        <div key={mk} className="flex items-center gap-2 text-sm">
                          <span className="w-14 shrink-0 text-xs text-muted-foreground">{monthLabel(mk)}</span>
                          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-muted">
                            <div className="h-full rounded-sm bg-primary/70" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-20 shrink-0 text-right text-xs text-muted-foreground">
                            {m.routes}r · {m.sessions}s
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

      {/* Log / Edit dialog */}
      <Dialog open={showLogDialog} onOpenChange={(v) => { if (!v) { setShowLogDialog(false); setEditData(null); } }}>
        <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editData ? "Edit Today's Session" : "Log Outdoor Session"}</DialogTitle>
            {editData && (
              <p className="text-xs text-amber-400 mt-1">
                You already have a session logged today — editing it.
              </p>
            )}
          </DialogHeader>
          <OutdoorLogForm
            spots={logSpots}
            defaultDate={today}
            defaultSpotName={outdoorSpots[0]?.name}
            defaultDiscipline={outdoorSpots[0]?.discipline}
            initialData={editData ?? undefined}
            onSuccess={handleLogSuccess}
          />
        </DialogContent>
      </Dialog>
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
