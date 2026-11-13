/**
 * @vitest-environment jsdom
 *
 * A330 (D288-FE) — «Technique (counts for the key)» in the outdoor log form:
 * it writes `technique_target` exactly as
 * `backend/data/schemas/outdoor_session_entry.v1.json` wants it
 * (`{metric: foot_slips_per_go | sample_readjust, value: 0-30, sample?}`,
 * nothing else), prefilled on an edit; on a PUT a key left out keeps the
 * stored value and `null` clears it (A324). The key-sessions card says when a
 * crag day ticked technique.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import type { KeyRequirement, OutdoorSession } from "@/lib/types";

const postOutdoorLog = vi.fn();
const putOutdoorLog = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status = 0;
  },
  getOutdoorLogByDate: vi.fn(),
  postOutdoorLog: (...a: unknown[]) => postOutdoorLog(...a),
  putOutdoorLog: (...a: unknown[]) => putOutdoorLog(...a),
}));
vi.mock("sonner", () => ({ toast: vi.fn() }));
vi.mock("@/lib/outbox", () => ({ enqueue: vi.fn(() => false) }));

import OutdoorLogForm from "../OutdoorLogForm";
import { parseTechniqueDraft, techniqueTargetField } from "@/lib/outdoor-technique";
import { outdoorTechniqueLine, requirementLine } from "@/lib/key-sessions";

afterEach(cleanup);

beforeEach(() => {
  postOutdoorLog.mockReset().mockResolvedValue({ status: "ok" });
  putOutdoorLog.mockReset().mockResolvedValue({ status: "ok", load_score: 37 });
});

function day(over: Partial<OutdoorSession> = {}): OutdoorSession {
  return {
    log_version: "outdoor.v2",
    date: "2026-11-08",
    spot_name: "Isatis",
    discipline: "boulder",
    duration_minutes: 240,
    routes: [{ name: "Le Mur", grade: "7a", attempts: [{ result: "sent" }] }],
    notes: "",
    ...over,
  };
}

const metric = () => screen.getByLabelText("Technique (counts for the key)") as HTMLSelectElement;
const value = () => screen.getByLabelText("Technique number (0-30)") as HTMLInputElement;
const sample = () => screen.getByLabelText("Route or pitch measured (optional)") as HTMLInputElement;

async function save() {
  await act(async () => {
    screen.getByRole("button", { name: /Save Changes|Log Session|Finish & save/ }).click();
  });
}

const posted = () => postOutdoorLog.mock.calls[0][0] as Record<string, unknown>;
const put = () => putOutdoorLog.mock.calls[0][0] as Record<string, unknown>;

describe("A330 — new log", () => {
  it("writes {metric, value, sample} when measured", async () => {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-11-08" defaultSpotName="Isatis" />);
    fireEvent.change(metric(), { target: { value: "foot_slips_per_go" } });
    fireEvent.change(value(), { target: { value: "2" } });
    fireEvent.change(sample(), { target: { value: "  Isatis L1 " } });
    await save();
    expect(postOutdoorLog).toHaveBeenCalledTimes(1);
    expect(posted().technique_target).toEqual({ metric: "foot_slips_per_go", value: 2, sample: "Isatis L1" });
  });

  it("a decimal with a comma, no route: {metric, value} only", async () => {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-11-08" defaultSpotName="Isatis" />);
    fireEvent.change(metric(), { target: { value: "sample_readjust" } });
    fireEvent.change(value(), { target: { value: "1,5" } });
    await save();
    expect(posted().technique_target).toEqual({ metric: "sample_readjust", value: 1.5 });
  });

  it("not measured → no technique_target key at all", async () => {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-11-08" defaultSpotName="Isatis" />);
    expect(metric().value).toBe("");
    expect(screen.queryByLabelText("Technique number (0-30)")).toBeNull();
    await save();
    expect("technique_target" in posted()).toBe(false);
  });

  it("an out-of-range or missing number is refused in the form, nothing sent", async () => {
    render(<OutdoorLogForm spots={[]} defaultDate="2026-11-08" defaultSpotName="Isatis" />);
    fireEvent.change(metric(), { target: { value: "foot_slips_per_go" } });
    fireEvent.change(value(), { target: { value: "31" } });
    await save();
    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(screen.getByText("Technique: the number must be between 0 and 30.")).toBeTruthy();
    fireEvent.change(value(), { target: { value: "" } });
    await save();
    expect(postOutdoorLog).not.toHaveBeenCalled();
    expect(screen.getByText(/Technique: enter the number \(0-30\)/)).toBeTruthy();
  });

  it("the live-session finish carries it too", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<OutdoorLogForm spots={[]} defaultDate="2026-11-08" defaultSpotName="Isatis" onSubmit={onSubmit} submitLabel="Finish & save" />);
    fireEvent.change(metric(), { target: { value: "foot_slips_per_go" } });
    fireEvent.change(value(), { target: { value: "0" } });
    await save();
    expect(onSubmit.mock.calls[0][0].technique_target).toEqual({ metric: "foot_slips_per_go", value: 0 });
  });
});

describe("A330 — edit (PUT)", () => {
  it("prefilled from the log, and sent back as is", async () => {
    render(
      <OutdoorLogForm
        spots={[]}
        initialData={day({ technique_target: { metric: "sample_readjust", value: 3, sample: "Isatis L1" } })}
      />,
    );
    expect(metric().value).toBe("sample_readjust");
    expect(value().value).toBe("3");
    expect(sample().value).toBe("Isatis L1");
    await save();
    expect(put().technique_target).toEqual({ metric: "sample_readjust", value: 3, sample: "Isatis L1" });
  });

  it("cleared («Not measured») → null, so the stored target goes", async () => {
    render(<OutdoorLogForm spots={[]} initialData={day({ technique_target: { metric: "foot_slips_per_go", value: 2 } })} />);
    fireEvent.change(metric(), { target: { value: "" } });
    await save();
    expect(put().technique_target).toBeNull();
  });

  it("no target before, none now → the key is left out (A324: absent keeps)", async () => {
    render(<OutdoorLogForm spots={[]} initialData={day()} />);
    await save();
    expect("technique_target" in put()).toBe(false);
  });

  it("added on an edit → sent", async () => {
    render(<OutdoorLogForm spots={[]} initialData={day()} />);
    fireEvent.change(metric(), { target: { value: "foot_slips_per_go" } });
    fireEvent.change(value(), { target: { value: "4" } });
    await save();
    expect(put().technique_target).toEqual({ metric: "foot_slips_per_go", value: 4 });
  });
});

describe("A330 — payload helpers", () => {
  it("parse: only the schema's keys, value 0-30", () => {
    expect(parseTechniqueDraft({ metric: "", value: "5", sample: "x" })).toEqual({ target: null, error: null });
    expect(parseTechniqueDraft({ metric: "foot_slips_per_go", value: "30", sample: "" }).target).toEqual({
      metric: "foot_slips_per_go",
      value: 30,
    });
    expect(parseTechniqueDraft({ metric: "foot_slips_per_go", value: "-1", sample: "" }).error).toBeTruthy();
    expect(parseTechniqueDraft({ metric: "foot_slips_per_go", value: "2x", sample: "" }).error).toBeTruthy();
    expect(parseTechniqueDraft({ metric: "foot_slips_per_go", value: "1", sample: "a".repeat(100) }).target?.sample).toHaveLength(80);
  });

  it("«add as another crag» never copies the edited crag's own target", () => {
    const own = { metric: "foot_slips_per_go" as const, value: 2 };
    expect(techniqueTargetField(own, "add", own)).toBeUndefined();
    expect(techniqueTargetField(null, "add", own)).toBeUndefined();
    expect(techniqueTargetField({ ...own, value: 1 }, "add", own)).toEqual({ ...own, value: 1 });
    expect(techniqueTargetField(null, "post", own)).toBeUndefined();
    expect(techniqueTargetField(null, "put", own)).toBeNull();
    expect(techniqueTargetField(null, "put", null)).toBeUndefined();
  });
});

describe("A330 — key-sessions card line", () => {
  function technique(done: KeyRequirement["done"], status: KeyRequirement["status"] = "done"): KeyRequirement {
    return {
      key: "technique",
      label: "Technique",
      target: 1,
      status,
      resolution: null,
      severity: "none",
      debt: 0,
      done,
      partial: [],
      planned: [],
      skipped: [],
    };
  }
  const outdoorRow = (tt: { metric: "foot_slips_per_go" | "sample_readjust"; value: number; sample?: string }) => ({
    date: "2026-11-08",
    slot: null,
    session_id: null,
    name: "outdoor Isatis",
    status: "done",
    dose: "full" as const,
    evidence: "outdoor: 2 scivolate di piede/giro (Isatis L1)",
    technique_target: tt,
  });

  it("«done outdoors: <value> <metric> (<route>)»", () => {
    const r = technique([outdoorRow({ metric: "foot_slips_per_go", value: 2, sample: "Isatis L1" })]);
    expect(requirementLine(r)).toBe("done outdoors: 2 foot slips per go (Isatis L1)");
    expect(outdoorTechniqueLine(technique([outdoorRow({ metric: "sample_readjust", value: 1 })]))).toBe(
      "done outdoors: 1 foot readjustment on a sample pitch",
    );
    expect(outdoorTechniqueLine(technique([outdoorRow({ metric: "foot_slips_per_go", value: 1.5 })]))).toBe(
      "done outdoors: 1.5 foot slips per go",
    );
  });

  it("a key done indoors still reads «Done»", () => {
    const r = technique([{ date: "2026-11-10", slot: "evening", session_id: "technique_focus_gym", status: "done", dose: "full" }]);
    expect(requirementLine(r)).toBe("Done");
  });
});
