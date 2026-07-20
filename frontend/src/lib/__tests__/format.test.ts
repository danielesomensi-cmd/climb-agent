import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { FEEDBACK_OPTIONS, formatDateShort, formatSessionName } from "@/lib/format";

describe("formatSessionName", () => {
  it("turns a session id into a title", () => {
    expect(formatSessionName("strength_long")).toBe("Strength Long");
    expect(formatSessionName("power_endurance_4x4")).toBe("Power Endurance 4x4");
  });

  it("leaves an already-formatted name alone", () => {
    expect(formatSessionName("Deload")).toBe("Deload");
  });
});

describe("formatDateShort", () => {
  it("formats an ISO date", () => {
    expect(formatDateShort("2026-07-20")).toBe("20 Jul");
    expect(formatDateShort("2026-01-01")).toBe("1 Jan");
    expect(formatDateShort("2026-12-31")).toBe("31 Dec");
  });

  it("returns anything that isn't an ISO date unchanged", () => {
    expect(formatDateShort("tomorrow")).toBe("tomorrow");
    expect(formatDateShort("")).toBe("");
  });

  it("does not shift the day for timezones west of UTC", () => {
    // The reason this parses by hand instead of using `new Date(str)`:
    // the Date constructor reads a bare YYYY-MM-DD as UTC midnight, which
    // renders as the PREVIOUS day anywhere west of Greenwich (finding F50).
    expect(formatDateShort("2026-07-20")).toBe("20 Jul");
  });
});

describe("FEEDBACK_OPTIONS", () => {
  it("covers the five difficulty levels the engine consumes", () => {
    expect(FEEDBACK_OPTIONS.map((o) => o.value)).toEqual([
      "very_easy", "easy", "ok", "hard", "very_hard",
    ]);
  });

  /**
   * A245 F-3 (F60). The ring class must be a literal Tailwind can see in the
   * source, never assembled at runtime — otherwise it is never generated and
   * the selected chip silently loses its ring.
   */
  it("pairs every colour with a matching literal ring class", () => {
    for (const opt of FEEDBACK_OPTIONS) {
      expect(opt.ring).toBe(opt.color.replace("bg-", "ring-"));
    }
  });

  it("declares the ring classes as literals in the source", () => {
    const src = readFileSync(join(process.cwd(), "src/lib/format.ts"), "utf8");
    for (const opt of FEEDBACK_OPTIONS) {
      expect(src, `${opt.ring} must appear literally for Tailwind to emit it`)
        .toContain(`"${opt.ring}"`);
    }
  });

  it("no component derives a ring class at runtime", () => {
    const chips = readFileSync(
      join(process.cwd(), "src/components/guided/guided-exercise-step.tsx"),
      "utf8",
    );
    expect(chips).not.toMatch(/ring-\$\{/);
  });
});
