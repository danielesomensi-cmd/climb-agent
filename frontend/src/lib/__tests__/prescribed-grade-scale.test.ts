/**
 * B344 — a lead-anchored target grade must not be rendered in Font casing.
 *
 * The engine computes target grades on a whole-grade letter ladder shared by
 * Font and French, and emits the canonical UPPERCASE value. On a rope drill
 * anchored to `lead_max_os` that reached the UI as "6C" — which reads as a Font
 * boulder grade (~7a+ French), i.e. far harder than the 6c French meant.
 */

import { describe, it, expect } from "vitest";
import { displayPrescribedGrade } from "@/lib/gradeUtils";

describe("displayPrescribedGrade", () => {
  it("lowercases a french-scale target", () => {
    expect(displayPrescribedGrade("6C", "french")).toBe("6c");
    expect(displayPrescribedGrade("7A", "french")).toBe("7a");
  });

  it("leaves a font-scale target untouched", () => {
    expect(displayPrescribedGrade("6C", "font")).toBe("6C");
  });

  it("is a no-op when the scale is absent (older cached payloads)", () => {
    expect(displayPrescribedGrade("6C", undefined)).toBe("6C");
    expect(displayPrescribedGrade("6C")).toBe("6C");
  });

  it("ignores an unknown scale rather than guessing", () => {
    expect(displayPrescribedGrade("6C", "yds")).toBe("6C");
  });

  it("round-trips safely: the engine uppercases on the way back in", () => {
    // normalize_font_grade() does .strip().upper() before lookup, so shipping
    // the lowercase value back as `used_grade` is safe.
    const shown = displayPrescribedGrade("6C", "french");
    expect(shown.toUpperCase()).toBe("6C");
  });
});
