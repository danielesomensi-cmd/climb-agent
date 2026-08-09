/**
 * @vitest-environment jsdom
 *
 * B330 — double-tapping "Log Session" must POST once.
 *
 * Context: the duplicate outdoor bookkeeping rows found in production on
 * 2026-08-09 were NOT caused by this (they came from the client calling
 * `complete_outdoor` on top of the server-side plan sync B277 already does,
 * fixed server-side in B329). But the form had no synchronous guard either, so
 * a genuine double tap fired two POSTs — each re-running the plan sync and
 * recomputing the day's ripple. This pins the guard.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor } from "@testing-library/react";

const postOutdoorLog = vi.fn();
const putOutdoorLog = vi.fn();

vi.mock("@/lib/api", () => ({
  postOutdoorLog: (...a: unknown[]) => postOutdoorLog(...a),
  putOutdoorLog: (...a: unknown[]) => putOutdoorLog(...a),
}));
vi.mock("sonner", () => ({ toast: vi.fn() }));
vi.mock("@/lib/outbox", () => ({ enqueue: vi.fn(() => false) }));

import OutdoorLogForm from "../OutdoorLogForm";

afterEach(cleanup);

const saveButton = () =>
  screen.getByRole("button", { name: /Log Session|Saving/ }) as HTMLButtonElement;

describe("OutdoorLogForm — double submit", () => {
  let release: () => void;

  beforeEach(() => {
    postOutdoorLog.mockReset();
    putOutdoorLog.mockReset();
    postOutdoorLog.mockImplementation(
      () =>
        new Promise<void>((r) => {
          release = r;
        }),
    );
  });

  function renderForm(onSuccess = vi.fn()) {
    render(
      <OutdoorLogForm
        spots={[]}
        defaultDate="2026-08-08"
        defaultSpotName="Berdorf"
        defaultDiscipline="lead"
        onSuccess={onSuccess}
      />,
    );
    return onSuccess;
  }

  it("posts once for two taps in the same batch", async () => {
    renderForm();
    await act(async () => {
      saveButton().click();
      saveButton().click();
    });
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
  });

  it("stays locked while the request is in flight", async () => {
    renderForm();
    await act(async () => {
      saveButton().click();
    });
    expect(saveButton().disabled).toBe(true);
    await act(async () => {
      saveButton().click();
      saveButton().click();
    });
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
  });

  it("calls onSuccess once, so the follow-up plan sync fires once", async () => {
    const onSuccess = renderForm();
    await act(async () => {
      saveButton().click();
      saveButton().click();
    });
    await act(async () => {
      release();
    });
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("does not submit at all without a spot name", async () => {
    render(
      <OutdoorLogForm spots={[]} defaultDate="2026-08-08" defaultSpotName="" />,
    );
    await act(async () => {
      saveButton().click();
    });
    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(screen.getByText("Spot name is required")).toBeTruthy();
  });

  it("re-enables after a failure so the user can retry", async () => {
    postOutdoorLog.mockRejectedValueOnce(new Error("boom"));
    renderForm();
    await act(async () => {
      saveButton().click();
    });
    await waitFor(() => expect(saveButton().disabled).toBe(false));
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);

    await act(async () => {
      saveButton().click();
    });
    expect(postOutdoorLog).toHaveBeenCalledTimes(2);
  });
});
