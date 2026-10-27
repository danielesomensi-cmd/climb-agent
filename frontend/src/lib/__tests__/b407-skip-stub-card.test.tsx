/**
 * @vitest-environment jsdom
 *
 * B407 — a skipped session is stored as a regeneration_easy stub carrying the
 * session actually skipped (B367 `skipped_original`). The card showed the stub:
 * on 27/10/2026 a home lunch ("Casa — gambe") skipped on a gym evening read
 * "Regeneration (Easy Climbing + Stretch) · Cocque · Skipped".
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }) }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }) }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  getSubscriptionStatus: vi.fn(),
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { SessionCard } from "@/components/training/session-card";
import type { SessionSlot } from "@/lib/types";

const GYMS = [
  { gym_id: "16710e5a", name: "Cocque", equipment: [] },
  { gym_id: "7bcac19a", name: "Boulder Forest", equipment: [] },
];

const stubResolved = {
  session: { session_name: "Regeneration (Easy Climbing + Stretch)" },
  resolved_session: { exercise_instances: [{ exercise_id: "general_pulse_raise", name: "Pulse Raise" }] },
};

function stub(original: Record<string, unknown>): SessionSlot {
  return {
    session_id: "regeneration_easy",
    slot: "lunch",
    location: "gym",
    gym_id: null,
    status: "skipped",
    resolved: stubResolved,
    skipped_original: original,
  } as unknown as SessionSlot;
}

function renderCard(session: SessionSlot) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SessionCard session={session} date="2026-10-27" gyms={GYMS} onUndo={() => {}} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("B407 — a skip stub shows the session that was skipped", () => {
  it("names the skipped custom, says Home, lists its exercises", () => {
    renderCard(stub({
      session_id: "custom_cs_53fc344d", slot: "lunch", location: "home", gym_id: null, status: "planned",
      is_custom: true, name: "Casa — gambe a una gamba", custom_session_id: "cs_53fc344d",
      exercises: [{ exercise_id: "reverse_lunge", name: "Reverse Lunge", sets: 3, reps: 8 }],
    }));
    expect(screen.getByText("Casa — gambe a una gamba")).toBeTruthy();
    expect(screen.queryByText(/Regeneration/)).toBeNull();
    expect(screen.getByText(/Home/)).toBeTruthy();
    expect(screen.queryByText(/Cocque/)).toBeNull();
    expect(screen.getByText("Skipped")).toBeTruthy();

    fireEvent.click(screen.getByText("Casa — gambe a una gamba"));
    expect(screen.getByText("Reverse Lunge")).toBeTruthy();
    expect(screen.queryByText("Pulse Raise")).toBeNull();
  });

  it("names a skipped catalog session and its own gym, without a Retry box", () => {
    renderCard(stub({
      session_id: "power_endurance_gym", slot: "evening", location: "gym", gym_id: "7bcac19a", status: "planned",
    }));
    expect(screen.getByText("Power Endurance Gym")).toBeTruthy();
    expect(screen.getByText(/Boulder Forest/)).toBeTruthy();

    fireEvent.click(screen.getByText("Power Endurance Gym"));
    expect(screen.queryByText("Retry")).toBeNull();
    expect(screen.queryByText("Pulse Raise")).toBeNull();
  });

  it("a stub without skipped_original (pre-B367) still renders as before", () => {
    renderCard({ ...stub({}), skipped_original: undefined } as SessionSlot);
    expect(screen.getByText("Regeneration (Easy Climbing + Stretch)")).toBeTruthy();
  });
});
