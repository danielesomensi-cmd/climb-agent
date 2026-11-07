/**
 * @vitest-environment jsdom
 *
 * B414 (INBOX-2026-11-04-ORPHAN) — the offline replay and a feedback the
 * server refuses because the session is no longer in the plan. The entry is
 * the only copy of that session's feedback: it is kept «to decide» (never
 * dropped like a 422), the queue goes on to the other entries (it is not a
 * network failure), it is not re-sent on its own, /today lists it, and once
 * the athlete placed the session (`clearOrphan`) the next pass sends it.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

const { ApiError, OrphanError, postFeedback, toast } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  /** What api.ts throws (SessionNotInPlanError): an ApiError with the code. */
  class OrphanError extends ApiError {
    code = "session_not_in_plan";
    date: string | null = "2026-11-04";
    sessionId: string | null = "treadmill_hiit_4x4";
    daySessions = [{ session_id: "custom_cs_320de282", slot: "lunch", status: "planned" }];
    constructor() {
      super(409, "This session is no longer in your plan for that day — nothing was saved.");
    }
  }
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), dismiss: vi.fn() });
  return { ApiError, OrphanError, postFeedback: vi.fn(), toast };
});

vi.mock("@/lib/api", () => ({
  ApiError,
  postFeedback: (...a: unknown[]) => postFeedback(...a),
}));
vi.mock("@/lib/guided-session-utils", () => ({
  getKeyPrefix: () => "guided_session_user_A_",
}));
vi.mock("sonner", () => ({ toast }));

import {
  announcePendingSync,
  buildGuidedFeedbackBody,
  clearOrphan,
  flushPendingGuidedFeedback,
  listUndecidedGuidedFeedback,
  type PendingGuidedState,
} from "@/lib/guided-pending-feedback";
import type { GuidedExercise } from "@/lib/types";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const exercises = [
  {
    exerciseId: "treadmill_incline_walk",
    name: "Incline walk",
    category: "cardio",
    blockUid: "main",
    loadModel: "bodyweight_only",
    prescription: { sets: 4 },
    suggested: {},
    status: "done",
    feedbackLabel: "hard",
  },
] as unknown as GuidedExercise[];

const ORPHAN_KEY = "guided_session_user_A_2026-11-04_treadmill_hiit_4x4";
const OTHER_KEY = "guided_session_user_A_2026-11-05_power_contact_gym";

function pending(date: string, sessionId: string): PendingGuidedState {
  const base = {
    version: 1 as const,
    date,
    sessionId,
    sessionName: sessionId,
    startedAt: `${date}T11:28:57.000Z`,
    currentIndex: 0,
    exercises,
    submitStatus: "feedback_pending" as const,
  };
  return { ...base, pendingFeedback: buildGuidedFeedbackBody(base, exercises, 1800) };
}

const read = (key: string) => JSON.parse(window.localStorage.getItem(key) ?? "null") as PendingGuidedState | null;

beforeEach(() => {
  const storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  vi.spyOn(console, "error").mockImplementation(() => {});
  postFeedback.mockReset();
  toast.warning.mockClear();
  // Insertion order = replay order: the orphan first, then a good one.
  storage.setItem(ORPHAN_KEY, JSON.stringify(pending("2026-11-04", "treadmill_hiit_4x4")));
  storage.setItem(OTHER_KEY, JSON.stringify(pending("2026-11-05", "power_contact_gym")));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("B414 — a refused orphan stays «to decide», the queue goes on", () => {
  it("keeps the exact body, marks it, sends the next one", async () => {
    const before = read(ORPHAN_KEY)!.pendingFeedback;
    postFeedback.mockImplementation(async (body: { log_entry: { session_id: string } }) => {
      if (body.log_entry.session_id === "treadmill_hiit_4x4") throw new OrphanError();
      return { status: "ok" };
    });

    const result = await flushPendingGuidedFeedback();

    expect(result).toMatchObject({ sent: 1, rejected: 0, failed: 0, undecided: 1 });
    expect(postFeedback).toHaveBeenCalledTimes(2);
    expect(read(OTHER_KEY)).toBeNull(); // sent
    const kept = read(ORPHAN_KEY)!;
    expect(kept.submitStatus).toBe("feedback_pending");
    expect(kept.pendingFeedback).toEqual(before); // duration and all
    expect(kept.orphan?.daySessions?.[0].session_id).toBe("custom_cs_320de282");

    announcePendingSync(result);
    expect(toast.warning).toHaveBeenCalledTimes(1);
  });

  it("is not re-sent on its own, and /today lists it", async () => {
    postFeedback.mockImplementation(async (body: { log_entry: { session_id: string } }) => {
      if (body.log_entry.session_id === "treadmill_hiit_4x4") throw new OrphanError();
      return { status: "ok" };
    });
    await flushPendingGuidedFeedback();
    postFeedback.mockClear();

    const again = await flushPendingGuidedFeedback();
    expect(postFeedback).not.toHaveBeenCalled();
    expect(again.undecided).toBe(0); // already waiting: not counted again (no second toast)
    expect(listUndecidedGuidedFeedback()).toEqual([
      { key: ORPHAN_KEY, date: "2026-11-04", sessionId: "treadmill_hiit_4x4", sessionName: "treadmill_hiit_4x4" },
    ]);
  });

  it("after the choice (clearOrphan) the next pass sends it", async () => {
    postFeedback.mockImplementationOnce(async () => {
      throw new OrphanError();
    });
    postFeedback.mockResolvedValue({ status: "ok" });
    await flushPendingGuidedFeedback();
    expect(read(ORPHAN_KEY)?.orphan).toBeTruthy();

    clearOrphan(ORPHAN_KEY);
    expect(read(ORPHAN_KEY)?.orphan).toBeUndefined();
    const result = await flushPendingGuidedFeedback();
    expect(result.sent).toBe(1);
    expect(read(ORPHAN_KEY)).toBeNull();
    expect(listUndecidedGuidedFeedback()).toEqual([]);
  });

  it("a genuine 422 is still dropped (and said), never confused with the orphan", async () => {
    window.localStorage.removeItem(OTHER_KEY);
    postFeedback.mockRejectedValue(new ApiError(422, "API 422: {\"detail\":\"bad payload\"}"));
    const result = await flushPendingGuidedFeedback();
    expect(result).toMatchObject({ rejected: 1, undecided: 0 });
    expect(read(ORPHAN_KEY)).toBeNull();
  });
});
