/**
 * A292 (R6b) — client mirror of `backend/engine/grade_evidence.supported_grade`.
 *
 * Preview only: the server re-checks everything on confirm. It lets the card
 * say "your answers support 7b" while the athlete is still answering, instead
 * of finding out from a 422.
 */
import { gradeRank } from "@/lib/gradeUtils";

export type EvidenceStyle = "onsight" | "flash" | "worked";

export interface GradeEvidenceRoute {
  key: string;
  date: string;
  spot_name: string | null;
  name: string | null;
  grade: string;
  style: string | null;
  explicit: boolean;
  in_trip: boolean;
}

export interface GradeEvidence {
  field: "lead_max_os";
  current: string | null;
  redpoint: string | null;
  proposed: string | null;
  routes: GradeEvidenceRoute[];
  distinct_days: number;
  distinct_spots: number;
  all_in_trip: boolean;
  dismissed: string | null;
  min_routes: number;
}

const norm = (s: string | null | undefined) => (s ?? "").trim().replace(/\s+/g, " ").toLowerCase();

/** Hardest grade with ≥ minRoutes confirmed routes at or above it, on two
 *  distinct days or two distinct crags; null when none qualifies. */
export function supportedGrade(
  routes: GradeEvidenceRoute[],
  answers: Record<string, EvidenceStyle | undefined>,
  minRoutes = 2,
): string | null {
  const confirmed = routes.filter((r) => answers[r.key] === "onsight" || answers[r.key] === "flash");
  const grades = [...new Set(confirmed.map((r) => r.grade))].sort((a, b) => gradeRank(b) - gradeRank(a));
  for (const g of grades) {
    const support = confirmed.filter((r) => gradeRank(r.grade) >= gradeRank(g));
    const days = new Set(support.map((r) => r.date));
    const spots = new Set(support.map((r) => norm(r.spot_name)));
    if (support.length >= minRoutes && (days.size >= 2 || spots.size >= 2)) return g;
  }
  return null;
}

/** Pre-filled answer: what the log already declares (onsight/flash), else none. */
export function initialAnswers(routes: GradeEvidenceRoute[]): Record<string, EvidenceStyle | undefined> {
  const out: Record<string, EvidenceStyle | undefined> = {};
  for (const r of routes) {
    out[r.key] = r.style === "onsight" || r.style === "flash" ? r.style : undefined;
  }
  return out;
}
