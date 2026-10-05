/**
 * @vitest-environment jsdom
 *
 * A298 — the ladder badge: level + dose, and the promotion proposal that only
 * a tap applies (custom rows); engine rows only inform.
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  resolveLadderPromotion: vi.fn(() => Promise.resolve({ family: "compression_floor", accepted: true, rows_rewritten: 1 })),
  apiErrorDetail: (_e: unknown, f: string) => f,
}));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { error: vi.fn() }) }));

import { resolveLadderPromotion } from "@/lib/api";
import { LadderBadge } from "../ladder-badge";
import type { LadderInfo } from "@/lib/types";

afterEach(cleanup);

const base: LadderInfo = {
  family: "compression_floor",
  level_idx: 3,
  n_levels: 6,
  level_name: "Straddle L-sit",
  band: "10–30 s",
  dose: "3x30 s",
  next_name: "V-sit 45°",
  proposal: { kind: "promotion", to_level_idx: 4, to_exercise_id: "v_sit_45", to_name: "V-sit 45°" },
};

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe("LadderBadge", () => {
  it("renders nothing without a ladder", () => {
    const { container } = wrap(<LadderBadge ladder={undefined} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows level and dose; an engine row only informs", () => {
    wrap(<LadderBadge ladder={base} />);
    expect(screen.getByText("Level 4/6 · Straddle L-sit")).toBeTruthy();
    expect(screen.getByText("3x30 s")).toBeTruthy();
    expect(screen.getByText("Ready for V-sit 45°: switch?")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Switch" })).toBeNull();
  });

  it("applies the promotion only on the tap", async () => {
    wrap(<LadderBadge ladder={base} customSessionId="cs_core" date="2026-10-06" />);
    expect(resolveLadderPromotion).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Switch" }));
    await waitFor(() =>
      expect(resolveLadderPromotion).toHaveBeenCalledWith("compression_floor", {
        accept: true,
        date: "2026-10-06",
        custom_session_id: "cs_core",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("button", { name: "Switch" })).toBeNull());
  });
});
