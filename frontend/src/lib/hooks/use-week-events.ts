"use client";

import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, NETWORK_ERROR_STATUS, applyEvents } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache } from "@/lib/week-cache";
import type { WeekPlan } from "@/lib/types";

type WeekCacheEntry = {
  week_num?: number;
  phase_id?: string | null;
  week_plan: WeekPlan;
};

/**
 * Coda FIFO globale (una sola per tab): due mutation sul week plan non possono
 * mai essere in volo insieme, nemmeno se partono da pagine o card diverse.
 */
let chain: Promise<unknown> = Promise.resolve();

/**
 * F6 (A245) — done/skip inviano l'INTERO week plan e il backend lo persiste
 * sovrascrivendo per intero. Due tap rapidi su due sessioni dello stesso giorno
 * partivano dallo stesso snapshot catturato al render: il secondo POST
 * sovrascriveva il primo e il mark-done andava perso (l'UI mostrava "done" fino
 * al refetch, poi la sessione ricompariva pianificata).
 *
 * Due guardie complementari:
 *  1. le chiamate sono serializzate — mai concorrenti;
 *  2. ogni chiamata rilegge il week plan dalla CACHE al momento in cui parte,
 *     non dalla closure del render, quindi riparte sempre dal risultato della
 *     precedente.
 *
 * La guardia `disabled` sui bottoni (session-card) copre il doppio tap sulla
 * stessa card; questa copre il caso cross-card e cross-pagina.
 */
export function useWeekEvents(weekNum: number) {
  const qc = useQueryClient();

  return useCallback(
    (events: Array<Record<string, unknown>>): Promise<{ week_plan: WeekPlan }> => {
      const run = chain.then(async () => {
        const cached = qc.getQueryData<WeekCacheEntry>(queryKeys.week(weekNum));
        const weekPlan = cached?.week_plan;
        if (!weekPlan) throw new Error("Week plan not loaded");

        // A245 B-4 — these events are deliberately NOT queued in the outbox:
        // they ship the whole week plan and the backend persists it wholesale,
        // so replaying a stale snapshot later would overwrite everything that
        // happened in between and could touch past sessions. Fail loudly.
        if (typeof navigator !== "undefined" && navigator.onLine === false) {
          throw new ApiError(
            NETWORK_ERROR_STATUS,
            "You're offline — this change can't be saved yet. Try again once you're connected.",
          );
        }

        const result = await applyEvents({ events, week_plan: weekPlan });

        // A245 G-2 (F34): mirrors onto the week(0) ⇄ week(N) alias so /today
        // and /week cannot disagree about the same seven days.
        writeWeekCache(qc, weekNum, result.week_plan);
        return result;
      });
      // La coda non deve morire su un errore del task precedente.
      chain = run.catch(() => {});
      return run;
    },
    [qc, weekNum],
  );
}
