import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * A245 C-5 (F37) — a network failure must never be presented as "this day has
 * no outdoor log". Doing so opened an empty new-log form over an existing
 * session, which then duplicates or overwrites real climbing data.
 */

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const getOutdoorLogByDate = vi.fn();
const getOutdoorSpots = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError,
  getOutdoorLogByDate: (...a: unknown[]) => getOutdoorLogByDate(...a),
  getOutdoorSpots: (...a: unknown[]) => getOutdoorSpots(...a),
}));

let mod: typeof import("@/lib/outdoor-log-target");

beforeEach(async () => {
  vi.resetModules();
  getOutdoorLogByDate.mockReset();
  getOutdoorSpots.mockReset();
  getOutdoorSpots.mockResolvedValue({ spots: [{ spot_id: "s1", name: "Arco" }] });
  mod = await import("@/lib/outdoor-log-target");
});

describe("resolveOutdoorLogTarget", () => {
  it("returns edit when a log exists", async () => {
    getOutdoorLogByDate.mockResolvedValue({ session: { date: "2026-07-20" } });

    const r = await mod.resolveOutdoorLogTarget("2026-07-20");

    expect(r.kind).toBe("edit");
    expect(r.kind === "edit" && r.session).toEqual({ date: "2026-07-20" });
  });

  it("returns new ONLY on a genuine 404", async () => {
    getOutdoorLogByDate.mockRejectedValue(new ApiError(404, "No outdoor session"));

    const r = await mod.resolveOutdoorLogTarget("2026-07-20");

    expect(r.kind).toBe("new");
  });

  it.each([
    [0, "offline"],
    [500, "server error"],
    [502, "bad gateway"],
  ])("returns unavailable — NOT new — on status %i", async (status) => {
    getOutdoorLogByDate.mockRejectedValue(new ApiError(status, "boom"));

    const r = await mod.resolveOutdoorLogTarget("2026-07-20");

    // The bug being pinned: this used to fall through to the new-log form.
    expect(r.kind).toBe("unavailable");
  });

  it("flags a spots failure but still allows logging", async () => {
    getOutdoorSpots.mockRejectedValue(new ApiError(0, "offline"));
    getOutdoorLogByDate.mockRejectedValue(new ApiError(404, "none"));

    const r = await mod.resolveOutdoorLogTarget("2026-07-20");

    expect(r.kind).toBe("new");
    expect(r.kind === "new" && r.spotsFailed).toBe(true);
    expect(r.kind === "new" && r.spots).toEqual([]);
  });

  it("does not let a spots failure block an existing log from opening", async () => {
    getOutdoorSpots.mockRejectedValue(new ApiError(0, "offline"));
    getOutdoorLogByDate.mockResolvedValue({ session: { date: "2026-07-20" } });

    const r = await mod.resolveOutdoorLogTarget("2026-07-20");

    expect(r.kind).toBe("edit");
  });
});
