/**
 * @vitest-environment jsdom
 *
 * B297 + A289 review — the card shows placement failures only: the historical
 * `no_placement_slot` and the retest policy's `blocked:no_paired_slot` (hang
 * placed, no later day for the pull-up). Policy decisions such as
 * `blocked:phase` or `slipped:gap` are not failures and stay hidden.
 */

import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { SkippedTestsCard } from "../skipped-tests-card";
import type { SkippedTest } from "@/lib/types";

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

function skipped(over: Partial<SkippedTest>): SkippedTest {
  return {
    test_id: "test_max_weighted_pullup",
    axis: "pulling",
    reason: "no_placement_slot",
    required: true,
    ...over,
  } as SkippedTest;
}

describe("SkippedTestsCard", () => {
  it("shows the legacy placement failure", () => {
    render(<SkippedTestsCard skipped={[skipped({})]} weekKey="2026-10-19" />);
    expect(screen.getByText(/Couldn.t schedule a test this week/)).toBeTruthy();
  });

  it("shows a pull-up the paired test day could not fit", () => {
    render(
      <SkippedTestsCard
        skipped={[skipped({ reason: "blocked:no_paired_slot" })]}
        weekKey="2026-10-19"
      />,
    );
    expect(screen.getByText(/Pulling strength test/)).toBeTruthy();
  });

  it("hides the policy's decisions", () => {
    const { container } = render(
      <SkippedTestsCard
        skipped={[
          skipped({ reason: "blocked:phase" }),
          skipped({ reason: "slipped:gap", axis: "finger", test_id: "test_max_hang_7s" }),
        ]}
        weekKey="2026-10-19"
      />,
    );
    expect(container.textContent).toBe("");
  });

  it("hides optional tests", () => {
    const { container } = render(
      <SkippedTestsCard skipped={[skipped({ required: false })]} weekKey="2026-10-19" />,
    );
    expect(container.textContent).toBe("");
  });
});
