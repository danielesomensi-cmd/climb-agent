/**
 * @vitest-environment jsdom
 *
 * B398 review — /settings.
 *
 * O4: a save writes the PUT /api/state response into the cache
 * (`applyStateResponse`). A GET /api/state already in flight when the PUT
 * answered (a focus refetch, the refresh() of another action) landed after
 * it and put the pre-save state back: the toggle just saved flipped back. The
 * in-flight GET is now cancelled before the write.
 *
 * O8: the inline editors (Availability, Equipment) became lazy chunks loaded
 * at the tap on Edit. A chunk that cannot be fetched (offline and never
 * cached, or gone after a deploy) took the whole page down. The chunks are
 * now preloaded on idle while online, and each editor sits in a
 * ChunkErrorBoundary that closes it and shows an inline error.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Component, type ReactNode } from "react";

const { api, chunks, loads } = vi.hoisted(() => ({
  api: {
    getState: vi.fn(),
    putState: vi.fn(),
    getWeek: vi.fn(),
    getOutdoorSpots: vi.fn(),
  },
  chunks: { availabilityMissing: false, equipmentMissing: false },
  loads: [] as string[],
}));

vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true }), UserButton: () => null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));
// next/dynamic as React.lazy + Suspense: the same failure mode as the real
// one (a rejected import throws during render and stays rejected).
vi.mock("next/dynamic", async () => {
  const { lazy, Suspense, createElement } = await import("react");
  return {
    default: (
      loader: () => Promise<React.ComponentType<Record<string, unknown>>>,
      opts?: { loading?: () => ReactNode },
    ) => {
      const Lazy = lazy(() => loader().then((C) => ({ default: C })));
      return function Dynamic(props: Record<string, unknown>) {
        return createElement(Suspense, { fallback: opts?.loading?.() ?? null }, createElement(Lazy, props));
      };
    },
  };
});
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getState: () => api.getState(),
  putState: (patch: unknown) => api.putState(patch),
  getWeek: (...a: unknown[]) => api.getWeek(...a),
  getOutdoorSpots: () => api.getOutdoorSpots(),
}));
vi.mock("@/lib/hooks/use-subscription", () => ({
  useSubscription: () => ({ status: "active", isActive: true, trialDaysRemaining: null, enforced: true }),
}));
vi.mock("@/lib/voice-cues", () => ({ isVoiceCuesEnabled: () => false, setVoiceCuesEnabled: vi.fn() }));
vi.mock("@/components/layout/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/components/settings/onsight-evidence-card", () => ({ OnsightEvidenceCard: () => null }));
/**
 * The inline editors' chunks, registered afresh before each test (doMock +
 * resetModules: a factory evaluated once would be cached for the whole file).
 * `loads` records each evaluation; a factory that throws is a chunk that fails.
 */
function mockEditorChunks() {
  vi.doMock("@/components/settings/availability-editor", () => {
    loads.push("availability-editor");
    if (chunks.availabilityMissing) throw new Error("Loading chunk availability-editor failed.");
    return { AvailabilityEditor: () => <div>Availability editor</div> };
  });
  vi.doMock("@/components/settings/equipment-editor", () => {
    loads.push("equipment-editor");
    if (chunks.equipmentMissing) throw new Error("Loading chunk equipment-editor failed.");
    return { EquipmentEditor: () => <div>Equipment editor</div> };
  });
}
vi.mock("@/components/settings/goal-editor", () => ({ GoalEditor: () => null }));
vi.mock("@/components/settings/profile-assessment-editor", () => ({ ProfileAssessmentEditor: () => null }));
vi.mock("@/components/settings/start-new-macrocycle-dialog", () => ({ StartNewMacrocycleDialog: () => null }));
vi.mock("@/components/training/regenerate-plan-sheet", () => ({
  RegeneratePlanSheet: () => null,
  optionToPreserveBefore: () => undefined,
}));

import { queryKeys } from "@/lib/query-keys";
import type { UserState } from "@/lib/types";

const stateWith = (grade: "font" | "v_scale") =>
  ({
    user: {},
    assessment: {},
    goal: {},
    equipment: { home_enabled: false, gyms: [] },
    availability: {},
    preferences: { grade_system_boulder: grade },
  }) as unknown as UserState;

/** Stands in for the route error boundary: reaching it = the page is gone. */
class RouteRoot extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false };
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  render() {
    return this.state.crashed ? <p>Page replaced by the error boundary</p> : this.props.children;
  }
}

let qc: QueryClient;

