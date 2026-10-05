import { describe, it, expect } from "vitest";
import {
  alertsForSession,
  describeActionAlerts,
  describeKeptPreview,
  describeKeptSessions,
  alertMessagesFor,
  describeUnmetSecondary,
  guardWarningsOf,
  isUserOwned,
  keptUserSessions,
  pruneGuardWarnings,
  structureAlert,
  weekAlerts,
} from "@/lib/week-alerts";
import type { GuardWarning, SecondaryWarning, SessionSlot, WeekPlan } from "@/lib/types";

/**
 * A300 + A301 — guards are alerts. These helpers only read the three lists the
 * backend returns (`guard_warnings`, `secondary_warnings`, `unmet_secondary`)
 * and must never phrase anything as "blocked" / "downgraded" / "eased".
 */

function gw(over: Partial<GuardWarning>): GuardWarning {
  return {
    code: "finger_gap",
    severity: "warning",
    date: "2026-10-06",
    slot: "evening",
    session_id: "strength_long",
    name: "Strength long",
    user_owned: true,
    with: [{ date: "2026-10-05", slot: "evening", session_id: "finger_max" }],
    message: "Strength long on 2026-10-06 loads the fingers within 1 day(s) of finger_max on 2026-10-05.",
    ...over,
  };
}

function sw(over: Partial<SecondaryWarning>): SecondaryWarning {
  return {
    date: "2026-10-07",
    slot: "lunch",
    session_id: "treadmill_hiit_4x4",
    focus: "hiit",
    code: "hiit_near_max",
    with: ["2026-10-08 finger_max"],
    ...over,
  };
}

function session(over: Partial<SessionSlot>): SessionSlot {
  return { session_id: "strength_long", location: "gym", slot: "evening", status: "planned", ...over };
}

function plan(days: Array<{ date: string; sessions: SessionSlot[] }>, extra: Partial<WeekPlan> = {}): WeekPlan {
  return { weeks: [{ days: days.map((d) => ({ weekday: "x", ...d })) }], ...extra } as WeekPlan;
}

describe("alertsForSession", () => {
  const p = plan(
    [
      { date: "2026-10-06", sessions: [session({})] },
      { date: "2026-10-07", sessions: [session({ session_id: "treadmill_hiit_4x4", slot: "lunch" })] },
    ],
    { secondary_warnings: [sw({})] },
  );

  it("matches a guard alert on date + slot + session_id", () => {
    const out = alertsForSession([gw({})], p, "2026-10-06", session({}));
    expect(out).toHaveLength(1);
    expect(out[0].source).toBe("guard");
    expect(out[0].title).toBe("Finger gap under 48 h");
    expect(out[0].message).toContain("finger_max");
  });

  it("does not put an alert on another slot or another session", () => {
    expect(alertsForSession([gw({})], p, "2026-10-06", session({ slot: "lunch" }))).toHaveLength(0);
    expect(alertsForSession([gw({})], p, "2026-10-06", session({ session_id: "other" }))).toHaveLength(0);
    expect(alertsForSession([gw({})], p, "2026-10-07", session({}))).toHaveLength(0);
  });

  it("adds the lunch-rotation alerts from week_plan.secondary_warnings", () => {
    const out = alertsForSession([], p, "2026-10-07", session({ session_id: "treadmill_hiit_4x4", slot: "lunch" }));
    expect(out).toHaveLength(1);
    expect(out[0].source).toBe("structure");
    expect(out[0].message).toContain("2026-10-08 finger_max");
  });

  it("never flags a done or skipped session (history)", () => {
    expect(alertsForSession([gw({})], p, "2026-10-06", session({ status: "done" }))).toEqual([]);
    expect(alertsForSession([gw({})], p, "2026-10-06", session({ status: "skipped" }))).toEqual([]);
  });

  it("tolerates missing inputs", () => {
    expect(alertsForSession(null, null, "2026-10-06", session({}))).toEqual([]);
    expect(alertsForSession(undefined, undefined, "2026-10-06", session({}))).toEqual([]);
  });
});

describe("weekAlerts", () => {
  const p = plan([], { secondary_warnings: [sw({ date: "2026-10-06", slot: "lunch" })] });

  it("orders by date, then slot, guard before lunch rules on a tie", () => {
    const out = weekAlerts(
      [gw({ date: "2026-10-08", code: "hard_cap" }), gw({ date: "2026-10-06", slot: "lunch", code: "hiit_near_max" })],
      p,
    );
    expect(out.map((a) => [a.date, a.source])).toEqual([
      ["2026-10-06", "guard"],
      ["2026-10-06", "structure"],
      ["2026-10-08", "guard"],
    ]);
  });

  it("filters one day for /today", () => {
    const out = weekAlerts([gw({ date: "2026-10-08" })], p, "2026-10-06");
    expect(out).toHaveLength(1);
    expect(out[0].source).toBe("structure");
  });

  it("is deterministic (same input → same output)", () => {
    const input = [gw({ date: "2026-10-08" }), gw({ date: "2026-10-06" })];
    expect(weekAlerts(input, p)).toEqual(weekAlerts([...input], p));
  });
});

