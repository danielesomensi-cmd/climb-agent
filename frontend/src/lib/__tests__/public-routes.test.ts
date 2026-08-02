import { describe, it, expect } from "vitest";
import { PUBLIC_ROUTES } from "../public-routes";
import { ONBOARDING_STEPS } from "../onboarding-steps";

describe("PUBLIC_ROUTES", () => {
  it("includes /onboarding/welcome (B-SHOP-FLYER-01: shop QR landing)", () => {
    expect(PUBLIC_ROUTES).toContain("/onboarding/welcome");
  });

  /**
   * A256 replaces the B292-era expectation ("only /welcome is public"). The
   * wizard is public on purpose now: the account is asked for at the submit
   * CTA on /review, not at step 1. See public-routes.ts.
   */
  it("makes every wizard step public (A256: no mid-wizard auth wall)", () => {
    for (const step of ONBOARDING_STEPS) {
      expect(PUBLIC_ROUTES).toContain(`/onboarding/${step}`);
    }
  });

  /**
   * B320 retired recovery-by-code. The route is gone, so listing it here would
   * open a path that no longer exists — and re-adding it would be the first
   * symptom of the dead feature coming back.
   */
  it("no longer exposes /onboarding/recover (B320: feature retired)", () => {
    expect(PUBLIC_ROUTES).not.toContain("/onboarding/recover");
  });

  /**
   * The wall has to keep standing SOMEWHERE. These two run only once a plan
   * exists, so a signed-out visitor reaching them means the wall moved by
   * accident rather than by design.
   */
  it("keeps post-plan steps gated", () => {
    for (const step of ["/onboarding/start-week", "/onboarding/install"]) {
      expect(PUBLIC_ROUTES).not.toContain(step);
    }
  });

  it("retains existing public routes (regression guard)", () => {
    expect(PUBLIC_ROUTES).toEqual(
      expect.arrayContaining(["/", "/sign-in(.*)", "/sign-up(.*)", "/legal", "/demo(.*)"]),
    );
  });
});
