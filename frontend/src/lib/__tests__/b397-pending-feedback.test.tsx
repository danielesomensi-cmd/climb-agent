/**
 * @vitest-environment jsdom
 *
 * B397 G3 — the guided player's offline feedback is sent once, whole, as soon
 * as the connection is back.
 *
 * Before: the replay ran only when /today mounted (not when the network came
 * back), rebuilt the payload without `session_duration_seconds`, showed
 * nothing, and every remount of /today fired another POST while the previous
 * one was in flight — and the server runs apply_feedback on each of them.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement, type ReactNode } from "react";
import { renderHook, act, waitFor, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { ApiError, postFeedback, toast } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  const toast = Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() });
  return { ApiError, postFeedback: vi.fn(), toast };
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
  buildGuidedFeedbackBody,
  flushPendingGuidedFeedback,
  pendingFeedbackBody,
  syncPendingGuidedFeedback,
  usePendingGuidedFeedback,
  type PendingGuidedState,
} from "@/lib/guided-pending-feedback";
import type { GuidedExercise } from "@/lib/types";

const KEY = "guided_session_user_A_2026-10-18_strength_long";
const STARTED = "2026-10-18T09:00:00.000Z";

const exercises = [
  {
    exerciseId: "max_hangs",
    name: "Max hangs",
    category: "finger_strength",
    blockUid: "main",
    loadModel: "external_load",
    prescription: { sets: 5 },
    suggested: {},
    status: "done",
    feedbackLabel: "hard",
    usedLoadKg: 12,
  },
] as unknown as GuidedExercise[];

function pendingState(extra: Partial<PendingGuidedState> = {}): PendingGuidedState {
  const base = {
    version: 1 as const,
    date: "2026-10-18",
    sessionId: "strength_long",
    sessionName: "Strength",
    startedAt: STARTED,
    currentIndex: 0,
    exercises,
    submitStatus: "feedback_pending" as const,
  };
  return {
    ...base,
    // What the player saved at the failed submit: a 62-minute session.
    pendingFeedback: buildGuidedFeedbackBody(base, exercises, 3720),
    ...extra,
  };
}

function deferred<T = unknown>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** jsdom here has no working localStorage (Node's own shadows it): a Map stand-in. */
class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

let qc: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(QueryClientProvider, { client: qc }, children);

beforeEach(() => {
  const storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  // The module logs every failed replay; the assertions below cover them.
  vi.spyOn(console, "error").mockImplementation(() => {});
  postFeedback.mockReset();
  toast.mockClear();
  toast.success.mockClear();
  toast.error.mockClear();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the replayed body", () => {
  it("is exactly what the player tried to send — duration included, hours later", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    postFeedback.mockResolvedValue({ status: "ok" });

    await flushPendingGuidedFeedback();

    expect(postFeedback).toHaveBeenCalledTimes(1);
    const body = postFeedback.mock.calls[0][0] as { log_entry: Record<string, unknown>; status: string };
    expect(body.status).toBe("done");
    expect(body.log_entry.session_duration_seconds).toBe(3720);
    expect(body.log_entry.started_at).toBe(STARTED);
    expect(body.log_entry.feedback_contract).toBe(2);
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("a pre-B397 entry (no saved body) is rebuilt with the same builder", () => {
    const legacy = pendingState();
    delete legacy.pendingFeedback;
    const body = pendingFeedbackBody(legacy);
    expect(body.log_entry.session_id).toBe("strength_long");
    expect(body.log_entry.session_duration_seconds).toBeUndefined();
    const items = (body.log_entry.actual as { exercise_feedback_v1: unknown[] }).exercise_feedback_v1;
    expect(items.length).toBe(1);
  });

  it("test sessions keep their planned tag", () => {
    const body = buildGuidedFeedbackBody(
      { date: "2026-10-18", sessionId: "test_day", startedAt: STARTED, isTestSession: true },
      exercises,
      600,
    );
    expect(body.log_entry.planned).toEqual([
      { session_id: "test_day", tags: { test: true }, exercise_instances: [] },
    ]);
  });
});

describe("never twice", () => {
  it("concurrent replays share ONE POST", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    const gate = deferred();
    postFeedback.mockReturnValue(gate.promise);

    // /today remounting, the `online` event and the player's "Send now".
    const a = flushPendingGuidedFeedback();
    const b = flushPendingGuidedFeedback();
    const c = flushPendingGuidedFeedback();
    await Promise.resolve();
    gate.resolve({ status: "ok" });
    const [ra, rb, rc] = await Promise.all([a, b, c]);

    expect(postFeedback).toHaveBeenCalledTimes(1);
    expect(ra).toBe(rb);
    expect(rb).toBe(rc);
    expect(ra.sent).toBe(1);
  });

  it("does not POST a session the server already logged (response lost to the timeout)", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    qc.setQueryData(["week", 0], {
      week_plan: {
        weeks: [
          {
            days: [
              {
                date: "2026-10-18",
                sessions: [
                  { session_id: "strength_long", status: "done", actual_exercises: [{ exercise_id: "max_hangs" }] },
                ],
              },
            ],
          },
        ],
      },
    });

    const result = await syncPendingGuidedFeedback(qc);

    expect(postFeedback).not.toHaveBeenCalled();
    expect(result.alreadySaved).toBe(1);
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it("a session marked done WITHOUT feedback still gets its feedback", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    qc.setQueryData(["week", 0], {
      week_plan: {
        weeks: [{ days: [{ date: "2026-10-18", sessions: [{ session_id: "strength_long", status: "done" }] }] }],
      },
    });
    postFeedback.mockResolvedValue({ status: "ok" });

    const result = await syncPendingGuidedFeedback(qc);

    expect(postFeedback).toHaveBeenCalledTimes(1);
    expect(result.sent).toBe(1);
  });
});

