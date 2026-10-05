/**
 * @vitest-environment jsdom
 *
 * A300 — the availability editor writes the slot structure only when the user
 * sets it. An untouched save must send the same payload as before A300 (the
 * backend guarantees byte-identical plans only for users without the fields).
 */

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";

import { AvailabilityEditor } from "../availability-editor";

afterEach(cleanup);

// Radix Slider needs ResizeObserver, which jsdom lacks.
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

const availability = {
  mon: { evening: { available: true, preferred_location: "gym", gym_id: "g1" } },
  tue: {
    lunch: { available: true, preferred_location: "gym", gym_id: "work" },
    evening: { available: true, preferred_location: "gym", gym_id: "g1" },
  },
};
const prefs = { target_training_days_per_week: 2, hard_day_cap_per_week: 2 };
const gyms = [{ gym_id: "g1", name: "Boulder", equipment: [] }, { gym_id: "work", name: "Work", equipment: [] }];

function setup(
  initialAvailability: Record<string, Record<string, unknown>> = availability,
  initialPrefs: Record<string, unknown> = prefs,
  keptPreview?: Array<{ date: string; slot: string; name: string }>,
) {
  const onSave = vi.fn();
  render(
    <AvailabilityEditor
      initialAvailability={initialAvailability}
      initialPlanningPrefs={initialPrefs as typeof prefs}
      gyms={gyms}
      onSave={onSave}
      onCancel={() => {}}
      keptPreview={keptPreview}
    />,
  );
  return onSave;
}

const save = () => fireEvent.click(screen.getByRole("button", { name: /Save & regenerate plan/ }));

describe("AvailabilityEditor — A300 slot structure", () => {
  it("an untouched save sends no structure field and no rotation", () => {
    const onSave = setup();
    save();
    const [avail, p] = onSave.mock.calls[0];
    expect(avail.tue.lunch).toEqual({ available: true, preferred_location: "gym", gym_id: "work" });
    expect(avail.mon.evening).toEqual({ available: true, preferred_location: "gym", gym_id: "g1" });
    expect(p).toEqual(prefs);
    expect("complementary_rotation" in p).toBe(false);
  });

  it("marks a lunch complementary with a time limit, and the rotation shows up", () => {
    const onSave = setup();
    const row = screen.getByTestId("slot-structure-tue-lunch");
    fireEvent.click(within(row).getByRole("radio", { name: "Complementary" }));
    fireEvent.change(within(row).getByLabelText("Max minutes"), { target: { value: "45" } });
    expect(screen.getByTestId("complementary-rotation")).toBeTruthy();
    save();
    const [avail, p] = onSave.mock.calls[0];
    expect(avail.tue.lunch).toMatchObject({ role: "complementary", max_minutes: 45 });
    // The rotation was not edited: the engine default applies, nothing is sent.
    expect("complementary_rotation" in p).toBe(false);
  });

  it("an edited rotation is sent in order", () => {
    const onSave = setup({ tue: { lunch: { available: true, preferred_location: "gym", gym_id: "work", role: "complementary" } } }, prefs);
    const rot = screen.getByTestId("complementary-rotation");
    fireEvent.click(within(rot).getByRole("button", { name: "Remove Legs" }));
    fireEvent.click(within(rot).getByRole("button", { name: "Move Zone 2 cardio (treadmill) up" }));
    save();
    expect(onSave.mock.calls[0][1].complementary_rotation).toEqual(["z2", "hiit", "upper_push_arms"]);
  });

  it("an invalid max minutes disables the save", () => {
    setup();
    const row = screen.getByTestId("slot-structure-mon-evening");
    fireEvent.change(within(row).getByLabelText("Max minutes"), { target: { value: "5" } });
    expect(screen.getByRole("button", { name: /Save & regenerate plan/ }).hasAttribute("disabled")).toBe(true);
  });

  it("back to 'Any' on a slot that never had a role sends no role key", () => {
    const onSave = setup();
    const row = screen.getByTestId("slot-structure-mon-evening");
    fireEvent.click(within(row).getByRole("radio", { name: "Primary" }));
    fireEvent.click(within(row).getByRole("radio", { name: "Any" }));
    save();
    expect("role" in onSave.mock.calls[0][0].mon.evening).toBe(false);
  });

  it("a complementary slot is not a training day", () => {
    // Monday's only slot is complementary: Monday is not a training day for
    // the primary passes (its slot has its own budget). The targets start in
    // range (jsdom cannot lay out a Radix slider whose min equals its max).
    setup(
      {
        ...availability,
        mon: { evening: { available: true, preferred_location: "gym", gym_id: "g1", role: "complementary" } },
        wed: { evening: { available: true, preferred_location: "gym", gym_id: "g1" } },
      },
      prefs,
    );
    expect(screen.getByText(/2 days with availability · 1 complementary slot/)).toBeTruthy();
  });

  it("says before saving which of the user's sessions are kept", () => {
    setup(availability, prefs, [{ date: "2026-10-06", slot: "evening", name: "Work — HIIT" }]);
    const note = screen.getByTestId("kept-preview").textContent ?? "";
    expect(note).toContain("Your session stays: Work — HIIT (2026-10-06 evening).");
    expect(note).toContain("Done and past sessions never change.");
  });

  it("shows no preview while the week is unknown", () => {
    setup();
    expect(screen.queryByTestId("kept-preview")).toBeNull();
  });
});
