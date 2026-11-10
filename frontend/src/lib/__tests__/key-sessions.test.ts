/**
 * A294 — pure helpers over `key_status`.
 */
import { describe, it, expect } from "vitest";
import {
  blockingConflicts,
  hasKeyIssues,
  keyDays,
  keyRoleFor,
  localToday,
  replacedBy,
  requirementLine,
  shortDay,
  techniqueProgressLine,
  whenLabel,
} from "@/lib/key-sessions";
import { elapsedDuration, MAX_SESSION_DURATION_S, plausibleDuration } from "@/lib/session-duration";
import type { KeyProposal, KeyRequirement, KeyStatus } from "@/lib/types";

function req(over: Partial<KeyRequirement>): KeyRequirement {
  return {
    key: "finger_max", label: "Finger max", target: 1, status: "missing", resolution: null,
    severity: "warning", debt: 1, done: [], partial: [], planned: [], skipped: [], ...over,
  };
}

function status(over: Partial<KeyStatus> = {}): KeyStatus {
  return {
    version: "a294.1", source: "a294", as_of: "2026-10-06", week_start: "2026-10-05", week_end: "2026-10-11",
    phase_id: "strength_power", is_current_week: true, is_past_week: false,
    requirements: [req({})],
    sessions: [
      { date: "2026-10-05", slot: "evening", session_id: "limit_boulder_gym", status: "planned", role: "key",
        keys: ["limit_power", "try_hard"], supporting: [] },
      { date: "2026-10-07", slot: "evening", session_id: "power_contact_gym", status: "planned", role: "optional",
        keys: [], supporting: ["limit_power"] },
      { date: "2026-10-09", slot: "evening", session_id: "strength_long", status: "skipped", role: "skipped",
        keys: ["finger_max"], supporting: [] },
    ],
    proposals: [], conflicts: [],
    summary: { required: 5, covered: 4, done: 0, missing: ["finger_max"], debt: 1, max_severity: "warning" },
    ...over,
  };
}

