// B293 — a session with zero resolved exercises must never be completable
import { describe, expect, it } from "vitest";
import { sessionResolutionState } from "../session-resolution";

const resolvedWith = (instances: number, blocks = 0) => ({
  resolved_session: {
    exercise_instances: Array.from({ length: instances }, (_, i) => ({ exercise_id: `e${i}` })),
    blocks: Array.from({ length: blocks }, (_, i) => ({ block_uid: `b${i}` })),
  },
});

describe("sessionResolutionState", () => {
  it("ok when exercises are resolved", () => {
    expect(sessionResolutionState({ resolved: resolvedWith(3) })).toBe("ok");
  });

  it("ok when only blocks are present (instruction-only content)", () => {
    expect(sessionResolutionState({ resolved: resolvedWith(0, 2) })).toBe("ok");
  });

  it("error when the backend marked a resolution failure", () => {
    expect(sessionResolutionState({ resolved: null, resolve_error: true })).toBe("error");
  });

  it("empty when resolved is null without an error marker", () => {
    expect(sessionResolutionState({ resolved: null })).toBe("empty");
  });

  it("empty when resolution succeeded but selected zero exercises", () => {
    expect(sessionResolutionState({ resolved: resolvedWith(0) })).toBe("empty");
  });

  it("custom sessions never depend on the resolver", () => {
    expect(sessionResolutionState({ is_custom: true, resolved: null })).toBe("ok");
  });

  it("a stale error marker does not override real content", () => {
    expect(sessionResolutionState({ resolved: resolvedWith(2), resolve_error: true })).toBe("ok");
  });
});
