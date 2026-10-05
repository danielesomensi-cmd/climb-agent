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
  requirementLine,
  shortDay,
} from "@/lib/key-sessions";
import type { KeyRequirement, KeyStatus } from "@/lib/types";

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

  it("describes every resolution in plain words", () => {
    expect(requirementLine(req({ status: "done" }))).toBe("Done");
    expect(requirementLine(req({ status: "planned", planned: [{ date: "2026-10-09", slot: "evening", session_id: "strength_long" }] })))
      .toBe("Next: Fri 09/10");
    expect(requirementLine(req({ resolution: "proposal" }))).toContain("catch-up proposed");
    expect(requirementLine(req({ resolution: "deferred_next", next_key: { date: "2026-10-09", slot: "evening", session_id: "strength_long" } })))
      .toContain("next key session Fri 09/10");
    expect(requirementLine(req({ resolution: "deferred_fatigue" }))).toContain("very hard");
    expect(requirementLine(req({ status: "partial", resolution: "let_go" }))).toMatch(/^Only a partial dose/);
    expect(requirementLine(req({ status: "not_due", due_by: "2026-10-29" }))).toContain("Thu 29/10");
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
    expect(shortDay("2026-10-05")).toBe("Mon 05/10");
    expect(localToday(new Date(2026, 9, 4, 23, 30))).toBe("2026-10-04");
  });
});
