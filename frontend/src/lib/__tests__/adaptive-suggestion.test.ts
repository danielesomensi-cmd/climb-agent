import { describe, it, expect, vi, beforeEach } from "vitest";

const toastMock = vi.fn();
vi.mock("sonner", () => ({ toast: (...args: unknown[]) => toastMock(...args) }));

import { describeAdaptiveSuggestion, notifyAdaptiveSuggestion } from "@/lib/adaptive-suggestion";

/**
 * B369 / A301 — after a very_hard / fail the backend changes nothing and
 * returns `adaptive_suggestion`. The UI shows its text; it never implies that
 * the plan was changed.
 */
beforeEach(() => toastMock.mockReset());

const base = {
  kind: "lighten_next_hard" as const,
  target_date: "2026-10-07",
  plan_changed: false as const,
  message: "That felt very hard: consider lightening your next hard session (2026-10-07). Nothing was changed in your plan.",
};

describe("describeAdaptiveSuggestion", () => {
  it("is null without a suggestion", () => {
    expect(describeAdaptiveSuggestion(undefined)).toBeNull();
    expect(describeAdaptiveSuggestion(null)).toBeNull();
    expect(describeAdaptiveSuggestion({ kind: "lighten_next_hard" })).toBeNull();
    expect(describeAdaptiveSuggestion({ ...base, message: "  " })).toBeNull();
  });

  it("shows the server text as is", () => {
    const d = describeAdaptiveSuggestion(base)!;
    expect(d.title).toBe("Consider lightening the next hard session");
    expect(d.description).toBe(base.message);
  });

  it("titles a recovery-day suggestion and always states nothing changed", () => {
    const d = describeAdaptiveSuggestion({ ...base, kind: "recovery_day", message: "Repeated very hard sessions." })!;
    expect(d.title).toBe("Consider a recovery day");
    expect(d.description).toContain("Nothing was changed in your plan.");
  });
});

describe("notifyAdaptiveSuggestion", () => {
  it("toasts once with a shortcut to build a custom, no-op otherwise", () => {
    notifyAdaptiveSuggestion(undefined);
    expect(toastMock).not.toHaveBeenCalled();
    notifyAdaptiveSuggestion(base);
    expect(toastMock).toHaveBeenCalledTimes(1);
    const [, opts] = toastMock.mock.calls[0] as [string, { action: { label: string } }];
    expect(opts.action.label).toBe("Build a custom");
  });
});
