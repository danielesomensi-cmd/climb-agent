"use client";

import { useMemo } from "react";
import { useOutdoorSessions } from "./use-outdoor";
import type { OutdoorRoute } from "@/lib/types";

export interface OutdoorDaysSummary {
  /** Vie loggate, per data. */
  routesMap: Record<string, OutdoorRoute[]>;
  /** Minuti totali, per data. */
  durationMap: Record<string, number>;
  /** Load della singola giornata, per data. */
  loadMap: Record<string, number>;
  /** B278 — load outdoor della settimana, coerente con header /week e report. */
  totalLoad: number;
  isLoading: boolean;
}

const EMPTY: Omit<OutdoorDaysSummary, "isLoading"> = {
  routesMap: {},
  durationMap: {},
  loadMap: {},
  totalLoad: 0,
};

/**
 * A286 E4 — le sessioni outdoor dei giorni "done" di una settimana.
 *
 * Prima `/today` chiamava `getOutdoorSessions()` dentro un `useEffect` keyato su
 * `weekPlan`. Con `structuralSharing: false` su `useWeekPlan` ogni mutazione
 * produce un nuovo riferimento, quindi l'effetto ripartiva a OGNI azione
 * dell'utente: una richiesta non cachata per ogni tap. Stessa medicina già data
 * alle free session in A245 F-5 — passare dalla cache di React Query.
 *
 * `doneDates` non deve essere memoizzato dal chiamante: la dipendenza vera è il
 * contenuto dell'elenco, non l'identità dell'array.
 */
export function useOutdoorDoneDays(
  doneDates: string[],
  enabled = true,
): OutdoorDaysSummary {
  const datesKey = useMemo(() => [...doneDates].sort().join(","), [doneDates]);
  const minDate = datesKey ? datesKey.split(",")[0] : undefined;

  const query = useOutdoorSessions(minDate, enabled && !!minDate);

  const derived = useMemo(() => {
    if (!datesKey || !query.data) return EMPTY;
    const wanted = new Set(datesKey.split(","));
    const routesMap: Record<string, OutdoorRoute[]> = {};
    const durationMap: Record<string, number> = {};
    const loadMap: Record<string, number> = {};
    let totalLoad = 0;
    for (const s of query.data.sessions) {
      if (!wanted.has(s.date)) continue;
      routesMap[s.date] = [...(routesMap[s.date] ?? []), ...s.routes];
      if (s.duration_minutes) {
        durationMap[s.date] = (durationMap[s.date] ?? 0) + s.duration_minutes;
      }
      if (s.load_score) {
        loadMap[s.date] = (loadMap[s.date] ?? 0) + s.load_score;
        totalLoad += s.load_score;
      }
    }
    return { routesMap, durationMap, loadMap, totalLoad };
  }, [datesKey, query.data]);

  return { ...derived, isLoading: query.isLoading };
}
