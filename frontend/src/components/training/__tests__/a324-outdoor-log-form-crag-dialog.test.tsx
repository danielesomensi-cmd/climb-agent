/**
 * @vitest-environment jsdom
 *
 * A324 — residuals of B401 (B-OUTDOOR-CRAG-PICKER points 2 and 4).
 *
 * «Log outdoor» (Today / Week) and «Quick log» (/outdoor) open the day's crag
 * in EDIT mode, and the edit now names that crag (`original_spot_name`), which
 * makes a rename legitimate again. So a crag name typed into an edit is either
 * a rename or the day's second crag: the form asks, in an in-app dialog,
 * instead of guessing.
 *   - Rename → PUT with original_spot_name (the server renames that crag).
 *   - Add    → POST of a new crag; the edited crag is untouched (no PUT).
 *   - Name unchanged → the plain PUT, no dialog.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act, waitFor } from "@testing-library/react";
import type { OutdoorSession } from "@/lib/types";

const { postOutdoorLog, putOutdoorLog, getOutdoorLogByDate, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return { postOutdoorLog: vi.fn(), putOutdoorLog: vi.fn(), getOutdoorLogByDate: vi.fn(), ApiError };
});

vi.mock("@/lib/api", () => ({
  ApiError,
  getOutdoorLogByDate: (d: string) => getOutdoorLogByDate(d),
  postOutdoorLog: (...a: unknown[]) => postOutdoorLog(...a),
  putOutdoorLog: (...a: unknown[]) => putOutdoorLog(...a),
}));
vi.mock("sonner", () => ({ toast: vi.fn() }));
vi.mock("@/lib/outbox", () => ({ enqueue: vi.fn(() => false) }));

import OutdoorLogForm from "../OutdoorLogForm";

afterEach(cleanup);

const BERDORF: OutdoorSession = {
  log_version: "outdoor.v2",
  date: "2026-11-01",
  spot_name: "Berdorf",
  discipline: "lead",
  duration_minutes: 180,
  routes: [{ name: "Ouverture", grade: "6b", attempts: [{ result: "sent" }] }],
};

let onSuccess: ReturnType<typeof vi.fn<(info?: { planSynced?: boolean }) => void>>;

beforeEach(() => {
  postOutdoorLog.mockReset().mockResolvedValue({ status: "ok", plan_synced: true });
  putOutdoorLog.mockReset().mockResolvedValue({ status: "ok", load_score: 20 });
  getOutdoorLogByDate.mockReset().mockResolvedValue({ session: BERDORF, sessions: [BERDORF] });
  onSuccess = vi.fn<(info?: { planSynced?: boolean }) => void>();
  render(<OutdoorLogForm spots={[]} initialData={BERDORF} onSuccess={onSuccess} />);
});

const typeCrag = (name: string) =>
  fireEvent.change(screen.getByPlaceholderText("Spot name"), { target: { value: name } });

async function clickSave() {
  await act(async () => {
    screen.getByRole("button", { name: "Save Changes" }).click();
  });
}

async function choose(name: RegExp | string) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
}

describe("A324 — edit mode names the crag it edits", () => {
  it("unchanged name → a plain PUT with original_spot_name, no dialog", async () => {
    await clickSave();
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(putOutdoorLog).toHaveBeenCalledTimes(1);
    expect(putOutdoorLog.mock.calls[0][0]).toMatchObject({ spot_name: "Berdorf", original_spot_name: "Berdorf" });
    expect(postOutdoorLog).not.toHaveBeenCalled();
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("a new name asks first: nothing is written until the athlete chooses", async () => {
    typeCrag("Freyr");
    await clickSave();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Rename Berdorf to Freyr" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add Freyr as another crag" })).toBeTruthy();
    expect(putOutdoorLog).not.toHaveBeenCalled();
    expect(postOutdoorLog).not.toHaveBeenCalled();

    await choose("Keep editing");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(putOutdoorLog).not.toHaveBeenCalled();
    expect(postOutdoorLog).not.toHaveBeenCalled();
  });

  it("Rename → PUT with original_spot_name, no POST", async () => {
    typeCrag("Freyr");
    await clickSave();
    await choose("Rename Berdorf to Freyr");
    await waitFor(() => expect(putOutdoorLog).toHaveBeenCalledTimes(1));
    expect(putOutdoorLog.mock.calls[0][0]).toMatchObject({ spot_name: "Freyr", original_spot_name: "Berdorf" });
    expect(postOutdoorLog).not.toHaveBeenCalled();
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("Add → POST of the new crag, and no PUT (Berdorf stays as it is)", async () => {
    typeCrag("Freyr");
    await clickSave();
    await choose("Add Freyr as another crag");
    await waitFor(() => expect(postOutdoorLog).toHaveBeenCalledTimes(1));
    const body = postOutdoorLog.mock.calls[0][0] as Record<string, unknown>;
    expect(body).toMatchObject({ date: "2026-11-01", spot_name: "Freyr" });
    expect("original_spot_name" in body).toBe(false);
    expect(putOutdoorLog).not.toHaveBeenCalled();
    expect(getOutdoorLogByDate).toHaveBeenCalledWith("2026-11-01");
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith({ planSynced: true }));
  });

  it("Add never lands on a crag already logged that day (a POST would replace it)", async () => {
    const freyr = { ...BERDORF, spot_name: "Freyr" };
    getOutdoorLogByDate.mockResolvedValue({ session: freyr, sessions: [BERDORF, freyr] });
    typeCrag("freyr ");
    await clickSave();
    await choose(/^Add freyr as another crag$/);
    await waitFor(() => expect(screen.getByText(/already logged on 2026-11-01 — nothing saved/)).toBeTruthy());
    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(putOutdoorLog).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("Add writes nothing when the day's crags cannot be read", async () => {
    getOutdoorLogByDate.mockRejectedValue(new ApiError(0, "offline"));
    typeCrag("Freyr");
    await clickSave();
    await choose("Add Freyr as another crag");
    await waitFor(() => expect(screen.getByText(/Couldn't check the crags/)).toBeTruthy());
    expect(postOutdoorLog).not.toHaveBeenCalled();
  });
});
