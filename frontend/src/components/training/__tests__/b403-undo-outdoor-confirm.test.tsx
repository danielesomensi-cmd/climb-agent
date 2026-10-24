/**
 * @vitest-environment jsdom
 *
 * B403 — "Undo completion" on a done crag day takes two taps (one stray tap
 * erased Daniele's 17/10 routes, 2026-10-24), and it says the routes stay.
 * A321 — "Topo & charts" shows only when the day is in the athlete's quaderno.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import type { DayPlan } from "@/lib/types";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), getQuaderno: vi.fn() }));

import { DayCard } from "../day-card";

afterEach(cleanup);

const DAY = {
  date: "2026-10-17",
  weekday: "sat",
  sessions: [],
  outdoor_spot_name: "Berdorf",
  outdoor_discipline: "lead",
  outdoor_session_status: "done",
} as unknown as DayPlan;

describe("DayCard — done crag day", () => {
  it("undoes only after the confirmation, and says the routes stay", () => {
    const onUndo = vi.fn();
    render(<DayCard day={DAY} onUndoOutdoor={onUndo} />);
    fireEvent.click(screen.getByRole("button", { name: /Undo completion/ }));
    expect(onUndo).not.toHaveBeenCalled();
    expect(screen.getByText(/Your routes stay logged/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onUndo).not.toHaveBeenCalled();
    expect(screen.queryByText(/Your routes stay logged/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Undo completion/ }));
    fireEvent.click(screen.getByRole("button", { name: "Mark not done" }));
    expect(onUndo).toHaveBeenCalledWith("2026-10-17");
  });

  it("offers Topo & charts only for a day the quaderno covers", () => {
    const { rerender } = render(<DayCard day={DAY} />);
    expect(screen.queryByRole("button", { name: /Topo & charts/ })).toBeNull();
    rerender(<DayCard day={DAY} hasQuaderno />);
    expect(screen.getByRole("button", { name: /Topo & charts/ })).toBeTruthy();
  });
});
