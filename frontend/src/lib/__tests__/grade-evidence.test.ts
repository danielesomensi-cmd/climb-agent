import { describe, expect, it } from "vitest";
import { initialAnswers, supportedGrade, type GradeEvidenceRoute } from "@/lib/grade-evidence";

const route = (key: string, grade: string, date: string, spot: string, style: string | null = null): GradeEvidenceRoute => ({
  key, grade, date, spot_name: spot, name: key, style, explicit: style !== null, in_trip: false,
});

const ROUTES = [
  route("nishiki", "7b+", "2026-06-28", "Berdorf"),
  route("blue", "7b", "2026-08-25", "Snake Valley (Kalymnos)"),
  route("ataraxia", "7b", "2026-08-27", "Snake Valley (Kalymnos)"),
  route("meraki", "7b", "2026-08-27", "Snake Valley (Kalymnos)"),
];

describe("supportedGrade (A292)", () => {
  it("supports 7b with Nishiki marked worked (two days at the same crag)", () => {
    expect(supportedGrade(ROUTES, { nishiki: "worked", blue: "onsight", ataraxia: "onsight", meraki: "flash" })).toBe("7b");
  });

  it("needs two days or two crags", () => {
    expect(supportedGrade(ROUTES, { ataraxia: "onsight", meraki: "onsight" })).toBeNull();
  });

  it("ranks + above the base grade, and worked routes do not count", () => {
    expect(supportedGrade(ROUTES, { nishiki: "onsight", blue: "onsight" })).toBe("7b");
    expect(supportedGrade(ROUTES, { nishiki: "worked", blue: "worked" })).toBeNull();
  });

  it("pre-fills only styles the log declares", () => {
    const a = initialAnswers([route("x", "7a", "2026-01-01", "A", "flash"), route("y", "7a", "2026-01-02", "A")]);
    expect(a).toEqual({ x: "flash", y: undefined });
  });
});