describe("failures", () => {
  it("keeps the entry when offline, and drops nothing silently", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    postFeedback.mockRejectedValue(new ApiError(0, "Network too slow"));

    const result = await flushPendingGuidedFeedback();

    expect(result.failed).toBe(1);
    expect(localStorage.getItem(KEY)).not.toBeNull();
  });

  it.each([401, 402, 403, 500, 503])("keeps the entry on %i (it can still succeed later)", async (status) => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    postFeedback.mockRejectedValue(new ApiError(status, "nope"));
    await flushPendingGuidedFeedback();
    expect(localStorage.getItem(KEY)).not.toBeNull();
  });

  it.each([400, 422])("drops a payload the server can never accept (%i) — and says so", async (status) => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    postFeedback.mockRejectedValue(new ApiError(status, "bad payload"));

    const { result } = renderHook(() => usePendingGuidedFeedback(true), { wrapper });
    void result;

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(localStorage.getItem(KEY)).toBeNull();
  });
});

describe("housekeeping (moved from /today, B127)", () => {
  it("drops finished/abandoned sessions after 24h but never a pending one", async () => {
    const old = new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString();
    const stale = "guided_session_user_A_2026-10-16_old";
    const oldPending = "guided_session_user_A_2026-10-16_pending";
    localStorage.setItem(stale, JSON.stringify({ ...pendingState(), submitStatus: undefined, startedAt: old }));
    localStorage.setItem(oldPending, JSON.stringify(pendingState({ startedAt: old })));
    postFeedback.mockRejectedValue(new ApiError(0, "offline"));

    await flushPendingGuidedFeedback();

    expect(localStorage.getItem(stale)).toBeNull();
    expect(localStorage.getItem(oldPending)).not.toBeNull();
  });

  it("never touches another user's scope", async () => {
    const other = "guided_session_user_B_2026-10-18_strength_long";
    localStorage.setItem(other, JSON.stringify(pendingState()));
    await flushPendingGuidedFeedback();
    expect(postFeedback).not.toHaveBeenCalled();
    expect(localStorage.getItem(other)).not.toBeNull();
  });
});

describe("usePendingGuidedFeedback — on mount and when the network comes back", () => {
  it("retries on `online`, sends once, keeps the duration and tells the user", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    // Mount while still offline: the replay fails and the entry stays.
    postFeedback.mockRejectedValueOnce(new ApiError(0, "offline"));

    renderHook(() => usePendingGuidedFeedback(true), { wrapper });
    await waitFor(() => expect(postFeedback).toHaveBeenCalledTimes(1));
    expect(localStorage.getItem(KEY)).not.toBeNull();
    expect(toast.success).not.toHaveBeenCalled();

    // The connection comes back while the user is still on /today.
    postFeedback.mockResolvedValue({ status: "ok" });
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });

    await waitFor(() => expect(postFeedback).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(localStorage.getItem(KEY)).toBeNull());
    const body = postFeedback.mock.calls[1][0] as { log_entry: Record<string, unknown> };
    expect(body.log_entry.session_duration_seconds).toBe(3720);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Session feedback synced."));

    // A second `online` (flapping wifi) has nothing left to send.
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(postFeedback).toHaveBeenCalledTimes(2);
  });

  it("does nothing until Clerk is ready (every replay needs a token)", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    renderHook(() => usePendingGuidedFeedback(false), { wrapper });
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(postFeedback).not.toHaveBeenCalled();
  });

  it("a remount while the POST is in flight does not send it again", async () => {
    localStorage.setItem(KEY, JSON.stringify(pendingState()));
    const gate = deferred();
    postFeedback.mockReturnValue(gate.promise);

    const first = renderHook(() => usePendingGuidedFeedback(true), { wrapper });
    await waitFor(() => expect(postFeedback).toHaveBeenCalledTimes(1));
    first.unmount();
    renderHook(() => usePendingGuidedFeedback(true), { wrapper });
    await new Promise((r) => setTimeout(r, 20));

    expect(postFeedback).toHaveBeenCalledTimes(1);
    await act(async () => {
      gate.resolve({ status: "ok" });
    });
    await waitFor(() => expect(localStorage.getItem(KEY)).toBeNull());
    expect(postFeedback).toHaveBeenCalledTimes(1);
  });
});
