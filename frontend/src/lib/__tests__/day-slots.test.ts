// B309 — the coach CTA hardcoded slot="evening"; on a day whose evening was
// already planned the insert 422'd and the custom session stayed orphaned.

import { describe, expect, it } from "vitest";
import { findDay, firstFreeSlot, occupiedSlots } from "../day-slots";
import type { DayPlan, WeekPlan } from "@/lib/types";

function day(partial: Partial<DayPlan>): DayPlan {
  return { date: "2026-07-29", weekday: "wed", sessions: [], ...partial } as DayPlan;
}

describe("firstFreeSlot", () => {
  it("prefers evening on an empty day (pre-B309 behaviour)", () => {
    expect(firstFreeSlot(day({}))).toBe("evening");
  });

  it("falls back to morning when evening is planned", () => {
    const d = day({ sessions: [{ slot: "evening", session_id: "route_endurance_gym" }] as DayPlan["sessions"] });
    expect(firstFreeSlot(d)).toBe("morning");
  });

  it("falls back to lunch when evening and morning are taken", () => {
    const d = day({
      sessions: [
        { slot: "evening", session_id: "a" },
        { slot: "morning", session_id: "b" },
      ] as DayPlan["sessions"],
    });
    expect(firstFreeSlot(d)).toBe("lunch");
  });

  it("returns null when the day is full", () => {
    const d = day({
      sessions: [
        { slot: "evening", session_id: "a" },
        { slot: "morning", session_id: "b" },
        { slot: "lunch", session_id: "c" },
      ] as DayPlan["sessions"],
    });
    expect(firstFreeSlot(d)).toBeNull();
  });

  it("counts other activities as occupying their slot (B276 list form)", () => {
    const d = day({ other_activities: [{ slot: "evening", name: "Chest" }] });
    expect(firstFreeSlot(d)).toBe("morning");
  });

  it("counts legacy scalar other activities (pre-B276 preserved days)", () => {
    const d = day({ other_activity: true, other_activity_slot: "evening", other_activity_name: "HIIT" });
    expect(occupiedSlots(d).has("evening")).toBe(true);
    expect(firstFreeSlot(d)).toBe("morning");
  });

  it("ignores slot-less sessions and activities", () => {
    const d = day({
      sessions: [{ session_id: "a" }] as DayPlan["sessions"],
      other_activities: [{ name: "walk" }],
    });
    expect(occupiedSlots(d).size).toBe(0);
    expect(firstFreeSlot(d)).toBe("evening");
  });
});

describe("findDay", () => {
  const week: WeekPlan = {
    weeks: [{ days: [day({ date: "2026-07-28" }), day({ date: "2026-07-29" })] }],
  };

  it("finds the day by date", () => {
    expect(findDay(week, "2026-07-29")?.date).toBe("2026-07-29");
  });

  it("returns null for a date outside the plan", () => {
    expect(findDay(week, "2026-08-05")).toBeNull();
  });
});
