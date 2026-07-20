import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * A245 C-1 (F8) — the paywall rule. This is the highest-consequence branch in
 * the app: get it wrong one way and a paying climber in a gym with no signal is
 * told to buy a subscription; get it wrong the other way and an expired
 * subscription keeps working forever.
 */

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

vi.mock("@/lib/api", () => ({
  ApiError,
  getSubscriptionStatus: vi.fn(),
}));

let shouldDenyOnError: (err: unknown, everAnswered: boolean) => boolean;

beforeEach(async () => {
  vi.resetModules();
  ({ shouldDenyOnError } = await import("@/lib/hooks/use-subscription"));
});

describe("shouldDenyOnError", () => {
  it.each([401, 402, 403])(
    "denies on %i even after a successful answer — the server ruled on entitlement",
    (status) => {
      expect(shouldDenyOnError(new ApiError(status, "nope"), true)).toBe(true);
    },
  );

  it.each([0, 408, 429, 500, 502, 503])(
    "keeps the last known state on transport failure %i",
    (status) => {
      expect(shouldDenyOnError(new ApiError(status, "boom"), true)).toBe(false);
    },
  );

  it("denies on ANY failure before the first successful answer (B202 fail-closed)", () => {
    expect(shouldDenyOnError(new ApiError(0, "offline"), false)).toBe(true);
    expect(shouldDenyOnError(new ApiError(500, "boom"), false)).toBe(true);
    expect(shouldDenyOnError(new TypeError("bad"), false)).toBe(true);
  });

  it("denies on a non-ApiError after a successful answer only if never answered", () => {
    // A thrown non-ApiError is unclassifiable; once we have a known-good state
    // it is still safer to keep it than to bounce a paying user to /subscribe.
    expect(shouldDenyOnError(new TypeError("bad"), true)).toBe(false);
  });
});
