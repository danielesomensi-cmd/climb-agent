import { describe, it, expect } from "vitest";
import {
  computeEliteScores,
  eliteInputsFromAddedLoads,
  extractEliteInputs,
  hasAnyEliteScore,
  normalizeAgainstAnchor,
} from "../eliteScoring";
import {
  ELITE_ANCHORS_V1,
  ELITE_ANCHOR_SET_VERSION,
  type EliteAxisAnchor,
} from "../eliteAnchors";
import {
  buildEliteAxisTooltipCopy,
  ELITE_SCALE_LINE,
  ELITE_UNAVAILABLE_LINE,
} from "../radarTooltip";

const AXES = [
  "finger_strength",
  "pulling_strength",
  "power_endurance",
  "technique",
  "endurance",
] as const;

/** The author's real stored numbers (audit D260 §3): lead, target 8a+, 76 kg. */
const AUTHOR = {
  bodyweightKg: 76,
  maxHangTotalKg: 122,
  weightedPullupTotalKg: 127.8,
};

describe("elite anchor table (D262)", () => {
  it("is versioned", () => {
    expect(ELITE_ANCHOR_SET_VERSION).toBe("elite_anchors_v1");
  });

  it("ships exactly two live axes and three greyed ones", () => {
    const live = AXES.filter((a) => ELITE_ANCHORS_V1[a].status === "live");
    expect(live).toEqual(["finger_strength", "pulling_strength"]);
    expect(ELITE_ANCHORS_V1.endurance.status).toBe("dormant");
    expect(ELITE_ANCHORS_V1.power_endurance.status).toBe("unavailable");
    expect(ELITE_ANCHORS_V1.technique.status).toBe("unavailable");
  });

  it("pins the documented anchor values", () => {
    expect(ELITE_ANCHORS_V1.finger_strength.elite).toBe(200);
    expect(ELITE_ANCHORS_V1.finger_strength.floor).toBe(100);
    expect(ELITE_ANCHORS_V1.pulling_strength.elite).toBe(187);
    expect(ELITE_ANCHORS_V1.pulling_strength.floor).toBe(100);
    // Dormant but decided: 8b-9a+ band median, Berta et al. 2025.
    expect(ELITE_ANCHORS_V1.endurance.elite).toBe(58.5);
  });

  it("gives axes with no benchmark no numbers at all", () => {
    for (const axis of ["power_endurance", "technique"] as const) {
      expect(ELITE_ANCHORS_V1[axis].elite).toBeNull();
      expect(ELITE_ANCHORS_V1[axis].floor).toBeNull();
      expect(ELITE_ANCHORS_V1[axis].metric).toBeNull();
    }
  });
});

describe("normalizeAgainstAnchor — pure normalization", () => {
  const anchor: EliteAxisAnchor = {
    status: "live",
    metric: "test",
    elite: 200,
    floor: 100,
    note: "",
  };

  it("scores the elite value at exactly 100", () => {
    expect(normalizeAgainstAnchor(200, anchor)).toBe(100);
  });

  it("scores the floor value at exactly 0", () => {
    expect(normalizeAgainstAnchor(100, anchor)).toBe(0);
  });

  it("scores the midpoint at 50", () => {
    expect(normalizeAgainstAnchor(150, anchor)).toBe(50);
  });

  it("clamps above-elite performance to 100 rather than overflowing", () => {
    expect(normalizeAgainstAnchor(260, anchor)).toBe(100);
  });

  it("clamps below-floor performance to 0 rather than going negative", () => {
    expect(normalizeAgainstAnchor(60, anchor)).toBe(0);
  });

  it("returns null (grey), never 0, for a missing input", () => {
    expect(normalizeAgainstAnchor(null, anchor)).toBeNull();
    expect(normalizeAgainstAnchor(undefined, anchor)).toBeNull();
    expect(normalizeAgainstAnchor(NaN, anchor)).toBeNull();
  });

  it("returns null for an axis with no anchor", () => {
    expect(normalizeAgainstAnchor(150, ELITE_ANCHORS_V1.technique)).toBeNull();
  });
});

