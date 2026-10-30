/**
 * @vitest-environment jsdom
 *
 * B408 — the manual-completion dialog pre-filled a slot constant (lunch 35',
 * evening 90') whatever the session said, while the card above it showed the
 * session's own "~N min". Lunch sessions go to 55' (C279): the constant must
 * not win when the session knows its duration. And the dialog stays mounted
 * between sessions, so the pre-fill must follow the session being completed.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import type { ComponentProps } from "react";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

import { FeedbackDialog, durationPrefillMinutes } from "@/components/training/feedback-dialog";
import { sessionEstimatedMinutes } from "@/lib/feedback-items";

afterEach(cleanup);

const durationInput = () => document.getElementById("session-duration") as HTMLInputElement;

type OnSubmit = ComponentProps<typeof FeedbackDialog>["onSubmit"];

function dialog(props: { estimatedMinutes?: number; slot?: string; onSubmit?: OnSubmit }) {
  return (
    <FeedbackDialog
      open
      onClose={vi.fn()}
      onSubmit={props.onSubmit ?? vi.fn()}
      exercises={[]}
      estimatedMinutes={props.estimatedMinutes}
      slot={props.slot}
    />
  );
}

describe("B408 — sessionEstimatedMinutes (the card's ~N min)", () => {
  it("catalog session: resolved.session.target_duration_min", () => {
    expect(sessionEstimatedMinutes({ resolved: { session: { target_duration_min: 55 } } })).toBe(55);
  });

  it("custom/adhoc: the top-level estimate (B298)", () => {
    expect(sessionEstimatedMinutes({ is_custom: true, target_duration_min: 45, resolved: null })).toBe(45);
  });

  it("the resolved estimate wins over the top-level one, as on the card", () => {
    expect(
      sessionEstimatedMinutes({ is_custom: true, target_duration_min: 45, resolved: { session: { target_duration_min: 50 } } }),
    ).toBe(50);
  });

  it("unknown → undefined: no estimate, zero, a non-custom top-level field, no session", () => {
    expect(sessionEstimatedMinutes({ resolved: { session: {} } })).toBeUndefined();
    expect(sessionEstimatedMinutes({ resolved: { session: { target_duration_min: 0 } } })).toBeUndefined();
    expect(sessionEstimatedMinutes({ target_duration_min: 40 })).toBeUndefined();
    expect(sessionEstimatedMinutes(null)).toBeUndefined();
  });
});

describe("B408 — durationPrefillMinutes", () => {
  it("the session's estimate wins over the slot constant", () => {
    expect(durationPrefillMinutes(55, "lunch")).toBe(55);
    expect(durationPrefillMinutes(70, "evening")).toBe(70);
  });

  it("falls back to the slot constant only when the estimate is unknown", () => {
    expect(durationPrefillMinutes(undefined, "lunch")).toBe(55);
    expect(durationPrefillMinutes(0, "evening")).toBe(120);
    expect(durationPrefillMinutes(undefined, undefined)).toBe(60);
    expect(durationPrefillMinutes(undefined, "night")).toBe(60);
  });
});

describe("B408 — the dialog's duration field", () => {
  it("pre-fills the session's estimate, not the lunch constant", () => {
    render(dialog({ estimatedMinutes: 47, slot: "lunch" }));
    expect(durationInput().value).toBe("47");
  });

  it("without an estimate, the slot constant", () => {
    render(dialog({ slot: "lunch" }));
    expect(durationInput().value).toBe("55");
  });

  it("follows the session when the mounted dialog is reused for another one", () => {
    const { rerender } = render(dialog({ slot: "" }));
    rerender(dialog({ estimatedMinutes: 55, slot: "lunch" }));
    expect(durationInput().value).toBe("55");
    rerender(dialog({ estimatedMinutes: 90, slot: "evening" }));
    expect(durationInput().value).toBe("90");
  });

  it("submitted untouched → the session's estimate; typed → what was typed", async () => {
    const onSubmit = vi.fn<OnSubmit>();
    render(dialog({ estimatedMinutes: 55, slot: "lunch", onSubmit }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Submit feedback" }));
    });
    expect(onSubmit.mock.calls[0][1]).toBe(55);

    fireEvent.change(durationInput(), { target: { value: "48" } });
    expect(durationInput().value).toBe("48");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Submit feedback" }));
    });
    expect(onSubmit.mock.calls[1][1]).toBe(48);
    // Submitting resets the field to the pre-fill.
    expect(durationInput().value).toBe("55");
  });
});
