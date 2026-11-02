/**
 * @vitest-environment jsdom
 *
 * A324 — the live logger knows who was on the sharp end.
 *
 * Real case: Cancer at Presles (31/10), alternate leads. Lead is the role
 * that turns a try into a send (green, milestones, onsight evidence), so the
 * selector must never fall back to it in silence — e.g. after the iPhone PWA
 * reloads in the background in the middle of a day on second.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { useState } from "react";

vi.mock("sonner", () => ({ toast: vi.fn() }));

import { LiveRouteLogger, type LiveRoute } from "../live-route-logger";

afterEach(cleanup);

function Harness({
  initial = [],
  discipline = "lead",
  spy = vi.fn(),
}: {
  initial?: LiveRoute[];
  discipline?: "lead" | "boulder" | "both";
  spy?: (r: LiveRoute[]) => void;
}) {
  const [routes, setRoutes] = useState<LiveRoute[]>(initial);
  return (
    <LiveRouteLogger
      discipline={discipline}
      startedAt="2026-10-31T08:00:00Z"
      routes={routes}
      onChange={(next) => {
        spy(next);
        setRoutes(next);
      }}
    />
  );
}

const radio = (name: string) => screen.getByRole("radio", { name }) as HTMLButtonElement;
const lastCall = (spy: ReturnType<typeof vi.fn>) => spy.mock.calls[spy.mock.calls.length - 1][0] as LiveRoute[];

describe("A324 — live logger: rope role", () => {
  it("starts on Lead; a lead send writes no rope_role (identical to an old log)", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    expect(radio("Lead").getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "✓ Sent" }));
    const [route] = lastCall(spy);
    expect(route.attempts[0].result).toBe("sent");
    expect("rope_role" in route.attempts[0]).toBe(false);
  });

  it("on 2nd the green Sent becomes a blue «Clean (2nd)» and writes rope_role second; the choice stays set", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    fireEvent.click(radio("Second"));
    expect(screen.queryByRole("button", { name: "✓ Sent" })).toBeNull();
    const clean = screen.getByRole("button", { name: "✓ Clean (2nd)" });
    expect(clean.className).toContain("text-info");
    expect(clean.className).not.toContain("text-success");

    fireEvent.click(clean);
    expect(lastCall(spy)[0].attempts[0]).toMatchObject({ result: "sent", rope_role: "second" });
    expect(radio("Second").getAttribute("aria-checked")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "✗ Fell / try" }));
    expect(lastCall(spy)[1].attempts[0]).toMatchObject({ result: "fell", rope_role: "second" });
  });

  it("after a reload the selector starts from the last try logged, not from Lead", () => {
    const restored: LiveRoute[] = [
      { name: "L1", grade: "6a+", atMin: 10, attempts: [{ result: "sent", logged_at: "2026-10-31T09:00:00Z" }] },
      { name: "L2", grade: "6c+", atMin: 40, attempts: [{ result: "sent", rope_role: "toprope", logged_at: "2026-10-31T09:40:00Z" }] },
    ];
    const spy = vi.fn();
    render(<Harness initial={restored} spy={spy} />);
    expect(radio("Top-rope").getAttribute("aria-checked")).toBe("true");
    expect(radio("Lead").getAttribute("aria-checked")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "✓ Clean (TR)" }));
    expect(lastCall(spy)[2].attempts[0]).toMatchObject({ rope_role: "toprope" });
  });

  it("the rows' +✓ / +✗ take the selected role", () => {
    const spy = vi.fn();
    const initial: LiveRoute[] = [{ name: "Cernes", grade: "7b+", atMin: 5, attempts: [{ result: "fell" }] }];
    render(<Harness initial={initial} spy={spy} />);
    fireEvent.click(radio("Top-rope"));
    fireEvent.click(screen.getByRole("button", { name: "Add a fall on top-rope" }));
    expect(lastCall(spy)[0].attempts[1]).toMatchObject({ result: "fell", rope_role: "toprope" });
  });
});

describe("A324 — live logger: A0, styles, footer", () => {
  it("A0 logs result aid on a rope", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    fireEvent.click(screen.getByRole("button", { name: "A0" }));
    expect(lastCall(spy)[0].attempts[0]).toMatchObject({ result: "aid" });
    expect(screen.getByText(/^A0 · 1 try$/)).toBeTruthy();
  });

  it("a boulder has no role selector and no A0", () => {
    render(<Harness discipline="boulder" />);
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.queryByRole("button", { name: "A0" })).toBeNull();
    expect(screen.getByRole("button", { name: "✓ Sent" })).toBeTruthy();
  });

  it("OS / FL only on a first-try send on lead", () => {
    const { unmount } = render(
      <Harness initial={[{ name: "L1", grade: "6a+", atMin: 1, attempts: [{ result: "sent", rope_role: "second" }] }]} />,
    );
    expect(screen.queryByRole("button", { name: "OS" })).toBeNull();
    expect(screen.getByText(/^Second clean · 1 try$/)).toBeTruthy();
    unmount();
    render(<Harness initial={[{ name: "L4", grade: "6c", atMin: 1, attempts: [{ result: "sent" }] }]} />);
    expect(screen.getByRole("button", { name: "OS" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "FL" })).toBeTruthy();
  });

  it("the automatic redpoint follows a send on lead only", () => {
    const spy = vi.fn();
    render(<Harness initial={[{ name: "P", grade: "7a", atMin: 1, attempts: [{ result: "fell" }] }]} spy={spy} />);
    fireEvent.click(radio("Second"));
    fireEvent.click(screen.getByRole("button", { name: "Add a clean try on second" }));
    expect(lastCall(spy)[0].style).toBeUndefined();
    fireEvent.click(radio("Lead"));
    fireEvent.click(screen.getByRole("button", { name: "Add a sent try" }));
    expect(lastCall(spy)[0].style).toBe("redpoint");
  });

  it("the footer counts sends on lead, and clean on 2nd/TR apart", () => {
    render(
      <Harness
        initial={[
          { name: "L1", grade: "6a+", atMin: 1, attempts: [{ result: "sent", rope_role: "second" }] },
          { name: "L4", grade: "6c", atMin: 2, attempts: [{ result: "sent" }] },
          { name: "L8", grade: "7b", atMin: 3, attempts: [{ result: "aid" }] },
        ]}
      />,
    );
    const footer = screen.getByText(/3 routes · 1 sent/);
    expect(footer.textContent).toBe("3 routes · 1 sent · 1 clean (2nd/TR)");
  });
});
