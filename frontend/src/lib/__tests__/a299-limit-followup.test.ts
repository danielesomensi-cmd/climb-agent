/**
 * A299 — residues of A296 (R6c).
 *
 * (1) the weekly "Hardest sends" row formatter;
 * (2) the post-session dialog logs the grade and the limit problems through the
 *     SAME builder the guided player uses (`limitFeedbackFields`);
 * (3) limit targets are read-time only: custom/adhoc rows carry the target of
 *     the day they are read for, the guided player uses it (and the wall the
 *     athlete picks), and a coach preview shows it only for its own today.
 */
import { describe, expect, it } from "vitest";
import {
  buildDialogFeedbackItems,
  buildGuidedFeedbackItems,
  extractFeedbackExercises,
  hasGradeInput,
  hasProblemLog,
  prefilledGrade,
  type FeedbackDialogExercise,
} from "@/lib/feedback-items";
import { buildGuidedStateFromExercises, limitSuggestedFields } from "@/lib/guided-session-utils";
import { describeLimitSend } from "@/lib/limit-problems";
import { previewLimitTarget } from "@/lib/adhoc-preview";
import { boulderGradeSystemOf } from "@/lib/gradeUtils";
import type { GuidedExercise, LimitProblemDraft } from "@/lib/types";

const limitSession = {
  resolved: {
    resolved_session: {
      exercise_instances: [
        {
          exercise_id: "limit_bouldering",
          name: "Limit bouldering",
          load_model: "grade_relative",
          suggested: {
            suggested_boulder_target: {
              target_grade: "7B",
              target_grade_low: "7A+",
              surface_selected: "board_kilter",
              log_problems: true,
            },
          },
        },
        {
          exercise_id: "arc_training",
          name: "ARC",
          load_model: "grade_relative",
          suggested: { suggested_grade: "6A", grade_scale: "french" },
        },
        {
          exercise_id: "max_hang_7s",
          load_model: "total_load",
          suggested: { suggested_external_load_kg: 30, suggested_total_load_kg: 106 },
        },
      ],
    },
  },
};

describe("A299 — dialog: grade field and limit problem logger", () => {
  const [limit, arc, hang] = extractFeedbackExercises(limitSession);

  it("extracts the target the guided player would show", () => {
    expect(limit).toMatchObject({
      grade: "7B",
      gradeLow: "7A+",
      surface: "board_kilter",
      logProblems: true,
    });
    expect(arc).toMatchObject({ grade: "6A", gradeScale: "french", logProblems: false });
    expect(hang.grade).toBeUndefined();
    expect(hasProblemLog(limit)).toBe(true);
    expect(hasGradeInput(arc) && !hasProblemLog(arc)).toBe(true);
    expect(hasGradeInput(hang)).toBe(false);
    // Pre-fill on the target's own scale (B344), as the guided player does.
    expect(prefilledGrade(arc)).toBe("6a");
  });

  it("a test exercise never gets a grade field", () => {
    const test: FeedbackDialogExercise = { exercise_id: "t", name: "T", grade: "7A", testField: "max_load_kg" };
    expect(hasGradeInput(test)).toBe(false);
  });

  it("sends the rated problems, the hardest send and the surface", () => {
    const rows: LimitProblemDraft[] = [
      { grade: "7B", attempts: 3, outcome: "sent" },
      { grade: "7B+", attempts: 4, outcome: "high_point", crux_moves: 2 },
      { grade: "7C", attempts: 1, outcome: null }, // never rated → never sent
    ];
    const [item] = buildDialogFeedbackItems([limit], {}, {}, {}, {}, { limit_bouldering: rows });
    expect(item).toEqual({
      exercise_id: "limit_bouldering",
      completed: true,
      surface_selected: "board_kilter",
      used_grade: "7B",
      problems: [
        { grade: "7B", attempts: 3, outcome: "sent" },
        { grade: "7B+", attempts: 4, outcome: "high_point", crux_moves: 2 },
      ],
    });
  });

  it("matches the guided player's payload for the same input", () => {
    const rows: LimitProblemDraft[] = [{ grade: "7B", attempts: 2, outcome: "sent" }];
    const [fromDialog] = buildDialogFeedbackItems([limit], { limit_bouldering: "hard" }, {}, {}, {}, { limit_bouldering: rows });
    const guided = {
      exerciseId: "limit_bouldering",
      name: "Limit bouldering",
      category: "",
      blockUid: "",
      loadModel: "grade_relative",
      prescription: {},
      suggested: { grade: "7B", surface: "board_kilter", logProblems: true },
      status: "done",
      feedbackLabel: "hard",
      usedGrade: "7B",
      problems: [{ grade: "7B", attempts: 2, outcome: "sent" }],
    } as GuidedExercise;
    const [fromPlayer] = buildGuidedFeedbackItems([guided]);
    expect(fromDialog).toEqual(fromPlayer);
  });

  it("without problems, the untouched target travels (the server holds it)", () => {
    const [item] = buildDialogFeedbackItems([limit], {}, {}, {});
    expect(item).toMatchObject({ used_grade: "7B", surface_selected: "board_kilter" });
    expect(item.problems).toBeUndefined();
    expect(item.feedback_label).toBeUndefined();
  });

  it("other grade exercises send what the user typed, else the pre-fill", () => {
    const [untouched] = buildDialogFeedbackItems([arc], {}, {}, {});
    expect(untouched.used_grade).toBe("6a");
    const [typed] = buildDialogFeedbackItems([arc], {}, {}, {}, { arc_training: " 6b " });
    expect(typed.used_grade).toBe("6b");
    const [cleared] = buildDialogFeedbackItems([arc], {}, {}, {}, { arc_training: "" });
    expect(cleared.used_grade).toBeUndefined();
  });

  it("a non-grade exercise is unchanged (no grade, no surface)", () => {
    const [item] = buildDialogFeedbackItems([hang], {}, { max_hang_7s: 30 }, {});
    expect(item).toEqual({
      exercise_id: "max_hang_7s",
      completed: true,
      used_external_load_kg: 30,
      used_total_load_kg: 106,
    });
  });
});

