/**
 * @vitest-environment jsdom
 *
 * B398 (O11) review — the spots list lives in the React Query cache
 * (`['outdoor','spots']`, fresh for 5 minutes), read by /settings and by the
 * outdoor log (`fetchOutdoorSpots`). The "+ Add new spot" of the replan and
 * quick-add dialogs called `addOutdoorSpot` directly: the new spot showed in
 * the dialog but not in /settings nor in the log picker until the cache went
 * stale. Both dialogs now append it to the cached list — and only to a cached
 * list: seeding an empty cache with the new spot alone would hide every other
 * spot for 5 minutes.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const { getOutdoorSpots, addOutdoorSpot } = vi.hoisted(() => ({
  getOutdoorSpots: vi.fn(),
  addOutdoorSpot: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getOutdoorSpots: () => getOutdoorSpots(),
  addOutdoorSpot: (body: unknown) => addOutdoorSpot(body),
  getSuggestedSessions: () => Promise.resolve({ suggestions: [], supplementary: [] }),
  getSessions: () => Promise.resolve({ sessions: [] }),
  getCustomSessions: () => Promise.resolve({ sessions: [] }),
}));

import { ReplanDialog } from "@/components/training/replan-dialog";
import { QuickAddDialog } from "@/components/training/quick-add-dialog";
import { queryKeys } from "@/lib/query-keys";
import type { OutdoorSpot } from "@/lib/types";

const ARCO: OutdoorSpot = { id: "spot_arco", name: "Arco", discipline: "lead" };
const BERDORF: OutdoorSpot = { id: "spot_new", name: "Berdorf", discipline: "lead" };

let qc: QueryClient;

beforeEach(() => {
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  getOutdoorSpots.mockResolvedValue({ spots: [ARCO] });
  addOutdoorSpot.mockResolvedValue({ spot: BERDORF });
});

afterEach(cleanup);

function renderWithClient(ui: ReactElement) {
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

async function clickText(label: string | RegExp) {
  await act(async () => {
    (screen.getByText(label).closest("button") as HTMLButtonElement).click();
  });
}

async function addSpotNamed(name: string) {
  await clickText("+ Add new spot");
  const input = screen.getByPlaceholderText(/Spot name/) as HTMLInputElement;
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
    setter.call(input, name);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await clickText("Save spot");
  await waitFor(() => expect(addOutdoorSpot).toHaveBeenCalledTimes(1));
}

const cachedSpots = () =>
  qc.getQueryData<{ spots: OutdoorSpot[] }>(queryKeys.outdoorSpots)?.spots.map((s) => s.id);

const dialogs: Array<{ name: string; open: () => Promise<void> }> = [
  {
    name: "ReplanDialog",
    open: async () => {
      renderWithClient(
        <ReplanDialog open date="2026-10-18" gyms={[]} onClose={vi.fn()} onApply={vi.fn()} />,
      );
      await clickText("Outdoor");
      await waitFor(() => expect(screen.getByText("Arco")).toBeTruthy());
    },
  },
  {
    name: "QuickAddDialog",
    open: async () => {
      renderWithClient(
        <QuickAddDialog
          open
          date="2026-10-18"
          gyms={[]}
          onClose={vi.fn()}
          onApply={vi.fn()}
          onApplyOutdoor={vi.fn()}
        />,
      );
      await clickText("Outdoor session");
      await waitFor(() => expect(screen.getByText("Arco")).toBeTruthy());
    },
  },
];

describe.each(dialogs)("B398 O11 review — $name: a spot added inline", ({ open }) => {
  it("joins the cached spots list read by /settings and the outdoor log", async () => {
    qc.setQueryData(queryKeys.outdoorSpots, { spots: [ARCO] });
    await open();
    await addSpotNamed("Berdorf");
    await waitFor(() => expect(cachedSpots()).toEqual(["spot_arco", "spot_new"]));
  });

  it("does not seed an empty cache with the new spot alone", async () => {
    await open();
    await addSpotNamed("Berdorf");
    // The dialog still selects it…
    await waitFor(() => expect(screen.getByText("Berdorf")).toBeTruthy());
    // …but no partial list is cached: the next reader fetches the full one.
    expect(qc.getQueryData(queryKeys.outdoorSpots)).toBeUndefined();
  });
});
