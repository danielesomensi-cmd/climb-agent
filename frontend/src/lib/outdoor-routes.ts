/**
 * Outdoor History route reading (A180 / B181 / A227 / B362), moved out of
 * `app/(main)/outdoor/page.tsx` by A324 so it can be tested.
 *
 * A324: a send is `sent` on lead (`outdoor-result.ts`). A route climbed clean
 * only on second / top-rope reads «second clean» / «TR clean» (blue), one only
 * in A0 reads «A0» (amber) — never a send, never a style. A route climbed on
 * top-rope first and led later is a redpoint: every try counts towards the
 * send, whoever led it.
 */
import type { OutdoorRoute, OutdoorSession } from "@/lib/types";
import {
  isLeadSend,
  routeAid,
  routeCleanNonLead,
  routeCleanRole,
} from "@/lib/outdoor-result";

/** How a route reads in the history: a send style, or what happened instead. */
export type RouteStyle =
  | "onsight"
  | "flash"
  | "redpoint"
  | "repeat"
  | "project"
  | "second_clean"
  | "tr_clean"
  | "aid";

export const STYLE_LABEL: Record<RouteStyle, string> = {
  onsight: "onsight",
  flash: "flash",
  redpoint: "sent",
  repeat: "repeat",
  project: "projecting",
  second_clean: "second clean",
  tr_clean: "TR clean",
  aid: "A0",
};

const SEND_STYLES: ReadonlySet<RouteStyle> = new Set(["onsight", "flash", "redpoint", "repeat"]);

/** A style that means the route was sent on lead. */
export function isSendStyle(style: RouteStyle): boolean {
  return SEND_STYLES.has(style);
}

/** Badge classes for a route style: green only for a lead send, blue for a
 *  clean ascent on second / top-rope, amber for A0, muted otherwise. */
export function routeStyleBadgeClass(style: RouteStyle): string {
  if (isSendStyle(style)) return "border-success/40 bg-success/15 text-success";
  if (style === "second_clean" || style === "tr_clean") return "border-info/40 bg-info/15 text-info";
  if (style === "aid") return "border-warning/40 bg-warning/15 text-warning";
  return "text-muted-foreground";
}

type RouteForStyle = Pick<OutdoorRoute, "style"> & { attempts?: OutdoorRoute["attempts"] };

/** What a route with no lead send reads as: clean on second / TR, A0, or a project. */
function unsentStyle(route: { attempts?: OutdoorRoute["attempts"] }): RouteStyle {
  if (routeCleanNonLead(route)) return routeCleanRole(route) === "toprope" ? "tr_clean" : "second_clean";
  if (routeAid(route)) return "aid";
  return "project";
}

/**
 * B181/A227 — effective style of a single route WITHIN one session.
 *
 * Canonical validity rule: onsight/flash are valid only on a true first-try
 * send (exactly one attempt, sent on lead). An explicit onsight/flash that
 * doesn't hold (e.g. tagged flash but multiple attempts) is downgraded to
 * redpoint on display — never rewritten in the log. A324: without a lead send
 * no style is shown, whatever the log says.
 */
export function sessionRouteStyle(route: RouteForStyle): RouteStyle {
  const attempts = route.attempts || [];
  const sendIdx = attempts.findIndex(isLeadSend);
  if (sendIdx === -1) return unsentStyle(route);
  const firstTry = sendIdx === 0 && attempts.length === 1;
  if (route.style === "onsight") return firstTry ? "onsight" : "redpoint";
  if (route.style === "flash") return firstTry ? "flash" : "redpoint";
  if (route.style === "redpoint" || route.style === "repeat") return route.style;
  return firstTry ? "flash" : "redpoint";
}

export interface RouteAggregate {
  name: string;
  spot: string;
  grade: string;
  discipline?: "lead" | "boulder";
  totalAttempts: number; // lifetime attempts across all sessions
  attemptsToSend: number | null; // attempts up to & incl. the first lead send (null = unsent)
  totalSessions: number;
  bestStyle: RouteStyle;
  isSent: boolean;
  lastDate: string;
}

/**
 * Aggregate a route across sessions, chronologically, so the displayed style is
 * coherent with the attempt count (A227 / B3). `bestStyle` reflects the FIRST
 * lead send's style; `attemptsToSend` counts attempts up to & including that
 * first lead send — every try before it counts, on any rope role, so top-rope
 * then lead is a redpoint (A324). `totalAttempts` stays the lifetime count.
 */
export function aggregateRoutes(sessions: OutdoorSession[]): RouteAggregate[] {
  // Group occurrences by route key, preserving chronological order.
  const groups = new Map<string, { name: string; spot: string; grade: string; discipline?: "lead" | "boulder"; occ: { date: string; route: OutdoorRoute }[] }>();
  const ordered = sessions.slice().sort((a, b) => a.date.localeCompare(b.date));
  for (const s of ordered) {
    for (const r of s.routes || []) {
      if (!r.name?.trim()) continue;
      if (!(r.attempts?.length)) continue;
      // B362: one route, one row — "Cima nikita" and "Cima Nikita " are the
      // same line. Group case/whitespace-insensitively, show the latest spelling.
      const name = r.name.trim().replace(/\s+/g, " ");
      const key = `${name.toLowerCase()}||${(s.spot_name || "").trim().toLowerCase()}`;
      const g = groups.get(key);
      if (g) {
        g.occ.push({ date: s.date, route: r });
        g.name = name;
        if (!g.grade && r.grade) g.grade = r.grade;
      } else {
        groups.set(key, { name, spot: s.spot_name || "", grade: r.grade || "", discipline: r.discipline, occ: [{ date: s.date, route: r }] });
      }
    }
  }

  const out: RouteAggregate[] = [];
  for (const g of groups.values()) {
    const name = g.name;
    let totalAttempts = 0;
    let attemptsToSend: number | null = null;
    let firstSendOnsight = false;
    let firstSendRepeat = false;
    let lastDate = g.occ[0].date;
    let running = 0;
    for (const { date, route } of g.occ) {
      const atts = route.attempts || [];
      for (let i = 0; i < atts.length; i++) {
        running += 1;
        totalAttempts += 1;
        if (attemptsToSend === null && isLeadSend(atts[i])) {
          attemptsToSend = running;
          firstSendOnsight = running === 1 && route.style === "onsight";
          // B362: sent before the app existed — a repeat, never a flash.
          firstSendRepeat = route.style === "repeat";
        }
      }
      if (date > lastDate) lastDate = date;
    }

    let bestStyle: RouteStyle;
    if (attemptsToSend === null) bestStyle = unsentStyle({ attempts: g.occ.flatMap((o) => o.route.attempts || []) });
    else if (firstSendRepeat) bestStyle = "repeat";
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
