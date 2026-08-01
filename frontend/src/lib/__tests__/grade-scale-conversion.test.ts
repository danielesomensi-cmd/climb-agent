import { describe, expect, it } from "vitest";
import {
  LEAD_GRADE_OPTIONS,
  BOULDER_GRADE_OPTIONS,
  V_SCALE_GRADES,
  YDS_GRADE_OPTIONS,
  gradeRank,
  vScaleToFont,
  ydsToFrench,
} from "@/lib/gradeUtils";

/**
 * A263 — the public assessment lets the user pick their scale, so every grade
 * they choose is converted before it reaches the engine. A wrong entry here is
 * invisible: the request succeeds and the profile is simply computed for a
 * different climber.
 */

describe("ydsToFrench", () => {
  it("maps every offered YDS option to a grade the engine accepts", () => {
    /* The engine rejects unknown grades with 422 (A262), so an option the
       picker offers but the conversion cannot handle would be a dead end the
       user cannot fix. */
    for (const yds of YDS_GRADE_OPTIONS) {
      const french = ydsToFrench(yds);
      expect(french, `${yds} → ${french}`).not.toBe(yds);
      expect(LEAD_GRADE_OPTIONS, `${yds} → ${french}`).toContain(french);
    }
  });

  it("is strictly monotonic — a harder YDS grade never maps lower", () => {
    const ranks = YDS_GRADE_OPTIONS.map((g) => gradeRank(ydsToFrench(g)));
    for (let i = 1; i < ranks.length; i++) {
      expect(ranks[i], `${YDS_GRADE_OPTIONS[i]} vs ${YDS_GRADE_OPTIONS[i - 1]}`)
        .toBeGreaterThan(ranks[i - 1]);
    }
  });

  it("is one-to-one, so two different answers cannot score identically", () => {
    const mapped = YDS_GRADE_OPTIONS.map(ydsToFrench);
    expect(new Set(mapped).size).toBe(mapped.length);
  });

  it("anchors on the conversions climbers would check first", () => {
    expect(ydsToFrench("5.10a")).toBe("6a");
    expect(ydsToFrench("5.11d")).toBe("7a+");
    expect(ydsToFrench("5.12d")).toBe("7c+");
    expect(ydsToFrench("5.14a")).toBe("8c");
  });

  it("passes unknown input through, so the backend rejects it", () => {
    expect(ydsToFrench("5.99z")).toBe("5.99z");
  });
});

describe("vScaleToFont", () => {
  it("maps every offered V grade onto a Font grade the picker knows", () => {
    for (const v of V_SCALE_GRADES) {
      const font = vScaleToFont(v);
      expect(BOULDER_GRADE_OPTIONS, `${v} → ${font}`).toContain(font);
    }
  });

  it("never maps a harder V grade lower", () => {
    const ranks = V_SCALE_GRADES.map((g) => gradeRank(vScaleToFont(g).toLowerCase()));
    for (let i = 1; i < ranks.length; i++) {
      expect(ranks[i]).toBeGreaterThanOrEqual(ranks[i - 1]);
    }
  });
});
