/**
 * @vitest-environment jsdom
 *
 * B414 (B414-4) — the Today card of a tested max that expires (model A,
 * Daniele 07/11): from 14 days before `valid_until`, and after it until a
 * choice is made, only «Do the test» and «Postpone the expiry» (2/4/6 weeks,
 * default 4, one button for both axes). Not dismissable. Dry run → summary →
 * confirm; an endpoint error is always shown, nothing pretends to be saved.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";

const { api, toast } = vi.hoisted(() => ({
  api: {
    requestRetest: vi.fn<(d: unknown) => Promise<unknown>>(),
    extendRetest: vi.fn<(d: unknown) => Promise<unknown>>(),
  },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({
  requestRetest: (d: unknown) => api.requestRetest(d),
  extendRetest: (d: unknown) => api.extendRetest(d),
  apiErrorDetail: (err: unknown, fallback: string) =>
    err instanceof Error && err.message.startsWith("detail:") ? err.message.slice(7) : fallback,
}));
vi.mock("sonner", () => ({ toast }));

import { TestExpiryCard, testExpiryVisible } from "../test-expiry-card";
import type { RetestAxisStatus, RetestStatus } from "@/lib/types";

function axis(over: Partial<RetestAxisStatus> = {}): RetestAxisStatus {
  return {
    axis: "finger",
    covered: true,
    protocol: "max_hang_7s_total_load",
    official_total_kg: 116,
    test_date: "2026-09-24",
    age_days: 80,
    confidence: "low",
    confidence_exposures: 0,
    confidence_min_exposures: 2,
    trend: null,
    delta_pct: null,
    previous_date: null,
    earliest_retest: "2026-11-05",
    signals: { count: 0, needed: 2 },
    fatigue: null,
    next_test: null,
    next_test_reason: "after_cycle_end",
    valid_until: "2026-12-22",
    expired: false,
    expiring: true,
    extended: false,
    declines: [],
    request: null,
    ...over,
  };
}

function status(axes: RetestAxisStatus[]): RetestStatus {
  return {
    as_of: "2026-12-10",
    stable_band_pct: 5,
    axes: Object.fromEntries(axes.map((a) => [a.axis, a])),
    covered_axes: axes.filter((a) => a.covered).map((a) => a.axis),
  };
}

const BOTH = [axis(), axis({ axis: "pulling", protocol: "weighted_pullup_2rm", official_total_kg: 123 })];

async function click(name: RegExp) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
}

beforeEach(() => {
  api.requestRetest.mockReset();
  api.extendRetest.mockReset();
  toast.success.mockClear();
});
afterEach(cleanup);

describe("when the card shows", () => {
  it("not before the 14-day window", () => {
    const s = status([axis({ expiring: false }), axis({ axis: "pulling", expiring: false })]);
    expect(testExpiryVisible(s)).toBe(false);
    const { container } = render(<TestExpiryCard status={s} onChanged={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("in the window: both axes, the validity day, the two choices, no ✕", () => {
    render(<TestExpiryCard status={status(BOTH)} onChanged={vi.fn()} />);
    expect(screen.getByText("Your finger and pull-up test is valid until 22 Dec")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Do the test" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Postpone the expiry" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /dismiss|not now/i })).toBeNull();
  });

  it("after the expiry it stays, and says nothing stopped", () => {
    render(<TestExpiryCard status={status([axis({ expiring: false, expired: true })])} onChanged={vi.fn()} />);
    expect(screen.getByText("Your finger test expired after 22 Dec")).toBeTruthy();
    expect(screen.getByText(/ladders and loads stay where they are/)).toBeTruthy();
  });

  it("a choice already made hides it: a request, a planned test, a postpone (out of the window)", () => {
    expect(testExpiryVisible(status([axis({ request: { requested_at: "2026-12-10", source: "app" } })]))).toBe(false);
    expect(
      testExpiryVisible(
        status([
          axis({
            next_test: { date: "2026-12-15", session_id: "test_max_hang_7s", source: "planned", trigger: "maintenance", reason: null, blockers: [] },
          }),
        ]),
      ),
    ).toBe(false);
    expect(testExpiryVisible(status([axis({ expiring: false, extended: true, valid_until: "2027-01-19" })]))).toBe(false);
    // A projected test is not a choice: the card stays.
    expect(
      testExpiryVisible(
        status([
          axis({
            next_test: { date: "2026-12-15", session_id: "test_max_hang_7s", source: "projected", trigger: "maintenance", reason: null, blockers: [] },
          }),
        ]),
      ),
    ).toBe(true);
  });

  it("an axis the policy does not schedule never shows it", () => {
    expect(testExpiryVisible(status([axis({ covered: false })]))).toBe(false);
  });
});

describe("Do the test", () => {
  it("dry run, summary, then the real request; the week reloads", async () => {
    api.requestRetest
      .mockResolvedValueOnce({ dry_run: true, action: "requested", axes: {}, go_to: "2026-12-12", weeks_marked_stale: [], retest_status: null })
      .mockResolvedValueOnce({ dry_run: false, action: "requested", axes: {}, go_to: "2026-12-12", weeks_marked_stale: [], retest_status: null });
    const onChanged = vi.fn();
    render(<TestExpiryCard status={status(BOTH)} onChanged={onChanged} />);
    await click(/^do the test$/i);
    expect(api.requestRetest).toHaveBeenLastCalledWith({ dry_run: true });
    expect(screen.getByText(/The test goes on 12 Dec/)).toBeTruthy();
    expect(onChanged).not.toHaveBeenCalled();
    await click(/request the test/i);
    expect(api.requestRetest).toHaveBeenLastCalledWith({});
    expect(toast.success).toHaveBeenCalledWith("Test requested — it goes on 12 Dec.");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("after the end of the cycle: «Start a new cycle», nothing written", async () => {
    api.requestRetest.mockResolvedValueOnce({ dry_run: true, action: "cycle_ended", axes: {}, go_to: null, weeks_marked_stale: [], retest_status: null });
    const onCycleEnded = vi.fn();
    render(<TestExpiryCard status={status(BOTH)} onChanged={vi.fn()} onCycleEnded={onCycleEnded} />);
    await click(/^do the test$/i);
    expect(screen.getByText(/the next one opens with the tests/)).toBeTruthy();
    await click(/start a new cycle/i);
    expect(onCycleEnded).toHaveBeenCalledTimes(1);
    expect(api.requestRetest).toHaveBeenCalledTimes(1);
  });

  it("an endpoint error is shown, nothing is confirmed", async () => {
    api.requestRetest.mockRejectedValueOnce(new Error("detail:No tested axis"));
    const onChanged = vi.fn();
    render(<TestExpiryCard status={status(BOTH)} onChanged={onChanged} />);
    await click(/^do the test$/i);
    expect(screen.getByText("No tested axis")).toBeTruthy();
    expect(onChanged).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe("Postpone the expiry", () => {
  it("4 weeks by default; the athlete picks 6; dry run, summary, confirm", async () => {
    api.extendRetest
      .mockResolvedValueOnce({ dry_run: true, weeks: 6, until: "2027-02-02", extensions: [], tests_removed: [{ date: "2026-12-15", session_id: "test_max_hang_7s" }], kept_user_owned_tests: [], weeks_marked_stale: [], retest_status: null })
      .mockResolvedValueOnce({ dry_run: false, weeks: 6, until: "2027-02-02", extensions: [], tests_removed: [], kept_user_owned_tests: [], weeks_marked_stale: [], retest_status: null });
    const onChanged = vi.fn();
    render(<TestExpiryCard status={status(BOTH)} onChanged={onChanged} />);
    await click(/postpone the expiry/i);
    expect(screen.getByRole("radio", { name: "4 weeks" }).getAttribute("aria-checked")).toBe("true");
    await act(async () => {
      fireEvent.click(screen.getByRole("radio", { name: "6 weeks" }));
    });
    await click(/^continue$/i);
    expect(api.extendRetest).toHaveBeenLastCalledWith({ weeks: 6, dry_run: true });
    expect(screen.getByText(/valid until 2 Feb\. The planned test leaves the plan/)).toBeTruthy();
    await click(/^postpone$/i);
    expect(api.extendRetest).toHaveBeenLastCalledWith({ weeks: 6 });
    expect(toast.success).toHaveBeenCalledWith("Expiry postponed — your max is valid until 2 Feb.");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("Cancel on the summary writes nothing", async () => {
    api.extendRetest.mockResolvedValueOnce({ dry_run: true, weeks: 4, until: "2027-01-19", extensions: [], tests_removed: [], kept_user_owned_tests: [], weeks_marked_stale: [], retest_status: null });
    const onChanged = vi.fn();
    render(<TestExpiryCard status={status(BOTH)} onChanged={onChanged} />);
    await click(/postpone the expiry/i);
    await click(/^continue$/i);
    expect(api.extendRetest).toHaveBeenLastCalledWith({ weeks: 4, dry_run: true });
    await click(/^cancel$/i);
    expect(api.extendRetest).toHaveBeenCalledTimes(1);
    expect(onChanged).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Do the test" })).toBeTruthy();
  });
});
