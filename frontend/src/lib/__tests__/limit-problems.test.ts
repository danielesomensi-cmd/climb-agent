import { describe, it, expect } from "vitest";
import {
  HARD_ATTEMPTS_GUARD,
  bestSent,
  clampAttempts,
  describeLimitSummary,
  hardAttempts,
  limitFeedbackFields,
  limitTargetFor,
  newProblem,
  ratedProblems,
  unratedCount,
} from "../limit-problems";
import type { LimitProblem } from "../types";

const P = (grade: string, outcome: LimitProblem["outcome"], attempts = 3): LimitProblem => ({ grade, outcome, attempts });

describe("A296 — limit problem log helpers", () => {
  it("counts hard attempts from target − 1 half grade, like the server", () => {
    const rows = [P("7B", "sent", 4), P("7A+", "no_progress", 5), P("7A", "sent", 9)];
    expect(hardAttempts(rows, "7B")).toBe(9);
    expect(hardAttempts(rows, undefined)).toBe(0);
    expect(HARD_ATTEMPTS_GUARD).toBe(20);
  });

  it("finds the hardest send and ignores high points", () => {
    expect(bestSent([P("7A", "sent"), P("7C", "high_point"), P("7B", "sent")])).toBe("7B");
    expect(bestSent([P("7C", "no_progress")])).toBeNull();
  });

  it("clamps attempts to 1..10", () => {
    expect(clampAttempts(0)).toBe(1);
    expect(clampAttempts(14)).toBe(10);
    expect(clampAttempts(Number.NaN)).toBe(1);
  });

  it("pre-fills a new row with the target but NO outcome (not a send by default)", () => {
    expect(newProblem("7b")).toEqual({ grade: "7B", attempts: 1, outcome: null });
    expect(newProblem("nope").grade).toBe("6C");
  });

  it("never sends an untouched row", () => {
    const rows = [newProblem("7B"), { ...newProblem("7B"), attempts: 6 }];
    expect(unratedCount(rows)).toBe(2);
    expect(ratedProblems(rows)).toEqual([]);
    // Untouched rows only: the old path (target as grade, unrated → holds).
    expect(limitFeedbackFields(rows, "7B")).toEqual({ used_grade: "7B" });
    const mixed = [{ ...newProblem("7B"), outcome: "no_progress" as const, crux_moves: 3 }, newProblem("7B")];
    expect(limitFeedbackFields(mixed, "7B")).toEqual({
      problems: [{ grade: "7B", attempts: 1, outcome: "no_progress", crux_moves: 3 }],
    });
  });

  it("drops crux moves on a send", () => {
    expect(ratedProblems([{ grade: "7B", attempts: 2, outcome: "sent", crux_moves: 2 }])).toEqual([
      { grade: "7B", attempts: 2, outcome: "sent" },
    ]);
  });

  it("reads the target of the surface the athlete picked", () => {
    const ex = {
      target_grade: "7A+",
      surface_selected: "board_kilter",
      surface_targets: { board_kilter: { target_grade: "7A+" }, spraywall: { target_grade: "7B", target_grade_low: "7A+" } },
    };
    expect(limitTargetFor(ex, null)).toEqual({ surface: "board_kilter", target: "7A+", targetLow: undefined });
    expect(limitTargetFor(ex, "spraywall")).toEqual({ surface: "spraywall", target: "7B", targetLow: "7A+" });
    expect(limitTargetFor(ex, "unknown").surface).toBe("board_kilter");
    expect(limitTargetFor({ target_grade: "7B" }, "spraywall")).toEqual({ surface: undefined, target: "7B", targetLow: undefined });
  });

  it("builds the payload: problems win, the target travels only without them", () => {
    expect(limitFeedbackFields([], "7B")).toEqual({ used_grade: "7B" });
    expect(limitFeedbackFields(undefined, undefined)).toEqual({});
    const rows = [P("7B", "high_point")];
    expect(limitFeedbackFields(rows, "7B")).toEqual({ problems: rows });
    const sent = [P("7A+", "sent"), P("7B", "sent")];
    expect(limitFeedbackFields(sent, "7B")).toEqual({ problems: sent, used_grade: "7B" });
    expect(limitFeedbackFields(Array.from({ length: 12 }, () => P("7A", "sent")), "7B").problems).toHaveLength(8);
  });

  it("describes the summary toast", () => {
    expect(describeLimitSummary(undefined)).toBeNull();
    expect(describeLimitSummary([])).toBeNull();
    expect(describeLimitSummary([{ step: 1, next_target_grade: "7B+" }])?.title).toBe("Limit target up: 7B+");
    const hold = describeLimitSummary([{ step: 0, next_target_grade: "7B", step_reason: "first_session_without_progress" }]);
    expect(hold?.title).toBe("Limit target holds at 7B");
    expect(hold?.description).toMatch(/two in a row/);
    const rp = describeLimitSummary([{ step: 1, next_target_grade: "7C+", rp_proposal: { grade: "7C+", current: "7C" } }]);
    expect(rp?.description).toMatch(/above your boulder redpoint \(7C\)/);
    const guard = describeLimitSummary([{ step: 0, next_target_grade: "7B", warning: "hard_attempts_guard", hard_attempts: 25 }]);
    expect(guard?.description).toMatch(/25 hard attempts/);
    // The guard only blocks a step up: a step down must not read "holds".
    const guardDown = describeLimitSummary([{ step: -1, next_target_grade: "7A+", warning: "hard_attempts_guard", hard_attempts: 22 }]);
    expect(guardDown?.title).toBe("Limit target down to 7A+");
    expect(guardDown?.description).not.toMatch(/holds/);
    expect(guardDown?.description).toMatch(/cannot go up/);
  });
});