describe("key-sessions helpers", () => {
  it("finds the role by date + slot", () => {
    expect(keyRoleFor(status(), "2026-10-05", "evening")?.role).toBe("key");
    expect(keyRoleFor(status(), "2026-10-05", "lunch")).toBeNull();
    expect(keyRoleFor(null, "2026-10-05", "evening")).toBeNull();
  });

  it("marks key days and lost days", () => {
    expect(keyDays(status())).toEqual({ "2026-10-05": "key", "2026-10-09": "lost" });
  });

  // B374 — Monday 12/10/2026: Max pulling skipped, but strength_long on Sunday
  // still carries it (debt 0). The star moves: no lost marker, no badge.
  it("does not mark a skipped key as lost when its stimulus is still covered", () => {
    const covered = status({
      requirements: [req({ status: "planned", debt: 0,
        planned: [{ date: "2026-10-11", slot: "evening", session_id: "strength_long" }] })],
      sessions: [
        { date: "2026-10-09", slot: "evening", session_id: "strength_long", status: "skipped", role: "skipped",
          keys: ["finger_max"], supporting: [] },
        { date: "2026-10-11", slot: "evening", session_id: "strength_long", status: "planned", role: "key",
          keys: ["finger_max"], supporting: [] },
      ],
    });
    expect(keyDays(covered)).toEqual({ "2026-10-11": "key" });
    expect(keyRoleFor(covered, "2026-10-09", "evening")).toBeNull();
    expect(keyRoleFor(covered, "2026-10-11", "evening")?.role).toBe("key");
  });

  it("keeps the lost marker and the badge role when the stimulus is still owed", () => {
    expect(keyRoleFor(status(), "2026-10-09", "evening")?.role).toBe("skipped");
  });

  it("describes every resolution in plain words", () => {
    expect(requirementLine(req({ status: "done" }))).toBe("Done");
    expect(requirementLine(req({ status: "planned", planned: [{ date: "2026-10-09", slot: "evening", session_id: "strength_long" }] })))
      .toBe("Next: Fri 9 Oct");
    expect(requirementLine(req({ resolution: "proposal" }))).toContain("catch-up proposed");
    expect(requirementLine(req({ resolution: "deferred_next", next_key: { date: "2026-10-09", slot: "evening", session_id: "strength_long" } })))
      .toContain("next key session Fri 9 Oct");
    expect(requirementLine(req({ resolution: "deferred_fatigue" }))).toContain("very hard");
    expect(requirementLine(req({ status: "partial", resolution: "let_go" }))).toMatch(/^Only a partial dose/);
    expect(requirementLine(req({ status: "not_due", due_by: "2026-10-29" }))).toContain("Thu 29 Oct");
  });

  it("knows when the card has something to say", () => {
    expect(hasKeyIssues(status())).toBe(true);
    expect(hasKeyIssues(status({ summary: { required: 5, covered: 5, done: 1, missing: [], debt: 0, max_severity: "none" } })))
      .toBe(false);
  });

  it("only key-related conflicts gate an insertion", () => {
    const out = blockingConflicts([
      { code: "finger_gap", severity: "medium", message: "x" },
      { code: "key_removed", severity: "high", message: "y" },
      { code: "key_replaced", severity: "medium", message: "z", replace_key: true },
    ]);
    expect(out.map((c) => c.code)).toEqual(["key_removed", "key_replaced"]);
  });

  it("recovery-guard codes never interrupt an insertion (A301-FE: alerts only)", () => {
    const out = blockingConflicts([
      { code: "finger_gap", severity: "high", message: "x" },
      { code: "pre_test_fatigue", severity: "high", message: "y" },
      { code: "test_downgraded", severity: "high", message: "z" },
    ]);
    expect(out).toEqual([]);
  });

  it("formats dates without timezone drift", () => {
    expect(shortDay("2026-10-05")).toBe("Mon 5 Oct");
    expect(localToday(new Date(2026, 9, 4, 23, 30))).toBe("2026-10-04");
  });

  // A325 — the 2026-11-09 case: a custom session listed two drills, one was done.
  const partialTech = (over: Partial<KeyRequirement> = {}) => req({
    key: "technique", label: "Technique", status: "partial", resolution: "topup",
    partial: [{ date: "2026-11-09", slot: "evening", session_id: "custom_cs_x", dose: "partial",
      dose_reason: "technique_drills" }],
    progress: { done: 1, needed: 2,
      drills_done: [{ exercise_id: "no_readjust_drill", name: "No Readjust Drill" }],
      drills_missed: [{ exercise_id: "tech_hard_target", name: "Hard Target" }] },
    hint: "1 of 2 drills done — add Hard Target to Boulder circuit gym on 2026-11-10",
    ...over,
  });

  it("A325: a technique dose one drill short says which drill is owed", () => {
    expect(techniqueProgressLine(partialTech())).toBe("1 of 2 drills done on Mon, Hard Target still to do");
    expect(requirementLine(partialTech()))
      .toBe("1 of 2 drills done on Mon, Hard Target still to do — one-tap add below");
    expect(requirementLine(partialTech({ resolution: "proposal" })))
      .toBe("1 of 2 drills done on Mon, Hard Target still to do — catch-up proposed below");
    const none = partialTech();
    none.progress!.drills_missed = [];
    expect(techniqueProgressLine(none)).toBe("1 of 2 drills done on Mon, 1 more to do");
    expect(techniqueProgressLine(req({}))).toBeNull();
  });

  it("A325: the drill added by hand shows on the planned row", () => {
    const r = partialTech({ status: "planned", resolution: null, debt: 0,
      planned: [{ date: "2026-11-10", slot: "evening", session_id: "boulder_circuit_gym", topup: true,
        drills: [{ exercise_id: "tech_hard_target", name: "Hard Target" }] }] });
    expect(requirementLine(r)).toBe("Hard Target added to Tue 10 Nov's session");
  });

  it("A325: says when the way one would say it", () => {
    expect(whenLabel("2026-11-10", "evening", "2026-11-10")).toBe("tonight");
    expect(whenLabel("2026-11-10", "lunch", "2026-11-10")).toBe("today (lunch)");
    expect(whenLabel("2026-11-11", "evening", "2026-11-10")).toBe("tomorrow (evening)");
    expect(whenLabel("2026-12-01", "lunch", "2026-11-30")).toBe("tomorrow (lunch)");
    expect(whenLabel("2026-11-12", "evening", "2026-11-10")).toBe("Thu 12 Nov (evening)");
  });

  it("A325: the replaced session of a proposal is its own side effect on that slot", () => {
    const p = {
      keys: ["technique"], date: "2026-11-10", slot: "evening", session_id: "technique_focus_gym",
      session_name: "Technique focus gym", location: "gym", gym_id: null, reduced_reentry_dose: false,
      side_effects: [
        { date: "2026-11-10", slot: "evening", from: "boulder_circuit_gym", to: "technique_focus_gym" },
        { date: "2026-11-11", slot: "evening", from: "limit_boulder_gym", to: "regeneration_easy" },
      ],
      apply: { endpoint: "/api/replanner/events", event: {} },
    } as KeyProposal;
    expect(replacedBy(p)?.from).toBe("boulder_circuit_gym");
    expect(replacedBy({ ...p, side_effects: [p.side_effects[1]] })).toBeNull();
  });

  it("A325: a duration is a measure only while it is plausible", () => {
    expect(plausibleDuration(5400)).toBe(5400);
    expect(plausibleDuration(MAX_SESSION_DURATION_S)).toBe(MAX_SESSION_DURATION_S);
    expect(plausibleDuration(37555)).toBeUndefined(); // 10 h 26 min — player left open overnight
    expect(plausibleDuration(null)).toBeUndefined();
    expect(plausibleDuration(-5)).toBeUndefined();
    const t0 = Date.UTC(2026, 10, 9, 18, 0, 0);
    expect(elapsedDuration(t0, t0 + 90 * 60 * 1000)).toBe(5400);
    expect(elapsedDuration(t0, t0 + 37555 * 1000)).toBeUndefined();
    expect(elapsedDuration(0, t0)).toBeUndefined();
  });
});
