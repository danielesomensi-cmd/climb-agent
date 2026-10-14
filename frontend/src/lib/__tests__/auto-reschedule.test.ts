/**
 * A315 — automatic key re-schedule: toast text and the Undo event.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const toastMock = vi.hoisted(() => Object.assign(vi.fn(), { error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toastMock }));

import { autoRescheduleText, showAutoReschedules, undoAutoRescheduleEvent, type AutoReschedule } from "@/lib/auto-reschedule";

const replaced: AutoReschedule = {
  adaptation_id: "ar_2026-10-11_evening_strength_long",
  keys: ["finger_max", "pulling_max"],
  date: "2026-10-11",
  slot: "evening",
  session_id: "strength_long",
  session_name: "Strength long",
  replaced: { date: "2026-10-11", slot: "evening", session_id: "finger_maintenance_gym",
              session_name: "Finger maintenance gym" },
};

describe("auto-reschedule", () => {
  beforeEach(() => {
    toastMock.mockReset();
    toastMock.error.mockReset();
  });

  it("names the keys, the day and what was replaced", () => {
    expect(autoRescheduleText(replaced)).toEqual({
      title: "Finger max + Max pulling moved to Sun 11/10",
      description: "Strength long on Sun 11/10 evening, in place of Finger maintenance gym.",
    });
    expect(autoRescheduleText({ ...replaced, replaced: null, keys: ["limit_power", "try_hard"] }).title)
      .toBe("Limit moved to Sun 11/10");
  });

  it("builds the undo event", () => {
    expect(undoAutoRescheduleEvent(replaced)).toEqual({
      event_type: "undo_auto_reschedule", adaptation_id: "ar_2026-10-11_evening_strength_long",
    });
  });

  it("shows one toast per re-schedule and Undo goes through the events queue", async () => {
    const run = vi.fn().mockResolvedValue({});
    showAutoReschedules([replaced], run);
    expect(toastMock).toHaveBeenCalledTimes(1);
    const opts = toastMock.mock.calls[0][1];
    expect(opts.action.label).toBe("Undo");
    opts.action.onClick();
    expect(run).toHaveBeenCalledWith([undoAutoRescheduleEvent(replaced)]);
    await Promise.resolve();
    await Promise.resolve();
    expect(toastMock).toHaveBeenLastCalledWith("Re-schedule undone");
  });

  it("does nothing without re-schedules", () => {
    showAutoReschedules(undefined, vi.fn());
    showAutoReschedules([], vi.fn());
    expect(toastMock).not.toHaveBeenCalled();
  });

  it("reports a refused undo", async () => {
    const run = vi.fn().mockRejectedValue(new Error("the re-scheduled session was already used or edited"));
    showAutoReschedules([replaced], run);
    toastMock.mock.calls[0][1].action.onClick();
    await new Promise((r) => setTimeout(r, 0));
    expect(toastMock.error).toHaveBeenCalledWith("the re-scheduled session was already used or edited");
  });
});
