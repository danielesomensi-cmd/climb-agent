import { describe, expect, it } from "vitest";
import {
  attemptBgClass,
  attemptChipClass,
  attemptGlyph,
  attemptKind,
  attemptLabel,
  attemptResultLabel,
  attemptTextClass,
  isBoulderRoute,
  isCleanNonLead,
  isLeadSend,
  isSendResult,
  lastAttemptRopeRole,
  nextAttemptResult,
  nextRopeRole,
  ropeRoleOf,
  routeAid,
  routeCleanNonLead,
  routeCleanRole,
  routeLeadSent,
  stripRopeOnly,
  withRopeRole,
} from "@/lib/outdoor-result";
import type { OutdoorAttempt } from "@/lib/types";

/**
 * A324 — who was on the sharp end (lead / second / top-rope) and A0, read
 * once for every view (twin of backend/engine/outdoor_attempt.py).
 *
 * Real case: Cancer at Presles, 31/10, climbed on alternate leads — the
 * pitches seconded clean had to be saved `fell` with a note, because a clean
 * `sent` would have counted as a send on lead.
 */

type Row = [OutdoorAttempt, string, string, string, string];

// [attempt, label, background, text, glyph]
const MATRIX: Row[] = [
  [{ result: "sent" }, "Sent", "bg-success", "text-success", "✓"],
  [{ result: "sent", rope_role: "lead" }, "Sent", "bg-success", "text-success", "✓"],
  [{ result: "sent", rope_role: "second" }, "Second clean", "bg-info", "text-info", "✓"],
  [{ result: "sent", rope_role: "toprope" }, "TR clean", "bg-info", "text-info", "✓"],
  [{ result: "fell" }, "Fell", "bg-danger", "text-danger", "✗"],
  [{ result: "fell", rope_role: "second" }, "Fell (2nd)", "bg-danger", "text-danger", "✗"],
  [{ result: "fell", rope_role: "toprope" }, "Fell (TR)", "bg-danger", "text-danger", "✗"],
  [{ result: "topped_out" }, "Top w/ rests", "bg-warning", "text-warning", "↑"],
  [{ result: "topped_out", rope_role: "toprope" }, "Top w/ rests (TR)", "bg-warning", "text-warning", "↑"],
  [{ result: "aid" }, "A0", "bg-warning", "text-warning", "A0"],
  [{ result: "aid", rope_role: "second" }, "A0 (2nd)", "bg-warning", "text-warning", "A0"],
];

describe("A324 — reading an attempt (result × rope role)", () => {
  it.each(MATRIX)("%o reads %s", (attempt, label, bg, text, glyph) => {
    expect(attemptLabel(attempt)).toBe(label);
    expect(attemptBgClass(attempt)).toBe(bg);
    expect(attemptTextClass(attempt)).toBe(text);
    expect(attemptGlyph(attempt)).toBe(glyph);
  });

  it("a clean ascent not on lead is never green and never a send", () => {
    for (const role of ["second", "toprope"] as const) {
      const a: OutdoorAttempt = { result: "sent", rope_role: role };
      expect(isLeadSend(a)).toBe(false);
      expect(isCleanNonLead(a)).toBe(true);
      expect(attemptKind(a)).toBe("clean_non_lead");
      expect(attemptBgClass(a)).not.toBe("bg-success");
      expect(attemptTextClass(a)).not.toBe("text-success");
      expect(attemptChipClass(a)).not.toContain("success");
    }
  });

  it("only sent on lead is a send; A0 and a top with rests never are", () => {
    expect(isLeadSend({ result: "sent" })).toBe(true);
    for (const result of ["fell", "topped_out", "aid"] as const) {
      expect(isLeadSend({ result })).toBe(false);
      expect(isCleanNonLead({ result, rope_role: "second" })).toBe(false);
    }
  });

  it("no rope role reads as lead (every log before A324)", () => {
    expect(ropeRoleOf({ result: "sent" })).toBe("lead");
    expect(ropeRoleOf({ result: "sent", rope_role: "top_rope" })).toBe("lead"); // unknown spelling
    expect(ropeRoleOf(undefined)).toBe("lead");
    expect(isLeadSend({ result: "sent" })).toBe(true);
  });

  it("the B393 string signatures still work, and a bare string is lead", () => {
    expect(isSendResult("sent")).toBe(true);
    expect(isSendResult("aid")).toBe(false);
    expect(attemptLabel("sent")).toBe("Sent");
    expect(attemptLabel("topped_out")).toBe("Top w/ rests");
    expect(attemptLabel("fell")).toBe("Fell");
    expect(attemptBgClass("sent")).toBe("bg-success");
    expect(attemptGlyph("topped_out")).toBe("↑");
    expect(attemptLabel(undefined)).toBe("Fell");
  });

  it("the form badge shows the result word next to its role tag", () => {
    expect(attemptResultLabel({ result: "sent" })).toBe("Sent");
    expect(attemptResultLabel({ result: "sent", rope_role: "second" })).toBe("Clean");
    expect(attemptResultLabel({ result: "aid", rope_role: "toprope" })).toBe("A0");
    expect(attemptResultLabel({ result: "fell", rope_role: "toprope" })).toBe("Fell");
  });
});

