import { describe, it, expect } from "vitest";
import { ONBOARDING_STEPS, stepIndexOf } from "@/lib/onboarding-steps";
import { describeSubmitError } from "@/lib/onboarding-submit";
import { ApiError } from "@/lib/api";

describe("onboarding step list", () => {
  it("does not count welcome — it is a hero screen with no input (F45)", () => {
    expect(ONBOARDING_STEPS).not.toContain("welcome");
  });

  it("does not count install — it runs after the plan exists now (F38)", () => {
    expect(ONBOARDING_STEPS).not.toContain("install");
  });

  it("makes the first fillable step report as 1 of N, not 2 of N", () => {
    expect(stepIndexOf("/onboarding/profile")).toBe(0);
  });

  it("resolves every step path it declares", () => {
    for (const step of ONBOARDING_STEPS) {
      expect(stepIndexOf(`/onboarding/${step}`)).toBeGreaterThanOrEqual(0);
    }
  });

  it("returns -1 for a route outside the wizard", () => {
    expect(stepIndexOf("/today")).toBe(-1);
  });
});

/**
 * A245 Phase D (F17) — the submit error copy. The rule being pinned is that the
 * user never sees a status code or a JSON body at the highest-intent moment in
 * the product, and that we only invite a retry when one could actually work.
 */
describe("describeSubmitError", () => {
  it("never leaks a raw status or JSON body", () => {
    for (const status of [400, 401, 422, 429, 500, 503, 0]) {
      const { message } = describeSubmitError(new ApiError(status, `API ${status}: {"detail":"boom"}`));
      expect(message).not.toMatch(/\d{3}/);
      expect(message).not.toContain("detail");
      expect(message).not.toContain("{");
    }
  });

  it("does not invite a retry that cannot succeed", () => {
    expect(describeSubmitError(new ApiError(429, "")).retryable).toBe(false);
    expect(describeSubmitError(new ApiError(401, "")).retryable).toBe(false);
  });

  it("invites a retry on transport and server faults", () => {
    expect(describeSubmitError(new ApiError(0, "")).retryable).toBe(true);
    expect(describeSubmitError(new ApiError(500, "")).retryable).toBe(true);
    expect(describeSubmitError(new ApiError(422, "")).retryable).toBe(true);
  });

  it("reassures that the answers survive, whatever failed", () => {
    for (const status of [0, 401, 422, 429, 500]) {
      const { message } = describeSubmitError(new ApiError(status, ""));
      expect(message.toLowerCase()).toMatch(/saved|redo the wizard/);
    }
  });

  it("handles a non-ApiError without throwing", () => {
    const r = describeSubmitError(new TypeError("Load failed"));
    expect(r.retryable).toBe(true);
    expect(r.message).not.toContain("Load failed");
  });
});
