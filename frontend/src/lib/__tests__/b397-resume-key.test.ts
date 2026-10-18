import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * B397 G1 — the guided resume key must not depend on Clerk being ready.
 *
 * Clerk.js comes from the network: for the first few hundred ms of every cold
 * open — and forever when the PWA opens offline — `window.Clerk.user` is
 * missing. The scope fell back to `anon`, so a reload mid-session found
 * nothing and bounced to /today, the resume banner stayed hidden, and offline
 * Start began again from zero.
 *
 * The fallback is now the last user Clerk identified on this device (the same
 * marker the offline plan cache trusts, B292b). Privacy rules pinned below:
 * Clerk's answer always wins, a signed-out Clerk means `anon`, and `anon`
 * entries are never handed to whoever signs in.
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

let storage: MemoryStorage;

/** Clerk answered: `userId` is signed in (or nobody, with null). */
function clerkReady(userId: string | null) {
  const Clerk = userId
    ? { session: {}, user: { id: userId }, loaded: true }
    : { session: null, user: null, loaded: true };
  vi.stubGlobal("window", { localStorage: storage, Clerk });
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("navigator", { onLine: true });
}

/** Clerk not loaded yet (cold open) or never (offline). */
function clerkNotReady({ online = true } = {}) {
  vi.stubGlobal("window", { localStorage: storage, Clerk: undefined });
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("navigator", { onLine: online });
}

const session = (extra: Record<string, unknown> = {}) =>
  JSON.stringify({
    version: 1,
    date: "2026-10-18",
    sessionId: "strength_long",
    sessionName: "Strength",
    startedAt: new Date().toISOString(),
    currentIndex: 2,
    exercises: [
      { exerciseId: "a", status: "done" },
      { exerciseId: "b", status: "done" },
      { exerciseId: "c", status: "pending" },
    ],
    ...extra,
  });

const KEY_A = "guided_session_user_A_2026-10-18_strength_long";
const KEY_B = "guided_session_user_B_2026-10-18_strength_long";
const KEY_ANON = "guided_session_anon_2026-10-18_strength_long";

beforeEach(() => {
  storage = new MemoryStorage();
  vi.resetModules();
});

afterEach(() => vi.unstubAllGlobals());

describe("resume key — Clerk not ready", () => {
  it("uses the user remembered on this device instead of anon", async () => {
    storage.setItem("climb-agent-last-user", "user_A");
    clerkNotReady();
    const { getKeyPrefix, guidedStorageKey } = await import("@/lib/guided-session-utils");

    expect(getKeyPrefix()).toBe("guided_session_user_A_");
    expect(guidedStorageKey("2026-10-18", "strength_long")).toBe(KEY_A);
  });

  it("finds a session saved while Clerk was ready — same key format, nothing to migrate", async () => {
    // Saved by Start with Clerk up (the normal case)...
    clerkReady("user_A");
    const first = await import("@/lib/guided-session-utils");
    storage.setItem(first.guidedStorageKey("2026-10-18", "strength_long"), session());

    // ...then the PWA is killed and reopened offline: Clerk never loads.
    vi.resetModules();
    clerkNotReady({ online: false });
    const { loadGuidedSession, getInProgressSession, hasSavedProgress } = await import(
      "@/lib/guided-session-utils"
    );

    const loaded = loadGuidedSession("2026-10-18", "strength_long");
    expect(loaded?.key).toBe(KEY_A);
    expect(loaded?.owner).toBe("user_A");
    expect(loaded?.state.currentIndex).toBe(2);
    // The /today banner and Start see it too.
    expect(getInProgressSession()?.key).toBe(KEY_A);
    expect(hasSavedProgress("2026-10-18", "strength_long")).toBe(true);
  });

  it("falls back to anon only when no user was ever identified here", async () => {
    clerkNotReady();
    const { getKeyPrefix, guidedScopeOwner } = await import("@/lib/guided-session-utils");
    expect(getKeyPrefix()).toBe("guided_session_anon_");
    expect(guidedScopeOwner()).toEqual({ userId: null, confirmed: false });
  });

  it("marks the remembered owner as NOT confirmed (the player re-checks it)", async () => {
    storage.setItem("climb-agent-last-user", "user_A");
    clerkNotReady();
    const { guidedScopeOwner } = await import("@/lib/guided-session-utils");
    expect(guidedScopeOwner()).toEqual({ userId: "user_A", confirmed: false });
  });
});

