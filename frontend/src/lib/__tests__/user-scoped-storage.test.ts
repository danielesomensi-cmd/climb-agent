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
  vi.stubGlobal("navigator", { onLine: true });
  const Clerk = userId
    ? { session: {}, user: { id: userId }, loaded: true }
    : { session: null, user: null, loaded: true };
  vi.stubGlobal("window", { localStorage: storage, Clerk });
  vi.stubGlobal("localStorage", storage);
}

/** B292b — offline: Clerk.js comes from the network, so it never initialises. */
function offline() {
  vi.stubGlobal("window", { localStorage: storage, Clerk: undefined });
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("navigator", { onLine: false });
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
    expect(storage.keys().filter((k) => k.startsWith("climb-agent-rq-cache")).length).toBe(1);

    purgePersistedCache();

    // The assertion that matters: the purger targeted the key that was
    // actually written, not a key it assumed was written.
    expect(storage.keys().filter((k) => k.startsWith("climb-agent-rq-cache"))).toEqual([]);
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
    // The mismatched payload is dropped. The only key left is the non-sensitive
    // "last user on this device" marker (B292b) — it is not a credential and is
    // what lets the cache survive an offline start, where Clerk cannot load.
    expect(storage.keys().filter((k) => k.startsWith("climb-agent-rq-cache"))).toEqual([]);
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

/**
 * B292b — the offline cold start, which is the entire point of the persisted
 * cache and the one case the original guard destroyed.
 *
 * Clerk.js is fetched from the network. With no connection it never
 * initialises, so `window.Clerk` is undefined, the user id resolves to null,
 * and the old code read that as "a different user" → purge. Every offline open
 * deleted the plan it was supposed to be showing.
 */
describe("offline cold start", () => {
  async function persistAs(userId: string) {
    signedInAs(userId);
    const mod = await import("@/lib/query-persist");
    await mod.createPersister().persistClient({
      timestamp: Date.now(),
      buster: "",
      clientState: { mutations: [], queries: [] },
    });
    // Restoring once online is what records "last user on this device".
    await mod.createPersister().restoreClient();
  }

  it("restores the cache when Clerk cannot load", async () => {
    await persistAs("user_1");

    vi.resetModules();
    offline();
    const mod = await import("@/lib/query-persist");
    const restored = await mod.createPersister().restoreClient();

    expect(restored).toBeDefined();
  });

  it("does NOT purge the cache when it cannot identify the user", async () => {
    await persistAs("user_1");

    vi.resetModules();
    offline();
    const mod = await import("@/lib/query-persist");
    await mod.createPersister().restoreClient();

    // The regression: an offline open used to wipe this.
    expect(storage.keys().some((k) => k.startsWith("climb-agent-rq-cache"))).toBe(true);
  });

  it("does not stall waiting for Clerk when the browser knows it is offline", async () => {
    await persistAs("user_1");

    vi.resetModules();
    offline();
    const mod = await import("@/lib/query-persist");

    const started = Date.now();
    await mod.createPersister().restoreClient();
    // Was 3s of blank screen on every single offline open.
    expect(Date.now() - started).toBeLessThan(500);
  });

  it("survives repeated offline opens", async () => {
    await persistAs("user_1");

    vi.resetModules();
    offline();
    const mod = await import("@/lib/query-persist");
    await mod.createPersister().restoreClient();
    await mod.createPersister().restoreClient();
    await mod.createPersister().restoreClient();

    expect(await mod.createPersister().restoreClient()).toBeDefined();
  });

  it("still refuses to restore across a real user switch", async () => {
    await persistAs("user_1");

    vi.resetModules();
    signedInAs("user_2"); // Clerk ANSWERED: genuinely someone else
    const mod = await import("@/lib/query-persist");

    expect(await mod.createPersister().restoreClient()).toBeUndefined();
    expect(storage.keys().filter((k) => k.startsWith("climb-agent-rq-cache"))).toEqual([]);
  });

  it("does not restore anything on a device that was never signed in", async () => {
    offline();
    const mod = await import("@/lib/query-persist");
    expect(await mod.createPersister().restoreClient()).toBeUndefined();
  });
});
