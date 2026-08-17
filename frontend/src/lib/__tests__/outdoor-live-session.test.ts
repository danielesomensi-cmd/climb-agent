import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * B336 — the live outdoor session must survive the crag.
 *
 * D279 F3: routes lived in React state and on the server only, so a phone that
 * died offline came back to an empty day. These tests pin the four rules that
 * make the device copy trustworthy: it round-trips, it is scoped to the user,
 * it expires, and it WINS over the server on restore — including in the one
 * case where "take whichever has more routes" would have been actively wrong.
 */

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
  keys() { return Array.from(this.map.keys()); }
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

vi.mock("@/lib/api", () => ({ ApiError, NETWORK_ERROR_STATUS: 0 }));

let currentPrefix = "guided_session_user_abc_";
vi.mock("@/lib/guided-session-utils", () => ({
  getKeyPrefix: () => currentPrefix,
}));

let storage: MemoryStorage;
let lib: typeof import("@/lib/outdoor-live-session");

const ROUTE = (name: string, grade: string) => ({
  name, grade, attempts: [{ result: "sent" as const }], atMin: 0,
});

function session(over: Partial<import("@/lib/outdoor-live-session").LiveOutdoorSession> = {}) {
  return {
    sessionId: "outdoor_active_20260820_1",
    isLocal: false,
    date: "2026-08-20",
    spotName: "Grande Grotta",
    discipline: "lead" as const,
    dayType: "project" as const,
    startedAt: "2026-08-20T05:00:00Z",
    routes: [ROUTE("DNA", "7a+")],
    ...over,
  };
}

beforeEach(async () => {
  storage = new MemoryStorage();
  currentPrefix = "guided_session_user_abc_";
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("window", { localStorage: storage });
  vi.stubGlobal("navigator", { onLine: true });
  vi.resetModules();
  lib = await import("@/lib/outdoor-live-session");
});

afterEach(() => vi.unstubAllGlobals());

describe("live outdoor session storage", () => {
  it("round-trips a session with its routes", () => {
    expect(lib.saveLiveSession(session())).toBe(true);
    const back = lib.loadLiveSession("2026-08-20");
    expect(back?.sessionId).toBe("outdoor_active_20260820_1");
    expect(back?.routes).toHaveLength(1);
    expect(back?.routes[0].grade).toBe("7a+");
    expect(back?.dayType).toBe("project");
  });

  it("survives the failure this brief exists for: state is gone, storage is not", () => {
    lib.saveLiveSession(session({ routes: [ROUTE("DNA", "7a+"), ROUTE("Priapos", "7c")] }));
    // Simulate the phone dying: every bit of React state is lost.
    expect(lib.loadLiveSession("2026-08-20")?.routes).toHaveLength(2);
  });

  it("does not hand back another day's session", () => {
    lib.saveLiveSession(session());
    expect(lib.loadLiveSession("2026-08-21")).toBeNull();
  });

  it("expires a session older than the TTL, and clears it", () => {
    lib.saveLiveSession(session());
    const later = Date.now() + lib.MAX_AGE_MS + 1;
    expect(lib.loadLiveSession("2026-08-20", later)).toBeNull();
    expect(lib.loadLiveSession("2026-08-20")).toBeNull(); // actually removed
  });

  it("keeps a long crag day + overnight", () => {
    lib.saveLiveSession(session());
    const twelveHoursLater = Date.now() + 12 * 60 * 60 * 1000;
    expect(lib.loadLiveSession("2026-08-20", twelveHoursLater)).not.toBeNull();
  });

  it("is scoped to the signed-in user — B is not handed A's session", () => {
    lib.saveLiveSession(session());
    currentPrefix = "guided_session_user_zzz_";
    expect(lib.loadLiveSession("2026-08-20")).toBeNull();
    currentPrefix = "guided_session_user_abc_";
    expect(lib.loadLiveSession("2026-08-20")).not.toBeNull();
  });

  it("clears on demand", () => {
    lib.saveLiveSession(session());
    lib.clearLiveSession();
    expect(lib.loadLiveSession("2026-08-20")).toBeNull();
  });

  it("returns null rather than throwing on a corrupt payload", () => {
    storage.setItem("climb-agent-outdoor-live-v1-guided_session_user_abc_", "{not json");
    expect(lib.loadLiveSession("2026-08-20")).toBeNull();
  });

  it("refuses a write it cannot make and says so", () => {
    const huge = session({
      routes: Array.from({ length: 20000 }, (_, i) => ROUTE(`route-${i}`, "7a")),
    });
    expect(lib.saveLiveSession(huge)).toBe(false);
  });
});

describe("restore precedence", () => {
  const server = session({ routes: [ROUTE("a", "6a"), ROUTE("b", "6b")] });

  it("prefers the device copy", () => {
    const local = session({ routes: [ROUTE("a", "6a"), ROUTE("b", "6b"), ROUTE("c", "6c")] });
    expect(lib.pickRestoredSession(local, server)?.routes).toHaveLength(3);
  });

  it("prefers the device copy EVEN WHEN IT HAS FEWER ROUTES", () => {
    // The deletion case. "Whichever has more routes" would resurrect the route
    // the athlete just removed — the one edit that makes local shorter.
    const local = session({ routes: [ROUTE("a", "6a")] });
    expect(lib.pickRestoredSession(local, server)?.routes).toHaveLength(1);
  });

  it("falls back to the server when the device has nothing", () => {
    expect(lib.pickRestoredSession(null, server)?.routes).toHaveLength(2);
  });

  it("uses the device copy when the server is unreachable", () => {
    const local = session({ isLocal: true });
    expect(lib.pickRestoredSession(local, null)).toBe(local);
  });

  it("returns null when neither side has anything", () => {
    expect(lib.pickRestoredSession(null, null)).toBeNull();
  });
});

describe("local session ids", () => {
  it("marks offline-started sessions and nothing else", () => {
    expect(lib.isLocalSessionId(lib.newLocalSessionId())).toBe(true);
    expect(lib.isLocalSessionId("outdoor_active_20260820_1")).toBe(false);
    expect(lib.isLocalSessionId(null)).toBe(false);
    expect(lib.isLocalSessionId(undefined)).toBe(false);
  });

  it("generates distinct ids", () => {
    expect(lib.newLocalSessionId()).not.toBe(lib.newLocalSessionId());
  });
});

describe("offline classification", () => {
  it("treats a transport failure as offline", () => {
    expect(lib.isOfflineError(new ApiError(0, "Network too slow"))).toBe(true);
    expect(lib.isOfflineError(new TypeError("Failed to fetch"))).toBe(true);
  });

  it("does NOT treat a server answer as offline", () => {
    // 402 is the subscription guard: starting a local session there would be a
    // silent bypass of a fail-closed gate.
    expect(lib.isOfflineError(new ApiError(402, "Subscription required"))).toBe(false);
    expect(lib.isOfflineError(new ApiError(422, "bad payload"))).toBe(false);
    expect(lib.isOfflineError(new ApiError(500, "boom"))).toBe(false);
  });

  it("reads a 401 as offline only when the browser says it is", () => {
    vi.stubGlobal("navigator", { onLine: false });
    expect(lib.isOfflineError(new ApiError(401, "unverifiable offline"))).toBe(true);
    vi.stubGlobal("navigator", { onLine: true });
    expect(lib.isOfflineError(new ApiError(401, "expired"))).toBe(false);
  });

  it("does not mistake our own unmount abort for a dead network", () => {
    expect(lib.isOfflineError(new DOMException("aborted", "AbortError"))).toBe(false);
  });
});
