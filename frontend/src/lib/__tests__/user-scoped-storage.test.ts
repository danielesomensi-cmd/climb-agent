import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * Regression guard for the whole B290 failure class.
 *
 * B290 was not "a typo in a key". It was a PRODUCER and a PURGER drifting
 * apart: `SessionScopeGuard` deleted `guided_session_clerk_*` while the live
 * writers were still producing exactly that prefix, so the cleanup routine ate
 * real user data on every app open. Nothing failed loudly.
 *
 * Every user-scoped store on this device has the same shape — one module writes
 * it, `SessionScopeGuard` clears it when the signed-in user changes — so every
 * one of them can fail the same way. These tests couple the two sides: write
 * through the REAL producer, clear through the REAL purger, and assert the
 * purger actually found it.
 *
 * A test that only called the purger and checked "no crash" would have passed
 * throughout the B290 outage.
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

function signedInAs(userId: string | null) {
  const Clerk = userId
    ? { session: {}, user: { id: userId }, loaded: true }
    : { session: null, user: null, loaded: true };
  vi.stubGlobal("window", { localStorage: storage, Clerk });
  vi.stubGlobal("localStorage", storage);
}

beforeEach(() => {
  storage = new MemoryStorage();
  vi.resetModules();
});

afterEach(() => vi.unstubAllGlobals());

describe("persisted React Query cache", () => {
  it("the purger clears what the persister wrote", async () => {
    signedInAs("user_1");
    const { createPersister, purgePersistedCache } = await import("@/lib/query-persist");

    const persister = createPersister();
    await persister.persistClient({
      timestamp: Date.now(),
      buster: "",
      clientState: { mutations: [], queries: [] },
    });
    expect(storage.keys().length).toBe(1);

    purgePersistedCache();

    // The assertion that matters: the purger targeted the key that was
    // actually written, not a key it assumed was written.
    expect(storage.keys()).toEqual([]);
  });

  it("refuses to persist anything when no user is identified", async () => {
    signedInAs(null);
    const { createPersister } = await import("@/lib/query-persist");

    await createPersister().persistClient({
      timestamp: Date.now(),
      buster: "",
      clientState: { mutations: [], queries: [] },
    });

    expect(storage.keys()).toEqual([]);
  });

  it("does not hand one user's cache to another", async () => {
    signedInAs("user_1");
    const mod = await import("@/lib/query-persist");
    await mod.createPersister().persistClient({
      timestamp: Date.now(),
      buster: "",
      clientState: { mutations: [], queries: [] },
    });

    signedInAs("user_2");
    const restored = await mod.createPersister().restoreClient();

    expect(restored).toBeUndefined();
    expect(storage.keys()).toEqual([]); // and the mismatched payload is dropped
  });
});

describe("root destination memory", () => {
  it("the purger clears what the writer wrote", async () => {
    signedInAs("user_1");
    const mod = await import("@/lib/last-destination");

    mod.writeLastDestination("/today");
    expect(mod.readLastDestination()).toBe("/today");

    mod.purgeLastDestination();

    expect(mod.readLastDestination()).toBeNull();
    expect(storage.keys()).toEqual([]);
  });

  it("only trusts the two values it writes", async () => {
    signedInAs("user_1");
    const mod = await import("@/lib/last-destination");

    storage.setItem("climb-agent-last-destination", "/subscribe");

    // An unexpected value must not be followed blindly on a cold offline start.
    expect(mod.readLastDestination()).toBeNull();
  });
});

describe("offline outbox", () => {
  it("is scoped per user — one user cannot drain another's queue", async () => {
    signedInAs("user_1");
    const outboxA = await import("@/lib/outbox");
    outboxA.enqueue("feedback", { a: 1 });
    expect(outboxA.pendingCount()).toBe(1);

    vi.resetModules();
    signedInAs("user_2");
    const outboxB = await import("@/lib/outbox");

    expect(outboxB.pendingCount()).toBe(0);
    // user_1's entry is still on the device, untouched, under its own key.
    expect(storage.keys().some((k) => k.includes("user_1"))).toBe(true);
  });
});
