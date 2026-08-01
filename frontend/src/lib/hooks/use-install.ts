"use client";

import { useCallback, useSyncExternalStore } from "react";
import {
  getCapability,
  hasNativePrompt,
  promptInstall,
  subscribeInstall,
  type InstallCapability,
} from "@/lib/install";
import { trackEvent } from "@/lib/analytics";

/**
 * A260 — install capability for the current browser, plus the one-tap install
 * action where the platform supports it.
 *
 * `capability` is null on the server and during hydration by design: every
 * branch of the decision reads `navigator`/`matchMedia`, which do not exist
 * server-side, and a guess would flash the wrong instructions at someone.
 * `useSyncExternalStore` gives exactly that for free — React uses the server
 * snapshot (null) while hydrating, then re-renders with the real value. Callers
 * render nothing while it is null.
 *
 * The client snapshot returns a plain string, so referential stability holds
 * without memoisation, and the store re-notifies when `beforeinstallprompt` or
 * `appinstalled` fires — which is when the answer can actually change.
 */
export function useInstall() {
  const capability = useSyncExternalStore<InstallCapability | null>(
    subscribeInstall,
    () => getCapability(hasNativePrompt()),
    () => null,
  );

  const install = useCallback(async () => {
    const outcome = await promptInstall();
    if (outcome) trackEvent(`install_native_${outcome}`);
    return outcome;
  }, []);

  return {
    capability,
    install,
    canInstallNatively: capability === "native-prompt",
  };
}
