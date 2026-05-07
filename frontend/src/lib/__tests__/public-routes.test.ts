import { describe, it, expect } from "vitest";
import { PUBLIC_ROUTES } from "../public-routes";

describe("PUBLIC_ROUTES", () => {
  it("includes /onboarding/welcome (B-SHOP-FLYER-01: shop QR landing)", () => {
    expect(PUBLIC_ROUTES).toContain("/onboarding/welcome");
  });

  it("keeps other onboarding steps gated (only /welcome is public)", () => {
    const otherOnboardingSteps = [
      "/onboarding/install",
      "/onboarding/profile",
      "/onboarding/discipline",
      "/onboarding/experience",
      "/onboarding/grades",
      "/onboarding/goals",
      "/onboarding/weaknesses",
      "/onboarding/tests",
      "/onboarding/limitations",
      "/onboarding/locations",
      "/onboarding/availability",
      "/onboarding/trips",
      "/onboarding/review",
      "/onboarding/start-week",
      "/onboarding/recover",
    ];
    for (const step of otherOnboardingSteps) {
      expect(PUBLIC_ROUTES).not.toContain(step);
    }
  });

  it("retains existing public routes (regression guard)", () => {
    expect(PUBLIC_ROUTES).toEqual(
      expect.arrayContaining(["/", "/sign-in(.*)", "/sign-up(.*)", "/legal", "/demo(.*)"]),
    );
  });
});
