/**
 * @vitest-environment jsdom
 *
 * A330 (D288-FE) — the reduced-week card: `GET /api/week` carries
 * `reduced_week` (A328 (b)) only when a reduced week is suggested. The card
 * says it, offers no plan-changing button, and is dismissed per suggested week.
 */
import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

import { ReducedWeekCard } from "../reduced-week-card";
import { reducedWeekDismissKey, reducedWeekText, shownReducedWeek } from "@/lib/reduced-week";
import type { ReducedWeekSuggestion } from "@/lib/types";

function rw(over: Partial<ReducedWeekSuggestion> = {}): ReducedWeekSuggestion {
  return {
    suggested: true,
    week_start: "2026-11-16",
    reasons: ["very_hard_7d"],
    skipped: null,
    as_of: "2026-11-13",
    message: "backend sentence",
    ...over,
  };
}

const FULL =
  "Consider a reduced week from Mon 16 Nov (two sessions rated very hard in the last 7 days): same climbing days, " +
  "half the sets, one finger exposure at your working load minus 10 %, no intervals, no tests. " +
  "Nothing changes in your plan unless you decide it.";

afterEach(cleanup);
// jsdom here has no working localStorage: a Map-backed stand-in, fresh per test.
beforeEach(() => {
  const store = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
    },
  });
});

describe("A330 — reduced-week text", () => {
  it("the sentence of the brief, the date as the app writes it", () => {
    const t = reducedWeekText(rw());
    expect(t.lead + t.rest).toBe(FULL);
  });

  it("several reasons are joined", () => {
    const t = reducedWeekText(rw({ reasons: ["very_hard_7d", "pain_block"] }));
    expect(t.rest).toMatch(/^ \(two sessions rated very hard in the last 7 days and an active pain report\):/);
    expect(reducedWeekText(rw({ reasons: ["athlete_request"] })).rest).toMatch(/^ \(you asked for it\):/);
  });

  it("shown only when suggested, with a week start", () => {
    expect(shownReducedWeek(undefined)).toBeNull();
    expect(shownReducedWeek(rw({ suggested: false }))).toBeNull();
    expect(shownReducedWeek(rw({ week_start: "" }))).toBeNull();
    expect(shownReducedWeek(rw())).not.toBeNull();
  });
});

describe("A330 — ReducedWeekCard", () => {
  it("renders the suggestion, with no button that changes the plan", () => {
    render(<ReducedWeekCard suggestion={rw()} />);
    expect(screen.getByTestId("reduced-week-card").textContent).toBe(FULL);
    // The only control is the dismiss.
    expect(screen.getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual(["Dismiss"]);
  });

  it("renders nothing without a suggestion", () => {
    const { container } = render(<ReducedWeekCard suggestion={undefined} />);
    expect(container.textContent).toBe("");
    cleanup();
    const r2 = render(<ReducedWeekCard suggestion={rw({ suggested: false })} />);
    expect(r2.container.textContent).toBe("");
  });

  it("dismiss hides it for that week only", () => {
    render(<ReducedWeekCard suggestion={rw()} />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByTestId("reduced-week-card")).toBeNull();
    expect(window.localStorage.getItem(reducedWeekDismissKey("2026-11-16"))).toBe("1");
    cleanup();

    // Same week again (next load): stays hidden.
    const again = render(<ReducedWeekCard suggestion={rw()} />);
    expect(again.container.textContent).toBe("");
    cleanup();

    // A suggestion for another week shows.
    render(<ReducedWeekCard suggestion={rw({ week_start: "2026-11-23" })} />);
    expect(screen.getByTestId("reduced-week-card").textContent).toContain("from Mon 23 Nov");
  });
});
