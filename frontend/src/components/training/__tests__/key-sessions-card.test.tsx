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

  // A325 — one drill short of the technique key.
  const topupStatus = () => status({
    as_of: "2026-11-10", week_start: "2026-11-09", week_end: "2026-11-15",
    requirements: [{
      key: "technique", label: "Technique", target: 1, status: "partial", resolution: "topup",
      severity: "warning", debt: 1, done: [], planned: [], skipped: [],
      partial: [{ date: "2026-11-09", slot: "evening", session_id: "custom_cs_x", dose: "partial" }],
      progress: { done: 1, needed: 2,
        drills_done: [{ exercise_id: "no_readjust_drill", name: "No Readjust Drill" }],
        drills_missed: [{ exercise_id: "tech_hard_target", name: "Hard Target" }] },
    }],
    proposals: [],
    topups: [{
      key: "technique", kind: "add_exercise", date: "2026-11-12", slot: "evening", session_index: 1,
      session_id: "boulder_circuit_gym", session_name: "Boulder circuit gym",
      exercise_id: "tech_hard_target", exercise_name: "Hard Target",
      from: { date: "2026-11-09", slot: "evening", session_id: "custom_cs_x" },
      drills_done: [{ exercise_id: "no_readjust_drill", name: "No Readjust Drill" }],
      apply: { endpoint: "/api/session/add-exercise", body: {
        date: "2026-11-12", session_index: 1, exercise_id: "tech_hard_target", position: "after_warmup" } },
    }],
    summary: { required: 1, covered: 0, done: 0, missing: ["technique"], debt: 1, max_severity: "warning" },
  });

  it("A325: says which drill is owed and offers to add it to a planned session", () => {
    const onTopup = vi.fn();
    render(<KeySessionsCard status={topupStatus()} compact collapsible onApplyTopup={onTopup} />);
    expect(screen.getByRole("button", { expanded: true })).toBeTruthy();
    expect(screen.getByText(/1 of 2 drills done on Mon, Hard Target still to do/)).toBeTruthy();
    const block = screen.getByTestId("key-topup");
    expect(block.textContent).toContain("Add Hard Target to Boulder circuit gym");
    expect(block.textContent).toContain("right after the warm-up");
    expect(screen.queryByText(/Swap/)).toBeNull();
    fireEvent.click(screen.getByText("Add the drill"));
    expect(onTopup).toHaveBeenCalledTimes(1);
    expect(onTopup.mock.calls[0][0].apply.body.position).toBe("after_warmup");
  });

  it("A325: the top-up goes away with its dismissed row", () => {
    render(<KeySessionsCard status={topupStatus()} onApplyTopup={() => {}} />);
    fireEvent.click(screen.getByLabelText("Hide Technique for this week"));
    expect(screen.queryByTestId("key-topup")).toBeNull();
  });

  it("A325: a re-schedule that replaces a session says it once — Swap A for B", () => {
    const st = status();
    st.proposals = [{
      ...st.proposals[0], keys: ["technique"], date: "2026-10-08", slot: "evening",
      session_id: "technique_focus_gym", session_name: "Technique focus gym",
      side_effects: [{ date: "2026-10-08", slot: "evening", from: "boulder_circuit_gym", to: "technique_focus_gym" }],
    }];
    const onApply = vi.fn();
    render(<KeySessionsCard status={st} onApplyProposal={onApply} />);
    expect(screen.getByTestId("key-proposal").textContent).toContain("Swap Boulder circuit gym for Technique focus gym");
    expect(screen.queryByText(/Also changes:/)).toBeNull();
    expect(screen.getByText("Nothing else in your week changes.")).toBeTruthy();
    fireEvent.click(screen.getByText("Swap sessions"));
    expect(onApply).toHaveBeenCalledTimes(1);
  });
});