describe("computeEliteScores", () => {
  it("scores the author plausibly below elite on both live axes", () => {
    const scores = computeEliteScores(AUTHOR);
    // 122/76 = 160.5% BW -> (160.5-100)/100*100
    expect(scores.finger_strength).toBe(61);
    // 127.8/76 = 168.2% BW -> (168.2-100)/87*100
    expect(scores.pulling_strength).toBe(78);
    expect(scores.finger_strength!).toBeLessThan(100);
    expect(scores.pulling_strength!).toBeLessThan(100);
  });

  it("greys the three axes with no live anchor", () => {
    const scores = computeEliteScores(AUTHOR);
    expect(scores.power_endurance).toBeNull();
    expect(scores.technique).toBeNull();
    expect(scores.endurance).toBeNull();
  });

  it("wakes the endurance axis up on data alone once an impulse exists (D261)", () => {
    const scores = computeEliteScores({ ...AUTHOR, enduranceImpulse: 58.5 });
    expect(scores.endurance).toBe(100);
    expect(computeEliteScores({ ...AUTHOR, enduranceImpulse: 39.25 }).endurance).toBe(50);
  });

  it("greys both strength axes when bodyweight is missing — never assumes 70kg", () => {
    const scores = computeEliteScores({
      maxHangTotalKg: 122,
      weightedPullupTotalKg: 127.8,
    });
    expect(scores.finger_strength).toBeNull();
    expect(scores.pulling_strength).toBeNull();
    expect(hasAnyEliteScore(scores)).toBe(false);
  });

  it("greys one axis independently of the other", () => {
    const scores = computeEliteScores({ bodyweightKg: 76, maxHangTotalKg: 122 });
    expect(scores.finger_strength).toBe(61);
    expect(scores.pulling_strength).toBeNull();
    expect(hasAnyEliteScore(scores)).toBe(true);
  });

  it("is deterministic — same inputs, same output", () => {
    expect(computeEliteScores(AUTHOR)).toEqual(computeEliteScores(AUTHOR));
  });
});

describe("extractEliteInputs — reads the existing /api/state payload", () => {
  it("prefers the 7s hangboard total and the direct pull-up 1RM", () => {
    const raw = extractEliteInputs({
      assessment: {
        body: { weight_kg: 76 },
        tests: {
          max_hang_20mm_7s_total_kg: 122,
          max_hang_20mm_5s_total_kg: 118,
          weighted_pullup_1rm_total_kg: 127.8,
        },
      },
    });
    expect(raw).toMatchObject({
      bodyweightKg: 76,
      maxHangTotalKg: 122,
      weightedPullupTotalKg: 127.8,
    });
  });

  it("falls back to the 5s hangboard total", () => {
    const raw = extractEliteInputs({
      assessment: { body: { weight_kg: 70 }, tests: { max_hang_20mm_5s_total_kg: 100 } },
    });
    expect(raw.maxHangTotalKg).toBe(100);
  });

  it("converts a loading-pin lift like the engine does (A266)", () => {
    const raw = extractEliteInputs({
      assessment: {
        body: { weight_kg: 70 },
        tests: { lp_max_lift_5s_left_kg: 50, lp_max_lift_5s_right_kg: 54 },
      },
    });
    // mean 52 * 1.85
    expect(raw.maxHangTotalKg).toBeCloseTo(96.2, 5);
  });

  it("drops an implausible one-hand lift instead of saturating the axis", () => {
    const raw = extractEliteInputs({
      assessment: {
        body: { weight_kg: 70 },
        tests: { lp_max_lift_5s_left_kg: 140 }, // 2.0x BW — a typo, not a climber
      },
    });
    expect(raw.maxHangTotalKg).toBeNull();
  });

  it("estimates a pull-up 1RM from submaximal reps (Brzycki, D38)", () => {
    const raw = extractEliteInputs({
      assessment: {
        body: { weight_kg: 70 },
        tests: { pullup_submaximal_reps: 5, pullup_submaximal_load_kg: 20 },
      },
    });
    // (70+20) * 36/32
    expect(raw.weightedPullupTotalKg).toBeCloseTo(101.25, 5);
  });

  it("falls back to top-level bodyweight fields", () => {
    expect(extractEliteInputs({ body: { weight_kg: 68 } }).bodyweightKg).toBe(68);
    expect(extractEliteInputs({ bodyweight_kg: 64 }).bodyweightKg).toBe(64);
  });

  it("survives an empty or absent state without throwing", () => {
    expect(extractEliteInputs(undefined).bodyweightKg).toBeNull();
    expect(extractEliteInputs({}).maxHangTotalKg).toBeNull();
    expect(hasAnyEliteScore(computeEliteScores(extractEliteInputs({})))).toBe(false);
  });
});

