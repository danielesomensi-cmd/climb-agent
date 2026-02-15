"use client";

import { useEffect, useState, useCallback } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { WeekGrid } from "@/components/training/week-grid";
import { DayCard } from "@/components/training/day-card";
import { Badge } from "@/components/ui/badge";
import { getWeek } from "@/lib/api";
import type { WeekPlan, DayPlan } from "@/lib/types";

/** Etichette italiane per i nomi delle fasi */
const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Forza & Potenza",
  power_endurance: "Resistenza alla Forza",
  performance: "Performance",
  deload: "Scarico",
};

/** Restituisce la data odierna in formato YYYY-MM-DD */
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWeek = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWeek(0);
      setWeekPlan(data.week_plan);
      setPhaseId(data.phase_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel caricamento");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWeek();
  }, [fetchWeek]);

  const today = todayISO();
  const days: DayPlan[] = weekPlan?.weeks.flatMap((w) => w.days) ?? [];
  const phaseLabel = phaseId
    ? PHASE_LABELS[phaseId] ?? phaseId.replace(/_/g, " ")
    : null;

  return (
    <>
      <TopBar title="Settimana" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        {/* Badge fase corrente */}
        {phaseLabel && !loading && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Fase:</span>
            <Badge variant="secondary">{phaseLabel}</Badge>
          </div>
        )}

        {/* Stato di caricamento */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Stato di errore */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={fetchWeek}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Riprova
            </button>
          </div>
        )}

        {/* Griglia settimanale */}
        {!loading && !error && weekPlan && (
          <WeekGrid weekPlan={weekPlan} currentDate={today} />
        )}

        {/* Lista dettagliata dei giorni */}
        {!loading && !error && days.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Dettaglio giornaliero
            </h2>
            {days.map((day) => (
              <DayCard key={day.date} day={day} />
            ))}
          </div>
        )}

        {/* Nessun piano */}
        {!loading && !error && !weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              Nessun piano settimanale disponibile.
            </p>
          </div>
        )}
      </main>
    </>
  );
}
