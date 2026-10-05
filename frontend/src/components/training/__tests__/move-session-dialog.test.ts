import { describe, it, expect } from "vitest";
import { freeMoveSlots } from "@/components/training/move-session-dialog";
import type { SessionSlot, WeekPlan } from "@/lib/types";

/**
 * A301-FE — a done or skipped session still occupies its slot: the backend
 * refuses a move onto it (422), so the dialog must not offer it.
 */
function s(over: Partial<SessionSlot>): SessionSlot {
  return { session_id: "strength_long", location: "gym", slot: "evening", status: "planned", ...over };
}

function plan(days: Array<{ date: string; sessions: SessionSlot[] }>): WeekPlan {
  return { weeks: [{ days: days.map((d) => ({ weekday: "monday", ...d })) }] } as WeekPlan;
}

describe("freeMoveSlots", () => {
  it("does not offer a slot that holds a done or skipped session", () => {
    const p = plan([
      {
        date: "2026-10-05",
        sessions: [s({ slot: "evening", status: "done" }), s({ slot: "lunch", status: "skipped", session_id: "z2" })],
      },
      { date: "2026-10-06", sessions: [s({ slot: "evening" })] },
    ]);
    const out = freeMoveSlots(p, "2026-10-06", "evening").map((x) => `${x.date} ${x.slot}`);
    expect(out).toEqual(["2026-10-05 morning", "2026-10-06 morning", "2026-10-06 lunch"]);
  });

  it("tolerates a day without sessions and an empty plan", () => {
    expect(freeMoveSlots(plan([{ date: "2026-10-07", sessions: undefined as never }]), "x", "y")).toHaveLength(3);
    expect(freeMoveSlots({ weeks: [] } as unknown as WeekPlan, "x", "y")).toEqual([]);
  });
});
