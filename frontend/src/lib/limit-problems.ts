/**
 * A296 — limit problem log (R6c).
 *
 * A limit session is logged problem by problem: grade (Font, always — the
 * display system is render-only), attempts and outcome. The server decides
 * the target step (backend/engine/limit_log.py); this module only builds the
 * payload and mirrors two numbers the logger shows live: the hard-attempt
 * count (finger-safety warning) and the hardest send.
 *
 * Constants mirror backend/engine/limit_log.py — keep them in sync.
 */
import { toast } from "sonner";
import { BOULDER_GRADE_OPTIONS } from "@/lib/gradeUtils";
import type { LimitProblem, LimitProblemDraft, LimitProblemOutcome } from "@/lib/types";

export const MAX_PROBLEMS = 8;
export const MAX_ATTEMPTS = 10;
export const HARD_ATTEMPTS_GUARD = 20;
/** UI cap on the crux-moves stepper (server accepts 0..50). */
export const MAX_CRUX_MOVES = 20;

/** Limit surfaces, labelled (keys = progression_v1.SURFACE_PRIORITY). */
export const SURFACE_LABELS: Readonly<Record<string, string>> = {
  board_kilter: "Kilter",
  board_moonboard: "MoonBoard",
  board_other: "Board",
  spraywall: "Spray wall",
  gym_boulder: "Boulder wall",
};

export function surfaceLabel(surface: string): string {
  return SURFACE_LABELS[surface] ?? surface.replace(/_/g, " ");
}

export const OUTCOME_OPTIONS: ReadonlyArray<{ value: LimitProblemOutcome; label: string }> = [
  { value: "sent", label: "Sent" },
  { value: "high_point", label: "High point" },
  { value: "no_progress", label: "No progress" },
];

function idx(grade: string | null | undefined): number {
  if (!grade) return -1;
  return BOULDER_GRADE_OPTIONS.indexOf(grade.trim().toUpperCase());
}

/** A new row, pre-filled with the target grade and NO outcome: an untouched
 *  row is not a send (nothing is rated by default, A295). */
export function newProblem(target: string | null | undefined): LimitProblemDraft {
  const t = idx(target);
  return { grade: t >= 0 ? BOULDER_GRADE_OPTIONS[t] : "6C", attempts: 1, outcome: null };
}

/**
 * The limit target on the surface the athlete picked (custom player): the
 * read carries one target per surface in `surface_targets`; without a pick,
 * or without the map, the server's default (`surface_selected`).
 */
export function limitTargetFor(
  ex: {
    target_grade?: string;
    target_grade_low?: string;
    surface_selected?: string;
    surface_targets?: Record<string, { target_grade?: string; target_grade_low?: string }>;
  },
  chosen?: string | null,
): { surface?: string; target?: string; targetLow?: string } {
  const surface = chosen && ex.surface_targets?.[chosen] ? chosen : ex.surface_selected;
  const row = surface ? ex.surface_targets?.[surface] : undefined;
  if (row) return { surface, target: row.target_grade, targetLow: row.target_grade_low };
  return { surface, target: ex.target_grade, targetLow: ex.target_grade_low };
}

/** Rows the athlete has rated (an outcome picked), in payload shape. */
export function ratedProblems(rows: LimitProblemDraft[] | undefined): LimitProblem[] {
  const out: LimitProblem[] = [];
  for (const r of rows ?? []) {
    if (!r.outcome) continue;
    const row: LimitProblem = { grade: r.grade, attempts: r.attempts, outcome: r.outcome };
    if (r.outcome !== "sent" && r.crux_moves && r.crux_moves > 0) row.crux_moves = r.crux_moves;
    if (r.name) row.name = r.name;
    out.push(row);
  }
  return out;
}

/** Rows still waiting for an outcome (they will not be sent). */
export function unratedCount(rows: LimitProblemDraft[] | undefined): number {
  return (rows ?? []).filter((r) => !r.outcome).length;
}

