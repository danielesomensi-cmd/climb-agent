import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import type { PersistedClient } from "@tanstack/react-query-persist-client";

/**
 * B396 — the React Query persister wrote on every cache event: ~100 KB of
 * JSON.stringify plus a synchronous localStorage.setItem, 5-10 times per tap,
 * guided session included. Now: the first write at once, then at most one per
 * PERSIST_THROTTLE_MS carrying the latest snapshot, flushed when the page is
 * hidden — and never after a purge (sign-out / account switch).
 */

const KEY = "climb-agent-rq-cache-v1";

class MemoryStorage {
  map = new Map<string, string>();
  writes = 0;
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) {
    if (k === KEY) this.writes += 1;
    this.map.set(k, v);
  }
  removeItem(k: string) { this.map.delete(k); }
}

let storage: MemoryStorage;
let listeners: Record<string, Array<() => void>>;
let visibility: "visible" | "hidden";

function client(tag: string): PersistedClient {
  return {
    timestamp: Date.now(),
    buster: "",
    clientState: { mutations: [], queries: [{ queryKey: [tag] } as never] },
  };
}

function storedTag(): string | null {
  const raw = storage.getItem(KEY);
  if (!raw) return null;
  const env = JSON.parse(raw) as { client: PersistedClient };
  return (env.client.clientState.queries[0]?.queryKey?.[0] as string) ?? null;
}

function storedUser(): string | null {
  const raw = storage.getItem(KEY);
  return raw ? (JSON.parse(raw) as { userId: string }).userId : null;
}

function signIn(userId: string) {
  vi.stubGlobal("window", {
    localStorage: storage,
    Clerk: { loaded: true, session: {}, user: { id: userId } },
    addEventListener: (type: string, fn: () => void) => {
      (listeners[type] ??= []).push(fn);
    },
  });
}

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  storage = new MemoryStorage();
  listeners = {};
  visibility = "visible";
  vi.stubGlobal("navigator", { onLine: true });
  vi.stubGlobal("document", {
    get visibilityState() {
      return visibility;
    },
  });
  signIn("user_1");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("throttled persist", () => {
  it("writes the first snapshot at once, then one trailing write with the latest", async () => {
    const { createPersister, PERSIST_THROTTLE_MS } = await import("@/lib/query-persist");
    const persister = createPersister();

    persister.persistClient(client("a"));
    expect(storage.writes).toBe(1);
    expect(storedTag()).toBe("a");

    // A burst of cache events inside the window: none hits storage yet…
    persister.persistClient(client("b"));
    persister.persistClient(client("c"));
    persister.persistClient(client("d"));
    expect(storage.writes).toBe(1);

    // …and the end of the window writes once, with the LAST snapshot.
    vi.advanceTimersByTime(PERSIST_THROTTLE_MS);
    expect(storage.writes).toBe(2);
    expect(storedTag()).toBe("d");
  });

  it("at most one write per window under a steady stream of events", async () => {
    const { createPersister, PERSIST_THROTTLE_MS } = await import("@/lib/query-persist");
    const persister = createPersister();

    for (let i = 0; i < 50; i++) {
      persister.persistClient(client(`e${i}`));
      vi.advanceTimersByTime(100); // 10 events per second, for 5 seconds
    }
    vi.advanceTimersByTime(PERSIST_THROTTLE_MS);

    expect(storage.writes).toBeLessThanOrEqual(7);
    expect(storedTag()).toBe("e49");
  });

  it("flushes the pending snapshot when the page is hidden (iOS may kill the PWA next)", async () => {
    const { createPersister } = await import("@/lib/query-persist");
    const persister = createPersister();

    persister.persistClient(client("a"));
    persister.persistClient(client("b"));
    expect(storedTag()).toBe("a");

    visibility = "hidden";
    listeners.visibilitychange?.forEach((fn) => fn());
    expect(storedTag()).toBe("b");
  });

  it("flushes on pagehide too", async () => {
    const { createPersister } = await import("@/lib/query-persist");
    const persister = createPersister();

    persister.persistClient(client("a"));
    persister.persistClient(client("b"));
    listeners.pagehide?.forEach((fn) => fn());
    expect(storedTag()).toBe("b");
  });

  it("a write scheduled before a purge never lands after it", async () => {
    const { createPersister, purgePersistedCache, PERSIST_THROTTLE_MS } = await import("@/lib/query-persist");
    const persister = createPersister();

    persister.persistClient(client("a"));
    persister.persistClient(client("user_1_private"));
    purgePersistedCache(); // sign-out / account switch

    vi.advanceTimersByTime(PERSIST_THROTTLE_MS * 2);
    expect(storage.getItem(KEY)).toBeNull();
  });

  it("the owner is the user signed in when the data was cached, not at flush time", async () => {
    const { createPersister, PERSIST_THROTTLE_MS } = await import("@/lib/query-persist");
    const persister = createPersister();

    persister.persistClient(client("a"));
    persister.persistClient(client("b"));
    signIn("user_2"); // no purge in between: the pending write is still user_1's

    vi.advanceTimersByTime(PERSIST_THROTTLE_MS);
    expect(storedTag()).toBe("b");
    expect(storedUser()).toBe("user_1");
  });

  it("still refuses to persist without an identified user", async () => {
    vi.stubGlobal("window", { localStorage: storage, Clerk: { loaded: true, session: null, user: null } });
    const { createPersister } = await import("@/lib/query-persist");
    createPersister().persistClient(client("a"));
    vi.advanceTimersByTime(5000);
    expect(storage.getItem(KEY)).toBeNull();
  });
});

describe("persisted queries (B396 — the three /today cards)", () => {
  it("adds quotes, tips and milestones to state and week", async () => {
    const { PERSISTED_QUERY_PREFIXES } = await import("@/lib/query-persist");
    expect(PERSISTED_QUERY_PREFIXES).toEqual(
      expect.arrayContaining(["state", "week", "quotes", "tips", "milestones"]),
    );
  });

  it("never the subscription: a cold open must ask the server first (B202)", async () => {
    const { PERSISTED_QUERY_PREFIXES } = await import("@/lib/query-persist");
    expect(PERSISTED_QUERY_PREFIXES).not.toContain("subscription");
  });
});
