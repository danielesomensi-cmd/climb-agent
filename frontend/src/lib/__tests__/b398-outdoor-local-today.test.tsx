/**
 * @vitest-environment jsdom
 *
 * B398 (O2) — /outdoor computed "today" with `new Date().toISOString()`, i.e.
 * the UTC day. In Italy (CEST, UTC+2) between midnight and 02:00 that is still
 * yesterday: "Start Outdoor Session" opened yesterday's live session and the
 * quick log was dated yesterday. The page now uses the local calendar day
 * (`toISODateLocal`, lib/dates).
 */
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, cleanup, act } from "@testing-library/react";
import { stripComments } from "./helpers/source-scan";

// Pin the zone before any Date is built (Node re-reads TZ on assignment).
const ORIGINAL_TZ = process.env.TZ;
process.env.TZ = "Europe/Rome";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({}) }));
vi.mock("@/components/layout/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/lib/api", () => ({ deleteOutdoorLog: vi.fn() }));
vi.mock("@/lib/hooks/use-state", () => ({
  useUserState: () => ({
    state: { outdoor_spots: [{ id: "s1", name: "Arco", discipline: "lead" }] },
  }),
}));
vi.mock("@/lib/hooks/queries/use-outdoor", () => ({
  fetchOutdoorSpots: vi.fn(),
  useOutdoorSessions: () => ({ data: { sessions: [] }, isLoading: false, error: null }),
  useOutdoorStats: () => ({ data: null, isLoading: false, error: null }),
}));

import OutdoorPage from "@/app/(main)/outdoor/page";
import { toISODateLocal } from "@/lib/dates";

beforeAll(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  // 00:30 on Sunday 18 October in Rome — still 22:30 on the 17th in UTC.
  vi.setSystemTime(new Date("2026-10-17T22:30:00Z"));
});

afterAll(() => {
  vi.useRealTimers();
  process.env.TZ = ORIGINAL_TZ;
});

afterEach(() => {
  cleanup();
  push.mockReset();
});

describe("B398 O2 — /outdoor uses the local day", () => {
  it("the clock is set where the bug lived: local and UTC days differ", () => {
    expect(new Date().toISOString().slice(0, 10)).toBe("2026-10-17");
    expect(toISODateLocal(new Date())).toBe("2026-10-18");
  });

  it("Start Outdoor Session opens the local day, not the UTC one", async () => {
    render(<OutdoorPage />);
    await act(async () => {
      screen.getByRole("button", { name: "Start Outdoor Session" }).click();
    });
    expect(push).toHaveBeenCalledWith("/outdoor/2026-10-18");
  });

  it("the page source no longer derives a date from toISOString()", () => {
    const code = stripComments(
      readFileSync(join(process.cwd(), "src/app/(main)/outdoor/page.tsx"), "utf8"),
    );
    expect(code).not.toMatch(/toISOString\(\)\s*\.\s*(split|slice)/);
    expect(code).toContain("toISODateLocal(new Date())");
  });
});
