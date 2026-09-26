"use client";

import { useEffect, useState } from "react";

/**
 * A286 E5 — ritarda la propagazione di un valore che cambia a ogni battuta.
 *
 * `useDeferredValue` non basta per una ricerca che fa rete: rimanda il render,
 * non la richiesta, quindi il picker esercizi sparava comunque una query per
 * carattere. Qui il valore si muove solo quando l'utente smette di scrivere.
 */
export function useDebouncedValue<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