describe("resume key — Clerk ready", () => {
  it("uses the signed-in user and remembers it for the next cold open", async () => {
    clerkReady("user_A");
    const { getKeyPrefix, guidedScopeOwner } = await import("@/lib/guided-session-utils");

    expect(getKeyPrefix()).toBe("guided_session_user_A_");
    expect(guidedScopeOwner()).toEqual({ userId: "user_A", confirmed: true });
    expect(storage.getItem("climb-agent-last-user")).toBe("user_A");
  });

  it("is anon when Clerk says nobody is signed in, whatever was remembered", async () => {
    storage.setItem("climb-agent-last-user", "user_A");
    clerkReady(null);
    const { getKeyPrefix } = await import("@/lib/guided-session-utils");
    expect(getKeyPrefix()).toBe("guided_session_anon_");
  });
});

describe("resume key — another user on the same device", () => {
  it("Clerk's answer wins over the remembered user", async () => {
    storage.setItem("climb-agent-last-user", "user_A");
    storage.setItem(KEY_A, session());
    clerkReady("user_B");
    const { loadGuidedSession, getInProgressSession, getKeyPrefix } = await import(
      "@/lib/guided-session-utils"
    );

    expect(getKeyPrefix()).toBe("guided_session_user_B_");
    // B cannot read A's session, through any reader.
    expect(loadGuidedSession("2026-10-18", "strength_long")).toBeNull();
    expect(getInProgressSession()).toBeNull();
    // A's data stays on the device, untouched, under A's own key.
    expect(storage.getItem(KEY_A)).not.toBeNull();
    // And the marker now points at B.
    expect(storage.getItem("climb-agent-last-user")).toBe("user_B");
  });

  it("each user keeps their own session side by side", async () => {
    storage.setItem(KEY_A, session({ currentIndex: 1 }));
    storage.setItem(KEY_B, session({ currentIndex: 2 }));
    clerkReady("user_B");
    const { loadGuidedSession } = await import("@/lib/guided-session-utils");
    expect(loadGuidedSession("2026-10-18", "strength_long")?.state.currentIndex).toBe(2);
  });

  it("never adopts anon entries for the user who signs in (nobody knows who wrote them)", async () => {
    storage.setItem(KEY_ANON, session({ submitStatus: "feedback_pending" }));
    storage.setItem("climb-agent-last-user", "user_A");
    clerkReady("user_A");
    const { migrateLegacyGuidedKeys, loadGuidedSession, getInProgressSession } = await import(
      "@/lib/guided-session-utils"
    );

    migrateLegacyGuidedKeys();

    expect(storage.getItem(KEY_A)).toBeNull();
    expect(loadGuidedSession("2026-10-18", "strength_long")).toBeNull();
    expect(getInProgressSession()).toBeNull();
    expect(storage.getItem(KEY_ANON)).not.toBeNull();
  });
});

describe("resume key — coupled to the offline plan cache (B292b)", () => {
  /**
   * The marker is written by query-persist when Clerk answers. If either module
   * renamed its key, the fallback would silently go back to `anon` — so write
   * through the REAL persister and read through the REAL guided scope.
   */
  it("the user query-persist identified is the guided owner offline", async () => {
    clerkReady("user_A");
    const qp = await import("@/lib/query-persist");
    await qp.createPersister().persistClient({
      timestamp: Date.now(),
      buster: "",
      clientState: { mutations: [], queries: [] },
    });
    await qp.createPersister().restoreClient(); // records the last user

    vi.resetModules();
    clerkNotReady({ online: false });
    const { getKeyPrefix, LAST_USER_KEY } = await import("@/lib/guided-session-utils");

    expect(getKeyPrefix()).toBe("guided_session_user_A_");
    expect(storage.getItem(LAST_USER_KEY)).toBe("user_A");
  });

  it("a sign-out (forgetLastUser) also drops the guided fallback", async () => {
    clerkReady("user_A");
    const g = await import("@/lib/guided-session-utils");
    g.getKeyPrefix(); // remembers user_A
    const qp = await import("@/lib/query-persist");
    qp.forgetLastUser();

    vi.resetModules();
    clerkNotReady();
    const { getKeyPrefix } = await import("@/lib/guided-session-utils");
    expect(getKeyPrefix()).toBe("guided_session_anon_");
  });
});

describe("B397 G7 — body weight from the state payload", () => {
  it("reads assessment.body.weight_kg and ignores anything that is not a weight", async () => {
    clerkReady("user_A");
    const { bodyweightFromState } = await import("@/lib/guided-session-utils");
    expect(bodyweightFromState({ assessment: { body: { weight_kg: 71.5 } } })).toBe(71.5);
    expect(bodyweightFromState({ assessment: { body: {} } })).toBeUndefined();
    expect(bodyweightFromState({ assessment: { body: { weight_kg: 0 } } })).toBeUndefined();
    expect(bodyweightFromState(undefined)).toBeUndefined();
    expect(bodyweightFromState(null)).toBeUndefined();
  });
});
