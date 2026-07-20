import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * B290 (closes F54) — every producer of the guided-session storage key must
 * agree, and they must keep agreeing.
 *
 * The bug this pins: A245 B-2 fixed ONE of three inline key builders. The
 * readers moved to the real Clerk user id; the two writers (the guided player
 * and SessionCard) kept emitting the literal string "clerk". Nothing failed
 * loudly — the guided player still round-tripped its own state — but resume
 * went blind, the offline feedback retry never found its queue, and the legacy
 * purge then deleted the live sessions those writers were still producing.
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

const SRC = join(process.cwd(), "src");

describe("guided storage key — single producer", () => {
  it("is scoped to the real user id, never the literal 'clerk'", async () => {
    signedInAs("user_2abcDEF");
    const { guidedStorageKey } = await import("@/lib/guided-session-utils");

    const key = guidedStorageKey("2026-07-20", "strength_long");
    expect(key).toBe("guided_session_user_2abcDEF_2026-07-20_strength_long");
    expect(key).not.toContain("guided_session_clerk_");
  });

  it("falls back to an explicit anon scope when signed out", async () => {
    signedInAs(null);
    const { guidedStorageKey } = await import("@/lib/guided-session-utils");
    expect(guidedStorageKey("2026-07-20", "s")).toBe("guided_session_anon_2026-07-20_s");
  });

  /**
   * The structural guard. A future edit that re-introduces an inline key would
   * pass every behavioural test above while breaking production exactly as
   * B290 did — so assert that no source file builds the prefix by hand.
   */
  it("no source file builds the key inline", () => {
    const files = [
      "app/(guided)/guided/[date]/[sessionId]/page.tsx",
      "components/training/session-card.tsx",
      "app/(main)/today/page.tsx",
    ];
    for (const rel of files) {
      // Strip comments first: this guard is about CODE. The files legitimately
      // describe the old key in prose so the next reader knows what went wrong.
      const src = readFileSync(join(SRC, rel), "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      // Template literals that assemble the prefix from a variable.
      expect(src, `${rel} builds the guided key inline`).not.toMatch(
        /`guided_session_\$\{/,
      );
      expect(src, `${rel} hardcodes the "clerk" scope`).not.toMatch(
        /guided_session_clerk_/,
      );
    }
  });
});

describe("legacy key migration", () => {
  const LEGACY = "guided_session_clerk_2026-07-20_strength_long";
  const session = (extra: Record<string, unknown> = {}) =>
    JSON.stringify({
      date: "2026-07-20",
      sessionId: "strength_long",
      startedAt: new Date().toISOString(),
      currentIndex: 1,
      exercises: [],
      ...extra,
    });

  it("moves a live session onto the current user's key", async () => {
    storage.setItem(LEGACY, session());
    signedInAs("user_1");
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();

    expect(storage.getItem("guided_session_user_1_2026-07-20_strength_long")).not.toBeNull();
    expect(storage.getItem(LEGACY)).toBeNull();
  });

  it("carries pending offline feedback with it", async () => {
    // The queued feedback lives INSIDE the session state, so migrating the
    // session is what rescues it.
    storage.setItem(LEGACY, session({ submitStatus: "feedback_pending" }));
    signedInAs("user_1");
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();

    const moved = storage.getItem("guided_session_user_1_2026-07-20_strength_long");
    expect(JSON.parse(moved!).submitStatus).toBe("feedback_pending");
  });

  it("does NOT adopt legacy data when nobody is signed in", async () => {
    storage.setItem(LEGACY, session());
    signedInAs(null);
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();

    // Left untouched — never handed to the anon scope.
    expect(storage.getItem(LEGACY)).not.toBeNull();
    expect(storage.getItem("guided_session_anon_2026-07-20_strength_long")).toBeNull();
  });

  it("never overwrites an existing key for the current user", async () => {
    const mine = "guided_session_user_1_2026-07-20_strength_long";
    storage.setItem(LEGACY, session({ currentIndex: 99 }));
    storage.setItem(mine, session({ currentIndex: 5 }));
    signedInAs("user_1");
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();

    expect(JSON.parse(storage.getItem(mine)!).currentIndex).toBe(5);
  });

  it("drops stale entries instead of adopting a previous owner's session", async () => {
    const old = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
    storage.setItem(LEGACY, session({ startedAt: old }));
    signedInAs("user_1");
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();

    expect(storage.getItem("guided_session_user_1_2026-07-20_strength_long")).toBeNull();
    expect(storage.getItem(LEGACY)).toBeNull();
  });

  it("is idempotent — a second open does not re-purge what it migrated", async () => {
    storage.setItem(LEGACY, session());
    signedInAs("user_1");
    const { migrateLegacyGuidedKeys } = await import("@/lib/guided-session-utils");

    migrateLegacyGuidedKeys();
    migrateLegacyGuidedKeys();

    expect(storage.getItem("guided_session_user_1_2026-07-20_strength_long")).not.toBeNull();
  });
});
