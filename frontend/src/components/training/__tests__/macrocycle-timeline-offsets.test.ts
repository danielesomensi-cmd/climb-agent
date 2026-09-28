/**
 * B355 — il prefix-sum degli offset di fase è stato riscritto senza mutare una
 * variabile di render (react-hooks/immutability). Questo test blocca il
 * risultato: la prima fase parte da 0, ciascuna dalla somma delle durate che la
 * precedono. Un off-by-one qui sposterebbe tutte le fasi del macrociclo, ed è
 * l'unico consumatore di `startWeek` (il ✓ di fase completata, A235).
 */

import { describe, it, expect } from "vitest";
import { phaseStartWeeks } from "../macrocycle-timeline";

describe("phaseStartWeeks", () => {
  it("parte da 0 e somma le durate precedenti", () => {
    // Macrociclo lead tipico: base 4, strength_power 3, power_endurance 3,
    // performance 2, deload 1 → 13 settimane.
    expect(phaseStartWeeks([4, 3, 3, 2, 1])).toEqual([0, 4, 7, 10, 12]);
  });

  it("gestisce fase singola e lista vuota", () => {
    expect(phaseStartWeeks([8])).toEqual([0]);
    expect(phaseStartWeeks([])).toEqual([]);
  });

  it("l'ultimo offset più la sua durata è il totale delle settimane", () => {
    const durations = [5, 2, 4, 3, 1];
    const offsets = phaseStartWeeks(durations);
    const total = durations.reduce((a, b) => a + b, 0);
    expect(offsets[offsets.length - 1] + durations[durations.length - 1]).toBe(
      total,
    );
  });
});
