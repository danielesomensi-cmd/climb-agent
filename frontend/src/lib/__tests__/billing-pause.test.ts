/**
 * @vitest-environment jsdom
 *
 * B323: the suite default is node; render/hook tests opt in per file.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

/**
 * A285 — `enforced` is the field that keeps the paused UI honest.
 *
 * The failure it prevents is specific: with billing paused the server calls
 * everyone `active`, so Settings would announce a subscription that does not
 * exist and offer a billing portal that 404s. The default matters as much as
 * the value — anything short of an explicit `false` must read as enforced,
 * or a stale cache or an older backend could hide a live paywall.
 */

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const getSubscriptionStatus = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError,
  getSubscriptionStatus: (...args: unknown[]) => getSubscriptionStatus(...args),
}));

let useSubscription: typeof import("@/lib/hooks/use-subscription").useSubscription;

beforeEach(async () => {
  vi.resetModules();
  getSubscriptionStatus.mockReset();
  ({ useSubscription } = await import("@/lib/hooks/use-subscription"));
});

/** What the server sends for an entitled user, minus the A285 field. */
const ENTITLED = {
  status: "active",
  is_active: true,
  trial_days_remaining: null,
  can_interact: true,
  has_payment_method: true,
};

const PAUSED = { ...ENTITLED, enforced: false };

describe("useSubscription — A285 enforced", () => {
  it("reports enforced=false when the server says billing is paused", async () => {
    getSubscriptionStatus.mockResolvedValue(PAUSED);
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.enforced).toBe(false);
    // The pause must still grant access — that is the whole point.
    expect(result.current.canInteract).toBe(true);
  });

  it("defaults to enforced when an older backend omits the field", async () => {
    getSubscriptionStatus.mockResolvedValue(ENTITLED);
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.enforced).toBe(true);
  });

  it("reports enforced=true for a genuine paying subscriber", async () => {
    getSubscriptionStatus.mockResolvedValue({ ...PAUSED, enforced: true });
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.enforced).toBe(true);
  });

  it("stays enforced while the first answer is still in flight", () => {
    getSubscriptionStatus.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useSubscription());

    expect(result.current.loading).toBe(true);
    expect(result.current.enforced).toBe(true);
  });

  it("stays enforced when the server denies (B202 fail-closed is untouched)", async () => {
    getSubscriptionStatus.mockRejectedValue(new ApiError(402, "nope"));
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.canInteract).toBe(false);
    expect(result.current.enforced).toBe(true);
  });
});
