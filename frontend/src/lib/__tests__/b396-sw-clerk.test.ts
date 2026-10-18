import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * B396 — Clerk's scripts get their own version-agnostic cache in the service
 * worker.
 *
 * They used to fall into the per-build cache (any `.js`), which `activate`
 * empties on every deploy: ~130 KB br plus a no-store redirect per script on
 * the critical path of the first open after each deploy. The rule that makes
 * a persistent cache safe: only a successful, NON-opaque (CORS) answer is ever
 * stored — Clerk loads both scripts with crossorigin="anonymous".
 *
 * The worker is executed for real here, against an in-memory Cache API.
 */
const SRC = readFileSync(join(process.cwd(), "public/sw.template.js"), "utf8");
const ORIGIN = "https://climbagent.app";
const CLERK_JS = "https://clerk.climbagent.app/npm/@clerk/clerk-js@6/dist/clerk.browser.js";
const CLERK_UI = "https://clerk.climbagent.app/npm/@clerk/ui@1/dist/ui.browser.js";

type FakeResponse = { ok: boolean; status: number; type: string; body: string; clone(): FakeResponse };

function fakeResponse(body: string, init: { status?: number; type?: string } = {}): FakeResponse {
  const status = init.status ?? 200;
  const res: FakeResponse = {
    ok: status >= 200 && status < 300,
    status,
    type: init.type ?? "cors",
    body,
    clone: () => res,
  };
  return res;
}

const keyOf = (req: string | { url: string }) => (typeof req === "string" ? req : req.url);

function loadWorker(fetchImpl: (req: Request) => Promise<unknown>) {
  const handlers: Record<string, (event: unknown) => void> = {};
  const store = new Map<string, Map<string, unknown>>();
  const cacheFor = (name: string) => {
    if (!store.has(name)) store.set(name, new Map());
    const m = store.get(name)!;
    const clone = (r: unknown) => (r && typeof (r as Response).clone === "function" ? (r as Response).clone() : r);
    return {
      match: async (req: string | { url: string }) => clone(m.get(keyOf(req))),
      put: async (req: string | { url: string }, res: unknown) => void m.set(keyOf(req), res),
      keys: async () => [...m.keys()].map((url) => ({ url })),
      delete: async (req: string | { url: string }) => m.delete(keyOf(req)),
    };
  };
  const caches = {
    open: async (name: string) => cacheFor(name),
    match: async (req: string | { url: string }, opts?: { cacheName?: string }) => {
      const names = opts?.cacheName ? [opts.cacheName] : [...store.keys()];
      for (const n of names) {
        const hit = store.get(n)?.get(keyOf(req));
        if (hit) return hit;
      }
      return undefined;
    },
    keys: async () => [...store.keys()],
    delete: async (name: string) => store.delete(name),
  };
  const self = {
    addEventListener: (type: string, fn: (event: unknown) => void) => {
      handlers[type] = fn;
    },
    location: { origin: ORIGIN },
    clients: { claim: async () => {} },
    skipWaiting: () => {},
  };
  new Function("self", "caches", "fetch", SRC)(self, caches, fetchImpl);
  return { handlers, store, caches };
}

async function request(worker: ReturnType<typeof loadWorker>, url: string) {
  let responded: Promise<unknown> | undefined;
  const waits: Promise<unknown>[] = [];
  worker.handlers.fetch({
    request: new Request(url, { mode: "cors" }),
    respondWith: (p: Promise<unknown>) => {
      responded = Promise.resolve(p);
    },
    waitUntil: (p: Promise<unknown>) => void waits.push(p),
  });
  const res = responded ? await responded : undefined;
  await Promise.all(waits);
  return { res, handled: responded !== undefined };
}

const constValue = (name: string) => SRC.match(new RegExp(`const ${name} = ([^;]+);`))?.[1] ?? "";

describe("service worker — Clerk scripts (B396)", () => {
  it("the Clerk cache is version-agnostic and survives activate", async () => {
    expect(constValue("CLERK_CACHE_NAME")).not.toMatch(/__BUILD_ID__|CACHE_NAME/);

    const worker = loadWorker(async () => fakeResponse("x"));
    await worker.caches.open("climb-agent-clerk-v1");
    await worker.caches.open("climb-agent-oldbuild");
    let done: Promise<unknown> = Promise.resolve();
    worker.handlers.activate({ waitUntil: (p: Promise<unknown>) => (done = p) });
    await done;

    expect([...worker.store.keys()]).toContain("climb-agent-clerk-v1");
    expect([...worker.store.keys()]).not.toContain("climb-agent-oldbuild");
  });

  it("first load: fetched and stored in the Clerk cache (not the per-build one)", async () => {
    const fetchImpl = vi.fn(async () => fakeResponse("clerk-js"));
    const worker = loadWorker(fetchImpl);

    const { res } = await request(worker, CLERK_JS);

    expect((res as FakeResponse).body).toBe("clerk-js");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(worker.store.get("climb-agent-clerk-v1")?.has(CLERK_JS)).toBe(true);
    expect(worker.store.get("climb-agent-__BUILD_ID__")?.has(CLERK_JS) ?? false).toBe(false);
  });

  it("next loads come from the cache, with no network at all while the copy is fresh", async () => {
    const fetchImpl = vi.fn(async () => fakeResponse("clerk-ui"));
    const worker = loadWorker(fetchImpl);

    await request(worker, CLERK_UI);
    const { res } = await request(worker, CLERK_UI);

    expect((res as FakeResponse).body).toBe("clerk-ui");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("a copy older than a day is served at once and refreshed in the background", async () => {
    let version = "v1";
    const fetchImpl = vi.fn(async () => fakeResponse(`clerk-js@${version}`));
    const worker = loadWorker(fetchImpl);
    await request(worker, CLERK_JS);

    // Age the stored copy past CLERK_REVALIDATE_MS.
    worker.store
      .get("climb-agent-clerk-v1")!
      .set(`${CLERK_JS}?sw-stored-at`, new Response(String(Date.now() - 25 * 60 * 60 * 1000)));
    version = "v2";

    const { res } = await request(worker, CLERK_JS);
    expect((res as FakeResponse).body).toBe("clerk-js@v1"); // no wait on the network
    expect(fetchImpl).toHaveBeenCalledTimes(2);

    const { res: next } = await request(worker, CLERK_JS);
    expect((next as FakeResponse).body).toBe("clerk-js@v2"); // the update landed
  });

  it("an OPAQUE response is passed through but never stored", async () => {
    const fetchImpl = vi.fn(async () => fakeResponse("", { status: 0, type: "opaque" }));
    const worker = loadWorker(fetchImpl);

    await request(worker, CLERK_JS);
    await request(worker, CLERK_JS);

    expect(worker.store.get("climb-agent-clerk-v1")?.has(CLERK_JS) ?? false).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("an error answer is never stored either", async () => {
    const worker = loadWorker(async () => fakeResponse("oops", { status: 503 }));
    await request(worker, CLERK_JS);
    expect(worker.store.get("climb-agent-clerk-v1")?.has(CLERK_JS) ?? false).toBe(false);
  });

  it("only Clerk's own domain: a same-origin /npm/@clerk path is not treated as Clerk", async () => {
    const worker = loadWorker(async () => fakeResponse("x", { type: "basic" }));
    await request(worker, `${ORIGIN}/npm/@clerk/clerk-js@6/dist/clerk.browser.js`);
    expect(worker.store.get("climb-agent-clerk-v1")?.size ?? 0).toBe(0);
  });
});
