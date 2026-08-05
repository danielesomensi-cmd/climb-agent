import { describe, expect, it } from "vitest";

import {
  founderNoteCta,
  shouldShowFounderNote,
  type FounderNoteData,
} from "../founder-note";

const note = (overrides: Partial<FounderNoteData> = {}): FounderNoteData => ({
  id: "note-1",
  title: "About that 0 on your fingers",
  body: ["That was our bug, not your fingers."],
  ...overrides,
});

const today = { isViewingToday: true };

describe("shouldShowFounderNote", () => {
  it("shows a fresh note on the today view", () => {
    expect(shouldShowFounderNote(note(), today)).toBe(true);
  });

  it("shows nothing for the overwhelming majority who have no note", () => {
    expect(shouldShowFounderNote(undefined, today)).toBe(false);
    expect(shouldShowFounderNote(null, today)).toBe(false);
  });

  it("stays hidden once dismissed server-side", () => {
    expect(
      shouldShowFounderNote(note({ dismissed_at: "2026-08-05T09:00:00Z" }), today),
    ).toBe(false);
  });

  it("stays hidden after an optimistic dismiss, even before the PUT lands", () => {
    expect(
      shouldShowFounderNote(note(), { isViewingToday: true, locallyDismissed: true }),
    ).toBe(false);
  });

  it("does not follow the user back to a past day", () => {
    expect(shouldShowFounderNote(note(), { isViewingToday: false })).toBe(false);
  });

  it("treats an empty note as a data error rather than a blank card", () => {
    expect(shouldShowFounderNote(note({ title: "   " }), today)).toBe(false);
    expect(shouldShowFounderNote(note({ body: [] }), today)).toBe(false);
    expect(shouldShowFounderNote(note({ body: ["", "  "] }), today)).toBe(false);
  });
});

describe("founderNoteCta", () => {
  it("returns the pair when both halves are present", () => {
    expect(
      founderNoteCta(note({ cta_label: "See your radar", cta_href: "/plan" })),
    ).toEqual({ label: "See your radar", href: "/plan" });
  });

  it("returns null when either half is missing — never a dangling link", () => {
    expect(founderNoteCta(note({ cta_label: "See your radar" }))).toBeNull();
    expect(founderNoteCta(note({ cta_href: "/plan" }))).toBeNull();
    expect(founderNoteCta(note())).toBeNull();
  });
});
