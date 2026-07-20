import { describe, it, expect } from "vitest";

import {
  addCustomSessionEvent,
  completeOtherActivityEvent,
  editOtherActivityEvent,
  markSessionEvent,
  moveSessionEvent,
  removeOtherActivityEvent,
  removeOutdoorEvent,
  replanOverrideEvent,
  undoOtherActivityEvent,
  undoOutdoorEvent,
} from "@/lib/week-events";

/**
 * A245 G-5 (F19) — the behaviour snapshot the phase acceptance requires BEFORE
 * the today↔week handlers are merged into one.
 *
 * Every assertion below is the exact payload the two pages were sending before
 * the extraction. If the merge changed what reaches `/api/replanner/*`, these
 * fail — which is the whole point: a dedup that silently alters a request is
 * worse than the duplication it removes.
 */
describe("replanner event payloads", () => {
  it("mark_done / mark_skipped / mark_planned", () => {
    expect(markSessionEvent("done", "2026-07-20", "strength_long")).toEqual({
      event_type: "mark_done",
      date: "2026-07-20",
      session_ref: "strength_long",
    });
    expect(markSessionEvent("skipped", "2026-07-20", "s")).toEqual({
      event_type: "mark_skipped",
      date: "2026-07-20",
      session_ref: "s",
    });
    expect(markSessionEvent("planned", "2026-07-20", "s")).toEqual({
      event_type: "mark_planned",
      date: "2026-07-20",
      session_ref: "s",
    });
  });

  it("move_session carries both endpoints", () => {
    expect(
      moveSessionEvent({
        from_date: "2026-07-20",
        from_slot: "evening",
        to_date: "2026-07-22",
        to_slot: "morning",
      }),
    ).toEqual({
      event_type: "move_session",
      from_date: "2026-07-20",
      from_slot: "evening",
      to_date: "2026-07-22",
      to_slot: "morning",
    });
  });

  it("add_custom_session omits gym_id when there is none", () => {
    const base = {
      custom_session_id: "cs_1",
      target_date: "2026-07-20",
      slot: "evening",
      location: "home",
    };
    expect(addCustomSessionEvent(base)).toEqual({ event_type: "add_custom_session", ...base });
    expect(addCustomSessionEvent({ ...base, gym_id: "g1" })).toMatchObject({ gym_id: "g1" });
  });

  describe("other activity", () => {
    it("complete: slot and duration are optional and OMITTED, not undefined", () => {
      expect(completeOtherActivityEvent("2026-07-20", undefined, "ok")).toEqual({
        event_type: "complete_other_activity",
        date: "2026-07-20",
        feedback: "ok",
      });
      // The backend distinguishes an absent key from a null one.
      expect(
        Object.keys(completeOtherActivityEvent("2026-07-20", undefined, "ok")),
      ).not.toContain("slot");
    });

    it("complete: includes slot and duration when given", () => {
      expect(completeOtherActivityEvent("2026-07-20", "evening", "hard", 75)).toEqual({
        event_type: "complete_other_activity",
        date: "2026-07-20",
        feedback: "hard",
        slot: "evening",
        duration_minutes: 75,
      });
    });

    it("complete: a zero duration is sent, not dropped", () => {
      // `if (durationMinutes)` would have swallowed 0; the guard is `!= null`.
      expect(completeOtherActivityEvent("2026-07-20", undefined, "ok", 0)).toMatchObject({
        duration_minutes: 0,
      });
    });

    it("undo / remove: identical shape, different event_type", () => {
      expect(undoOtherActivityEvent("2026-07-20")).toEqual({
        event_type: "undo_other_activity",
        date: "2026-07-20",
      });
      expect(removeOtherActivityEvent("2026-07-20", "lunch")).toEqual({
        event_type: "remove_other_activity",
        date: "2026-07-20",
        slot: "lunch",
      });
    });

    it("edit: passes only the fields provided", () => {
      expect(editOtherActivityEvent("2026-07-20", "evening", { feedback: "easy" })).toEqual({
        event_type: "edit_other_activity",
        date: "2026-07-20",
        slot: "evening",
        feedback: "easy",
      });
    });
  });

  it("outdoor undo / remove", () => {
    expect(undoOutdoorEvent("2026-07-20")).toEqual({
      event_type: "undo_outdoor",
      date: "2026-07-20",
    });
    expect(removeOutdoorEvent("2026-07-20")).toEqual({
      event_type: "remove_outdoor",
      date: "2026-07-20",
    });
  });

  it("replan override omits optional keys", () => {
    expect(
      replanOverrideEvent({ date: "2026-07-20", intent: "rest", location: "home" }),
    ).toEqual({ date: "2026-07-20", intent: "rest", location: "home" });

    expect(
      replanOverrideEvent({
        date: "2026-07-20",
        intent: "swap",
        location: "gym",
        gym_id: "g1",
        session_index: 1,
      }),
    ).toEqual({
      date: "2026-07-20",
      intent: "swap",
      location: "gym",
      gym_id: "g1",
      session_index: 1,
    });
  });

  it("replan override keeps session_index 0 — a falsy but meaningful value", () => {
    expect(
      replanOverrideEvent({
        date: "2026-07-20",
        intent: "swap",
        location: "gym",
        session_index: 0,
      }),
    ).toMatchObject({ session_index: 0 });
  });
});
