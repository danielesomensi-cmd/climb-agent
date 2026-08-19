/**
 * @vitest-environment jsdom
 *
 * B339 — the sign-in page must never be a blank screen.
 *
 * The bug these pin: `<SignIn />` renders nothing until Clerk's frontend API
 * answers, so a blocked `clerk.climbagent.app` produced an empty black page and
 * the visitor concluded the app was broken. The contract is now: something is
 * always on screen, and after the timeout that something names the cause.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";

const mockUseAuth = vi.fn();
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => mockUseAuth(),
}));

import { ClerkGate } from "../clerk-gate";

const CHILD = <p>the real sign-in form</p>;

describe("ClerkGate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
    mockUseAuth.mockReset();
  });

  it("renders the children once Clerk has loaded", () => {
    mockUseAuth.mockReturnValue({ isLoaded: true });
    render(<ClerkGate>{CHILD}</ClerkGate>);
    expect(screen.getByText("the real sign-in form")).toBeTruthy();
  });

  it("shows a loading state — never a blank page — while Clerk is still loading", () => {
    mockUseAuth.mockReturnValue({ isLoaded: false });
    const { container } = render(<ClerkGate>{CHILD}</ClerkGate>);

    expect(container.textContent).toContain("Loading sign-in");
    // The failure message must not fire early: a slow network is not a block.
    expect(screen.queryByText(/Can't reach the sign-in service/)).toBeNull();
    expect(screen.queryByText("the real sign-in form")).toBeNull();
  });

  it("explains the failure after the timeout instead of leaving an empty screen", () => {
    mockUseAuth.mockReturnValue({ isLoaded: false });
    render(<ClerkGate>{CHILD}</ClerkGate>);

    act(() => {
      vi.advanceTimersByTime(8000);
    });

    expect(screen.getByText(/Can't reach the sign-in service/)).toBeTruthy();
    // The recovery affordance is what makes it actionable, not the wording.
    expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy();
  });

  it("still yields to Clerk when it loads after the timeout has fired", () => {
    mockUseAuth.mockReturnValue({ isLoaded: false });
    const { rerender } = render(<ClerkGate>{CHILD}</ClerkGate>);

    act(() => {
      vi.advanceTimersByTime(8000);
    });
    expect(screen.getByText(/Can't reach the sign-in service/)).toBeTruthy();

    mockUseAuth.mockReturnValue({ isLoaded: true });
    rerender(<ClerkGate>{CHILD}</ClerkGate>);

    expect(screen.getByText("the real sign-in form")).toBeTruthy();
    expect(screen.queryByText(/Can't reach the sign-in service/)).toBeNull();
  });
});