async function renderSettings() {
  // A fresh module graph per test: each lazy editor keeps its first outcome.
  const { default: SettingsPage } = await import("@/app/(main)/settings/page");
  render(
    <QueryClientProvider client={qc}>
      <RouteRoot>
        <SettingsPage />
      </RouteRoot>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText("Boulder grade system")).toBeTruthy());
}

const section = (id: string) => within(document.getElementById(id) as HTMLElement);

async function tapEdit(sectionId: string) {
  await act(async () => {
    section(sectionId).getByRole("button", { name: "Edit" }).click();
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 20));
  });
}

beforeEach(() => {
  vi.resetModules();
  mockEditorChunks();
  vi.clearAllMocks();
  loads.length = 0;
  chunks.availabilityMissing = false;
  chunks.equipmentMissing = false;
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  api.getState.mockResolvedValue(stateWith("font"));
  api.getOutdoorSpots.mockResolvedValue({ spots: [] });
  api.getWeek.mockResolvedValue({ week_plan: [] });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("B398 O4 review — a GET in flight does not undo a save", () => {
  it("the toggle keeps the saved value when an older GET /api/state lands after the PUT", async () => {
    await renderSettings();
    expect(screen.getByRole("button", { name: "Switch to V-scale" })).toBeTruthy();

    // A refetch of the state starts (focus, another action's refresh) and is
    // slow: it carries the state as it was before the save.
    let resolveOldGet: (s: UserState) => void = () => {};
    api.getState.mockImplementation(() => new Promise<UserState>((r) => (resolveOldGet = r)));
    await act(async () => {
      void qc.invalidateQueries({ queryKey: queryKeys.state, exact: true });
    });
    expect(api.getState).toHaveBeenCalledTimes(2);

    // The user saves the toggle; the PUT answers with the new state.
    api.putState.mockResolvedValue(stateWith("v_scale"));
    await act(async () => {
      screen.getByRole("button", { name: "Switch to V-scale" }).click();
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Switch to Font" })).toBeTruthy());

    // The old GET lands now.
    await act(async () => {
      resolveOldGet(stateWith("font"));
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(screen.getByRole("button", { name: "Switch to Font" })).toBeTruthy();
    const cached = qc.getQueryData<UserState>(queryKeys.state) as { preferences: { grade_system_boulder: string } };
    expect(cached.preferences.grade_system_boulder).toBe("v_scale");
  });
});

describe("B398 O8 review — the inline editors' chunks", () => {
  it("are preloaded once the page is idle, while online, before any tap", async () => {
    await renderSettings();
    expect(loads).toEqual([]);
    await waitFor(() => expect(loads.sort()).toEqual(["availability-editor", "equipment-editor"]), {
      timeout: 2000,
    });
  });

  it("offline, wait for the connection to come back", async () => {
    const onLine = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    await renderSettings();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 500));
    });
    expect(loads).toEqual([]);

    onLine.mockReturnValue(true);
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(loads.sort()).toEqual(["availability-editor", "equipment-editor"]), {
      timeout: 2000,
    });
  });

  it.each([
    { name: "Availability", sectionId: "sec-availability", flag: "availabilityMissing" as const },
    { name: "Equipment", sectionId: "sec-equipment", flag: "equipmentMissing" as const },
  ])("$name: a missing chunk closes the editor with an inline error, the page stays", async ({ sectionId, flag }) => {
    chunks[flag] = true;
    await renderSettings();
    await tapEdit(sectionId);

    expect(screen.queryByText("Page replaced by the error boundary")).toBeNull();
    expect(screen.getByText("Boulder grade system")).toBeTruthy();
    // Back to the card, with the reason under it.
    expect(section(sectionId).getByRole("alert").textContent).toMatch(/editor couldn.t load/i);
    // Review round 2: the failure lasts for the page's life — the note offers a reload.
    expect(section(sectionId).getByRole("button", { name: "Reload" })).toBeTruthy();
    expect(section(sectionId).getByRole("button", { name: "Edit" })).toBeTruthy();
  });

  // Review round 3 — offline a reload cannot fetch the chunk: no Reload button then.
  it("offline, the note says it needs a connection and offers no Reload", async () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    try {
      chunks.availabilityMissing = true;
      await renderSettings();
      await tapEdit("sec-availability");
      expect(section("sec-availability").getByRole("alert").textContent).toMatch(/needs a connection/i);
      expect(section("sec-availability").queryByRole("button", { name: "Reload" })).toBeNull();
    } finally {
      Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    }
  });

  it("opens the editor when its chunk loads", async () => {
    await renderSettings();
    await tapEdit("sec-availability");
    await waitFor(() => expect(screen.getByText("Availability editor")).toBeTruthy());
    expect(section("sec-availability").queryByRole("alert")).toBeNull();
  });
});
