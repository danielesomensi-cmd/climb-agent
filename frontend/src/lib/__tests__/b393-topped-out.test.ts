import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { attemptBgClass, attemptGlyph, attemptLabel, isSendResult } from "@/lib/outdoor-result";
import { stripComments } from "./helpers/source-scan";

/** Every view (and view helper) that reads an outdoor attempt's outcome. */
const VIEWS = [
  "app/(main)/outdoor/page.tsx",
  "app/(main)/outdoor/[date]/page.tsx",
  "app/(main)/reports/weekly/page.tsx",
  "components/training/day-card.tsx",
  "components/training/OutdoorLogForm.tsx",
  "components/outdoor/try-breakdown.tsx",
  "components/outdoor/live-route-logger.tsx",
  "lib/outdoor-routes.ts",
];

/**
 * B393 — `topped_out` (top with rests: hangdog, top-rope, in pieces) is not a
 * send. Real case: Isatis 7c+ [topped_out, fell, fell] showed «Isatis Send».
 */
describe("B393 — topped_out is never a send", () => {
  it("only `sent` is a send", () => {
    expect(isSendResult("sent")).toBe(true);
    expect(isSendResult("topped_out")).toBe(false);
    expect(isSendResult("fell")).toBe(false);
    expect(isSendResult(undefined)).toBe(false);
  });

  it("topped_out has its own amber look and label", () => {
    expect(attemptBgClass("topped_out")).toBe("bg-warning");
    expect(attemptLabel("topped_out")).toBe("Top w/ rests");
    expect(attemptGlyph("topped_out")).toBe("↑");
    expect(attemptBgClass("sent")).toBe("bg-success");
    expect(attemptBgClass("fell")).toBe("bg-danger");
  });

  it("no view treats topped_out as sent inline any more", () => {
    const root = path.resolve(__dirname, "../../");
    for (const rel of VIEWS) {
      const src = readFileSync(path.join(root, rel), "utf8");
      expect(src, rel).not.toMatch(/=== "sent" \|\| [a-z.]+ === "topped_out"/);
    }
  });

  /**
   * A324 — a send is `sent` on LEAD. A bare result string carries no rope
   * role, so a view that compares `.result === "sent"` or hands `a.result` to
   * a helper counts a clean second / top-rope as a green send. Views pass the
   * whole attempt (`isLeadSend(a)`, `attemptLabel(a)`, …) — outdoor-result.ts
   * is the only place that reads `result`.
   */
  it("no view reads a send from the bare result (A324)", () => {
    const root = path.resolve(__dirname, "../../");
    const RESULT_HELPER_ON_STRING =
      /\b(?:isSendResult|isToppedResult|isAidResult|attemptLabel|attemptResultLabel|attemptBgClass|attemptTextClass|attemptChipClass|attemptGlyph|attemptKind|isLeadSend|isCleanNonLead)\(\s*[^),]*\.result\b/;
    for (const rel of VIEWS) {
      const code = stripComments(readFileSync(path.join(root, rel), "utf8"));
      expect(code, rel).not.toMatch(/\.result\s*[!=]==?\s*["']sent["']/);
      expect(code, rel).not.toMatch(/\bisSendResult\(/);
      expect(code, rel).not.toMatch(RESULT_HELPER_ON_STRING);
    }
  });
});