describe("eliteInputsFromAddedLoads — the public /assessment page (A268)", () => {
  it("converts added loads to totals the way the public endpoint does", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: 76,
      max_hang_added_kg: 46,
      weighted_pullup_added_kg: 51.8,
    });
    expect(raw.bodyweightKg).toBe(76);
    expect(raw.maxHangTotalKg).toBe(122);
    expect(raw.weightedPullupTotalKg).toBeCloseTo(127.8, 5);
  });

  it("scores identically to the /plan path for the same athlete", () => {
    // Same numbers, one expressed as added load and one as a stored total.
    const viaAdded = computeEliteScores(
      eliteInputsFromAddedLoads({
        bodyweight_kg: 76,
        max_hang_added_kg: 46,
        weighted_pullup_added_kg: 51.8,
      }),
    );
    const viaState = computeEliteScores(
      extractEliteInputs({
        assessment: {
          body: { weight_kg: 76 },
          tests: {
            max_hang_20mm_7s_total_kg: 122,
            weighted_pullup_1rm_total_kg: 127.8,
          },
        },
      }),
    );
    expect(viaAdded).toEqual(viaState);
    expect(viaAdded.finger_strength).toBe(61);
    expect(viaAdded.pulling_strength).toBe(78);
  });

  it("handles an assisted pull-up (negative added load)", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: 67,
      weighted_pullup_added_kg: -22, // 22 kg of assistance
    });
    expect(raw.weightedPullupTotalKg).toBe(45);
    expect(computeEliteScores(raw).pulling_strength).toBe(0); // below the 100% BW floor
  });

  it("refuses to score numbers without a bodyweight — no 70kg stand-in", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: null,
      max_hang_added_kg: 46,
      weighted_pullup_added_kg: 51.8,
    });
    expect(raw.maxHangTotalKg).toBeNull();
    expect(raw.weightedPullupTotalKg).toBeNull();
    expect(hasAnyEliteScore(computeEliteScores(raw))).toBe(false);
  });

  it("greys one axis independently of the other", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: 70,
      max_hang_added_kg: 40,
    });
    expect(raw.maxHangTotalKg).toBe(110);
    expect(raw.weightedPullupTotalKg).toBeNull();
    expect(hasAnyEliteScore(computeEliteScores(raw))).toBe(true);
  });

  it("hides the toggle for a visitor who entered no numbers at all", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: null,
      max_hang_added_kg: null,
      weighted_pullup_added_kg: null,
    });
    expect(hasAnyEliteScore(computeEliteScores(raw))).toBe(false);
  });

  it("drops an assistance larger than bodyweight instead of going negative", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: 60,
      weighted_pullup_added_kg: -75,
    });
    expect(raw.weightedPullupTotalKg).toBeNull();
  });

  it("never carries an endurance impulse — the public page collects none", () => {
    const raw = eliteInputsFromAddedLoads({
      bodyweight_kg: 76,
      max_hang_added_kg: 46,
    });
    expect(raw.enduranceImpulse).toBeNull();
    expect(computeEliteScores(raw).endurance).toBeNull();
  });
});

describe("elite mode tooltip copy (D262)", () => {
  it("tells live axes what the elite scale means", () => {
    const copy = buildEliteAxisTooltipCopy("finger_strength", "lead")!;
    expect(copy.relative).toContain("100 means elite level");
    expect(copy.low).toContain(ELITE_SCALE_LINE);
    expect(copy.low).toContain("200% bodyweight");
    expect(copy.relative).not.toContain(ELITE_UNAVAILABLE_LINE);
  });

  it("says plainly that greyed axes have no benchmark", () => {
    for (const axis of ["power_endurance", "technique", "endurance"] as const) {
      const copy = buildEliteAxisTooltipCopy(axis, "lead")!;
      expect(copy.relative).toBe(ELITE_UNAVAILABLE_LINE);
    }
  });

  it("keeps the boulder labels and the 300-char budget", () => {
    for (const axis of AXES) {
      for (const disc of ["lead", "boulder"] as const) {
        const copy = buildEliteAxisTooltipCopy(axis, disc)!;
        expect(copy.description.length).toBeLessThanOrEqual(300);
        expect(copy.relative.length).toBeLessThanOrEqual(300);
        expect(copy.low.length).toBeLessThanOrEqual(300);
      }
    }
  });

  it("never mentions the goal grade in elite mode", () => {
    const copy = buildEliteAxisTooltipCopy("finger_strength", "lead")!;
    expect(copy.relative + copy.low).not.toContain("{target}");
    expect(copy.relative).not.toContain("your goal grade");
  });
});

describe("display-only guarantee (A267 non-negotiable)", () => {
  it("computes without any network or storage API present", () => {
    // The module is imported in a bare Node context: no fetch mock, no
    // localStorage, no document. If any code path tried to persist or send the
    // elite scores, this would throw rather than return a number.
    expect(typeof globalThis.localStorage).toBe("undefined");
    const scores = computeEliteScores(AUTHOR);
    expect(scores.finger_strength).toBe(61);
  });

  it("leaves the raw input object untouched", () => {
    const input = { ...AUTHOR };
    const snapshot = JSON.stringify(input);
    computeEliteScores(input);
    extractEliteInputs({ assessment: { body: { weight_kg: 76 } } });
    expect(JSON.stringify(input)).toBe(snapshot);
  });

  it("leaves the anchor table untouched", () => {
    const snapshot = JSON.stringify(ELITE_ANCHORS_V1);
    computeEliteScores(AUTHOR);
    computeEliteScores({ bodyweightKg: 76, maxHangTotalKg: 999 });
    expect(JSON.stringify(ELITE_ANCHORS_V1)).toBe(snapshot);
  });
});
