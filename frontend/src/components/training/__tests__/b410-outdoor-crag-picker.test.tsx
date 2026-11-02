/**
 * @vitest-environment jsdom
 *
 * B410 (B-OUTDOOR-CRAG-PICKER point 3) — a day can hold several crags (B341):
 *   - the picker lists them and opens the chosen one, or a new log;
 *   - `needsCragPicker`: the pencil goes straight to a single crag, «Log
 *     routes» / «Quick log» on a day with a log always ask;
 *   - the log form: the date is locked in edit mode, and a NEW log never
 *     lands on a crag already logged that day (since B412 the POST would be
 *     added to that crag's log: the same outing counted twice) — except a
 *     live session finishing through the form (B412: it joins the crag).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
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
import { OutdoorCragPicker } from "../outdoor-crag-picker";
import { needsCragPicker, sessionsOfDay } from "@/lib/outdoor-crag-choice";

afterEach(cleanup);

const crag = (spot_name: string, n: number): OutdoorSession => ({
  log_version: "outdoor.v2",
  date: "2026-08-25",
  spot_name,
  discipline: "lead",
  duration_minutes: 120,
  routes: Array.from({ length: n }, (_, i) => ({ name: `R${i}`, grade: "6b", attempts: [{ result: "sent" as const }] })),
});
const SYMP = crag("Symplegades", 3);
const SNAKE = crag("Snake Valley", 1);

describe("needsCragPicker / sessionsOfDay", () => {
  it("the pencil opens a single crag directly, asks on a multi-crag day", () => {
    expect(needsCragPicker([SYMP], "edit")).toBe(false);
    expect(needsCragPicker([SYMP, SNAKE], "edit")).toBe(true);
  });
  it("«Log routes» / «Quick log» on a day with a log always ask (edit or add)", () => {
    expect(needsCragPicker([SYMP], "log")).toBe(true);
    expect(needsCragPicker([SYMP, SNAKE], "log")).toBe(true);
  });
  it("no crag, no picker", () => {
    expect(needsCragPicker([], "log")).toBe(false);
    expect(needsCragPicker([], "edit")).toBe(false);
  });
  it("sessionsOfDay: every crag, else the one session (older servers)", () => {
    expect(sessionsOfDay({ session: SNAKE, sessions: [SYMP, SNAKE] })).toEqual([SYMP, SNAKE]);
    expect(sessionsOfDay({ session: SNAKE })).toEqual([SNAKE]);
    expect(sessionsOfDay({ session: SNAKE, sessions: [] })).toEqual([SNAKE]);
  });
});

describe("OutdoorCragPicker", () => {
  it("lists every crag with its routes, opens the one tapped", () => {
    const onEdit = vi.fn();
    const onAdd = vi.fn();
    render(<OutdoorCragPicker sessions={[SYMP, SNAKE]} onEdit={onEdit} onAdd={onAdd} />);
    expect(screen.getByText("2 crags are logged on this day. Which one do you want to open?")).toBeTruthy();
    expect(screen.getByText("3 routes")).toBeTruthy();
    expect(screen.getByText("1 route")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Edit Snake Valley" }));
    expect(onEdit).toHaveBeenCalledWith(SNAKE);
    expect(onAdd).not.toHaveBeenCalled();
  });
  it("«Add another crag» opens a new log", () => {
    const onEdit = vi.fn();
    const onAdd = vi.fn();
    render(<OutdoorCragPicker sessions={[SYMP]} onEdit={onEdit} onAdd={onAdd} />);
    expect(screen.getByText("This day already has a session logged. Edit it, or add another crag?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Add another crag/ }));
    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(onEdit).not.toHaveBeenCalled();
  });
});

describe("OutdoorLogForm — B410 guards", () => {
  beforeEach(() => {
    postOutdoorLog.mockReset().mockResolvedValue({ status: "ok", plan_synced: true });
    putOutdoorLog.mockReset().mockResolvedValue({ status: "ok", load_score: 20 });
    getOutdoorLogByDate.mockReset();
  });

  it("edit mode: the date cannot change", () => {
    render(<OutdoorLogForm spots={[]} initialData={SYMP} />);
    const date = screen.getByDisplayValue("2026-08-25") as HTMLInputElement;
    expect(date.disabled).toBe(true);
    expect(screen.getByText(/delete it and log it again on the right day/)).toBeTruthy();
  });

  it("new log: the date stays editable", () => {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-08-25" />);
    expect((screen.getByDisplayValue("2026-08-25") as HTMLInputElement).disabled).toBe(false);
  });

  async function logNew(spot: string) {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-08-25" />);
    fireEvent.change(screen.getByPlaceholderText("Spot name"), { target: { value: spot } });
    await act(async () => {
      screen.getByRole("button", { name: "Log Session" }).click();
    });
  }

  it("a new log on a crag already logged that day saves nothing (it would count twice)", async () => {
    getOutdoorLogByDate.mockResolvedValue({ session: SNAKE, sessions: [SYMP, SNAKE] });
    await logNew("  symplegades ");
    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(screen.getByText(/symplegades is already logged on 2026-08-25 — nothing saved/)).toBeTruthy();
  });

  it("B412: a live session finishing at a crag already logged that day is saved (it joins that crag)", async () => {
    getOutdoorLogByDate.mockResolvedValue({ session: SYMP, sessions: [SYMP] });
    render(<OutdoorLogForm spots={[]} defaultDate="2026-08-25" liveSession submitLabel="Finish & save" />);
    fireEvent.change(screen.getByPlaceholderText("Spot name"), { target: { value: "Symplegades" } });
    await act(async () => {
      screen.getByRole("button", { name: "Finish & save" }).click();
    });
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/already logged/)).toBeNull();
  });

  it("another crag of the same day is a new log", async () => {
    getOutdoorLogByDate.mockResolvedValue({ session: SYMP, sessions: [SYMP] });
    await logNew("Snake Valley");
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
  });

  it("no log that day (404): logs as before", async () => {
    getOutdoorLogByDate.mockRejectedValue(new ApiError(404, "No outdoor session"));
    await logNew("Symplegades");
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
  });

  it("the check cannot run (offline): logs as before, the outbox keeps offline logging", async () => {
    getOutdoorLogByDate.mockRejectedValue(new ApiError(0, "offline"));
    await logNew("Symplegades");
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
  });
});
