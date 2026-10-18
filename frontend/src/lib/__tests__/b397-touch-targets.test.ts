import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { stripComments } from "./helpers/source-scan";

/**
 * B397 G5/G6 — targets you can hit with chalky hands, and confirmations that
 * are not `window.confirm` (a native dialog over a PWA, blocked in some
 * standalone modes, and the one thing a double tap confirms by accident).
 */
const src = (rel: string) => stripComments(readFileSync(join(process.cwd(), "src", rel), "utf8"));

const page = src("app/(guided)/guided/[date]/[sessionId]/page.tsx");

describe("guided touch targets", () => {
  it("progress dots are at least 32 px wide and 44 px tall", () => {
    const bar = src("components/guided/guided-progress-bar.tsx");
    expect(bar).toContain("min-w-[32px]");
    expect(bar).toContain("min-h-[44px]");
  });

  it("Finish early and its confirmation are 44 px targets", () => {
    const block = page.slice(page.indexOf("confirmFinish ? ("), page.indexOf("Finish session early") + 40);
    expect(block).toContain("Keep going");
    expect(block).toContain("Finish now");
    expect(block.match(/min-h-\[44px\]/g)?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("the Undo button of the toast is thumb-sized", () => {
    const m = page.match(/actionButtonStyle:\s*\{\s*minHeight:\s*(\d+)/);
    expect(m).not.toBeNull();
    expect(Number(m![1])).toBeGreaterThanOrEqual(32);
  });

  it("no window.confirm anywhere in the guided player", () => {
    for (const rel of [
      "app/(guided)/guided/[date]/[sessionId]/page.tsx",
      "components/guided/guided-summary.tsx",
      "components/guided/guided-exercise-step.tsx",
    ]) {
      expect(src(rel), rel).not.toMatch(/\bconfirm\(/);
    }
  });
});
