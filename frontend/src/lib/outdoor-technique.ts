/**
 * A330 (D288-FE) — the «Technique (counts for the key)» block of the outdoor
 * log form. Pure, no React.
 *
 * Since A329 a crag day ticks the weekly technique key only with a logged,
 * measurable target: `technique_target` on the outdoor entry, exactly as
 * `backend/data/schemas/outdoor_session_entry.v1.json` wants it —
 * `{metric: foot_slips_per_go | sample_readjust, value: 0-30, sample?: ≤ 80}`,
 * nothing else (additionalProperties false). On an edit (PUT) a key the
 * request leaves out keeps the stored value and `null` clears it (A324).
 */
import type { OutdoorTechniqueMetric, OutdoorTechniqueTarget } from "@/lib/types";

export const TECHNIQUE_VALUE_MAX = 30;
export const TECHNIQUE_SAMPLE_MAX = 80;

export const TECHNIQUE_METRICS: Array<{ value: OutdoorTechniqueMetric; label: string; hint: string }> = [
  {
    value: "foot_slips_per_go",
    label: "Foot slips per go",
    hint: "On your project: how many times a foot slipped, per go. An average can be decimal (1.5).",
  },
  {
    value: "sample_readjust",
    label: "Foot readjustments on a sample pitch",
    hint: "One pitch you pick (video or partner): how many times you re-placed a foot after setting it.",
  },
];

/** What the form holds: the metric (`""` = not measured) and the raw inputs. */
export interface TechniqueDraft {
  metric: OutdoorTechniqueMetric | "";
  value: string;
  sample: string;
}

export function techniqueDraftOf(tt: OutdoorTechniqueTarget | null | undefined): TechniqueDraft {
  if (!tt || !TECHNIQUE_METRICS.some((m) => m.value === tt.metric)) return { metric: "", value: "", sample: "" };
  return {
    metric: tt.metric,
    value: typeof tt.value === "number" && Number.isFinite(tt.value) ? String(tt.value) : "",
    sample: tt.sample ?? "",
  };
}

/**
 * The target the draft describes (null = not measured), or the error that
 * keeps the form from saving. A comma is a decimal point (Italian keyboards).
 */
export function parseTechniqueDraft(d: TechniqueDraft): { target: OutdoorTechniqueTarget | null; error: string | null } {
  if (!d.metric) return { target: null, error: null };
  const raw = d.value.trim().replace(",", ".");
  if (!raw) return { target: null, error: `Technique: enter the number (0-${TECHNIQUE_VALUE_MAX}), or pick «Not measured».` };
  const value = Number(raw);
  if (!/^(\d+\.?\d*|\.\d+)$/.test(raw) || !Number.isFinite(value) || value < 0 || value > TECHNIQUE_VALUE_MAX) {
    return { target: null, error: `Technique: the number must be between 0 and ${TECHNIQUE_VALUE_MAX}.` };
  }
  const sample = d.sample.trim().slice(0, TECHNIQUE_SAMPLE_MAX);
  return { target: sample ? { metric: d.metric, value, sample } : { metric: d.metric, value }, error: null };
}

function sameTarget(a: OutdoorTechniqueTarget | null | undefined, b: OutdoorTechniqueTarget | null | undefined): boolean {
  if (!a || !b) return !a && !b;
  return a.metric === b.metric && a.value === b.value && (a.sample?.trim() || "") === (b.sample?.trim() || "");
}

/**
 * The `technique_target` key of the request body, `undefined` = leave it out.
 *
 * - `post`: a new log — the target when measured, else nothing.
 * - `put`: an edit — the target when measured; `null` when the log had one
 *   and the form no longer does (an explicit clear); else nothing (absent
 *   keeps the stored value, A324 — never wipe what the form did not show).
 * - `add`: «Add as another crag» from an edit — only a target typed here,
 *   not the edited crag's own (like routes, notes and duration).
 */
export function techniqueTargetField(
  target: OutdoorTechniqueTarget | null,
  mode: "post" | "put" | "add",
  initial?: OutdoorTechniqueTarget | null,
): OutdoorTechniqueTarget | null | undefined {
  if (mode === "add") return target && !sameTarget(target, initial) ? target : undefined;
  if (target) return target;
  if (mode === "put" && initial) return null;
  return undefined;
}
