/**
 * A298 — bodyweight ladders on the client: badge text, proposal, the stepper
 * measures sent under the right field, the custom session id of a guided row.
 */
import { describe, it, expect, vi } from "vitest";

vi.mock("sonner", () => ({ toast: vi.fn() }));

import { toast } from "sonner";
import { asLadder, ladderSubtitle, ladderTitle, notifyBwLadderUpdates, proposalText } from "@/lib/bw-ladder";
import { asMeasure, measureFields, stepperBounds } from "@/lib/measured-feedback";
import { buildGuidedStateFromExercises } from "@/lib/guided-session-utils";
import type { LadderInfo } from "@/lib/types";

const ladder: LadderInfo = {
  family: "compression_floor",
  level_idx: 3,
  n_levels: 6,
  level_name: "Straddle L-sit",
  band: "10–30 s",
  dose: "3x20 s",
  next_exercise_id: "v_sit_45",
  next_name: "V-sit 45°",
  frozen: false,
  manual_only_next: false,
  gate: "compression_pulses",
  proposal: null,
};

describe("ladder badge text", () => {
  it("is 1-based for humans and lists band, next level and gate", () => {
    expect(ladderTitle(ladder)).toBe("Level 4/6 · Straddle L-sit");
    expect(ladderSubtitle(ladder)).toBe("band 10–30 s · next: V-sit 45° · needs compression pulses");
    expect(ladderSubtitle({ ...ladder, frozen: true, manual_only_next: true, gate: null })).toBe(
      "band 10–30 s · doses frozen this phase · next: V-sit 45° (manual only)",
    );
  });

  it("phrases a promotion and a switch differently, nothing without a proposal", () => {
    expect(proposalText(ladder)).toBeNull();
    const to = { to_level_idx: 4, to_exercise_id: "v_sit_45", to_name: "V-sit 45°" };
    expect(proposalText({ ...ladder, proposal: { kind: "promotion", ...to } })).toBe("Ready for V-sit 45°: switch?");
    expect(proposalText({ ...ladder, proposal: { kind: "switch", ...to } })).toBe("Your level is V-sit 45°: switch?");
  });

  it("asLadder rejects malformed payloads", () => {
    expect(asLadder(undefined)).toBeUndefined();
    expect(asLadder({ family: "x" })).toBeUndefined();
    expect(asLadder(ladder)).toEqual(ladder);
  });

  it("toasts the feedback lines once, nothing when empty", () => {
    notifyBwLadderUpdates([]);
    notifyBwLadderUpdates(undefined);
    expect(toast).not.toHaveBeenCalled();
    notifyBwLadderUpdates([{ family: "compression_floor", message: "Next time: 3x25 s" }, { message: "" }]);
    expect(toast).toHaveBeenCalledTimes(1);
    expect(vi.mocked(toast).mock.calls[0][1]).toMatchObject({ description: "Next time: 3x25 s" });
  });
});

describe("A298 stepper measures", () => {
  it("are known measures", () => {
    for (const m of ["bw_reps", "bw_hold", "feet_readjust", "fear_max"]) expect(asMeasure(m)).toBe(m);
  });

  it("send the stepper value under the server field of each measure", () => {
    expect(measureFields("bw_reps", { lastSetReps: 6 })).toEqual({ last_set_reps: 6 });
    expect(measureFields("bw_hold", { lastSetReps: 18 })).toEqual({ held_s: 18 });
    expect(measureFields("feet_readjust", { lastSetReps: 1 })).toEqual({ sample_readjust: 1 });
    expect(measureFields("fear_max", { lastSetReps: 0 })).toEqual({ fear_max: 0 });
    expect(measureFields("bw_hold", {})).toEqual({});
  });

  it("bound the stepper per measure", () => {
    expect(stepperBounds("fear_max").max).toBe(10);
    expect(stepperBounds("bw_hold").max).toBe(120);
    expect(stepperBounds("bw_reps", 8).max).toBe(14);
  });
});

describe("guided rows of a custom session", () => {
  it("carry the ladder and the custom session id the tap rewrites", () => {
    const st = buildGuidedStateFromExercises("custom_cs_ab12", "Core", "2026-10-06", [
      { exercise_id: "straddle_l_sit", sets: 3, work_seconds: 20, ladder, measure: "bw_hold" },
    ]);
    const ex = st!.exercises[0];
    expect(ex.suggested.ladder).toEqual(ladder);
    expect(ex.suggested.customSessionId).toBe("cs_ab12");
    expect(ex.suggested.measure).toBe("bw_hold");
    const adhoc = buildGuidedStateFromExercises("adhoc_1", "x", "2026-10-06", [{ exercise_id: "pushup", sets: 3 }]);
    expect(adhoc!.exercises[0].suggested.customSessionId).toBeUndefined();
  });
});
