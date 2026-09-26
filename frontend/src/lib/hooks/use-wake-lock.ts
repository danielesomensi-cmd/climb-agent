"use client";

import { useEffect, useRef } from "react";

type WakeLockSentinel = {
  release: () => Promise<void>;
  addEventListener: (type: "release", listener: () => void) => void;
  removeEventListener?: (type: "release", listener: () => void) => void;
};

type NavigatorWithWakeLock = Navigator & {
  wakeLock?: {
    request: (type: "screen") => Promise<WakeLockSentinel>;
  };
};

/**
 * Keeps the screen awake while `enabled` is true. iOS Safari supports this
 * from 16.4+. If the API is unavailable, this hook is a silent noop so the
 * page still works — the screen will just dim on its usual schedule.
 *
 * A286 — il lock non veniva mai riacquisito dopo un background. Il browser lo
 * rilascia da solo quando il documento smette di essere visibile, ma nessuno
 * annullava `sentinelRef`: al ritorno in foreground la guardia
 * `!sentinelRef.current` era falsa e la riacquisizione non partiva mai. Ora il
 * sentinel si auto-annulla sull'evento `release`, così il visibilitychange
 * trova davvero il campo vuoto e richiede un lock nuovo.
 */
export function useWakeLock(enabled: boolean) {
  const sentinelRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let released = false;
    // A286 — una richiesta alla volta: visibilitychange e il mount possono
    // arrivare a distanza di pochi ms e `request()` è asincrona.
    let pending = false;

    const acquire = async () => {
      const nav = navigator as NavigatorWithWakeLock;
      if (!nav.wakeLock) return;
      if (pending || sentinelRef.current) return;
      // Safari rifiuta (e lancia) se il documento non è visibile.
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      pending = true;
      try {
        const sentinel = await nav.wakeLock.request("screen");
        if (released) {
          await sentinel.release().catch(() => {});
          return;
        }
        // Il rilascio automatico del browser deve svuotare il ref, altrimenti
        // la riacquisizione non scatterà mai più.
        sentinel.addEventListener("release", () => {
          if (sentinelRef.current === sentinel) sentinelRef.current = null;
        });
        sentinelRef.current = sentinel;
      } catch {
        /* UA may deny (battery saver, doc hidden) — silent */
      } finally {
        pending = false;
      }
    };

    // Re-acquire when returning to foreground (iOS releases on background).
    const onVisible = () => {
      if (document.visibilityState === "visible") void acquire();
    };

    void acquire();
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      released = true;
      document.removeEventListener("visibilitychange", onVisible);
      if (sentinelRef.current) {
        sentinelRef.current.release().catch(() => {});
        sentinelRef.current = null;
      }
    };
  }, [enabled]);
}
