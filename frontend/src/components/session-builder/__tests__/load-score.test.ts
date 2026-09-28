/**
 * B356 — il session builder mostrava "Load: 0" con qualunque esercizio dentro.
 *
 * La formula era giusta (`min(85, round(Σ fatigue_cost × 1.5))`, la stessa di
 * backend/engine/custom_session.py): era la MAPPA a essere sempre vuota, perché
 * l'unico `updateFatigueCost` che la riempiva non veniva chiamato da nessuno.
 * Questi test coprono quindi la costruzione della mappa dal catalogo, non solo
 * l'aritmetica — un test sulla sola formula sarebbe passato anche con il bug.
 *
 * LIMITE DICHIARATO: bloccano `buildFatigueMap` e `computeLoadScore`, NON il
 * cablaggio fra i due dentro il componente. Se qualcuno ripuntasse `fatigueCosts`
 * su una mappa vuota, questi test resterebbero verdi. Coprire anche il cablaggio
 * richiede un test di componente su SessionBuilder (query client + mock di
 * useCustomSession/useBuilderExercises + router): non fatto qui.
 */

import { describe, it, expect } from "vitest";
import { buildFatigueMap, computeLoadScore } from "../session-builder";

const CATALOG = [
  { id: "max_hang_10s", fatigue_cost: 9 },
  { id: "pullup_weighted", fatigue_cost: 7 },
  { id: "core_plank", fatigue_cost: 2 },
  { id: "senza_costo" },
];

function entry(exercise_id: string) {
  // computeLoadScore legge solo exercise.exercise_id.
  return { exercise: { exercise_id } } as Parameters<typeof computeLoadScore>[0][number];
}

describe("buildFatigueMap", () => {
  it("indicizza il catalogo per id", () => {
    const map = buildFatigueMap(CATALOG);
    expect(map.get("max_hang_10s")).toBe(9);
    expect(map.get("pullup_weighted")).toBe(7);
  });

  it("tratta un costo mancante come 0 invece di undefined", () => {
    expect(buildFatigueMap(CATALOG).get("senza_costo")).toBe(0);
  });

  it("regge un catalogo non ancora arrivato", () => {
    expect(buildFatigueMap(undefined).size).toBe(0);
  });
});

describe("computeLoadScore", () => {
  const map = buildFatigueMap(CATALOG);

  it("NON è zero quando la sessione ha esercizi — il bug di B356", () => {
    const score = computeLoadScore([entry("max_hang_10s"), entry("pullup_weighted")], map);
    expect(score).toBeGreaterThan(0);
    expect(score).toBe(24); // (9 + 7) * 1.5
  });

  it("somma i costi e arrotonda", () => {
    expect(computeLoadScore([entry("core_plank")], map)).toBe(3); // 2 * 1.5
  });

  it("taglia a 85, come il backend", () => {
    const tanti = Array.from({ length: 20 }, () => entry("max_hang_10s"));
    expect(computeLoadScore(tanti, map)).toBe(85); // 20*9*1.5 = 270 → 85
  });

  it("una sessione vuota vale 0", () => {
    expect(computeLoadScore([], map)).toBe(0);
  });

  it("un esercizio non in catalogo non fa esplodere il conto", () => {
    expect(computeLoadScore([entry("inesistente")], map)).toBe(0);
  });
});
