/**
 * @vitest-environment jsdom
 *
 * A324 — the outdoor log form (new log and pencil edit) records who led each
 * try and the A0 result:
 *   [L / 2nd / TR] [result] [✕] per try, the role only on a rope;
 *   the result cycles Sent → Fell → A0 on a rope, Sent ⇄ Fell on a boulder;
 *   a top with rests is never promoted by a tap (B393).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act, waitFor } from "@testing-library/react";
import type { OutdoorSession } from "@/lib/types";

const postOutdoorLog = vi.fn();
const putOutdoorLog = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status = 0;
  },
  getOutdoorLogByDate: vi.fn(),
  postOutdoorLog: (...a: unknown[]) => postOutdoorLog(...a),
  putOutdoorLog: (...a: unknown[]) => putOutdoorLog(...a),
}));
vi.mock("sonner", () => ({ toast: vi.fn() }));
vi.mock("@/lib/outbox", () => ({ enqueue: vi.fn(() => false) }));

import OutdoorLogForm from "../OutdoorLogForm";

afterEach(cleanup);

beforeEach(() => {
  postOutdoorLog.mockReset().mockResolvedValue({ status: "ok" });
  putOutdoorLog.mockReset().mockResolvedValue({ status: "ok", load_score: 37 });
});

function day(routes: OutdoorSession["routes"], discipline: OutdoorSession["discipline"] = "lead"): OutdoorSession {
  return {
    log_version: "outdoor.v2",
    date: "2026-10-31",
    spot_name: "Presles",
    discipline,
    duration_minutes: 300,
    routes,
    notes: "Cancer",
  };
}

/** The result badge / role chip of try `tryNo` (1-based) of the first route, or of `route`. */
const resultBadge = (tryNo: number, route = "[^ ]+") =>
  screen.getByRole("button", { name: new RegExp(`^${route} try ${tryNo}, result: `) });
const roleChip = (tryNo: number, route = "[^ ]+") =>
  screen.queryByRole("button", { name: new RegExp(`^${route} try ${tryNo}, who led: `) });

async function save() {
  await act(async () => {
    screen.getByRole("button", { name: /Save Changes|Log Session/ }).click();
  });
}

const sentRoutes = () => (putOutdoorLog.mock.calls[0][0] as { routes: OutdoorSession["routes"] }).routes;

describe("A324 — result cycle", () => {
  it("on a rope: Sent → Fell → A0 → Sent", () => {
    render(<OutdoorLogForm spots={[]} initialData={day([{ name: "L2", grade: "6c+", attempts: [{ result: "sent" }] }])} />);
    expect(resultBadge(1).textContent).toBe("Sent");
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("Fell");
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("A0");
    expect(resultBadge(1).className).toContain("text-warning");
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("Sent");
  });

  it("on a boulder: Sent ⇄ Fell, and no role chip", () => {
    render(
      <OutdoorLogForm spots={[]} initialData={day([{ name: "B", grade: "7a", attempts: [{ result: "sent" }] }], "boulder")} />,
    );
    expect(roleChip(1)).toBeNull();
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("Fell");
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("Sent");
  });

  it("a top with rests becomes Fell, never Sent (B393)", () => {
    render(<OutdoorLogForm spots={[]} initialData={day([{ name: "Isatis", grade: "7c+", attempts: [{ result: "topped_out" }] }])} />);
    expect(resultBadge(1).textContent).toBe("Top w/ rests");
    fireEvent.click(resultBadge(1));
    expect(resultBadge(1).textContent).toBe("Fell");
  });
});

describe("A324 — rope role", () => {
  it("the chip cycles L → 2nd → TR → L, and a clean second is blue «Clean», not a green Sent", () => {
    render(<OutdoorLogForm spots={[]} initialData={day([{ name: "L1", grade: "6a+", attempts: [{ result: "sent" }] }])} />);
    expect(roleChip(1)!.textContent).toBe("L");
    fireEvent.click(roleChip(1)!);
    expect(roleChip(1)!.textContent).toBe("2nd");
    expect(resultBadge(1).textContent).toBe("Clean");
    expect(resultBadge(1).className).toContain("text-info");
    expect(resultBadge(1).className).not.toContain("success");
    fireEvent.click(roleChip(1)!);
    expect(roleChip(1)!.textContent).toBe("TR");
    fireEvent.click(roleChip(1)!);
    expect(roleChip(1)!.textContent).toBe("L");
  });

  it("the payload carries rope_role; lead is left out (identical to an old log)", async () => {
    render(
      <OutdoorLogForm
        spots={[]}
        initialData={day([
          { name: "L1", grade: "6a+", attempts: [{ result: "sent" }] },
          { name: "L4", grade: "6c", attempts: [{ result: "sent" }] },
        ])}
      />,
    );
    fireEvent.click(roleChip(1, "L1")!); // L1 → second
    await save();
    const routes = sentRoutes();
    expect(routes[0].attempts[0]).toEqual({ result: "sent", rope_role: "second" });
    expect(routes[1].attempts[0]).toEqual({ result: "sent" });
  });

  it("no style survives without a send on lead", async () => {
    render(
      <OutdoorLogForm
        spots={[]}
        initialData={day([{ name: "L1", grade: "6a+", style: "onsight", attempts: [{ result: "sent" }] }])}
      />,
    );
    fireEvent.click(roleChip(1)!); // now a clean second: no onsight
    await save();
    expect(sentRoutes()[0].style).toBeUndefined();
  });

  it("a new try takes the role of the route's last try", async () => {
    render(
      <OutdoorLogForm
        spots={[]}
        initialData={day([{ name: "Cernes", grade: "7b+", attempts: [{ result: "fell", rope_role: "toprope" }] }])}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Add attempt" }));
    expect(roleChip(2)!.textContent).toBe("TR");
    await save();
    expect(sentRoutes()[0].attempts[1]).toEqual({ result: "sent", rope_role: "toprope" });
  });

  it("switching the session to boulder drops roles and turns A0 into a fall", async () => {
    render(
      <OutdoorLogForm
        spots={[]}
        initialData={day([
          { name: "L5", grade: "7a+", attempts: [{ result: "aid", rope_role: "second" }, { result: "sent", rope_role: "toprope" }] },
        ])}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "boulder" }));
    expect(roleChip(1)).toBeNull();
    await save();
    expect(sentRoutes()[0].attempts).toEqual([{ result: "fell" }, { result: "sent" }]);
  });
});

describe("A324 — an edit keeps what it does not show", () => {
  it("emptied notes go as null (the server keeps any key left out)", async () => {
    render(<OutdoorLogForm spots={[]} initialData={day([{ name: "L1", grade: "6a+", attempts: [{ result: "sent" }] }])} />);
    const notes = document.querySelector("textarea") as HTMLTextAreaElement;
    fireEvent.change(notes, { target: { value: "" } });
    await save();
    await waitFor(() => expect(putOutdoorLog).toHaveBeenCalledTimes(1));
    const body = putOutdoorLog.mock.calls[0][0] as Record<string, unknown>;
    expect(body.notes).toBeNull();
    // day_type / conditions / spot_id are not sent: the server carries them over.
    expect("day_type" in body).toBe(false);
    expect("conditions" in body).toBe(false);
  });
});
