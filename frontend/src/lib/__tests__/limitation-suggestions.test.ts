import { describe, it, expect } from "vitest";
import { describeLimitationSuggestions } from "../limitation-suggestions";

describe("A295 review — limitation suggestions", () => {
  it("is silent when there is nothing", () => {
    expect(describeLimitationSuggestions(undefined)).toBeNull();
    expect(describeLimitationSuggestions([])).toBeNull();
    expect(describeLimitationSuggestions([{ nope: 1 }])).toBeNull();
  });

  it("says pain when the suggestion comes from a pain 3/3", () => {
    const msg = describeLimitationSuggestions([
      { exercise_id: null, zone: "elbow", suggested_severity: "active", source: "pain" },
    ]);
    expect(msg?.title).toBe("Pain reported on your elbow");
    expect(msg?.description).toMatch(/limitation/);
  });

  it("dedupes zones of B38 suggestions", () => {
    const msg = describeLimitationSuggestions([
      { exercise_id: "a", zone: "finger" },
      { exercise_id: "b", zone: "finger" },
    ]);
    expect(msg?.title).toBe("Your finger may need more care");
  });
});
