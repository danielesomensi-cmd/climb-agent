/**
 * @vitest-environment jsdom
 *
 * A321 — "Topo & charts" opens the athlete's quaderno on the tapped day, in a
 * sandboxed iframe, with a link signed at opening time.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

const getQuaderno = vi.fn();

vi.mock("@/lib/api", () => ({
  getQuaderno: () => getQuaderno(),
  quadernoPageUrl: (pagePath: string, date: string) =>
    `https://api.test${pagePath}?theme=dark#${date}`,
}));

import { QuadernoButton } from "../quaderno-viewer";

afterEach(cleanup);

const INFO = {
  available: true,
  generated: "2026-10-24T21:40:35+02:00",
  days: ["2026-10-17", "2026-10-11"],
  page_path: "/api/quaderno/v/tok.123.sig/standalone.html",
  expires_at: 9_999_999_999,
};

describe("QuadernoButton", () => {
  beforeEach(() => getQuaderno.mockReset());

  it("opens the day's page in a sandboxed, no-referrer iframe", async () => {
    getQuaderno.mockResolvedValue(INFO);
    render(<QuadernoButton date="2026-10-17" />);
    expect(getQuaderno).not.toHaveBeenCalled(); // nothing is signed until the tap

    fireEvent.click(screen.getByRole("button", { name: /Topo & charts/ }));
    const frame = (await screen.findByTitle("Topo and charts, 2026-10-17")) as HTMLIFrameElement;
    expect(frame.getAttribute("src")).toBe(
      "https://api.test/api/quaderno/v/tok.123.sig/standalone.html?theme=dark#2026-10-17",
    );
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(getQuaderno).toHaveBeenCalledTimes(1);
  });

  it("signs a fresh link on every opening", async () => {
    getQuaderno.mockResolvedValue(INFO);
    render(<QuadernoButton date="2026-10-17" />);
    fireEvent.click(screen.getByRole("button", { name: /Topo & charts/ }));
    await screen.findByTitle("Topo and charts, 2026-10-17");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByTitle("Topo and charts, 2026-10-17")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: /Topo & charts/ }));
    await screen.findByTitle("Topo and charts, 2026-10-17");
    expect(getQuaderno).toHaveBeenCalledTimes(2);
  });

  it("says so when the day is not in the report", async () => {
    getQuaderno.mockResolvedValue({ ...INFO, days: ["2026-10-11"] });
    render(<QuadernoButton date="2026-10-17" />);
    fireEvent.click(screen.getByRole("button", { name: /Topo & charts/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Couldn.t open the report/);
    expect(screen.queryByTitle("Topo and charts, 2026-10-17")).toBeNull();
  });

  it("offers a retry when the request fails", async () => {
    getQuaderno.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(INFO);
    render(<QuadernoButton date="2026-10-17" />);
    fireEvent.click(screen.getByRole("button", { name: /Topo & charts/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByTitle("Topo and charts, 2026-10-17")).toBeTruthy();
  });
});
