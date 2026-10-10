/**
 * @vitest-environment jsdom
 *
 * A294 — the key-sessions card: rows per stimulus, proposal with declared side
 * effects and one-tap apply, compact mode silent when the week is on track.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

import { KeySessionsCard } from "../key-sessions-card";
import type { KeyStatus } from "@/lib/types";

afterEach(() => {
  cleanup();
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

function status(over: Partial<KeyStatus> = {}): KeyStatus {
  return {
    version: "a294.1", source: "a294", as_of: "2026-10-06", week_start: "2026-10-05", week_end: "2026-10-11",
    phase_id: "strength_power", is_current_week: true, is_past_week: false,
    requirements: [
      { key: "finger_max", label: "Finger max", target: 1, status: "missing", resolution: "proposal",
        severity: "critical", debt: 1, done: [], partial: [], planned: [], skipped: [] },
      { key: "technique", label: "Technique", target: 1, status: "done", resolution: null,
        severity: "none", debt: 0, done: [{ date: "2026-10-05", slot: "evening", session_id: "technique_focus_gym" }],
        partial: [], planned: [], skipped: [] },
    ],
    sessions: [],
    proposals: [{
      keys: ["finger_max", "pulling_max"], date: "2026-10-10", slot: "evening", session_id: "strength_long",
      session_name: "Strength long", location: "gym", gym_id: "g1", reduced_reentry_dose: false,
      side_effects: [{ date: "2026-10-11", slot: "evening", from: "finger_maintenance_gym", to: "regeneration_easy" }],
      apply: { endpoint: "/api/replanner/events", event: { event_type: "add_planned_session" } },
    }],
    conflicts: [],
    summary: { required: 2, covered: 1, done: 1, missing: ["finger_max"], debt: 1, max_severity: "critical" },
    ...over,
  };
}

describe("KeySessionsCard", () => {
  it("renders rows, the proposal and its side effects", () => {
    render(<KeySessionsCard status={status()} onApplyProposal={() => {}} />);
    expect(screen.getByText("Key sessions this week")).toBeTruthy();
    expect(screen.getByText("Finger max")).toBeTruthy();
    expect(screen.getByText(/catch-up proposed/)).toBeTruthy();
    expect(screen.getByText(/Also changes:/).textContent).toContain("Finger maintenance gym → Regeneration easy");
  });

  it("applies the proposal with one tap", async () => {
    const onApply = vi.fn();
    render(<KeySessionsCard status={status()} onApplyProposal={onApply} />);
    fireEvent.click(screen.getByText("Add to my week"));
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0].session_id).toBe("strength_long");
  });

  it("compact mode stays silent when nothing is owed", () => {
    const ok = status({
      requirements: [status().requirements[1]], proposals: [],
      summary: { required: 1, covered: 1, done: 1, missing: [], debt: 0, max_severity: "none" },
    });
    const { container } = render(<KeySessionsCard status={ok} compact />);
    expect(container.innerHTML).toBe("");
  });

  it("hides past weeks and missing status", () => {
    const { container } = render(<KeySessionsCard status={status({ is_past_week: true })} />);
    expect(container.innerHTML).toBe("");
    const r2 = render(<KeySessionsCard status={null} />);
    expect(r2.container.innerHTML).toBe("");
  });

  it("collapsible (A308, /today): open when something is critical or proposed", () => {
    render(<KeySessionsCard status={status()} compact collapsible onApplyProposal={() => {}} />);
    expect(screen.getByRole("button", { expanded: true })).toBeTruthy();
    expect(screen.getByText("Add to my week")).toBeTruthy();
  });

  it("collapsible (A308, /today): a one-line summary otherwise, opening on tap", () => {
    const mild = status({
      requirements: [{ ...status().requirements[0], severity: "warning" }, status().requirements[1]],
      proposals: [],
      summary: { ...status().summary, max_severity: "warning" },
    });
    render(<KeySessionsCard status={mild} compact collapsible />);
    const toggle = screen.getByRole("button", { expanded: false });
    expect(toggle.textContent).toContain("1/2 on track");
    expect(screen.queryByText("Finger max")).toBeNull();
    fireEvent.click(toggle);
    expect(screen.getByText("Finger max")).toBeTruthy();
  });

  it("a dismissed row disappears for the week", () => {
    render(<KeySessionsCard status={status()} />);
    fireEvent.click(screen.getByLabelText("Hide Finger max for this week"));
    expect(screen.queryByText("Finger max")).toBeNull();
  });
});
