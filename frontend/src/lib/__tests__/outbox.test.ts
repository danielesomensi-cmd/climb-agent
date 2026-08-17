import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

/**
 * A245 B-4 — the outbox exists so that nothing logged offline is ever lost
 * silently. These tests pin the three rules that make that true:
 * retryable vs permanent failures, expiry, and ordering.
 */

// Minimal localStorage for the node test environment.
class MemoryStorage {
  private map = new Map<string, string>();
  get length() {
    return this.map.size;
  }
  key(i: number) {
    return Array.from(this.map.keys())[i] ?? null;
  }
  getItem(k: string) {
    return this.map.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.map.set(k, v);
  }
  removeItem(k: string) {
    this.map.delete(k);
  }
  clear() {
    this.map.clear();
  }
}

const postFeedback = vi.fn();
const postOutdoorLog = vi.fn();
const logFreeClimb = vi.fn();
const finishOutdoorSession = vi.fn();

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

vi.mock("@/lib/api", () => ({
  ApiError,
  NETWORK_ERROR_STATUS: 0,
  postFeedback: (...a: unknown[]) => postFeedback(...a),
  postOutdoorLog: (...a: unknown[]) => postOutdoorLog(...a),
  logFreeClimb: (...a: unknown[]) => logFreeClimb(...a),
  finishOutdoorSession: (...a: unknown[]) => finishOutdoorSession(...a),
}));

vi.mock("@/lib/guided-session-utils", () => ({
  getKeyPrefix: () => "guided_session_user_abc_",
}));

const toastError = vi.fn();
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: (...a: unknown[]) => toastError(...a) }),
}));

let outbox: typeof import("@/lib/outbox");

