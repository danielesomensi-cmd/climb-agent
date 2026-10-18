/**
 * @vitest-environment jsdom
 *
 * B398 review (round 2) — /plan and /settings mounted their lazy dialogs
 * (next/dynamic) at render, closed: the chunk was fetched at once and, offline
 * right after a deploy, a chunk the service worker had never seen threw during
 * render and the route error boundary replaced the page. LazyWhenOpen fetches
 * nothing until the first open, and a chunk that cannot load closes the
 * dialog with a toast instead of taking the page down.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { Component, lazy, Suspense, type ReactNode } from "react";

const { toast } = vi.hoisted(() => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }),
}));
vi.mock("sonner", () => ({ toast }));

import { LazyWhenOpen } from "@/components/lazy-when-open";
import { CHUNK_RELOAD_MESSAGE } from "@/lib/chunk-load";

/** Stands in for the route's error.tsx. */
class RouteRoot extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false };
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  render() {
    return this.state.crashed ? <p>Page replaced by the error boundary</p> : this.props.children;
  }
}

function lazyDialog(outcome: "ok" | "missing") {
  const loader = vi.fn(() =>
    outcome === "missing"
      ? Promise.reject(new Error("Loading chunk regenerate-plan-sheet failed."))
      : Promise.resolve({ default: ({ open }: { open: boolean }) => (open ? <div>Dialog open</div> : null) }),
  );
  const Lazy = lazy(loader);
  function Dialog({ open }: { open: boolean }) {
    return (
      <Suspense fallback={null}>
        <Lazy open={open} />
      </Suspense>
    );
  }
  return { Dialog, loader };
}

function Page({ open, onFail, Dialog }: { open: boolean; onFail: () => void; Dialog: (p: { open: boolean }) => ReactNode }) {
  return (
    <RouteRoot>
      <p>Plan page</p>
      <LazyWhenOpen open={open} onFail={onFail}>
        <Dialog open={open} />
      </LazyWhenOpen>
    </RouteRoot>
  );
}

async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 10));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LazyWhenOpen", () => {
  it("fetches nothing while the dialog has never been opened", async () => {
    const { Dialog, loader } = lazyDialog("missing");
    render(<Page open={false} onFail={() => {}} Dialog={Dialog} />);
    await flush();
    expect(loader).not.toHaveBeenCalled();
    expect(screen.getByText("Plan page")).toBeTruthy();
  });

  it("mounts it on the first open and keeps it mounted after closing", async () => {
    const { Dialog, loader } = lazyDialog("ok");
    const { rerender } = render(<Page open={false} onFail={() => {}} Dialog={Dialog} />);
    rerender(<Page open onFail={() => {}} Dialog={Dialog} />);
    expect(await screen.findByText("Dialog open")).toBeTruthy();
    rerender(<Page open={false} onFail={() => {}} Dialog={Dialog} />);
    await flush();
    expect(screen.queryByText("Dialog open")).toBeNull();
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("a chunk that cannot load closes the dialog with a toast, and the page stays", async () => {
    const { Dialog } = lazyDialog("missing");
    const onFail = vi.fn();
    const { rerender } = render(<Page open={false} onFail={onFail} Dialog={Dialog} />);
    rerender(<Page open onFail={onFail} Dialog={Dialog} />);
    await flush();
    expect(onFail).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(CHUNK_RELOAD_MESSAGE, expect.objectContaining({ action: expect.anything() }));
    expect(screen.queryByText("Page replaced by the error boundary")).toBeNull();
    expect(screen.getByText("Plan page")).toBeTruthy();
  });
});
