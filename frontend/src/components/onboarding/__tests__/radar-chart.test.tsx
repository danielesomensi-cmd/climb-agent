/**
 * @vitest-environment jsdom
 *
 * B323 — render tests for the assessment radar.
 *
 * These close the two guarantees the A267 brief asked for and that could not be
 * written before, because the suite had no DOM: (1) a test asserting **zero
 * write or network requests** when the Goal/Elite toggle is flipped, and (2) a
 * regression pinning Goal mode to exactly what B304 shipped.
 *
 * What jsdom does NOT give us: layout. `getBoundingClientRect` returns zeros, so
 * these tests verify that the tooltip's clamping is *wired up and applied*, not
 * that the box is visually on-screen at 320px. The arithmetic itself is covered
 * by `lib/__tests__/radar-tooltip.test.ts`; the visual acceptance still needs a
 * real browser.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RadarChart } from "../radar-chart";
import type { AssessmentProfile } from "@/lib/types";

/** The author's real production profile (target 8b, 76 kg). */
const PROFILE: AssessmentProfile = {
  finger_strength: 100,
  pulling_strength: 96,
  power_endurance: 53,
  technique: 30,
  endurance: 51,
};

/** His real measured numbers, the input the Elite scale needs. */
const ELITE_INPUTS = {
  bodyweightKg: 76,
  maxHangTotalKg: 122,
  weightedPullupTotalKg: 127.8,
};

/**
 * The legend grid below the chart. Scoping to it matters: every axis name also
 * exists as an SVG `<tspan>`, so an unscoped `getByText` finds two nodes.
 */
function legend(): HTMLElement {
  const el = document.querySelector<HTMLElement>("div.grid");
  if (!el) throw new Error("legend grid not found");
  return el;
}

function axisRow(label: string): HTMLElement {
  // Each legend cell is `<div><span>Label ⓘ</span><span>value</span></div>`.
  const row = within(legend()).getByText(label).closest("div");
  if (!row) throw new Error(`no legend row for ${label}`);
  return row;
}

/** The value rendered next to an axis: a score, "—", or the At-target badge. */
function axisValue(label: string): string {
  const spans = within(axisRow(label)).getAllByText(/.+/, { selector: "span" });
  return spans[spans.length - 1].textContent ?? "";
}

/** Data points only. The ⓘ icons are `<circle>` elements too (lucide). */
function dataPoints(container: HTMLElement): NodeListOf<Element> {
  return container.querySelectorAll("circle[fill='var(--primary)']");
}

async function openTooltip(label: string) {
  await userEvent.click(screen.getByRole("button", { name: `Info about ${label}` }));
}

afterEach(cleanup);

describe("Goal mode — regression against what B304 shipped", () => {
  it("renders all five axes with their stored scores", () => {
    render(<RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />);
    expect(axisValue("Pulling Strength")).toBe("96");
    expect(axisValue("Power Endurance")).toBe("53");
    expect(axisValue("Technique & Tactics")).toBe("30");
    expect(axisValue("Endurance")).toBe("51");
  });

  it("shows the At-target badge instead of a bare 100", () => {
    render(<RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />);
    expect(axisValue("Finger Strength")).toBe("✓ At target");
    expect(screen.queryByText("100")).toBeNull();
  });

  it("renders no toggle and no elite subtitle without elite inputs", () => {
    render(<RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />);
    expect(screen.queryByRole("group", { name: "Comparison scale" })).toBeNull();
    expect(screen.queryByText("vs elite level")).toBeNull();
    expect(screen.queryByText(/Readiness for/)).toBeNull(); // the page owns it
  });

  it("renders no toggle when the elite inputs cannot score anything", () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={{ bodyweightKg: null, maxHangTotalKg: 122 }}
      />,
    );
    expect(screen.queryByRole("group", { name: "Comparison scale" })).toBeNull();
  });

  it("is byte-identical with and without an unusable eliteInputs prop", () => {
    const { container: a } = render(
      <RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />,
    );
    const withoutProp = a.innerHTML;
    cleanup();
    const { container: b } = render(
      <RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" eliteInputs={{}} />,
    );
    expect(b.innerHTML).toBe(withoutProp);
  });

  it("draws a five-vertex polygon and five data points", () => {
    const { container } = render(
      <RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />,
    );
    const data = container.querySelector("polygon[fill='var(--primary)']");
    expect(data?.getAttribute("points")?.split(" ")).toHaveLength(5);
    expect(dataPoints(container)).toHaveLength(5);
  });

  it("uses boulder labels for a boulder athlete", () => {
    render(<RadarChart profile={PROFILE} discipline="boulder" targetGrade="7C" />);
    expect(within(legend()).getByText("Pulling Power")).toBeTruthy();
    expect(within(legend()).getByText("Movement & Reading")).toBeTruthy();
  });
});

