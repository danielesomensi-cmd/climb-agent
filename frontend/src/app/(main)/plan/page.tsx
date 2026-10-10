"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { ChevronDown, Info } from "lucide-react";
import { TopBar } from "@/components/layout/top-bar";
import { RadarChart } from "@/components/onboarding/radar-chart";
import { MacrocycleTimeline } from "@/components/training/macrocycle-timeline";
import { MilestonesCard } from "@/components/training/milestones-card";
import { PausedBanner } from "@/components/training/paused-banner";
import { useUserState } from "@/lib/hooks/use-state";
import { useCatalogSessions } from "@/lib/hooks/queries/use-catalog";
import { generateMacrocycle, getStateStatus, getWeek } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  RegeneratePlanSheet,
  optionToPreserveBefore,
  type RegenerateStartOption,
} from "@/components/training/regenerate-plan-sheet";
import { PERIODIZATION_RATIONALE, PHASE_RATIONALES } from "@/lib/phase-rationales";
import { getDiscipline } from "@/lib/gradeUtils";
import {
  computeEliteScores,
  extractEliteInputs,
  hasAnyEliteScore,
} from "@/lib/eliteScoring";
import { getPhaseName } from "@/lib/phase-labels";
import { computeCurrentWeek } from "@/lib/phase-progress";
import {
  domainWeightRows,
  formatCycleHeadline,
  getCyclePosition,
  getIntensityCapLabel,
  getSessionLabel,
} from "@/lib/plan-labels";
import { cn } from "@/lib/utils";
import type { Phase } from "@/lib/types";
import { parseISODateLocal } from "@/lib/dates";

/** A311 — placeholder shaped like the page (hero card, radar, phase rows). */
function PlanSkeleton() {
  return (
    <div className="space-y-6" aria-hidden="true">
      <div className="space-y-3 rounded-xl border border-border p-4">
        <div className="h-3 w-20 animate-pulse rounded bg-muted/40" />
        <div className="h-5 w-3/4 animate-pulse rounded bg-muted/40" />
        <div className="h-10 animate-pulse rounded-lg bg-muted/25" />
      </div>
      <div className="h-64 animate-pulse rounded-xl border border-border bg-muted/20" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-xl border border-border bg-muted/20" />
        ))}
      </div>
      <span className="sr-only">Loading your plan…</span>
    </div>
  );
}