/** Attempts on problems at ≥ target − 1 half grade (server: hard_attempts). */
export function hardAttempts(problems: LimitProblemDraft[], target: string | null | undefined): number {
  const t = idx(target);
  if (t < 0) return 0;
  return problems.reduce((sum, p) => (idx(p.grade) >= t - 1 ? sum + p.attempts : sum), 0);
}

/** Hardest sent grade, or null. */
export function bestSent(problems: LimitProblemDraft[]): string | null {
  let best = -1;
  for (const p of problems) {
    if (p.outcome !== "sent") continue;
    best = Math.max(best, idx(p.grade));
  }
  return best >= 0 ? BOULDER_GRADE_OPTIONS[best] : null;
}

/** Clamp crux moves into 0..MAX_CRUX_MOVES. */
export function clampCrux(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(MAX_CRUX_MOVES, Math.round(n)));
}

/** Clamp attempts into 1..MAX_ATTEMPTS. */
export function clampAttempts(n: number): number {
  if (!Number.isFinite(n)) return 1;
  return Math.max(1, Math.min(MAX_ATTEMPTS, Math.round(n)));
}

/**
 * Feedback fields of a limit exercise. With rated problems: `problems` plus
 * `used_grade` = the hardest send (omitted when nothing was sent — the server
 * reads the problems). Rows without an outcome are dropped. Without rated
 * problems: the old path, `used_grade` = what the athlete left in the grade
 * field (pre-filled with the target; unrated, the server holds the target).
 */
export function limitFeedbackFields(
  problems: LimitProblemDraft[] | undefined,
  fallbackGrade: string | undefined,
): { problems?: LimitProblem[]; used_grade?: string } {
  const rows = ratedProblems(problems).slice(0, MAX_PROBLEMS);
  if (rows.length === 0) return fallbackGrade ? { used_grade: fallbackGrade } : {};
  const top = bestSent(rows);
  return top ? { problems: rows, used_grade: top } : { problems: rows };
}

// ── POST /api/feedback → limit_summary ───────────────────────────────────

export interface LimitSummary {
  exercise_id?: string;
  surface?: string;
  target_grade?: string | null;
  next_target_grade?: string | null;
  step?: number | null;
  step_reason?: string | null;
  hard_attempts?: number | null;
  qualifies?: boolean | null;
  warning?: string;
  rp_proposal?: { grade: string; current: string };
}

/** Toast text for the limit summary, or null when there is nothing to say. */
export function describeLimitSummary(raw: unknown): { title: string; description: string } | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const s = raw[0] as LimitSummary;
  if (!s || typeof s !== "object") return null;
  const parts: string[] = [];
  if (s.warning === "hard_attempts_guard") {
    parts.push(
      `${s.hard_attempts ?? "Many"} hard attempts: the target cannot go up after a session like this. Give your fingers a full recovery before the next limit session.`,
    );
  }
  if (s.rp_proposal) {
    parts.push(
      `You sent ${s.rp_proposal.grade}, above your boulder redpoint (${s.rp_proposal.current}). If it was a real send, update it in Settings → Profile & Maxes — the app never changes it on its own.`,
    );
  }
  let title: string;
  if (s.step === 1 && s.next_target_grade) title = `Limit target up: ${s.next_target_grade}`;
  else if (s.step === -1 && s.next_target_grade) title = `Limit target down to ${s.next_target_grade}`;
  else if (s.next_target_grade && (s.step === 0 || s.step_reason)) title = `Limit target holds at ${s.next_target_grade}`;
  else if (parts.length === 0) return null;
  else title = "Limit session logged";
  if (s.step_reason === "first_session_without_progress") {
    parts.unshift("One session without progress never lowers the target — two in a row would.");
  } else if (s.step_reason === "reentry") {
    parts.unshift("Re-entry after a break: the target comes back up once the re-entry sessions are done.");
  }
  return { title, description: parts.join(" ") };
}

export function notifyLimitSummary(raw: unknown): void {
  const msg = describeLimitSummary(raw);
  if (!msg) return;
  toast(msg.title, { description: msg.description || undefined, duration: 10000 });
}
