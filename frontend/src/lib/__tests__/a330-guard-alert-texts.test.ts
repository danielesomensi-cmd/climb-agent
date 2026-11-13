/**
 * A330 (D288-FE) — the A327 guard codes get their own title and message in
 * the app instead of the generic «Recovery alert» + backend text:
 * finger_hard_cap, max_hang_cap, crag_block (rest_day / no_hard / finger_72h)
 * and finger_low_gap (gap / per_day). The payloads below are the shapes
 * `backend/engine/guards_v1.py` emits. A field missing → the backend message.
 */
import { describe, it, expect } from "vitest";

import { alertMessagesFor, guardAlert, guardMessage, guardTitle, weekAlerts } from "@/lib/week-alerts";
import type { GuardWarning } from "@/lib/types";

function gw(over: Partial<GuardWarning> & Record<string, unknown>): GuardWarning {
  return {
    code: "finger_hard_cap",
    severity: "warning",
    date: "2026-11-12",
    slot: "evening",
    session_id: "limit_boulder_gym",
    name: "Limit Boulder Gym",
    user_owned: false,
    with: [],
    message: "BACKEND TEXT",
    ...over,
  } as GuardWarning;
}

const CRAG = { crag_days: ["2026-11-07", "2026-11-08"], finger_ok_from: "2026-11-11T18:00" };

describe("A330 — titles", () => {
  it("names each new code, never the generic fallback", () => {
    expect(guardTitle("finger_hard_cap")).toBe("Above the weekly finger-hard cap");
    expect(guardTitle("max_hang_cap")).toBe("Above the weekly max-hang cap");
    expect(guardTitle("finger_low_gap")).toBe("Light finger work too close");
    expect(guardTitle("crag_block")).toBe("After a crag block");
  });

  it("crag_block: one title per detail", () => {
    expect(guardTitle("crag_block", "rest_day")).toBe("Rest day after a crag block");
    expect(guardTitle("crag_block", "no_hard")).toBe("No hard session after a crag block");
    expect(guardTitle("crag_block", "finger_72h")).toBe("Fingers wait after a crag block");
    expect(guardTitle("crag_block", "something_new")).toBe("After a crag block");
  });

  it("an unknown code still reads «Recovery alert»; old titles unchanged", () => {
    expect(guardTitle("brand_new_code")).toBe("Recovery alert");
    expect(guardTitle("post_outdoor")).toBe("After an outdoor day");
    expect(guardTitle("hard_cap")).toBe("Above your weekly hard-day cap");
  });
});

