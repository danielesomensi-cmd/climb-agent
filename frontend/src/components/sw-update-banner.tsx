"use client";

/**
 * SwUpdateBanner — detects when a new service worker is waiting and prompts
 * the user to reload. Without this banner, iOS PWA users had to manually quit
 * the app from the multitasking switcher to pick up a new build (B196).
 *
 * Flow:
 *   1. SW registration in layout.tsx fires; this component listens for
 *      `updatefound` events on the registration.
 *   2. When a new worker enters the `installed` state with an existing
 *      controller, we know an update is waiting → show the banner.
 *   3. User taps "Aggiorna": post `SKIP_WAITING` to the waiting worker, then
 *      reload once `controllerchange` fires.
 */

import { useEffect, useState } from "react";

export function SwUpdateBanner() {
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;

    let cancelled = false;

    function trackWaiting(reg: ServiceWorkerRegistration) {
      if (reg.waiting && navigator.serviceWorker.controller) {
        if (!cancelled) setWaitingWorker(reg.waiting);
      }
      reg.addEventListener("updatefound", () => {
        const installing = reg.installing;
        if (!installing) return;
        installing.addEventListener("statechange", () => {
          if (
            installing.state === "installed" &&
            navigator.serviceWorker.controller &&
            !cancelled
          ) {
            setWaitingWorker(installing);
          }
        });
      });
    }

    navigator.serviceWorker.getRegistration().then((reg) => {
      if (!reg || cancelled) return;
      trackWaiting(reg);
      // Probe for updates on mount; harmless no-op if already current.
      reg.update().catch(() => {});
    });

    function onControllerChange() {
      if (!cancelled) window.location.reload();
    }
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    return () => {
      cancelled = true;
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
    };
  }, []);

  if (!waitingWorker) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-[100] w-[min(92vw,420px)] -translate-x-1/2 rounded-lg border border-primary/40 bg-background/95 p-3 shadow-lg backdrop-blur">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm">
          <span className="font-medium">Nuova versione disponibile.</span>
          <span className="ml-1 text-muted-foreground">Ricarica per aggiornare.</span>
        </p>
        <button
          type="button"
          onClick={() => waitingWorker.postMessage({ type: "SKIP_WAITING" })}
          className="shrink-0 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground active:opacity-80"
        >
          Aggiorna
        </button>
      </div>
    </div>
  );
}
