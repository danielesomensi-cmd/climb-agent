/**
 * @vitest-environment jsdom
 *
 * A300 + A301 — the alerts card on /week (whole week + unmet complementary
 * slots) and on /today (one day). Heads-up wording only.
 */

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { WeekAlertsCard } from "../week-alerts-card";
import type { GuardWarning, WeekPlan } from "@/lib/types";

afterEach(cleanup);

const guard: GuardWarning = {
  code: "hard_back_to_back",
  severity: "warning",
  date: "2026-10-07",
  slot: "evening",
  session_id: "limit_boulder_gym",
  name: "Limit boulder",
  user_owned: true,
  with: [{ date: "2026-10-06", slot: "evening", session_id: "strength_long" }],
  message: "Limit boulder on 2026-10-07 is a hard session the day after Strength long on 2026-10-06: back-to-back hard days.",
};

const plan = {
  weeks: [{ days: [] }],
  secondary_warnings: [
    { date: "2026-10-06", slot: "lunch", session_id: "upper_push_arms_lunch", focus: "upper_push_arms", code: "biceps_before_heavy_pull", with: ["2026-10-07 weighted_pullups"] },
  ],
  unmet_secondary: [{ date: "2026-10-09", slot: "lunch", focus: "hiit", reason: "no_session_fits", candidates: ["treadmill_hiit_4x4"] }],
} as unknown as WeekPlan;

describe("WeekAlertsCard", () => {
  it("renders nothing without alerts (no empty card for users without A300/A301 data)", () => {
    const { container } = render(<WeekAlertsCard guardWarnings={[]} weekPlan={{ weeks: [{ days: [] }] } as unknown as WeekPlan} />);
    expect(container.innerHTML).toBe("");
    const { container: c2 } = render(<WeekAlertsCard guardWarnings={null} weekPlan={null} />);
    expect(c2.innerHTML).toBe("");
  });

  it("lists guard + lunch-rule alerts and free complementary slots for the week", () => {
    render(<WeekAlertsCard guardWarnings={[guard]} weekPlan={plan} />);
    expect(screen.getByText("2 alerts this week")).toBeTruthy();
    expect(screen.getByText("Back-to-back hard days")).toBeTruthy();
    expect(screen.getByText("Biceps before heavy pulling")).toBeTruthy();
    expect(screen.getByText("Complementary slots left free")).toBeTruthy();
    expect(screen.getByText(/no HIIT \(treadmill\) session fits/)).toBeTruthy();
    const text = screen.getByTestId("week-alerts-card").textContent ?? "";
    expect(text).toContain("your sessions stay as planned");
    expect(text).not.toMatch(/downgrad|eased|blocked|anyway/i);
  });

  it("filters one day on /today", () => {
    render(<WeekAlertsCard guardWarnings={[guard]} weekPlan={plan} date="2026-10-07" compact />);
    expect(screen.getByText("1 alert today")).toBeTruthy();
    expect(screen.queryByText("Biceps before heavy pulling")).toBeNull();
    expect(screen.queryByText("Complementary slots left free")).toBeNull();
  });
});
