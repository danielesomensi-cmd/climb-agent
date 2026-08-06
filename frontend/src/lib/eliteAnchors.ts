// A267 — elite radar anchors, v1. DATA ONLY: no logic lives in this file.
//
// These anchors are **display-only** (research decision D262, see
// `docs/research/assessment_scoring_research_2026-08.md`). They exist so the
// radar can answer "how far am I from the top of the sport?" alongside the
// engine's own question, "how ready am I for my goal?".
//
// Nothing derived from this table is ever persisted, sent to the API, or read
// by the engine. The engine's axis scores stay target-relative and untouched.
//
// ── Why unisex (male-derived) values ──────────────────────────────────────
// The strength anchors come from survey data on elite performers. Once
// normalized to body mass, the reported male/female difference on these two
// metrics is not significant, and the female elite sub-sample is n=5 — too
// small to justify a second anchor set that would read as authoritative. One
// unisex set is the honest option until there is enough data for more. This is
// recorded as an open question in §4 of the research file.
//
// ── Confidence ────────────────────────────────────────────────────────────
// Finger and Pulling are **survey-grade**, medium confidence. The only
// peer-reviewed finger anchor available describes a *one-hand MVC* protocol,
// which is not the two-arm max hang climb-agent collects; adopting it would
// mean a conversion on top of an anchor, so it is deferred to v1.1 (D262).

import type { AssessmentProfile } from "@/lib/types";

export type AxisKey = keyof AssessmentProfile;

/** Version tag for the anchor set. Bump when any number below changes. */
export const ELITE_ANCHOR_SET_VERSION = "elite_anchors_v1";

/**
 * `live` — the axis renders an elite-relative score when its input is present.
 * `dormant` — the anchor is decided but no input exists yet; renders grey.
 * `unavailable` — no defensible quantitative anchor exists; renders grey.
 */
export type EliteAnchorStatus = "live" | "dormant" | "unavailable";

export interface EliteAxisAnchor {
  status: EliteAnchorStatus;
  /** Human-readable metric, shown in the tooltip. Null when nothing is measured. */
  metric: string | null;
  /** Raw value scoring 100. Null for `unavailable`. */
  elite: number | null;
  /** Raw value scoring 0. Null for `unavailable`. */
  floor: number | null;
  /** Provenance / caveat, shown in the tooltip for live axes. */
  note: string;
}

export const ELITE_ANCHORS_V1: Record<AxisKey, EliteAxisAnchor> = {
  finger_strength: {
    status: "live",
    metric: "Two-arm max hang on a 20mm edge, total load as % of bodyweight",
    // 200% BW = elite. 100% BW = a bodyweight-only hang, the floor of the scale.
    elite: 200,
    floor: 100,
    note: "Elite anchor: 200% bodyweight on a two-arm 20mm max hang (survey data, medium confidence).",
  },
  pulling_strength: {
    status: "live",
    metric: "Weighted pull-up 1RM, total load as % of bodyweight",
    elite: 187,
    floor: 100,
    note: "Elite anchor: 187% bodyweight on a weighted pull-up 1RM (survey data, medium confidence).",
  },
  endurance: {
    // D261/D262: the anchor is decided — 58.5 kg·s·kg⁻¹, the median of the
    // 8b–9a+ band in Berta et al. 2025 — but nothing produces the input yet.
    // It goes live by data, not by code, the day `test_endurance_intermittent`
    // ships and starts writing an impulse.
    status: "dormant",
    metric: "Intermittent hang impulse (kg·s·kg⁻¹), 8s:2s to failure",
    elite: 58.5,
    floor: 20.0, // p10 of the lowest band (5+–6b+) in the same dataset
    note: "Elite anchor: 58.5 kg·s·kg⁻¹ intermittent impulse. Dormant until the endurance test ships.",
  },
  power_endurance: {
    // Permanently greyed (D262): no benchmark exists. The repeater constants the
    // engine uses are unsourced (audit D260 §7) and cannot anchor an elite scale.
    status: "unavailable",
    metric: null,
    elite: null,
    floor: null,
    note: "No defensible elite benchmark exists for this axis.",
  },
  technique: {
    // Permanently greyed (D262). D266 additionally demotes the redpoint-onsight
    // gap that currently drives this axis — there is nothing to anchor.
    status: "unavailable",
    metric: null,
    elite: null,
    floor: null,
    note: "No defensible elite benchmark exists for this axis.",
  },
};
