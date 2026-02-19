"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { WeekGrid } from "@/components/training/week-grid";
import { DayCard } from "@/components/training/day-card";
import { ReplanDialog } from "@/components/training/replan-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getWeek, getState, applyOverride } from "@/lib/api";
import type { WeekPlan, DayPlan, Macrocycle } from "@/lib/types";

/** English labels for phase names */
const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

/** Returns today's date in YYYY-MM-DD format */
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function WeekPage() {
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [weekNum, setWeekNum] = useState(0); // 0 = current week
  const [displayWeekNum, setDisplayWeekNum] = useState(1);
  const [macrocycle, setMacrocycle] = useState<Macrocycle | null>(null);
  const [gyms, setGyms] = useState<
    Array<{ name: string; equipment: string[] }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replanDate, setReplanDate] = useState<string | null>(null);
  const dayRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const handleDayClick = useCallback((date: string) => {
    dayRefs.current[date]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, []);

  const fetchWeek = useCallback(async (wn: number) => {
    setLoading(true);
    setError(null);
    try {
      const weekData = await getWeek(wn);
      setWeekPlan(weekData.week_plan);
      setPhaseId(weekData.phase_id);
      setDisplayWeekNum(weekData.week_num);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [weekData, stateData] = await Promise.all([
        getWeek(0),
        getState(),
      ]);
      setWeekPlan(weekData.week_plan);
      setPhaseId(weekData.phase_id);
      setDisplayWeekNum(weekData.week_num);
      setMacrocycle(stateData.macrocycle ?? null);
      const eq = stateData.equipment as Record<string, unknown> | undefined;
      setGyms(
        (eq?.gyms as Array<{ name: string; equipment: string[] }>) ?? []
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitial();
  }, [fetchInitial]);

  const totalWeeks = macrocycle?.total_weeks ?? 0;

  const handlePrevWeek = () => {
    if (displayWeekNum <= 1) return;
    const newWn = displayWeekNum - 1;
    setWeekNum(newWn);
    fetchWeek(newWn);
  };

  const handleNextWeek = () => {
    if (totalWeeks > 0 && displayWeekNum >= totalWeeks) return;
    const newWn = displayWeekNum + 1;
    setWeekNum(newWn);
    fetchWeek(newWn);
  };

  /** Handle replan: call override API and update week plan */
  async function handleReplanApply(rdata: {
    intent: string;
    location: string;
    gym_id?: string;
  }) {
    if (!weekPlan || !replanDate) return;
    setError(null);
    try {
      const result = await applyOverride({
        intent: rdata.intent,
        location: rdata.location,
        reference_date: replanDate,
        target_date: replanDate,
        gym_id: rdata.gym_id,
        phase_id: phaseId ?? undefined,
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update plan");
    } finally {
      setReplanDate(null);
    }
  }

  const today = todayISO();
  const days: DayPlan[] = weekPlan?.weeks.flatMap((w) => w.days) ?? [];
  const phaseLabel = phaseId
    ? PHASE_LABELS[phaseId] ?? phaseId.replace(/_/g, " ")
    : null;

  return (
    <>
      <TopBar title="Week" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Week navigation */}
        {!loading && weekPlan && (
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={handlePrevWeek}
              disabled={displayWeekNum <= 1}
            >
              <ChevronLeft className="size-4 mr-1" />
              Previous
            </Button>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              <span className="text-sm font-medium">
                Week {displayWeekNum}{totalWeeks > 0 ? ` / ${totalWeeks}` : ""}
              </span>
              {phaseLabel && (
                <Badge variant="secondary">{phaseLabel}</Badge>
              )}
              {weekPlan?.weekly_load_summary?.total_load != null && (
                <Badge variant="outline">Load: {weekPlan.weekly_load_summary.total_load}</Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNextWeek}
              disabled={totalWeeks > 0 && displayWeekNum >= totalWeeks}
            >
              Next
              <ChevronRight className="size-4 ml-1" />
            </Button>
          </div>
        )}

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
              onClick={fetchInitial}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Weekly grid */}
        {!loading && !error && weekPlan && (
          <WeekGrid
            weekPlan={weekPlan}
            currentDate={today}
            onDayClick={handleDayClick}
          />
        )}

        {/* Detailed day list */}
        {!loading && !error && days.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Daily detail
            </h2>
            {days.map((day) => (
              <div
                key={day.date}
                ref={(el) => {
                  dayRefs.current[day.date] = el;
                }}
              >
                <DayCard
                  day={day}
                  gyms={gyms}
                  showActions
                  onReplan={(date) => setReplanDate(date)}
                />
              </div>
            ))}
          </div>
        )}

        {/* No plan */}
        {!loading && !error && !weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              No weekly plan available.
            </p>
          </div>
        )}
      </main>

      {/* Replan dialog */}
      <ReplanDialog
        open={replanDate !== null}
        date={replanDate ?? ""}
        gyms={gyms}
        onClose={() => setReplanDate(null)}
        onApply={handleReplanApply}
      />
    </>
  );
}