describe("pruneGuardWarnings", () => {
  it("drops alerts of sessions removed or completed, keeps the open ones", () => {
    const p = plan([
      { date: "2026-10-06", sessions: [session({})] },
      { date: "2026-10-07", sessions: [session({ status: "done" })] },
    ]);
    const kept = pruneGuardWarnings(
      [gw({}), gw({ date: "2026-10-07" }), gw({ date: "2026-10-09" })],
      p,
    );
    expect(kept.map((w) => w.date)).toEqual(["2026-10-06"]);
  });
});

describe("structure alert texts", () => {
  it.each([
    ["hiit_near_max", "max session"],
    ["biceps_before_heavy_pull", "24 h before heavy pulling"],
    ["legs_before_limit", "48 h before a limit"],
    ["pretrip_no_hard", "pre-trip"],
    ["hiit_weekly_cap", "second HIIT"],
  ])("%s", (code, text) => {
    expect(structureAlert(sw({ code })).message).toContain(text);
  });
});

describe("describeUnmetSecondary", () => {
  it("names each reason without calling it an error", () => {
    expect(describeUnmetSecondary({ date: null, slot: null, focus: "legs", reason: "rotation_overflow" })).toContain("Legs");
    expect(describeUnmetSecondary({ date: "2026-10-06", slot: "lunch", focus: null, reason: "no_focus" })).toContain("no focus family");
    expect(describeUnmetSecondary({ date: "2026-10-06", slot: "lunch", focus: null, reason: "rotation_exhausted" })).toContain("fewer families");
    expect(describeUnmetSecondary({ date: "2026-10-06", slot: "lunch", focus: "hiit", reason: "no_session_fits" })).toContain("HIIT");
  });
});

describe("describeActionAlerts (A301: the action went through)", () => {
  it("returns null when there is nothing to say", () => {
    expect(describeActionAlerts(undefined)).toBeNull();
    expect(describeActionAlerts([])).toBeNull();
  });

  it("says the action was applied and nothing else changed — never downgraded/eased/blocked", () => {
    const msg = describeActionAlerts(["A.", "B.", "A."])!;
    expect(msg.title).toBe("Added — 2 alerts");
    expect(msg.description).toContain("nothing else in the plan was changed");
    expect(msg.description).not.toMatch(/eased|downgrad|blocked|anyway|lighter/i);
  });

  it("names the action", () => {
    expect(describeActionAlerts(["A."], "Moved")!.title).toBe("Moved — 1 alert");
    expect(describeActionAlerts(["A."], "Changed")!.title).toBe("Changed — 1 alert");
  });
});

describe("guardWarningsOf", () => {
  it("reads the sibling only when it is an array", () => {
    expect(guardWarningsOf({ guard_warnings: [gw({})] })).toHaveLength(1);
    expect(guardWarningsOf({ week_plan: {} })).toBeUndefined();
    expect(guardWarningsOf(null)).toBeUndefined();
  });
});

describe("isUserOwned / keptUserSessions (mirror of backend user_owned.py)", () => {
  it("recognises every user marker", () => {
    for (const m of ["quick_add", "user_forced", "manual_override", "key_reschedule", "custom_add", "generated_add", "user_moved"]) {
      expect(isUserOwned(session({ constraints_applied: [m] }))).toBe(true);
    }
    expect(isUserOwned(session({ forced: true }))).toBe(true);
    expect(isUserOwned(session({ is_custom: true }))).toBe(true);
    expect(isUserOwned(session({ _user_edited: true }))).toBe(true);
    expect(isUserOwned(session({ constraints_applied: ["pass1"] }))).toBe(false);
    expect(isUserOwned(session({}))).toBe(false);
  });

  it("lists the user's sessions from today on, not the past nor the done ones", () => {
    const p = plan([
      { date: "2026-10-05", sessions: [session({ is_custom: true, name: "Past custom" })] },
      { date: "2026-10-06", sessions: [session({ is_custom: true, name: "My custom" }), session({ status: "done", forced: true })] },
      { date: "2026-10-07", sessions: [session({ session_id: "legs_strength", constraints_applied: ["quick_add"], slot: "lunch" }), session({})] },
    ]);
    const kept = keptUserSessions(p, "2026-10-06");
    expect(kept).toEqual([
      { date: "2026-10-06", slot: "evening", name: "My custom" },
      { date: "2026-10-07", slot: "lunch", name: "legs strength" },
    ]);
    expect(describeKeptSessions(kept)).toContain("Kept your 2 sessions");
    expect(describeKeptSessions([])).toContain("nothing to keep");
    expect(describeKeptPreview(kept.slice(0, 1))).toBe("Your session stays: My custom (2026-10-06 evening).");
    expect(describeKeptPreview(kept)).toMatch(/^Your 2 sessions stay:/);
    expect(describeKeptPreview([])).toContain("no sessions of your own");
  });
});

describe("alertMessagesFor", () => {
  it("returns the alerts flagged on the session or naming it in `with`", () => {
    const flagged = gw({ date: "2026-10-07", slot: "lunch", message: "flagged" });
    const named = gw({ date: "2026-10-08", message: "named", with: [{ date: "2026-10-07", slot: "lunch", session_id: "x" }] });
    const other = gw({ date: "2026-10-07", slot: "evening", message: "other slot", with: [] });
    expect(alertMessagesFor([flagged, named, other], "2026-10-07", "lunch")).toEqual(["flagged", "named"]);
    expect(alertMessagesFor(undefined, "2026-10-07", "lunch")).toEqual([]);
  });
});
