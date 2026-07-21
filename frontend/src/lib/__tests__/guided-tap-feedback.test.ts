import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { stripComments } from "./helpers/source-scan";

/**
 * A247 — "did my tap register?"
 *
 * Two independent gaps produced the same confusion during a guided session:
 *
 *  1. Tapping Done at the BOTTOM of a long exercise card advanced the index,
 *     the card re-rendered with the next exercise, and the scroll position
 *     stayed put — leaving you at the bottom of a different exercise, usually
 *     looking at another Done button.
 *  2. The base Button declared only `hover:` styles, which do nothing on a
 *     touchscreen, so the press itself was invisible.
 */
const src = (rel: string) =>
  stripComments(readFileSync(join(process.cwd(), "src", rel), "utf8"));

describe("guided session scrolls to the new exercise", () => {
  const page = src("app/(guided)/guided/[date]/[sessionId]/page.tsx");

  it("scrolls on every change of currentIndex", () => {
    expect(page).toContain("window.scrollTo");
    const effect = page.slice(page.indexOf("window.scrollTo"));
    const deps = effect.slice(effect.indexOf("}, ["), effect.indexOf("]);") + 3);
    expect(deps).toContain("currentIndex");
  });

  it("jumps instantly rather than animating", () => {
    // A 300ms smooth scroll reads as "the page is still settling", which is the
    // opposite of a confirmation.
    expect(page).toMatch(/behavior:\s*"instant"/);
  });

  it("does not fight the summary screen", () => {
    const effect = page.slice(page.indexOf("window.scrollTo") - 400, page.indexOf("window.scrollTo"));
    expect(effect).toContain("showSummary");
  });
});

describe("buttons show and feel the press", () => {
  const button = src("components/ui/button.tsx");

  it("has an active state, not only hover", () => {
    // `hover:` never fires on a touchscreen — this was the entire problem.
    expect(button).toContain("active:scale-");
    expect(button).toContain("active:brightness-");
  });

  it("respects prefers-reduced-motion", () => {
    expect(button).toContain("motion-reduce:active:scale-100");
  });

  it("fires one haptic tick, from the base component", () => {
    expect(button).toContain("tapFeedback()");
  });

  it("still calls the caller's onClick", () => {
    // A haptic that swallowed the handler would break every button in the app.
    expect(button).toMatch(/onClick\?\.\(event\)/);
  });

  it("no screen adds its own haptic on top (would double-buzz)", () => {
    const guided = src("app/(guided)/guided/[date]/[sessionId]/page.tsx");
    expect(guided).not.toContain("confirmFeedback");
  });
});

describe("haptics helper", () => {
  beforeEach(() => vi.resetModules());
  afterEach(() => vi.unstubAllGlobals());

  it("is a no-op when the platform has no vibrate (iOS Safari)", async () => {
    vi.stubGlobal("navigator", {});
    const { tapFeedback } = await import("@/lib/haptics");
    expect(() => tapFeedback()).not.toThrow();
  });

  it("calls vibrate when available", async () => {
    const vibrate = vi.fn();
    vi.stubGlobal("navigator", { vibrate });
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    expect(vibrate).toHaveBeenCalledOnce();
  });

  it("never throws when vibrate itself throws", async () => {
    // Some browsers throw if the page is not visible; a buzz is never worth
    // breaking a tap over.
    vi.stubGlobal("navigator", {
      vibrate: () => {
        throw new Error("not allowed");
      },
    });
    const { tapFeedback } = await import("@/lib/haptics");
    expect(() => tapFeedback()).not.toThrow();
  });
});
