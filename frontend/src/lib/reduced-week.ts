/**
 * A330 (D288-FE) — the reduced-week suggestion of `GET /api/week` (A328 (b),
 * D288 R3-b), for the UI. Pure, no React.
 *
 * The backend adds `reduced_week` to the CURRENT week's response only when a
 * reduced week is suggested (two sessions rated very hard in 7 days, an active
 * pain report, or the athlete asked the coach). It is never applied: the card
 * only says it, and the plan changes only if the athlete decides it.
 */
import type { ReducedWeekSuggestion } from "@/lib/types";
import { shortDay } from "@/lib/key-sessions";

/** The reasons, as the athlete reads them (mirror of `reduced_week.REASON_TEXT`). */
const REASON_TEXT: Record<string, string> = {
  very_hard_7d: "two sessions rated very hard in the last 7 days",
  pain_block: "an active pain report",
  athlete_request: "you asked for it",
};

const isIsoDay = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v);

/** The suggestion when there is one to show (suggested, with a valid week start). */
export function shownReducedWeek(rw: ReducedWeekSuggestion | null | undefined): ReducedWeekSuggestion | null {
  return rw && rw.suggested && isIsoDay(rw.week_start) ? rw : null;
}

export function reducedWeekReasons(rw: Pick<ReducedWeekSuggestion, "reasons">): string {
  return (rw.reasons ?? [])
    .map((r) => REASON_TEXT[r] ?? String(r).replace(/_/g, " "))
    .join(" and ");
}

/**
 * The card's sentence, split so the lead can be emphasised:
 * «Consider a reduced week from Mon 16 Nov» + « (why): same climbing days, …».
 */
export function reducedWeekText(rw: ReducedWeekSuggestion): { lead: string; rest: string } {
  const why = reducedWeekReasons(rw);
  return {
    lead: `Consider a reduced week from ${shortDay(rw.week_start.slice(0, 10))}`,
    rest:
      `${why ? ` (${why})` : ""}: same climbing days, half the sets, one finger exposure at your working load ` +
      "minus 10 %, no intervals, no tests. Nothing changes in your plan unless you decide it.",
  };
}

/** localStorage key of «dismissed» — per suggested week. */
export function reducedWeekDismissKey(weekStart: string): string {
  return `reduced-week-dismissed:${weekStart.slice(0, 10)}`;
}

export function readReducedWeekDismissed(weekStart: string): boolean {
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(reducedWeekDismissKey(weekStart)) === "1";
  } catch {
    return false;
  }
}

export function writeReducedWeekDismissed(weekStart: string): void {
  try {
    window.localStorage.setItem(reducedWeekDismissKey(weekStart), "1");
  } catch {
    /* private mode / blocked storage: the dismiss just does not stick */
  }
}
