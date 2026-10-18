/**
 * @vitest-environment jsdom
 *
 * B398 (O10) review — the More drawer became a lazy chunk (next/dynamic),
 * mounted on idle by BottomNav, which lives in the (main) layout. When that
 * chunk cannot be fetched (offline and never cached, or gone after a deploy)
 * React.lazy throws during render: with no boundary in between, the error
 * climbed to global-error and replaced the whole app — today's session
 * included. BottomNav now wraps the drawer in ChunkErrorBoundary: More goes
 * inert, the tabs and the page keep working.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor } from "@testing-library/react";
import { Component, type ReactNode } from "react";

const { chunk } = vi.hoisted(() => ({ chunk: { missing: false } }));

vi.mock("next/navigation", () => ({ usePathname: () => "/today" }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
// next/dynamic as React.lazy + Suspense: the same failure mode as the real
// one (a rejected import throws during render and stays rejected).
vi.mock("next/dynamic", async () => {
  const { lazy, Suspense, createElement } = await import("react");
  return {
    default: (loader: () => Promise<React.ComponentType<Record<string, unknown>>>) => {
      const Lazy = lazy(() => loader().then((C) => ({ default: C })));
      return function Dynamic(props: Record<string, unknown>) {
        return createElement(Suspense, { fallback: null }, createElement(Lazy, props));
      };
    },
  };
});
/**
 * The drawer's chunk, registered afresh before each test (doMock +
 * resetModules: a factory evaluated once would be cached for the whole file).
 * A factory that throws is an import that rejects.
 */
function mockDrawerChunk() {
  vi.doMock("@/components/layout/more-drawer", () => {
    if (chunk.missing) throw new Error("Loading chunk app/more-drawer failed.");
    return {
      MoreDrawer: ({ open }: { open: boolean }) => (open ? <div>More drawer open</div> : null),
    };
  });
}

/** Stands in for global-error: anything that reaches it replaced the app. */
class AppRoot extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false };
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  render() {
    return this.state.crashed ? <p>App replaced by global-error</p> : this.props.children;
  }
}

async function renderNav() {
  // A fresh module graph per test: the lazy drawer keeps its first outcome.
  const { BottomNav } = await import("@/components/layout/bottom-nav");
  render(
    <AppRoot>
      <BottomNav />
    </AppRoot>,
  );
}

async function tapMore() {
  await act(async () => {
    screen.getByRole("button", { name: "More" }).click();
  });
}

beforeEach(() => {
  vi.resetModules();
  mockDrawerChunk();
  chunk.missing = false;
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("B398 O10 review — a missing More drawer chunk", () => {
  it("opens the drawer when the chunk loads", async () => {
    await renderNav();
    await tapMore();
    await waitFor(() => expect(screen.getByText("More drawer open")).toBeTruthy());
  });

  it("leaves the nav and the rest of the app working", async () => {
    chunk.missing = true;
    await renderNav();
    await tapMore();
    // Give the rejected import time to surface.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(screen.queryByText("App replaced by global-error")).toBeNull();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Today" })).toBeTruthy();
    expect(screen.queryByText("More drawer open")).toBeNull();
  });
});