describe("Elite mode", () => {
  it("defaults to Goal and only switches on an explicit tap", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    expect(screen.getByRole("button", { name: "Goal" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Readiness for 8b")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(screen.getByRole("button", { name: "Elite" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("vs elite level")).toBeTruthy();
  });

  it("shows the elite-relative scores on the two live axes", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(axisValue("Finger Strength")).toBe("61");
    expect(axisValue("Pulling Strength")).toBe("78");
  });

  it("greys the three benchmark-less axes with an em dash, never a zero", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    for (const label of ["Power Endurance", "Technique & Tactics", "Endurance"]) {
      expect(axisValue(label)).toBe("—");
    }
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.getByText(/no defensible elite benchmark yet/)).toBeTruthy();
  });

  it("drops the polygon for spokes when fewer than three axes are live", async () => {
    const { container } = render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(container.querySelector("polygon[fill='var(--primary)']")).toBeNull();
    expect(container.querySelectorAll("line[stroke='var(--primary)']")).toHaveLength(2);
    expect(dataPoints(container)).toHaveLength(2);
  });

  it("returns to the exact Goal rendering when toggled back", async () => {
    const { container } = render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    const goal = container.innerHTML;
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(container.innerHTML).not.toBe(goal);
    await userEvent.click(screen.getByRole("button", { name: "Goal" }));
    expect(container.innerHTML).toBe(goal);
  });

  it("keeps a live axis when only one measurement exists", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={{ bodyweightKg: 76, maxHangTotalKg: 122 }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(axisValue("Finger Strength")).toBe("61");
    expect(axisValue("Pulling Strength")).toBe("—");
  });
});

describe("tooltips", () => {
  it("frames Goal-mode copy against the target grade", async () => {
    render(<RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />);
    await openTooltip("Finger Strength");
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toContain("8b");
    expect(tip.textContent).toContain("100 means you're already there");
  });

  it("swaps to the elite framing without mentioning the goal grade", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    await openTooltip("Finger Strength");
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toContain("100 means elite level");
    expect(tip.textContent).toContain("8b–9a level performance");
    expect(tip.textContent).not.toContain("100 means you're already there");
  });

  it("says plainly that a greyed axis has no benchmark", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    await openTooltip("Technique & Tactics");
    expect(screen.getByRole("tooltip").textContent).toContain(
      "Elite benchmark not available for this axis",
    );
  });

  it("applies the viewport clamp it computed", async () => {
    // jsdom has no layout: every rect is zero, which would read as "overflows
    // the left edge by 0px". Stub a rect that genuinely overflows so the wiring
    // — measure, compute, write a transform — is exercised end to end.
    const spy = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockReturnValue({
        left: -24, right: 264, top: 100, bottom: 300,
        width: 288, height: 200, x: -24, y: 100, toJSON: () => ({}),
      } as DOMRect);
    try {
      render(<RadarChart profile={PROFILE} discipline="lead" targetGrade="8b" />);
      await openTooltip("Finger Strength");
      const tip = screen.getByRole("tooltip");
      // 12 - (-24) = 36px of correction, and the box is revealed only after it.
      expect(tip.style.transform).toBe("translateX(calc(-50% + 36px))");
      expect(tip.style.visibility).toBe("visible");
    } finally {
      spy.mockRestore();
    }
  });
});

describe("the toggle writes nothing — A267's non-negotiable", () => {
  let calls: string[];

  beforeEach(() => {
    calls = [];
    const trap = (name: string) => (...args: unknown[]) => {
      calls.push(`${name}(${String(args[0] ?? "")})`);
      return undefined as never;
    };
    vi.stubGlobal("fetch", trap("fetch"));
    vi.stubGlobal("XMLHttpRequest", class { open = trap("xhr.open"); send = trap("xhr.send"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(trap("localStorage.setItem"));
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(trap("localStorage.removeItem"));
    Object.defineProperty(navigator, "sendBeacon", {
      configurable: true,
      value: trap("sendBeacon"),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("issues no request and touches no storage across a full toggle cycle", async () => {
    render(
      <RadarChart
        profile={PROFILE}
        discipline="lead"
        targetGrade="8b"
        eliteInputs={ELITE_INPUTS}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    await openTooltip("Finger Strength");
    await userEvent.click(screen.getByRole("button", { name: "Goal" }));
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));

    expect(calls).toEqual([]);
  });

  it("leaves the profile and the raw inputs untouched", async () => {
    const profile = { ...PROFILE };
    const inputs = { ...ELITE_INPUTS };
    const before = JSON.stringify({ profile, inputs });
    render(
      <RadarChart profile={profile} discipline="lead" targetGrade="8b" eliteInputs={inputs} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    await userEvent.click(screen.getByRole("button", { name: "Goal" }));
    expect(JSON.stringify({ profile, inputs })).toBe(before);
  });

  it("does not persist the mode — a fresh mount is back on Goal", async () => {
    const props = {
      profile: PROFILE,
      discipline: "lead" as const,
      targetGrade: "8b",
      eliteInputs: ELITE_INPUTS,
    };
    const first = render(<RadarChart {...props} />);
    await userEvent.click(screen.getByRole("button", { name: "Elite" }));
    expect(screen.getByText("vs elite level")).toBeTruthy();
    first.unmount();

    render(<RadarChart {...props} />);
    expect(screen.getByText("Readiness for 8b")).toBeTruthy();
    expect(screen.queryByText("vs elite level")).toBeNull();
  });
});