describe("A299 — read-time limit targets in the guided player", () => {
  const customRow = {
    exercise_id: "limit_bouldering",
    sets: 1,
    target_grade: "7B",
    target_grade_low: "7A+",
    surface_selected: "board_kilter",
    surface_options: ["board_kilter", "gym_boulder"],
    surface_targets: {
      board_kilter: { target_grade: "7B", target_grade_low: "7A+" },
      gym_boulder: { target_grade: "7C", target_grade_low: "7B+" },
    },
    log_problems: true,
  };

  it("maps the read-time target of a custom/adhoc row onto the player", () => {
    const state = buildGuidedStateFromExercises("custom_cs", "Limit", "2026-10-07", [customRow])!;
    expect(state.exercises[0].suggested).toMatchObject({
      grade: "7B",
      gradeLow: "7A+",
      gradeScale: "font",
      logProblems: true,
      surface: "board_kilter",
      surfaceOptions: ["board_kilter", "gym_boulder"],
    });
  });

  it("a row read without a target (or a stored row) gets nothing", () => {
    expect(limitSuggestedFields({ exercise_id: "limit_bouldering", sets: 1 })).toEqual({});
    expect(limitSuggestedFields({ exercise_id: "x", target_grade: "7B" })).toEqual({});
  });

  it("the wall the athlete picked is what the feedback says", () => {
    const state = buildGuidedStateFromExercises("custom_cs", "Limit", "2026-10-07", [customRow])!;
    const ex: GuidedExercise = {
      ...state.exercises[0],
      status: "done",
      chosenSurface: "gym_boulder",
      usedGrade: "7C",
      problems: [{ grade: "7C", attempts: 2, outcome: "sent" }],
    };
    const [item] = buildGuidedFeedbackItems([ex]);
    expect(item.surface_selected).toBe("gym_boulder");
    const [unchosen] = buildGuidedFeedbackItems([{ ...ex, chosenSurface: undefined }]);
    expect(unchosen.surface_selected).toBe("board_kilter");
  });
});

describe("A299 — coach preview target only for its own today", () => {
  const row = { target_grade: "7B", target_grade_low: "7A+", surface_selected: "board_kilter" };

  it("shows the target on the day it was computed for", () => {
    expect(previewLimitTarget(row, "2026-10-07", "2026-10-07")).toBe("limit 7A+–7B · Kilter");
    expect(previewLimitTarget(row, "2026-10-07", "2026-10-07", "v_scale")).toBe("limit V7–V8 · Kilter");
  });

  it("hides it on an older card or without a date", () => {
    expect(previewLimitTarget(row, "2026-10-06", "2026-10-07")).toBeNull();
    expect(previewLimitTarget(row, undefined, "2026-10-07")).toBeNull();
    expect(previewLimitTarget({}, "2026-10-07", "2026-10-07")).toBeNull();
  });
});

describe("A299 — weekly report: hardest sends per surface", () => {
  it("formats a row on the athlete's scale", () => {
    const row = { surface: "board_kilter", max_grade_sent: "7A+", sends: 3, sources: ["custom", "planned"], target_grade: "7B" };
    expect(describeLimitSend(row)).toEqual({ surface: "Kilter", grade: "7A+", detail: "3 sends · limit target 7B" });
    expect(describeLimitSend(row, "v_scale").grade).toBe("V7");
  });

  it("says when the sends came only from free climbing", () => {
    const row = { surface: "gym_boulder", max_grade_sent: "7A", sends: 1, sources: ["free"], target_grade: null };
    expect(describeLimitSend(row).detail).toBe("1 send · free climbing");
  });

  it("reads the display preference from the state, Font by default", () => {
    expect(boulderGradeSystemOf({ preferences: { grade_system_boulder: "v_scale" } })).toBe("v_scale");
    expect(boulderGradeSystemOf({ preferences: {} })).toBe("font");
    expect(boulderGradeSystemOf(undefined)).toBe("font");
  });
});
