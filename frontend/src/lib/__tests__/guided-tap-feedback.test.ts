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
 *
 * Second round (field-tested by Daniele): scroll-to-top was not enough — the
 * sticky header plus the process-cue banner pushed the next exercise's TITLE
 * below the fold. And `navigator.vibrate` is a no-op on iOS, so the haptic now
 * rides the iOS 17.4+ hidden-switch trick as a fallback.
 */
const src = (rel: string) =>
  stripComments(readFileSync(join(process.cwd(), "src", rel), "utf8"));

describe("guided session scrolls the new exercise's title into view", () => {
  const page = src("app/(guided)/guided/[date]/[sessionId]/page.tsx");

  it("scrolls on every change of currentIndex", () => {
    expect(page).toContain("window.scrollTo");
    const effect = page.slice(page.indexOf("window.scrollTo"));
    const deps = effect.slice(effect.indexOf("}, ["), effect.indexOf("]);") + 3);
    expect(deps).toContain("currentIndex");
  });

  it("anchors to the exercise card, offset by the sticky header height", () => {
    // Scroll-to-top left the title hidden under header + process-cue banner.
    // The card starts with the title, so card-under-header == title visible.
    expect(page).toContain("contentRef");
    expect(page).toContain("headerRef");
    expect(page).toMatch(/headerRef\.current\?\.offsetHeight/);
  });

  it("scrolls smoothly but respects prefers-reduced-motion", () => {
    expect(page).toContain("prefers-reduced-motion");
    expect(page).toMatch(/reduceMotion\s*\?\s*"auto"\s*:\s*"smooth"/);
  });

  it("waits a frame so the new card has rendered before measuring", () => {
    // Scrolling before the re-render targets a stale layout position.
    expect(page).toContain("requestAnimationFrame");
    expect(page).toContain("cancelAnimationFrame");
  });

  it("also fires on the last-exercise → summary transition", () => {
    // The summary heading must be visible too, so showSummary is a dep, not
    // an early-return guard.
    const effect = page.slice(page.indexOf("window.scrollTo"));
    const deps = effect.slice(effect.indexOf("}, ["), effect.indexOf("]);") + 3);
    expect(deps).toContain("showSummary");
    expect(page).not.toMatch(/showSummary\)\s*return/);
  });
});

describe("buttons show and feel the press", () => {
  const button = src("components/ui/button.tsx");

  it("has an active state, not only hover", () => {
    // `hover:` never fires on a touchscreen — this was the entire problem.
    expect(button).toContain("active:scale-");
    expect(button).toContain("active:brightness-");
  });

  it("presses down instantly, releases eased (~100ms)", () => {
    expect(button).toContain("duration-100");
    expect(button).toContain("active:duration-0");
  });

  it("respects prefers-reduced-motion", () => {
    expect(button).toContain("motion-reduce:active:scale-100");
  });

  it("fires one haptic tick on pointerdown, from the base component", () => {
    // pointerdown, not click: the tick must land while the finger is still on
    // the glass — after lift-off it reads as lag.
    expect(button).toContain("tapFeedback()");
    expect(button).toContain("onPointerDown={handlePointerDown}");
  });

  it("still calls the caller's onPointerDown", () => {
    // A haptic that swallowed the handler would break every button in the app.
    expect(button).toMatch(/onPointerDown\?\.\(event\)/);
  });

  it("no screen adds its own haptic on top (would double-buzz)", () => {
    const guided = src("app/(guided)/guided/[date]/[sessionId]/page.tsx");
    expect(guided).not.toContain("confirmFeedback");
  });
});

describe("guided raw buttons (not on the base Button) get the same treatment", () => {
  it.each([
    "components/guided/exercise-timer.tsx",
    "components/guided/guided-exercise-step.tsx",
    "components/guided/guided-progress-bar.tsx",
  ])("%s wires tapFeedback on pointerdown", (rel) => {
    const file = src(rel);
    expect(file).toContain('from "@/lib/haptics"');
    expect(file).toContain("onPointerDown");
    expect(file).toContain("tapFeedback");
  });

  it("timer controls have a visible pressed state with motion-reduce guard", () => {
    const timer = src("components/guided/exercise-timer.tsx");
    expect(timer).toContain("active:scale-95");
    expect(timer).toContain("motion-reduce:active:scale-100");
  });
});

// ---------------------------------------------------------------------------
// haptics runtime
// ---------------------------------------------------------------------------

type FakeElement = {
  setAttribute: ReturnType<typeof vi.fn>;
  style: Record<string, string>;
  appendChild: ReturnType<typeof vi.fn>;
  click: ReturnType<typeof vi.fn>;
  isConnected: boolean;
  type?: string;
  tabIndex?: number;
};

function makeFakeDom() {
  const made: Record<string, FakeElement[]> = {};
  const make = (): FakeElement => ({
    setAttribute: vi.fn(),
    style: {},
    appendChild: vi.fn(),
    click: vi.fn(),
    isConnected: true,
  });
  const doc = {
    body: { appendChild: vi.fn() },
    createElement: (tag: string) => {
      const el = make();
      (made[tag] ??= []).push(el);
      return el;
    },
  };
  return { doc, made };
}

describe("haptics helper", () => {
  beforeEach(() => vi.resetModules());
  afterEach(() => vi.unstubAllGlobals());

  it("calls vibrate when available (Android) and skips the switch", async () => {
    const vibrate = vi.fn();
    const { doc, made } = makeFakeDom();
    vi.stubGlobal("navigator", { vibrate });
    vi.stubGlobal("document", doc);
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    expect(vibrate).toHaveBeenCalledOnce();
    expect(made["label"]).toBeUndefined();
  });

  it("falls back to the iOS switch-toggle tick when vibrate is missing", async () => {
    const { doc, made } = makeFakeDom();
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", doc);
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    const label = made["label"]?.[0];
    expect(label).toBeDefined();
    expect(label!.click).toHaveBeenCalledOnce();
    // Apple's proprietary switch rendering carries the haptic.
    const input = made["input"]?.[0];
    expect(input!.setAttribute).toHaveBeenCalledWith("switch", "");
    expect(input!.type).toBe("checkbox");
    expect(input!.tabIndex).toBe(-1);
  });

  it("hides the switch without display:none (iOS ignores undisplayed toggles)", async () => {
    const { doc, made } = makeFakeDom();
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", doc);
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    const label = made["label"]![0];
    expect(label.setAttribute).toHaveBeenCalledWith("aria-hidden", "true");
    expect(label.style.display).toBeUndefined();
    expect(label.style.pointerEvents).toBe("none");
    expect(label.style.position).toBe("fixed");
  });

  it("creates the switch once and reuses it across taps", async () => {
    const { doc, made } = makeFakeDom();
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", doc);
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    tapFeedback();
    tapFeedback();
    expect(made["label"]).toHaveLength(1);
    expect(made["label"][0].click).toHaveBeenCalledTimes(3);
  });

  it("is a silent no-op when neither engine exists (SSR)", async () => {
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", undefined);
    const { tapFeedback } = await import("@/lib/haptics");
    expect(() => tapFeedback()).not.toThrow();
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

  it("never throws when the switch click throws", async () => {
    const { doc, made } = makeFakeDom();
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", doc);
    const { tapFeedback } = await import("@/lib/haptics");
    tapFeedback();
    made["label"][0].click.mockImplementation(() => {
      throw new Error("boom");
    });
    expect(() => tapFeedback()).not.toThrow();
  });
});