describe("A324 — writing an attempt", () => {
  it("lead is written as absent, the other roles as they are", () => {
    expect(withRopeRole({ result: "sent", rope_role: "second" }, "lead")).toEqual({ result: "sent" });
    expect("rope_role" in withRopeRole({ result: "sent" }, "lead")).toBe(false);
    expect(withRopeRole({ result: "fell", notes: "x" }, "toprope")).toEqual({
      result: "fell",
      notes: "x",
      rope_role: "toprope",
    });
  });

  it("the result cycles sent → fell → A0 on a rope, sent ⇄ fell on a boulder", () => {
    expect(nextAttemptResult("sent", true)).toBe("fell");
    expect(nextAttemptResult("fell", true)).toBe("aid");
    expect(nextAttemptResult("aid", true)).toBe("sent");
    expect(nextAttemptResult("sent", false)).toBe("fell");
    expect(nextAttemptResult("fell", false)).toBe("sent");
  });

  it("a top with rests is never promoted to a send by a tap (B393)", () => {
    expect(nextAttemptResult("topped_out", true)).toBe("fell");
    expect(nextAttemptResult("topped_out", false)).toBe("fell");
  });

  it("the role cycles Lead → 2nd → TR → Lead", () => {
    expect(nextRopeRole("lead")).toBe("second");
    expect(nextRopeRole("second")).toBe("toprope");
    expect(nextRopeRole("toprope")).toBe("lead");
  });

  it("a boulder loses rope roles and A0 (A0 → fell), the same object when clean", () => {
    const clean = { name: "B", grade: "7a", attempts: [{ result: "sent" as const }] };
    expect(stripRopeOnly(clean)).toBe(clean);
    const dirty = {
      name: "B",
      grade: "7a",
      attempts: [
        { result: "sent" as const, rope_role: "toprope" as const },
        { result: "aid" as const },
      ],
    };
    expect(stripRopeOnly(dirty).attempts).toEqual([{ result: "sent" }, { result: "fell" }]);
  });

  it("a boulder is the route's discipline, else the session's (backend is_boulder_route)", () => {
    expect(isBoulderRoute({ discipline: "boulder" }, "lead")).toBe(true);
    expect(isBoulderRoute({ discipline: "lead" }, "boulder")).toBe(false);
    expect(isBoulderRoute({}, "boulder")).toBe(true);
    expect(isBoulderRoute({}, "both")).toBe(false);
  });
});

describe("A324 — routes", () => {
  const route = (...attempts: OutdoorAttempt[]) => ({ attempts });

  it("send / clean non-lead / A0 are exclusive, as in the backend", () => {
    const sentAfterSecond = route({ result: "sent", rope_role: "second" }, { result: "sent" });
    expect(routeLeadSent(sentAfterSecond)).toBe(true);
    expect(routeCleanNonLead(sentAfterSecond)).toBe(false);

    const second = route({ result: "sent", rope_role: "second" });
    expect(routeLeadSent(second)).toBe(false);
    expect(routeCleanNonLead(second)).toBe(true);
    expect(routeCleanRole(second)).toBe("second");
    expect(routeAid(second)).toBe(false);

    const tr = route({ result: "fell" }, { result: "sent", rope_role: "toprope" });
    expect(routeCleanRole(tr)).toBe("toprope");

    const aid = route({ result: "aid" });
    expect(routeAid(aid)).toBe(true);
    expect(routeLeadSent(aid)).toBe(false);
    expect(routeCleanNonLead(aid)).toBe(false);

    // A0 then clean on second: clean wins, A0 does not count (backend route_aid).
    const aidThenClean = route({ result: "aid" }, { result: "sent", rope_role: "second" });
    expect(routeAid(aidThenClean)).toBe(false);
    expect(routeCleanNonLead(aidThenClean)).toBe(true);
  });

  it("the live logger restores the role of the LAST try logged", () => {
    expect(lastAttemptRopeRole([])).toBeNull();
    expect(lastAttemptRopeRole([{ attempts: [{ result: "sent" }] }])).toBe("lead");
    expect(
      lastAttemptRopeRole([
        { attempts: [{ result: "sent", rope_role: "second", logged_at: "2026-10-31T10:00:00Z" }] },
        { attempts: [{ result: "sent", logged_at: "2026-10-31T09:00:00Z" }] },
      ]),
    ).toBe("second"); // by time, not by position: a try added to an older route
    expect(
      lastAttemptRopeRole([
        { attempts: [{ result: "sent" }] },
        { attempts: [{ result: "fell", rope_role: "toprope" }] },
      ]),
    ).toBe("toprope"); // no timestamps: the last one in order
  });
});

describe("A324 — weekly report", () => {
  it("shows the routes climbed clean on 2nd / TR next to the lead sends", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const code = readFileSync(join(process.cwd(), "src", "app/(main)/reports/weekly/page.tsx"), "utf8");
    expect(code).toContain("report.outdoor.routes_clean_non_lead");
    expect(code).toMatch(/clean on 2nd\/TR/);
  });
});
