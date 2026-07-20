import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { findInSources } from "./helpers/source-scan";

import { parseISODateLocal, shiftISODate, toISODateLocal } from "@/lib/dates";

/**
 * A245 G-1 (F50) — `new Date("2026-07-20")` is UTC midnight per spec, which is
 * still the 19th anywhere west of Greenwich. Half the call sites appended
 * "T00:00:00" and half did not, so plan start dates, the current-week
 * computation and the phase celebration were a day off for some users only.
 */
describe("parseISODateLocal", () => {
  it("returns local midnight, not UTC midnight", () => {
    const d = parseISODateLocal("2026-07-20");
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(6); // July
    expect(d.getDate()).toBe(20);
    expect(d.getHours()).toBe(0);
  });

  it("keeps the calendar day the user typed, in any timezone", () => {
    // The bug, stated as a test: the local day must equal the string's day.
    for (const iso of ["2026-01-01", "2026-07-20", "2026-12-31", "2026-02-28"]) {
      expect(toISODateLocal(parseISODateLocal(iso))).toBe(iso);
    }
  });

  it("differs from the naive constructor west of UTC (and never east)", () => {
    const naive = new Date("2026-07-20");
    const ours = parseISODateLocal("2026-07-20");
    // Same calendar day for us, whatever the host offset.
    expect(toISODateLocal(ours)).toBe("2026-07-20");
    // The naive one is an instant, not a calendar day: it only agrees at UTC+0
    // or east of it.
    if (new Date().getTimezoneOffset() > 0) {
      expect(toISODateLocal(naive)).not.toBe("2026-07-20");
    }
  });

  it("tolerates a full timestamp by using its date part", () => {
    expect(toISODateLocal(parseISODateLocal("2026-07-20T18:30:00Z"))).toBe("2026-07-20");
  });

  it("returns an Invalid Date for junk instead of a plausible wrong one", () => {
    for (const junk of ["", "tomorrow", "20-07-2026", "2026/07/20"]) {
      expect(Number.isNaN(parseISODateLocal(junk).getTime())).toBe(true);
    }
  });
});

describe("shiftISODate", () => {
  it("shifts whole days", () => {
    expect(shiftISODate("2026-07-20", 7)).toBe("2026-07-27");
    expect(shiftISODate("2026-07-20", -7)).toBe("2026-07-13");
  });

  it("crosses month and year boundaries", () => {
    expect(shiftISODate("2026-07-31", 1)).toBe("2026-08-01");
    expect(shiftISODate("2026-12-31", 1)).toBe("2027-01-01");
    expect(shiftISODate("2026-01-01", -1)).toBe("2025-12-31");
  });

  it("handles a leap day", () => {
    expect(shiftISODate("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("survives a DST transition without losing or gaining a day", () => {
    // Europe/Rome springs forward on 2026-03-29. A naive +24h would land at
    // 01:00 on the same day in some zones; day arithmetic must not care.
    expect(shiftISODate("2026-03-28", 1)).toBe("2026-03-29");
    expect(shiftISODate("2026-03-29", 1)).toBe("2026-03-30");
  });

  it("returns the input unchanged when it isn't a date", () => {
    expect(shiftISODate("nope", 3)).toBe("nope");
  });
});

/**
 * Structural guard: the naive constructor must not creep back in. A new
 * `new Date(someIsoString)` compiles fine and is wrong only for some users.
 */
describe("no naive ISO parsing in source", () => {
  it("nothing parses a plain date string with the Date constructor", () => {
    // Comments are stripped first: the migrated files legitimately describe the
    // old `new Date(start_date)` in prose so the next reader knows what broke.
    const hits = findInSources(
      join(process.cwd(), "src"),
      /new Date\(\s*(?:[A-Za-z_$][\w$]*\.)*(start_date|end_date|dateStr|iso)\s*\)/,
    );
    expect(hits, `use parseISODateLocal():\n${hits.join("\n")}`).toEqual([]);
  });

  it("the migrated call sites import the helper", () => {
    const phase = readFileSync(join(process.cwd(), "src/lib/phase-progress.ts"), "utf8");
    expect(phase).toContain("parseISODateLocal");
  });
});
