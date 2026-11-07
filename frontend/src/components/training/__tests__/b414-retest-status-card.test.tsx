/**
 * @vitest-environment jsdom
 *
 * B414 (B414-4, A319-FE, A320-FE superseded) — the tested-maxes card on /week:
 * until when each max is valid («Valid until», «Extended to», «Expired after
 * … — your ladders and loads keep going»), the texts of the new reasons
 * (end of the cycle, declined, postponed to <until>, the pull-up waiting for
 * the hang test's day), the athlete's request, the two choices of the expiry
 * card, and «Undo postpone» (DELETE, dry run first). No «Not now».
 */
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";

const { api, toast } = vi.hoisted(() => ({
  api: {
    requestRetest: vi.fn<(d: unknown) => Promise<unknown>>(),
    extendRetest: vi.fn<(d: unknown) => Promise<unknown>>(),
    undoRetestDecline: vi.fn<(axis: string, dry: boolean) => Promise<unknown>>(),
  },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({
  requestRetest: (d: unknown) => api.requestRetest(d),
  extendRetest: (d: unknown) => api.extendRetest(d),
  undoRetestDecline: (axis: string, dry: boolean) => api.undoRetestDecline(axis, dry),
  apiErrorDetail: (_err: unknown, fallback: string) => fallback,
}));
vi.mock("sonner", () => ({ toast }));

import { RetestStatusCard } from "../retest-status-card";
import type { RetestAxisStatus, RetestStatus } from "@/lib/types";

function axis(over: Partial<RetestAxisStatus> = {}): RetestAxisStatus {
  return {
    axis: "finger",
    covered: true,
    protocol: "max_hang_7s_total_load",
    official_total_kg: 116,
    test_date: "2026-09-24",
    age_days: 44,
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
    expiring: false,
    extended: false,
    tested_until: "2026-12-22",
    declines: [],
    request: null,
    plan_edit_declines: [],
    ...over,
  };
}

function status(axes: RetestAxisStatus[]): RetestStatus {
  return {
    as_of: "2026-11-07",
    stable_band_pct: 5,
    axes: Object.fromEntries(axes.map((a) => [a.axis, a])),
    covered_axes: axes.filter((a) => a.covered).map((a) => a.axis),
  };
}

beforeEach(() => {
  api.undoRetestDecline.mockReset();
  toast.success.mockClear();
});
afterEach(cleanup);

describe("validity of the max", () => {
  it("valid until / extended to / expired after (nothing stops)", () => {
    render(
      <RetestStatusCard
        status={status([
          axis({}),
          axis({ axis: "pulling", extended: true, valid_until: "2027-01-19", protocol: "weighted_pullup_2rm" }),
        ])}
      />,
    );
    expect(screen.getByText("Valid until 22 Dec")).toBeTruthy();
    expect(screen.getByText("Extended to 19 Jan")).toBeTruthy();
    cleanup();
    render(<RetestStatusCard status={status([axis({ expired: true })])} />);
    expect(screen.getByText("Expired after 22 Dec — your ladders and loads keep going")).toBeTruthy();
  });
});

describe("why there is no next test", () => {
  it.each([
    ["after_cycle_end", {}, /the cycle ends first — the next cycle opens with the tests/],
    ["declined", {}, /you declined this test/],
    [
      "postponed",
      { declines: [{ axis: "finger", kind: "postpone", trigger: "expiry", reason: "other", declined_at: "2026-11-07", until: "2027-01-19", source: "app" }] },
      /you postponed it to 19 Jan/,
    ],
    ["blocked:no_paired_slot", {}, /the pull-up test needs the hang test's day, with weights there: it waits for its next turn/],
  ])("%s", (reason, over, text) => {
    render(<RetestStatusCard status={status([axis({ next_test_reason: reason, ...(over as Partial<RetestAxisStatus>) })])} />);
    expect(screen.getByText(text)).toBeTruthy();
  });

  it("an axis the policy does not schedule no longer reads «older than 90 days»", () => {
    render(<RetestStatusCard status={status([axis({ covered: false, next_test_reason: "not_tested_recently" })])} />);
    expect(screen.queryByText(/older than 90 days/)).toBeNull();
    expect(screen.getByText(/periodic test reminder covers it/)).toBeTruthy();
  });

  it("the athlete's request is shown", () => {
    render(<RetestStatusCard status={status([axis({ request: { requested_at: "2026-11-07", source: "app" } })])} />);
    expect(screen.getByText("You asked for the test on 7 Nov.")).toBeTruthy();
  });
});

describe("the choices", () => {
  it("without onChanged (read-only use) no buttons", () => {
    render(<RetestStatusCard status={status([axis({})])} />);
    expect(screen.queryByRole("button", { name: "Do the test" })).toBeNull();
  });

  it("with onChanged: Do the test and Postpone the expiry, never «Not now»", () => {
    render(<RetestStatusCard status={status([axis({})])} onChanged={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Do the test" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Postpone the expiry" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /not now/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /undo postpone/i })).toBeNull();
  });

  it("Undo postpone: dry run shows the validity it goes back to, then the DELETE", async () => {
    const postponed = axis({
      extended: true,
      valid_until: "2027-01-19",
      declines: [{ axis: "finger", kind: "postpone", trigger: "expiry", reason: "other", declined_at: "2026-11-07", until: "2027-01-19", source: "app" }],
    });
    api.undoRetestDecline
      .mockResolvedValueOnce({ dry_run: true, removed: [{}], tests_removed: [], weeks_marked_stale: [], retest_status: status([axis({})]) })
      .mockResolvedValueOnce({ dry_run: false, removed: [{}], tests_removed: [], weeks_marked_stale: [], retest_status: status([axis({})]) });
    const onChanged = vi.fn();
    render(<RetestStatusCard status={status([postponed])} onChanged={onChanged} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /undo postpone \(finger/i }));
    });
    expect(api.undoRetestDecline).toHaveBeenLastCalledWith("finger", true);
    expect(screen.getByText("Your max goes back to valid until 22 Dec.")).toBeTruthy();
    expect(onChanged).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^undo postpone$/i }));
    });
    expect(api.undoRetestDecline).toHaveBeenLastCalledWith("finger", false);
    expect(toast.success).toHaveBeenCalledWith("Postpone undone.");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("Undo postpone: an error is shown, nothing reloads", async () => {
    const postponed = axis({
      declines: [{ axis: "finger", kind: "postpone", trigger: "expiry", reason: "other", declined_at: "2026-11-07", until: "2027-01-19", source: "app" }],
    });
    api.undoRetestDecline.mockRejectedValueOnce(new Error("x"));
    const onChanged = vi.fn();
    render(<RetestStatusCard status={status([postponed])} onChanged={onChanged} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /undo postpone/i }));
    });
    expect(screen.getByText(/couldn't check your plan/i)).toBeTruthy();
    expect(onChanged).not.toHaveBeenCalled();
  });
});
