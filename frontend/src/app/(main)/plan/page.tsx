"use client";

import { useState } from "react";
import Link from "next/link";
import { TopBar } from "@/components/layout/top-bar";
import { RadarChart } from "@/components/onboarding/radar-chart";
import { MacrocycleTimeline } from "@/components/training/macrocycle-timeline";
import { useUserState } from "@/lib/hooks/use-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { Phase } from "@/lib/types";

/** Phase labels */
const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

/** Domain labels */
const DOMAIN_LABELS: Record<string, string> = {
  finger_strength: "Finger strength",
  pulling_strength: "Pulling strength",
  power_endurance: "Power endurance",
  technique: "Technique",
  endurance: "Endurance",
  body_composition: "Body composition",
  power: "Power",
  strength: "Strength",
  conditioning: "Conditioning",
  flexibility: "Flexibility",
  prehab: "Prehab",
};

/** Compute the current week of the macrocycle based on the start date */
function computeCurrentWeek(startDate: string): number {
  const start = new Date(startDate);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();
  const diffWeeks = Math.floor(diffMs / (7 * 24 * 60 * 60 * 1000));
  return Math.max(1, diffWeeks + 1);
}

export default function PlanPage() {
  const { state, loading, error, refresh } = useUserState();
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);

  const macrocycle = state?.macrocycle ?? null;
  const profile = state?.assessment?.profile ?? null;
  const currentWeek = macrocycle ? computeCurrentWeek(macrocycle.start_date) : undefined;

  function togglePhase(phaseId: string) {
    setExpandedPhase((prev) => (prev === phaseId ? null : phaseId));
  }

  return (
    <>
      <TopBar title="Plan" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={refresh}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* No macrocycle generated */}
        {!loading && !error && !macrocycle && (
          <div className="rounded-lg border border-dashed p-8 text-center space-y-4">
            <p className="text-muted-foreground text-lg">
              No plan generated
            </p>
            <p className="text-sm text-muted-foreground">
              Complete the onboarding process to generate your personalized training plan.
            </p>
            <Link href="/onboarding/welcome">
              <Button>Start onboarding</Button>
            </Link>
          </div>
        )}

        {/* Main content */}
        {!loading && !error && macrocycle && (
          <>
            {/* Assessment profile radar chart */}
            {profile && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Assessment profile</CardTitle>
                </CardHeader>
                <CardContent className="flex justify-center">
                  <RadarChart profile={profile} />
                </CardContent>
              </Card>
            )}

            <Separator />

            {/* Macrocycle timeline */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Macrocycle</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {macrocycle.total_weeks} weeks starting from{" "}
                  {new Date(macrocycle.start_date).toLocaleDateString("en-US", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </p>
              </CardHeader>
              <CardContent>
                <MacrocycleTimeline
                  macrocycle={macrocycle}
                  currentWeek={currentWeek}
                />
              </CardContent>
            </Card>

            <Separator />

            {/* Phase details */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Phase details
              </h2>

              {macrocycle.phases.map((phase: Phase) => {
                const isExpanded = expandedPhase === phase.phase_id;
                const label =
                  PHASE_LABELS[phase.energy_system] ?? phase.phase_name;

                return (
                  <Card
                    key={phase.phase_id}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                    onClick={() => togglePhase(phase.phase_id)}
                  >
                    <CardHeader className="pb-0">
                      <div className="flex items-center justify-between gap-2">
                        <CardTitle className="text-sm">{label}</CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px]">
                            {phase.duration_weeks} wk
                          </Badge>
                          <Badge variant="secondary" className="text-[10px]">
                            {phase.intensity_cap}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>

                    {isExpanded && (
                      <CardContent className="space-y-4 pt-3">
                        {/* Domain weights */}
                        {Object.keys(phase.domain_weights).length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-muted-foreground mb-2">
                              Domain weights
                            </p>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                              {Object.entries(phase.domain_weights).map(
                                ([domain, weight]) => (
                                  <div
                                    key={domain}
                                    className="flex items-center justify-between text-xs"
                                  >
                                    <span className="text-muted-foreground">
                                      {DOMAIN_LABELS[domain] ?? domain}
                                    </span>
                                    <span className="font-mono font-semibold">
                                      {typeof weight === "number"
                                        ? `${Math.round(weight * 100)}%`
                                        : weight}
                                    </span>
                                  </div>
                                )
                              )}
                            </div>
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
                                  className="text-[10px]"
                                >
                                  {sessionId.replace(/_/g, " ")}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    )}
                  </Card>
                );
              })}
            </div>
          </>
        )}
      </main>
    </>
  );
}
