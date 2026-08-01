"use client";

import { useEffect } from "react";
// Imported for its module-level side effect: registering the
// `beforeinstallprompt` listener. Chromium fires that event once per page load,
// usually before any route component mounts, and Next's client-side navigation
// never reloads — so a listener registered inside the install screen would
// always be too late. Mounted in the root layout for that reason alone.
import "@/lib/install";
import { trackEvent } from "@/lib/analytics";

export function InstallCapture() {
  useEffect(() => {
    const onInstalled = () => trackEvent("install_completed");
    window.addEventListener("appinstalled", onInstalled);
    return () => window.removeEventListener("appinstalled", onInstalled);
  }, []);

  return null;
}
