/**
 * @vitest-environment jsdom
 *
 * B414 step 26 — three P3 texts.
 *
 * - B372-FE-COPY: since B372 `post_outdoor` follows every outdoor day that
 *   counts (planned, logged hard, big load, no route log), not only a big
 *   one: the title says «After an outdoor day» (the reason is in the message).
 * - B-GOAL-DEADLINE-DERIVED (1)(2): Settings shows «Plan ends» from the
 *   macrocycle's `end_date`, not the derived `goal.deadline`; the goal editor
 *   says the new duration applies from the next cycle (the regeneration after
 *   a goal edit keeps the cycle's own length).
 * - The in-app guide: back squat with a barbell, goblet squat without (the
 *   equipment decides, B414 step 13).
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { guardAlert, guardTitle } from "@/lib/week-alerts";
import { planEndLabel } from "@/lib/plan-end";
import type { GuardWarning } from "@/lib/types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("B372-FE-COPY", () => {
  it("post_outdoor reads «After an outdoor day»", () => {
    expect(guardTitle("post_outdoor")).toBe("After an outdoor day");
    const w = { code: "post_outdoor", date: "2026-11-02", message: "Planned outdoor day on Sunday." } as unknown as GuardWarning;
    expect(guardAlert(w).title).toBe("After an outdoor day");
    expect(guardAlert(w).message).toBe("Planned outdoor day on Sunday.");
  });
});

describe("B-GOAL-DEADLINE-DERIVED — the end of the plan", () => {
  it("is the macrocycle's last day, whatever the time zone", () => {
    expect(planEndLabel("2026-12-06")).toBe("December 6, 2026");
    expect(planEndLabel("2026-12-06T00:00:00")).toBe("December 6, 2026");
  });

  it("no cycle → a dash", () => {
    expect(planEndLabel(undefined)).toBe("—");
    expect(planEndLabel(null)).toBe("—");
    expect(planEndLabel("soon")).toBe("—");
  });
});

describe("B-GOAL-DEADLINE-DERIVED — the goal editor says when a new duration applies", () => {
  it("one sentence under the duration", async () => {
    // jsdom has no ResizeObserver (the duration slider measures itself).
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    const { GoalEditor } = await import("@/components/settings/goal-editor");
    render(
      <GoalEditor
        open
        currentGoal={{ discipline: "lead", target_grade: "8a", total_weeks: 12 }}
        grades={{ lead_max_rp: "7c" }}
        onConfirm={() => {}}
        onCancel={() => {}}
        saving={false}
      />,
    );
    expect(screen.getByText(/The cycle you are in keeps its length: a new duration applies from your next cycle/)).toBeTruthy();
  });
});

describe("in-app guide — legs lunch", () => {
  it("back squat with a barbell, goblet squat without", async () => {
    const { GUIDE_SECTIONS } = await import("@/lib/guide-content");
    const section = GUIDE_SECTIONS.find((g) => g.id === "next-weeks-availability");
    expect(section).toBeTruthy();
    const { container } = render(<div>{section!.body}</div>);
    const legs = Array.from(container.querySelectorAll("li")).find((li) => li.textContent?.startsWith("Legs"));
    expect(legs?.textContent).toMatch(/back squat where the gym has a barbell, goblet squat where it has only dumbbells/);
  });
});