beforeEach(async () => {
  const storage = new MemoryStorage();
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("window", { localStorage: storage });
  vi.resetModules();
  postFeedback.mockReset();
  postOutdoorLog.mockReset();
  logFreeClimb.mockReset();
  finishOutdoorSession.mockReset();
  toastError.mockReset();
  outbox = await import("@/lib/outbox");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("outbox", () => {
  it("queues an entry and reports it as pending", () => {
    expect(outbox.enqueue("feedback", { a: 1 })).toBe(true);
    expect(outbox.pendingCount()).toBe(1);
  });

  it("sends queued entries and empties the queue on success", async () => {
    outbox.enqueue("feedback", { a: 1 });
    outbox.enqueue("outdoor_log", { date: "2026-07-20" });
    postFeedback.mockResolvedValue({});
    postOutdoorLog.mockResolvedValue({});

    const res = await outbox.flush();

    expect(res).toEqual({ sent: 2, remaining: 0 });
    expect(outbox.pendingCount()).toBe(0);
  });

  it("splits session_id out of a free_climb payload", async () => {
    outbox.enqueue("free_climb", { session_id: "s1", grade: "7a", attempts: 2 });
    logFreeClimb.mockResolvedValue({ index: 0, logged_at: "" });

    await outbox.flush();

    expect(logFreeClimb).toHaveBeenCalledWith("s1", { grade: "7a", attempts: 2 });
  });

  it("KEEPS an entry when the failure is retryable (offline)", async () => {
    outbox.enqueue("feedback", { a: 1 });
    postFeedback.mockRejectedValue(new ApiError(0, "Network too slow"));

    const res = await outbox.flush();

    expect(res.sent).toBe(0);
    expect(outbox.pendingCount()).toBe(1);
    expect(toastError).not.toHaveBeenCalled();
  });

  it.each([500, 502, 408, 429])("keeps an entry on retryable status %i", async (status) => {
    outbox.enqueue("feedback", { a: 1 });
    postFeedback.mockRejectedValue(new ApiError(status, "later"));

    await outbox.flush();

    expect(outbox.pendingCount()).toBe(1);
  });

  it("DROPS an entry on a permanent 4xx — but tells the user", async () => {
    outbox.enqueue("feedback", { a: 1 });
    postFeedback.mockRejectedValue(new ApiError(422, "bad payload"));

    const res = await outbox.flush();

    expect(res.remaining).toBe(0);
    expect(outbox.pendingCount()).toBe(0);
    // Never drop user data silently — that is the whole point of Phase B.
    expect(toastError).toHaveBeenCalledOnce();
  });

  // --- B336: outdoor_finish ---------------------------------------------------

  it("replays an outdoor_finish against its server session id", async () => {
    outbox.enqueue("outdoor_finish", {
      session_id: "outdoor_active_20260820_1",
      spot_name: "Grande Grotta",
      discipline: "lead",
      routes: [{ name: "DNA", grade: "7a+", attempts: [{ result: "sent" }] }],
    });
    finishOutdoorSession.mockResolvedValue({ status: "done" });

    const res = await outbox.flush();

    expect(finishOutdoorSession).toHaveBeenCalledWith("outdoor_active_20260820_1", {
      spot_name: "Grande Grotta",
      discipline: "lead",
      routes: [{ name: "DNA", grade: "7a+", attempts: [{ result: "sent" }] }],
    });
    expect(res).toEqual({ sent: 1, remaining: 0 });
  });

  it("keeps an outdoor_finish queued while still offline", async () => {
    outbox.enqueue("outdoor_finish", { session_id: "s1", spot_name: "Odyssey" });
    finishOutdoorSession.mockRejectedValue(new ApiError(0, "offline"));

    await outbox.flush();

    expect(outbox.pendingCount()).toBe(1);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("treats a 404 on outdoor_finish as already applied, NOT as a rejection", async () => {
    // The likeliest cause is that the original finish succeeded and only its
    // response was lost: the log exists, so "rejected by the server" would be
    // both alarming and false.
    outbox.enqueue("outdoor_finish", { session_id: "s1", spot_name: "Odyssey" });
    finishOutdoorSession.mockRejectedValue(new ApiError(404, "not found"));

    const res = await outbox.flush();

    expect(res).toEqual({ sent: 1, remaining: 0 });
    expect(outbox.pendingCount()).toBe(0);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("still warns when an outdoor_finish is genuinely rejected", async () => {
    outbox.enqueue("outdoor_finish", { session_id: "s1" });
    finishOutdoorSession.mockRejectedValue(new ApiError(422, "bad payload"));

    await outbox.flush();

    expect(outbox.pendingCount()).toBe(0);
    expect(toastError).toHaveBeenCalledOnce();
  });

  it("does not extend the 404 pass to other kinds", async () => {
    outbox.enqueue("outdoor_log", { date: "2026-08-20" });
    postOutdoorLog.mockRejectedValue(new ApiError(404, "not found"));

    await outbox.flush();

    expect(toastError).toHaveBeenCalledOnce();
  });

  it("stops the pass at the first retryable failure so order is preserved", async () => {
    outbox.enqueue("feedback", { first: true });
    outbox.enqueue("outdoor_log", { second: true });
    postFeedback.mockRejectedValue(new ApiError(0, "offline"));
    postOutdoorLog.mockResolvedValue({});

    await outbox.flush();

    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(outbox.pendingCount()).toBe(2);
  });

  it("expires entries older than 72h and warns instead of dropping silently", async () => {
    outbox.enqueue("feedback", { a: 1 });
    // Age the stored entry past the cap.
    const key = localStorage.key(0)!;
    const stored = JSON.parse(localStorage.getItem(key)!);
    stored[0].createdAt = Date.now() - 73 * 60 * 60 * 1000;
    localStorage.setItem(key, JSON.stringify(stored));

    const res = await outbox.flush();

    expect(res).toEqual({ sent: 0, remaining: 0 });
    expect(postFeedback).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledOnce();
  });

  it("collapses concurrent flushes", async () => {
    outbox.enqueue("feedback", { a: 1 });
    let resolve: (v: unknown) => void = () => {};
    postFeedback.mockReturnValue(new Promise((r) => (resolve = r)));

    const first = outbox.flush();
    const second = await outbox.flush();
    expect(second.sent).toBe(0); // short-circuited, did not start a second pass

    resolve({});
    await first;
    expect(postFeedback).toHaveBeenCalledOnce();
  });
});
