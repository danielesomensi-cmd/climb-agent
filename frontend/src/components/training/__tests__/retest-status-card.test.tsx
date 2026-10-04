/**
 * @vitest-environment jsdom
 *
 * A289 — the retest status card renders the policy's payload as information:
 * official max, confidence, ±5 % trend, next test with its reason, live flags.
 */

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { RetestStatusCard } from "../retest-status-card";
import type { RetestAxisStatus, RetestStatus } from "@/lib/types";

afterEach(cleanup);

function axis(over: Partial<RetestAxisStatus>): RetestAxisStatus {
  return {
    axis: "finger",
    covered: true,
    protocol: "max_hang_7s_total_load",
    official_total_kg: 116,
    test_date: "2026-09-24",
    age_days: 10,
    confidence: "low",
    confidence_exposures: 0,
    confidence_min_exposures: 2,
    trend: "stable",
    delta_pct: -4.9,
    previous_date: "2026-05-19",
    earliest_retest: "2026-10-22",
    signals: { count: 0, needed: 2 },
    fatigue: null,
    next_test: {
      date: "2026-10-24",
      session_id: "test_max_hang_7s",
      source: "planned",
      trigger: "end_of_phase_slipped",
      reason: "End-of-strength retest moved one week.",
      blockers: [],
    },
    next_test_reason: null,
    ...over,
  };
}

function status(axes: RetestAxisStatus[]): RetestStatus {
  return {
    as_of: "2026-10-04",
    stable_band_pct: 5,
    axes: Object.fromEntries(axes.map((a) => [a.axis, a])),
    covered_axes: axes.filter((a) => a.covered).map((a) => a.axis),
  };
}

describe("RetestStatusCard", () => {
  it("renders nothing without a payload", () => {
    const { container } = render(<RetestStatusCard status={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows max, confidence, stable trend and the planned test with its reason", () => {
    render(
      <RetestStatusCard
        status={status([
          axis({}),
          axis({ axis: "pulling", official_total_kg: 123, delta_pct: 0.8, protocol: "weighted_pullup_2rm" }),
        ])}
      />,
    );
    expect(screen.getByText(/Finger max/).textContent).toContain("116 kg");
    expect(screen.getByText(/Pull-up 2RM/).textContent).toContain("123 kg");
    expect(screen.getAllByText(/low confidence · stable \(-4.9%\)/).length).toBe(1);
    expect(screen.getByText(/stable \(\+0.8%\)/)).toBeTruthy();
    expect(screen.getAllByText(/24 Oct/).length).toBe(2);
    expect(screen.getAllByText(/End-of-strength retest moved one week/).length).toBe(2);
  });

  it("flags live blockers without moving the test", () => {
    render(
      <RetestStatusCard
        status={status([
          axis({
            next_test: {
              date: "2026-10-24",
              session_id: "test_max_hang_7s",
              source: "planned",
              trigger: null,
              reason: null,
              blockers: [{ code: "very_hard" }, { code: "recent_finger", date: "2026-10-23" }],
            },
          }),
        ])}
      />,
    );
    expect(screen.getByText(/very hard session in the 3 days before/)).toBeTruthy();
    expect(screen.getByText(/hard finger day less than 72 h before/)).toBeTruthy();
    expect(screen.getByText(/The test stays where it is/)).toBeTruthy();
  });

  it("explains why there is no next test", () => {
    render(
      <RetestStatusCard
        status={status([axis({ next_test: null, next_test_reason: "blocked:phase" })])}
      />,
    );
    expect(screen.getByText(/performance and deload phases/)).toBeTruthy();
  });

  it("labels a projected test as the earliest day", () => {
    render(
      <RetestStatusCard
        status={status([
          axis({
            next_test: {
              date: "2026-10-22",
              session_id: "test_max_hang_7s",
              source: "projected",
              trigger: "end_of_phase_slipped",
              reason: null,
              blockers: [],
            },
          }),
        ])}
      />,
    );
    expect(screen.getByText(/Next test from/)).toBeTruthy();
  });
});
