import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { PUBLIC_ROUTES } from "@/lib/public-routes";

const SW = readFileSync(join(process.cwd(), "public/sw.template.js"), "utf8");

/**
 * B292 — the offline shell shipped broken because every failure on the path was
 * silent.
 *
 * `/offline` and `/manifest.json` were behind Clerk and answered 404. The
 * service worker precached `/today` and `/week`, which are also behind Clerk,
 * and swallowed each `cache.add()` rejection per-URL — so the install
 * "succeeded" with an essentially empty cache and the PWA still would not open
 * with no network.
 */
describe("service worker precache", () => {
  const staticAssets: string[] = (() => {
    const m = SW.match(/const STATIC_ASSETS = \[([\s\S]*?)\];/);
    if (!m) throw new Error("STATIC_ASSETS not found in sw.template.js");
    return [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  })();

  it("precaches only routes the middleware lets through unauthenticated", () => {
    // Anything else 404s at install time and silently drops out of the cache.
    const publicish = (url: string) =>
      PUBLIC_ROUTES.some((r) => r === url || (r.endsWith("(.*)") && url.startsWith(r.slice(0, -4))));

    const notPublic = staticAssets.filter((u) => !publicish(u));
    expect(notPublic).toEqual([]);
  });

  it("still precaches the offline fallback itself", () => {
    // A fallback that isn't in the cache can never be served.
    expect(staticAssets).toContain("/offline");
  });

  it("does not precache authenticated app routes", () => {
    expect(staticAssets).not.toContain("/today");
    expect(staticAssets).not.toContain("/week");
  });

  it("reports a precache failure loudly", () => {
    // It stays non-fatal (one bad URL must not abort the install) but must not
    // be a console.warn nobody reads — that is how the empty shell shipped.
    expect(SW).toMatch(/PRECACHE FAILED/);
  });
});

describe("public routes", () => {
  it("exposes the offline fallback", () => {
    expect(PUBLIC_ROUTES).toContain("/offline");
  });

  it("exposes the PWA manifest", () => {
    // The middleware matcher excludes `.webmanifest` but not `.json`
    // (`js(?!on)`), so this file needs an explicit entry.
    expect(PUBLIC_ROUTES).toContain("/manifest.json");
  });

  it("does not accidentally expose the authenticated app", () => {
    for (const guarded of ["/today", "/week", "/settings", "/plan"]) {
      expect(PUBLIC_ROUTES).not.toContain(guarded);
    }
  });
});

describe("empty-state guard on /today", () => {
  const today = readFileSync(
    join(process.cwd(), "src/app/(main)/today/page.tsx"),
    "utf8",
  );

  it("never shows the onboarding prompt while state is still being fetched", () => {
    const block = today.slice(today.indexOf("No macrocycle — prompt to start onboarding"));
    const condition = block.slice(0, block.indexOf("&& ("));
    expect(condition).toContain("!stateQuery.isFetching");
  });
});
