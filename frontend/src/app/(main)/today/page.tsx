"use client";

import { useEffect, useState, useCallback } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { DayCard } from "@/components/training/day-card";
import { FeedbackDialog } from "@/components/training/feedback-dialog";
import { getWeek, applyEvents, postFeedback } from "@/lib/api";
import type { WeekPlan, DayPlan } from "@/lib/types";

/** Nomi dei giorni della settimana in italiano */
const WEEKDAY_FULL_IT: Record<number, string> = {
  0: "Domenica",
  1: "Lunedi",
  2: "Martedi",
  3: "Mercoledi",
  4: "Giovedi",
  5: "Venerdi",
  6: "Sabato",
};

/** Nomi dei mesi in italiano */
const MONTH_IT: Record<number, string> = {
  0: "Gennaio",
  1: "Febbraio",
  2: "Marzo",
  3: "Aprile",
  4: "Maggio",
  5: "Giugno",
  6: "Luglio",
  7: "Agosto",
  8: "Settembre",
  9: "Ottobre",
  10: "Novembre",
  11: "Dicembre",
};

/** Restituisce la data odierna in formato YYYY-MM-DD */
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Formatta la data odierna come "Lunedi 15 Febbraio" */
function formatTodaySubtitle(): string {
  const d = new Date();
  const dayName = WEEKDAY_FULL_IT[d.getDay()] ?? "";
  const dayNum = d.getDate();
  const monthName = MONTH_IT[d.getMonth()] ?? "";
  return `${dayName} ${dayNum} ${monthName}`;
}

export default function TodayPage() {
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackSessionId, setFeedbackSessionId] = useState<string | null>(null);

  const fetchWeek = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWeek(0);
      setWeekPlan(data.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel caricamento");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWeek();
  }, [fetchWeek]);

  /** Trova il giorno di oggi nel piano settimanale */
  const today = todayISO();
  const todayPlan: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date === today);

  /** Segna una sessione come completata */
  async function handleMarkDone(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            type: "session_done",
            date: today,
            session_id: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);

      // Apri dialog feedback
      setFeedbackSessionId(sessionId);
      setFeedbackOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel salvataggio");
    }
  }

  /** Segna una sessione come saltata */
  async function handleMarkSkipped(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            type: "session_skipped",
            date: today,
            session_id: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel salvataggio");
    }
  }

  /** Invia il feedback della sessione */
  async function handleFeedbackSubmit(feedback: Record<string, string>) {
    if (!feedbackSessionId) return;
    try {
      await postFeedback({
        log_entry: {
          date: today,
          session_id: feedbackSessionId,
          exercise_feedback: feedback,
        },
        status: "done",
      });
    } catch {
      // Feedback non critico, non blocchiamo l'UX
    } finally {
      setFeedbackOpen(false);
      setFeedbackSessionId(null);
    }
  }

  // Esercizi per il dialog di feedback (semplificato: usiamo session_id come placeholder)
  const feedbackExercises = feedbackSessionId
    ? [{ exercise_id: feedbackSessionId, name: feedbackSessionId.replace(/_/g, " ") }]
    : [];

  return (
    <>
      <TopBar title="Oggi" subtitle={formatTodaySubtitle()} />

      <main className="mx-auto max-w-2xl space-y-4 p-4">
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

        {/* Giorno di oggi */}
        {!loading && !error && todayPlan && (
          <DayCard
            day={todayPlan}
            onMarkDone={handleMarkDone}
            onMarkSkipped={handleMarkSkipped}
          />
        )}

        {/* Nessuna sessione oggi (giorno di riposo) */}
        {!loading && !error && todayPlan && todayPlan.sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              Non ci sono sessioni oggi
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Goditi il riposo e recupera per la prossima sessione.
            </p>
          </div>
        )}

        {/* Piano settimanale non trovato per oggi */}
        {!loading && !error && !todayPlan && weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              Non ci sono sessioni oggi
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Nessun piano trovato per la data odierna.
            </p>
          </div>
        )}
      </main>

      {/* Dialog per il feedback post-sessione */}
      <FeedbackDialog
        open={feedbackOpen}
        onClose={() => {
          setFeedbackOpen(false);
          setFeedbackSessionId(null);
        }}
        onSubmit={handleFeedbackSubmit}
        exercises={feedbackExercises}
      />
    </>
  );
}