describe("A330 — messages", () => {
  it("finger_hard_cap: count, cap, crag days included", () => {
    const a = guardAlert(gw({ code: "finger_hard_cap", count: 4, cap: 3 }));
    expect(a.title).toBe("Above the weekly finger-hard cap");
    expect(a.message).toBe(
      "This week has 4 finger-hard days, crag days included; the cap is 3. Limit Boulder Gym on Thu 12 Nov is past it.",
    );
  });

  it("max_hang_cap: count and cap", () => {
    const m = guardMessage(gw({ code: "max_hang_cap", count: 3, cap: 2, name: "Finger Strength Home", session_id: "finger_strength_home" }));
    expect(m).toBe("This week has 3 max-hang days; the cap is 2. Finger Strength Home on Thu 12 Nov is past it.");
  });

  it("crag_block rest_day: the day after the block is a true rest day", () => {
    const a = guardAlert(gw({ code: "crag_block", detail: "rest_day", date: "2026-11-09", ...CRAG }));
    expect(a.title).toBe("Rest day after a crag block");
    expect(a.message).toBe(
      "After 2 hard crag days in a row (Sat 7 Nov – Sun 8 Nov), Mon 9 Nov is meant as a true rest day: " +
        "Limit Boulder Gym is planned on it. A lunch extra or recovery / prehab is fine.",
    );
  });

  it("crag_block no_hard: no hard session two days after", () => {
    const m = guardMessage(gw({ code: "crag_block", detail: "no_hard", date: "2026-11-10", ...CRAG }));
    expect(m).toBe(
      "Tue 10 Nov is the second day after 2 hard crag days in a row (Sat 7 Nov – Sun 8 Nov): " +
        "no hard session that day, and Limit Boulder Gym is a hard one.",
    );
  });

  it("crag_block finger_72h: hard finger work only from the date and hour", () => {
    const m = guardMessage(
      gw({ code: "crag_block", detail: "finger_72h", date: "2026-11-11", slot: "lunch", name: "Max Hangs", ...CRAG }),
    );
    expect(m).toBe(
      "After 2 hard crag days in a row (Sat 7 Nov – Sun 8 Nov), hard finger work only from Wed 11 Nov, 18:00 " +
        "(72 h after the crag): Max Hangs on Wed 11 Nov (lunch) comes earlier.",
    );
  });

  it("finger_low_gap gap: names the nearer finger session and the hours", () => {
    const m = guardMessage(
      gw({
        code: "finger_low_gap",
        detail: "gap",
        gap_h: 6,
        low_count: 1,
        date: "2026-11-12",
        slot: "lunch",
        name: "Finger Aerobic Base",
        session_id: "finger_aerobic_base",
        with: [{ date: "2026-11-12", slot: "morning", session_id: "finger_maintenance_gym" }],
      }),
    );
    expect(m).toBe(
      "Finger Aerobic Base on Thu 12 Nov is less than 6 h from Finger maintenance gym (same day, morning): " +
        "a light finger session needs 6 h from any other finger session.",
    );
  });

  it("finger_low_gap gap after a crag day, with a slower recovery (7.5 h)", () => {
    const m = guardMessage(
      gw({
        code: "finger_low_gap",
        detail: "gap",
        gap_h: 7.5,
        date: "2026-11-08",
        slot: "evening",
        name: "Finger Aerobic Base",
        with: [{ date: "2026-11-08", slot: null, session_id: null }],
      }),
    );
    expect(m).toBe(
      "Finger Aerobic Base on Sun 8 Nov is less than 7.5 h from your crag day on Sun 8 Nov: " +
        "a light finger session needs 7.5 h from any other finger session.",
    );
  });

  it("finger_low_gap per_day: more than 2 light sessions in a day", () => {
    const m = guardMessage(
      gw({ code: "finger_low_gap", detail: "per_day", gap_h: 6, low_count: 3, name: "Hang Ramp-up", date: "2026-11-12" }),
    );
    expect(m).toBe("Thu 12 Nov has 3 light finger sessions, at most 2 a day: Hang Ramp-up is one too many.");
  });

  it("no display name → the session id made readable", () => {
    const m = guardMessage(gw({ code: "max_hang_cap", count: 3, cap: 2, name: null, session_id: "finger_max_home" }));
    expect(m).toContain("Finger max home on Thu 12 Nov is past it.");
  });

  it("a field missing (older server) → the backend's message", () => {
    expect(guardMessage(gw({ code: "finger_hard_cap" }))).toBe("BACKEND TEXT");
    expect(guardMessage(gw({ code: "crag_block", detail: "rest_day" }))).toBe("BACKEND TEXT");
    expect(guardMessage(gw({ code: "crag_block", detail: "finger_72h", crag_days: CRAG.crag_days }))).toBe("BACKEND TEXT");
    expect(guardMessage(gw({ code: "finger_low_gap", detail: "gap", gap_h: 6, with: [] }))).toBe("BACKEND TEXT");
  });

  it("the other codes keep the backend's message", () => {
    expect(guardMessage(gw({ code: "finger_gap" }))).toBe("BACKEND TEXT");
    expect(guardMessage(gw({ code: "hard_cap", count: 5, cap: 4 }))).toBe("BACKEND TEXT");
  });

  it("the week list and the post-action toast carry the app's text", () => {
    const w = gw({ code: "max_hang_cap", count: 3, cap: 2 });
    const [a] = weekAlerts([w], null);
    expect(a.title).toBe("Above the weekly max-hang cap");
    expect(a.message).toContain("This week has 3 max-hang days");
    expect(alertMessagesFor([w], "2026-11-12", "evening")).toEqual([a.message]);
  });
});