export default function PlanPage() {
  const { isLoaded: authReady } = useAuth();
  const { state, loading, error, refresh } = useUserState(authReady);
  // A311: `undefined` = the user has not toggled anything yet, so the current
  // phase shows expanded on load. Derived at render, no effect needed.
  const [expandedPhase, setExpandedPhase] = useState<string | null | undefined>(undefined);
  const [expandedRationale, setExpandedRationale] = useState<string | null>(null);
  const [aboutPlanOpen, setAboutPlanOpen] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [staleDismissed, setStaleDismissed] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenDialogOpen, setRegenDialogOpen] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);

  const macrocycle = state?.macrocycle ?? null;
  const profile = state?.assessment?.profile ?? null;
  const currentWeek = macrocycle ? computeCurrentWeek(macrocycle) : undefined;
  const discipline = getDiscipline((state?.goal as Record<string, unknown>)?.goal_type as string | undefined);
  const cyclePosition =
    macrocycle && currentWeek != null
      ? getCyclePosition(macrocycle, currentWeek, discipline)
      : null;
  const currentPhaseId = cyclePosition?.phaseId ?? null;
  const openPhaseId = expandedPhase === undefined ? currentPhaseId : expandedPhase;

  // A311: session_pool ids → catalog names (cached for the session, A187).
  const catalogSessions = useCatalogSessions(authReady && !!macrocycle);
  const sessionNames = useMemo(
    () => new Map((catalogSessions.data?.sessions ?? []).map((s) => [s.id, s.name])),
    [catalogSessions.data],
  );
  // B304: axis scores are readiness-for-goal, not absolute — surface the goal
  // grade so every number on the radar reads in context.
  const goalObj = (state?.goal as Record<string, unknown>) ?? {};
  const targetGrade =
    (goalObj.target_grade as string) ||
    (goalObj.target_boulder_grade as string) ||
    ((macrocycle?.goal_snapshot as Record<string, unknown> | undefined)?.target_grade as string) ||
    null;
  // A267 — raw strength numbers for the display-only Elite comparison. They are
  // already in the /api/state payload, so this adds no request and no storage.
  // When nothing measurable is on file the toggle does not appear and the card
  // keeps its own "Readiness for …" subtitle.
  const eliteInputs = extractEliteInputs(state);
  const showsEliteToggle = hasAnyEliteScore(computeEliteScores(eliteInputs));

  const checkStale = useCallback(async () => {
    try {
      const { is_macrocycle_stale } = await getStateStatus();
      setIsStale(is_macrocycle_stale);
    } catch {
      /* silent — non-critical */
    }
  }, []);

  // B155: gate on Clerk readiness
  useEffect(() => {
    if (!authReady) return;
    checkStale();
  }, [checkStale, authReady]);

  function togglePhase(phaseId: string) {
    setExpandedPhase(openPhaseId === phaseId ? null : phaseId);
  }

  async function handleRegenMacro(option: RegenerateStartOption) {
    setRegenerating(true);
    setRegenError(null);
    try {
      await generateMacrocycle(undefined, 12, "current");
      // Force-refresh current week with preserve_before guard
      const preserveBefore = optionToPreserveBefore(option);
      await getWeek(0, true, preserveBefore);
      await refresh();
      setRegenDialogOpen(false);
      setIsStale(false);
      setStaleDismissed(false);
    } catch (e) {
      setRegenError(e instanceof Error ? e.message : "Regeneration failed");
    } finally {
      setRegenerating(false);
    }
  }

  const showStaleBanner = isStale && !staleDismissed;

  return (
    <>
      <TopBar title="Plan" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        <PausedBanner since={macrocycle?.pause?.active_since} />

        {/* Loading state */}
        {loading && <PlanSkeleton />}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm font-medium text-destructive">
              Couldn&rsquo;t load your plan
            </p>
            <p className="mt-1 text-xs text-fg-muted">{error}</p>
            <Button variant="outline" className="mt-3 h-11" onClick={refresh}>
              Retry
            </Button>
          </div>
        )}

        {/* No macrocycle generated */}
        {!loading && !error && !macrocycle && (
          <div className="rounded-lg border border-dashed p-8 text-center space-y-4">
            <p className="text-lg font-semibold">No plan yet</p>
            <p className="text-sm text-muted-foreground">
              Complete the onboarding process to generate your personalized training plan.
            </p>
            <Button asChild className="h-11">
              <Link href="/onboarding/welcome">Start onboarding</Link>
            </Button>
          </div>
        )}

        {/* Main content */}
        {!loading && !error && macrocycle && (
          <>
            {/* Dirty-state banner — mutually exclusive with the standalone button below */}
            {showStaleBanner && (
              <div className="rounded-lg border border-warning/30 bg-warning/15 p-4 space-y-3">
                <p className="text-sm text-warning">
                  Your profile has changed since this plan was generated.
                  Only the remaining phases will be updated &mdash; completed
                  sessions and load progression are safe.
                </p>
                <div className="flex gap-2">
                  <Button
                    className="h-11"
                    onClick={() => setRegenDialogOpen(true)}
                    disabled={regenerating}
                  >
                    {regenerating ? "Processing..." : "Update remaining plan"}
                  </Button>
                  <Button
                    className="h-11"
                    variant="ghost"
                    onClick={() => setStaleDismissed(true)}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            )}

            {/* Macrocycle timeline */}
            <Card>
              <CardHeader>
                <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Macrocycle
                </CardTitle>
                {/* A311: lead with where the athlete is in the cycle. */}
                {cyclePosition && (
                  <p className="text-lg font-semibold leading-snug">
                    {formatCycleHeadline(cyclePosition)}
                  </p>
                )}
                <p className="text-sm text-muted-foreground">
                  {macrocycle.total_weeks} weeks starting from{" "}
                  {parseISODateLocal(macrocycle.start_date).toLocaleDateString("en-US", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </p>
              </CardHeader>
              <CardContent>
                <MacrocycleTimeline
                  showProgress
                  macrocycle={macrocycle}
                  currentWeek={currentWeek}
                  discipline={discipline}
                />
              </CardContent>
            </Card>

            {/* Regenerate macrocycle button — hidden when dirty-state banner is visible */}
            {!showStaleBanner && (
              <div className="flex flex-col items-center gap-1">
                <Button
                  variant="outline"
                  className="h-11"
                  onClick={() => setRegenDialogOpen(true)}
                  disabled={regenerating}
                >
                  {regenerating ? "Processing..." : "Regenerate Macrocycle"}
                </Button>
                <p className="text-[11px] text-muted-foreground text-center max-w-xs">
                  Recalculates remaining phases based on your current profile.
                  Completed phases are preserved.
                </p>
              </div>
            )}

            {/* Regen error */}
            {regenError && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-center">
                <p className="text-sm text-destructive">{regenError}</p>
              </div>
            )}

            {/* Assessment profile radar chart */}
            {profile && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Assessment profile</CardTitle>
                  {targetGrade && !showsEliteToggle && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Readiness for {targetGrade}
                    </p>
                  )}
                </CardHeader>
                <CardContent className="flex justify-center">
                  <RadarChart
                    profile={profile}
                    discipline={discipline}
                    targetGrade={targetGrade}
                    eliteInputs={eliteInputs}
                  />
                </CardContent>
              </Card>
            )}

            <Separator />

            {/* About your plan — expandable */}
            <button
              type="button"
              className="flex min-h-11 items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setAboutPlanOpen((prev) => !prev)}
              aria-expanded={aboutPlanOpen}
            >
              <Info className="size-3.5" aria-hidden="true" />
              <span>{aboutPlanOpen ? "Hide" : "About your plan"}</span>
              <ChevronDown
                className={cn("size-3.5 transition-transform", aboutPlanOpen && "rotate-180")}
                aria-hidden="true"
              />
            </button>
            {aboutPlanOpen && (
              <Card>
                <CardContent className="pt-4">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {PERIODIZATION_RATIONALE.text}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Phase details */}
            <div className="space-y-3">
              <div>
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Phase details
                </h2>
                <p className="text-xs text-muted-foreground mt-1">Tap a phase and open &quot;About this phase&quot; for the science behind each training block.</p>
              </div>

              {macrocycle.phases.map((phase: Phase) => {
                const isExpanded = openPhaseId === phase.phase_id;
                const isCurrent = currentPhaseId === phase.phase_id;
                const label = getPhaseName(phase.phase_id, discipline);
                const intensity = getIntensityCapLabel(phase.intensity_cap);
                const weightRows = domainWeightRows(phase.domain_weights);

                return (
                  <Card
                    key={phase.phase_id}
                    className={cn("gap-0 py-0", isCurrent && "border-primary")}
                  >
                    <button
                      type="button"
                      className="flex min-h-14 w-full items-center justify-between gap-2 rounded-xl px-6 py-3 text-left transition-colors hover:bg-muted/50"
                      onClick={() => togglePhase(phase.phase_id)}
                      aria-expanded={isExpanded}
                    >
                      <span className="min-w-0 space-y-0.5">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold">{label}</span>
                          {isCurrent && <Badge className="text-[10px]">Current</Badge>}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {phase.duration_weeks} {phase.duration_weeks === 1 ? "week" : "weeks"}
                          {intensity && ` · ${intensity}`}
                        </span>
                      </span>
                      <ChevronDown
                        className={cn(
                          "size-4 shrink-0 text-muted-foreground transition-transform",
                          isExpanded && "rotate-180",
                        )}
                        aria-hidden="true"
                      />
                    </button>

                    {isExpanded && (
                      <CardContent className="space-y-4 pb-4">
                        {/* Domain weights — A311: thin bars, heaviest first */}
                        {weightRows.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-2">
                              Training focus
                            </p>
                            <ul className="space-y-1.5">
                              {weightRows.map((row) => (
                                <li
                                  key={row.domain}
                                  className="grid grid-cols-[7.5rem_1fr_2.5rem] items-center gap-2 text-xs"
                                >
                                  <span className="truncate text-muted-foreground">{row.label}</span>
                                  <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                                    <span
                                      className="block h-full rounded-full bg-primary"
                                      style={{ width: `${row.pct}%` }}
                                    />
                                  </span>
                                  <span className="text-right font-medium tabular-nums">
                                    {row.pct}%
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Session pool */}
                        {phase.session_pool.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-2">
                              Available sessions
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {phase.session_pool.map((sessionId) => (
                                <Badge
                                  key={sessionId}
                                  variant="outline"
                                  className="text-[11px]"
                                >
                                  {getSessionLabel(sessionId, sessionNames)}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* About this phase — rationale */}
                        {PHASE_RATIONALES[phase.phase_id] && (
                          <div>
                            <button
                              type="button"
                              className="flex min-h-11 items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                              onClick={() =>
                                setExpandedRationale((prev) =>
                                  prev === phase.phase_id ? null : phase.phase_id
                                )
                              }
                              aria-expanded={expandedRationale === phase.phase_id}
                            >
                              <Info className="size-3.5" aria-hidden="true" />
                              <span>About this phase</span>
                              <ChevronDown
                                className={cn(
                                  "size-3.5 transition-transform",
                                  expandedRationale === phase.phase_id && "rotate-180",
                                )}
                                aria-hidden="true"
                              />
                            </button>
                            {expandedRationale === phase.phase_id && (() => {
                              const r = PHASE_RATIONALES[phase.phase_id];
                              return (
                                <div className="mt-1 text-xs text-muted-foreground space-y-2 pl-5">
                                  <p className="leading-relaxed">{r.text}</p>
                                  {r.duration_note && (
                                    <p className="text-warning">{r.duration_note}</p>
                                  )}
                                  {r.common_mistake && (
                                    <p className="rounded-sm border border-danger/30 bg-danger/15 px-2 py-1.5 text-danger">
                                      <span className="font-semibold">Common mistake:</span> {r.common_mistake}
                                    </p>
                                  )}
                                  {r.what_to_expect && (
                                    <p className="text-success">{r.what_to_expect}</p>
                                  )}
                                </div>
                              );
                            })()}
                          </div>
                        )}
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>

            {/* A239: milestone gallery */}
            <MilestonesCard />
          </>
        )}
      </main>

      {/* ----- Macrocycle regeneration sheet ----- */}
      <RegeneratePlanSheet
        open={regenDialogOpen}
        onOpenChange={setRegenDialogOpen}
        onConfirm={handleRegenMacro}
        loading={regenerating}
      />
    </>
  );
}
