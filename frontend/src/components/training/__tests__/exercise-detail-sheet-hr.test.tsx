/**
 * @vitest-environment jsdom
 *
 * A317 — the exercise sheet shows the A316 heart-rate band: bpm with a recorded
 * HRmax, percentages + a Settings hint without, nothing on non-cardio rows.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

const userState = vi.hoisted(() => ({ current: null as unknown, enabled: [] as boolean[] }));
vi.mock("@/lib/hooks/use-state", () => ({
  useUserState: (enabled = true) => {
    userState.enabled.push(enabled);
    return { state: enabled ? userState.current : null, loading: false, error: null, refresh: vi.fn() };
  },
}));

import { ExerciseDetailSheet } from "../exercise-detail-sheet";

afterEach(() => {
  cleanup();
  userState.current = null;
  userState.enabled = [];
});

const hiit = {
  exercise_id: "treadmill_hiit_4x4",
  name: "Treadmill HIIT 4x4",
  prescription: { sets: 4, work_seconds: 240, rest_between_sets_seconds: 180 },
  hr_target: { basis: "hr_max", work_pct: [90, 95], recovery_pct: [65, 75] },
};

describe("ExerciseDetailSheet heart rate (A317)", () => {
  it("shows the bands in bpm with a recorded HRmax", () => {
    userState.current = { body: { hr_max_bpm: 190 } };
    render(<ExerciseDetailSheet open onOpenChange={() => {}} exercise={hiit} />);
    expect(screen.getByTestId("hr-target").textContent).toBe("Work 171-180 bpm · Recovery 124-142 bpm");
    expect(screen.queryByText(/Set your max heart rate/)).toBeNull();
  });

  it("falls back to percentages and the Settings hint without HRmax", () => {
    userState.current = { body: {} };
    render(<ExerciseDetailSheet open onOpenChange={() => {}} exercise={hiit} />);
    expect(screen.getByTestId("hr-target").textContent).toBe("Work 90-95% HRmax · Recovery 65-75% HRmax");
    expect(screen.getByText(/Set your max heart rate in Settings/)).toBeTruthy();
  });

  it("renders nothing and fetches no state for a non-cardio exercise", () => {
    userState.current = { body: { hr_max_bpm: 190 } };
    render(
      <ExerciseDetailSheet
        open
        onOpenChange={() => {}}
        exercise={{ exercise_id: "pullup", name: "Pull-up", prescription: { sets: 3, reps: 8 } }}
      />,
    );
    expect(screen.queryByTestId("hr-target")).toBeNull();
    expect(userState.enabled).not.toContain(true);
  });
});
