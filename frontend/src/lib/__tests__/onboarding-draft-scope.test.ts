import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * A256 — the wizard is public, so an anonymous draft is now a thing that
 * actually gets produced on real devices. That turns a previously dormant
 * asymmetry into a live data-leak path:
 *
 *   - `loadDraft()` ADOPTS `..._anon` when a user signs in (by design: the
 *     answers typed before signing up belong to whoever just signed up).
 *   - `clearOnboardingDraft()` used to delete only `..._user_XXX`.
 *
 * So after a successful submit the anonymous copy survived on the device. The
 * next visitor to start the wizard anonymously — a friend's phone, a gym
 * tablet, a shared laptop — would have it adopted into THEIR wizard and see the
 * previous person's name, age, weight and grades pre-filled.
 *
 * The test drives the real key generator rather than a hardcoded string: the
 * bug class here is precisely a purger and a producer drifting apart (cf. the
 * B290 guard in user-scoped-storage.test.ts), which a test asserting its own
 * assumed key would not catch.
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
let session: MemoryStorage;

function signedInAs(userId: string | null) {
  const Clerk = userId
    ? { session: {}, user: { id: userId }, loaded: true }
    : { session: null, user: null, loaded: true };
  vi.stubGlobal("window", { localStorage: storage, sessionStorage: session, Clerk });
  vi.stubGlobal("localStorage", storage);
  vi.stubGlobal("sessionStorage", session);
}

beforeEach(() => {
  storage = new MemoryStorage();
  session = new MemoryStorage();
  vi.resetModules();
});

afterEach(() => vi.unstubAllGlobals());

describe("onboarding draft scoping", () => {
  it("clears the anonymous draft too, not just the signed-in one", async () => {
    signedInAs("user_1");
    const { clearOnboardingDraft, draftKey } = await import(
      "@/components/onboarding/onboarding-context"
    );

    // The state right after a public-wizard signup: answers were typed
    // anonymously, then mirrored under the real user on adoption.
    const envelope = JSON.stringify({
      data: { profile: { name: "Somebody Else" } },
      deepestStep: 11,
      savedAt: Date.now(),
    });
    storage.setItem(draftKey(null), envelope);
    storage.setItem(draftKey("user_1"), envelope);

    clearOnboardingDraft();

    expect(storage.getItem(draftKey("user_1"))).toBeNull();
    // The one that used to survive.
    expect(storage.getItem(draftKey(null))).toBeNull();
    expect(storage.keys()).toEqual([]);
  });

  it("keeps anonymous and signed-in drafts under distinct keys", async () => {
    signedInAs("user_1");
    const { draftKey } = await import("@/components/onboarding/onboarding-context");
    expect(draftKey(null)).not.toBe(draftKey("user_1"));
  });

  it("does not touch another signed-in user's draft", async () => {
    signedInAs("user_1");
    const { clearOnboardingDraft, draftKey } = await import(
      "@/components/onboarding/onboarding-context"
    );
    storage.setItem(draftKey("user_2"), "{}");

    clearOnboardingDraft();

    expect(storage.getItem(draftKey("user_2"))).toBe("{}");
  });
});
