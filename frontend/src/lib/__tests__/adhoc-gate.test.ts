// B306 — adhoc gate: noun+stem routing (B282) + short-follow-up routing.
// Field failure 2026-07-28: "Si" / "Crea!" after the coach offered a build
// fell to /chat, where the LLM fabricated an "I built you a session" reply.
import { describe, expect, it } from "vitest";
import {
  isAdhocFollowUp,
  looksLikeAdhoc,
  shouldRouteToAdhoc,
} from "../adhoc-gate";

describe("looksLikeAdhoc (B282 behavior preserved)", () => {
  it("routes direct build requests, IT and EN", () => {
    expect(
      looksLikeAdhoc("Creami una sessione di core e bloccaggi di 60 minuti a casa"),
    ).toBe(true);
    expect(looksLikeAdhoc("build me a 45-min pulling session")).toBe(true);
    expect(looksLikeAdhoc("mi prepari un allenamento veloce?")).toBe(true);
  });

  it("routes clitic forms without the noun", () => {
    expect(looksLikeAdhoc("riprovi a crearla?")).toBe(true);
    expect(looksLikeAdhoc("mandamela")).toBe(true);
  });

  it("does not route plain questions", () => {
    expect(looksLikeAdhoc("perché questa settimana è deload?")).toBe(false);
    expect(looksLikeAdhoc("Si")).toBe(false);
    expect(looksLikeAdhoc("Crea!")).toBe(false);
  });
});

describe("isAdhocFollowUp (B306)", () => {
  const adhocContext = [
    { content: "Che allenamento potrei fare oggi? Un'oretta di core direi" },
    { content: "Vuoi che ti prepari una sessione di core e bloccaggi?" },
  ];
  const neutralContext = [
    { content: "come sta andando il mio allenamento?" },
    { content: "Sta andando bene, sei in fase performance." },
  ];

  it("routes short affirmations when the conversation is adhoc-flavored", () => {
    expect(isAdhocFollowUp("Si", adhocContext)).toBe(true);
    expect(isAdhocFollowUp("Crea!", adhocContext)).toBe(true);
    expect(isAdhocFollowUp("rimettila", adhocContext)).toBe(true);
  });

  it("routes short follow-ups after a composed card", () => {
    const withCard = [{ content: "I built you a session", hasAdhocCard: true }];
    expect(isAdhocFollowUp("rifalla più corta", withCard)).toBe(true);
  });

  it("ignores short messages in a neutral conversation", () => {
    expect(isAdhocFollowUp("Si", neutralContext)).toBe(false);
    expect(isAdhocFollowUp("grazie!", neutralContext)).toBe(false);
  });

  it("ignores long messages even in adhoc context (noun+stem gate decides)", () => {
    expect(
      isAdhocFollowUp(
        "spiegami perché hai scelto proprio questi esercizi e non altri per me",
        adhocContext,
      ),
    ).toBe(false);
  });

  it("only looks at the recent window", () => {
    const oldAdhoc = [
      { content: "creami una sessione" },
      ...Array.from({ length: 6 }, (_, i) => ({ content: `chiacchiera ${i}` })),
    ];
    expect(isAdhocFollowUp("Si", oldAdhoc)).toBe(false);
  });
});

describe("shouldRouteToAdhoc", () => {
  it("is the union of the two gates", () => {
    expect(shouldRouteToAdhoc("creami una sessione", [])).toBe(true);
    expect(
      shouldRouteToAdhoc("Si", [{ content: "ti preparo una sessione?" }]),
    ).toBe(true);
    expect(shouldRouteToAdhoc("Si", [])).toBe(false);
  });
});
