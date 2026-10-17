import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { attemptBgClass, attemptGlyph, attemptLabel, isSendResult } from "@/lib/outdoor-result";

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
    for (const rel of [
      "app/(main)/outdoor/page.tsx",
      "components/training/day-card.tsx",
      "components/outdoor/try-breakdown.tsx",
      "components/outdoor/live-route-logger.tsx",
    ]) {
      const src = readFileSync(path.join(root, rel), "utf8");
      expect(src, rel).not.toMatch(/=== "sent" \|\| [a-z.]+ === "topped_out"/);
    }
  });
});
